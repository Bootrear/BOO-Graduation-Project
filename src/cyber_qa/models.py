"""Local-only, pinned DPR models and explicitly budgeted model inputs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import time

import numpy as np

from .data.chunking import InputBudget, token_ids
from .resources import load_tokenizers


def file_sha256(path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_loading_info(role, loading):
    prefix = {"context": "ctx_encoder", "question": "question_encoder",
              "reader": "span_predictor.encoder"}[role]
    # DPREncoder uses BertModel(add_pooling_layer=False) and the raw CLS state.
    # Original checkpoints also carry the unused BERT dense/tanh pooler.
    allowed = {f"{prefix}.bert_model.pooler.dense.{name}" for name in ("weight", "bias")}
    allowed.add(f"{prefix}.bert_model.embeddings.position_ids")
    unexpected = set(loading.get("unexpected_keys", [])) - allowed
    if (loading.get("missing_keys") or loading.get("mismatched_keys")
            or loading.get("error_msgs") or unexpected):
        raise ValueError(f"DPR checkpoint did not load completely: {role}: {loading}")


class DPRRuntime:
    def __init__(self, *, model_config="configs/dpr-models.v1.json", model_root="models/dpr",
                 device="auto", budget: InputBudget | None = None):
        import torch

        started = time.perf_counter()
        self.torch = torch
        self.tokenizers, self.provenance = load_tokenizers(model_config, model_root)
        expected_models = {"context": "facebook/dpr-ctx_encoder-single-nq-base",
                           "question": "facebook/dpr-question_encoder-single-nq-base",
                           "reader": "facebook/dpr-reader-single-nq-base"}
        if any(self.provenance[role]["model_id"] != model for role, model in expected_models.items()):
            raise ValueError("the baseline requires the matched single-nq DPR model family")
        self.model_root = Path(model_root)
        self.budget = budget or InputBudget()
        self.device = "cuda" if device == "auto" and torch.cuda.is_available() else ("cpu" if device == "auto" else device)
        self.models = {}
        self.weight_hashes = {}
        self.loading_info = {}
        self.model_load_seconds = time.perf_counter() - started
        torch.backends.cuda.matmul.allow_tf32 = False

    def verify_weights(self, role):
        spec = self.provenance[role]
        folder = self.model_root / role / spec["revision"]
        receipt = json.loads((folder / "resources.json").read_text())
        expected = receipt.get("upstream_weights")
        if not expected:
            raise ValueError("upstream-verified weight receipt required; rerun fetch_dpr_resources.py --weights")
        weight = folder / "pytorch_model.bin"
        actual = file_sha256(weight)
        if (weight.stat().st_size != expected["size"] or actual != expected["sha256"]
                or actual != receipt["sha256"]["pytorch_model.bin"]):
            raise ValueError(f"model weight size/checksum mismatch: {role}")
        return actual

    def assert_snapshot_compatible(self, manifest):
        expected = manifest.preprocessing_config
        if expected["input_budget"] != self.budget.to_dict() or expected["tokenizers"] != self.provenance:
            raise ValueError("model/tokenizer/budget does not match the passage snapshot")

    def load_model(self, role):
        if role not in self.models:
            from transformers import DPRContextEncoder, DPRQuestionEncoder, DPRReader

            classes = {"context": DPRContextEncoder, "question": DPRQuestionEncoder, "reader": DPRReader}
            spec = self.provenance[role]
            folder = self.model_root / role / spec["revision"]
            started = time.perf_counter()
            actual = self.verify_weights(role)
            model, loading = classes[role].from_pretrained(
                folder, local_files_only=True, use_safetensors=False, output_loading_info=True)
            validate_loading_info(role, loading)
            self.loading_info[role] = loading
            model.eval().to(self.device)
            self.models[role] = model
            self.weight_hashes[role] = actual
            self.model_load_seconds += time.perf_counter() - started
        return self.models[role]

    def question_ids(self, question: str) -> list[int]:
        if not isinstance(question, str) or not question.strip():
            raise ValueError("question must be non-empty text")
        ids = token_ids(self.tokenizers["question"], question.strip())
        if not ids or len(ids) > self.budget.question_max_tokens:
            raise ValueError(f"question token count {len(ids)} outside 1..{self.budget.question_max_tokens}; rejected without truncation")
        return ids

    def passage_parts(self, passage):
        tokenizer = self.tokenizers["context"]
        title = token_ids(tokenizer, passage.title)
        truncated = len(title) > self.budget.title_max_tokens
        body = tokenizer(passage.text, add_special_tokens=False, truncation=False,
                         return_offsets_mapping=True, verbose=False)
        if not body["input_ids"] or len(body["input_ids"]) > self.budget.passage_max_tokens:
            raise ValueError("passage does not fit the frozen tokenizer budget")
        return title[:self.budget.title_max_tokens], body["input_ids"], body["offset_mapping"], truncated

    def encode_context(self, passages, batch_size=32):
        if type(batch_size) is not int or batch_size < 1:
            raise ValueError("batch_size must be a positive integer")
        model = self.load_model("context")
        tokenizer = self.tokenizers["context"]
        embeddings = []
        for start in range(0, len(passages), batch_size):
            rows = []
            for passage in passages[start:start + batch_size]:
                title, body, _, _ = self.passage_parts(passage)
                rows.append([tokenizer.cls_token_id] + title + [tokenizer.sep_token_id] + body + [tokenizer.sep_token_id])
            batch = tokenizer.pad({"input_ids": rows}, padding=True, return_tensors="pt").to(self.device)
            # Original DPR encoders use one segment for the title/text pair.
            batch["token_type_ids"] = self.torch.zeros_like(batch["input_ids"])
            with self.torch.inference_mode():
                vectors = model(**batch).pooler_output
            if vectors.ndim != 2 or vectors.shape[0] != len(rows) or vectors.shape[1] != 768:
                raise ValueError("unexpected DPR context embedding shape")
            embeddings.append(vectors.float().cpu().numpy())
        array = np.concatenate(embeddings) if embeddings else np.empty((0, 768), dtype=np.float32)
        validate_vectors(array)
        return array

    def encode_question(self, question):
        ids = self.question_ids(question)
        model = self.load_model("question")
        tokenizer = self.tokenizers["question"]
        batch = tokenizer.pad({"input_ids": [[tokenizer.cls_token_id] + ids + [tokenizer.sep_token_id]]},
                              padding=True, return_tensors="pt").to(self.device)
        with self.torch.inference_mode():
            result = model(**batch).pooler_output
        if tuple(result.shape) != (1, 768):
            raise ValueError("unexpected DPR question embedding shape")
        vectors = result.float().cpu().numpy()
        validate_vectors(vectors)
        return vectors[0]


def validate_vectors(vectors):
    if vectors.ndim != 2 or vectors.shape[1] == 0 or not np.isfinite(vectors).all():
        raise ValueError("embeddings must be a finite 2-D matrix")
    norms = np.linalg.norm(vectors.astype(np.float64), axis=1)
    if np.any(norms == 0) or not np.isfinite(norms).all():
        raise ValueError("embeddings contain zero or non-finite norms")
