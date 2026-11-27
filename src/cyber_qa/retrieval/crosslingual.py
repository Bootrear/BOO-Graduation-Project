"""Qwen3 cross-lingual embedding index with reproducible provenance checks."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable

import numpy as np

INDEX_SCHEMA = "crosslingual-index-v2"
INPUT_BUDGET = 8192
QUERY_INSTRUCTION = (
    "Given a cybersecurity question, retrieve English CWE passages that contain "
    "evidence needed to answer the question."
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def validate_index_arrays(vectors: np.ndarray, passage_ids: list[str]) -> None:
    if vectors.ndim != 2 or vectors.shape[0] != len(passage_ids):
        raise ValueError("vector and passage ID shapes are incompatible")
    if len(set(passage_ids)) != len(passage_ids):
        raise ValueError("passage IDs must be unique")
    if not np.isfinite(vectors).all():
        raise ValueError("index vectors contain NaN or Inf")
    if np.any(np.linalg.norm(vectors.astype(np.float64), axis=1) == 0):
        raise ValueError("index vectors contain a zero vector")


def write_index(output_dir: Path, vectors: np.ndarray, passage_ids: list[str],
                records: list[dict], manifest: dict) -> dict:
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite index directory: {output_dir}")
    validate_index_arrays(vectors, passage_ids)
    if len(records) != len(passage_ids):
        raise ValueError("record count does not match passage IDs")
    if [record["passage_id"] for record in records] != passage_ids:
        raise ValueError("record order does not match passage IDs")
    output_dir.mkdir(parents=True)
    np.save(output_dir / "vectors.npy", np.asarray(vectors), allow_pickle=False)
    (output_dir / "passage_ids.json").write_bytes(canonical_json_bytes(passage_ids) + b"\n")
    (output_dir / "passages.jsonl").write_text(
        "".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records),
        encoding="utf-8")
    completed = {
        **manifest,
        "schema_version": INDEX_SCHEMA,
        "count": len(passage_ids),
        "embedding_dimension": int(vectors.shape[1]),
        "dtype": str(vectors.dtype),
        "metric": "cosine",
        "normalized": False,
        "input_budget": INPUT_BUDGET,
        "truncation_policy": "tokenizer truncation on the right to 8192 tokens; record truncated passages",
        "pooling": "last non-padding token of AutoModel.last_hidden_state",
        "prefix_policy": {
            "query": f"Instruct: {QUERY_INSTRUCTION}\nQuery:<original question>",
            "document": "no prefix",
        },
        "passage_ids_sha256": sha256_file(output_dir / "passage_ids.json"),
        "vectors_sha256": sha256_file(output_dir / "vectors.npy"),
        "index_sha256": sha256_file(output_dir / "vectors.npy"),
        "passages_sha256": sha256_file(output_dir / "passages.jsonl"),
    }
    (output_dir / "manifest.json").write_bytes(canonical_json_bytes(completed) + b"\n")
    completed["manifest_sha256"] = sha256_file(output_dir / "manifest.json")
    return completed


def load_index(index_dir: Path, *, expected_snapshot_id: str | None = None,
               expected_model_revision: str | None = None) -> tuple[dict, np.ndarray, list[str], list[dict]]:
    manifest_path = index_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != INDEX_SCHEMA or manifest.get("metric") != "cosine":
        raise ValueError("unsupported cross-lingual index schema or metric")
    if expected_snapshot_id and manifest.get("snapshot_id") != expected_snapshot_id:
        raise ValueError("index snapshot is incompatible")
    if expected_model_revision and manifest.get("model_revision") != expected_model_revision:
        raise ValueError("index model revision is incompatible")
    for filename, key in (("vectors.npy", "vectors_sha256"),
                          ("passage_ids.json", "passage_ids_sha256"),
                          ("passages.jsonl", "passages_sha256")):
        if sha256_file(index_dir / filename) != manifest.get(key):
            raise ValueError(f"index file hash mismatch: {filename}")
    vectors = np.load(index_dir / "vectors.npy", allow_pickle=False)
    passage_ids = json.loads((index_dir / "passage_ids.json").read_text(encoding="utf-8"))
    records = [json.loads(line) for line in (index_dir / "passages.jsonl").read_text(encoding="utf-8").splitlines()]
    validate_index_arrays(vectors, passage_ids)
    if len(records) != manifest.get("count") or vectors.shape[1] != manifest.get("embedding_dimension"):
        raise ValueError("index manifest dimensions/count do not match stored files")
    if [record.get("passage_id") for record in records] != passage_ids:
        raise ValueError("passage records do not align with the ID map")
    return manifest, vectors, passage_ids, records


def search(vectors: np.ndarray, passage_ids: list[str], query_vector: np.ndarray, top_n: int) -> list[dict]:
    if type(top_n) is not int or top_n < 0:
        raise ValueError("top_n must be a non-negative integer")
    validate_index_arrays(vectors, passage_ids)
    query = np.asarray(query_vector, dtype=np.float64)
    matrix = vectors.astype(np.float64)
    if query.ndim != 1 or query.shape[0] != matrix.shape[1]:
        raise ValueError("query vector dimension does not match index")
    if not np.isfinite(query).all() or np.linalg.norm(query) == 0:
        raise ValueError("query vector must be finite and non-zero")
    scores = matrix @ query / (np.linalg.norm(matrix, axis=1) * np.linalg.norm(query))
    if not np.isfinite(scores).all():
        raise ValueError("cosine scoring produced non-finite values")
    order = sorted(range(len(passage_ids)), key=lambda i: (-float(scores[i]), passage_ids[i]))[:top_n]
    return [{"passage_id": passage_ids[i], "retrieval_rank": rank,
             "retrieval_score": float(scores[i])} for rank, i in enumerate(order, start=1)]


def last_token_pool(hidden_states, attention_mask):
    """Pool the last non-padding token; tokenizer is configured with left padding."""
    return hidden_states[:, -1]


def encode_texts(model, tokenizer, texts: Iterable[str], *, device: str,
                 batch_size: int, max_length: int = INPUT_BUDGET) -> tuple[np.ndarray, list[bool]]:
    import torch

    texts = list(texts)
    if not texts:
        return np.empty((0, int(model.config.hidden_size)), dtype=np.float32), []
    if batch_size <= 0 or max_length <= 0:
        raise ValueError("batch_size and max_length must be positive")
    tokenizer.padding_side = "left"
    output, truncated = [], []
    model.eval()
    for start in range(0, len(texts), batch_size):
        batch_texts = texts[start:start + batch_size]
        full_lengths = [len(tokenizer(text, add_special_tokens=True, truncation=False)["input_ids"])
                        for text in batch_texts]
        encoded = tokenizer(batch_texts, padding=True, truncation=True, max_length=max_length,
                            return_tensors="pt")
        truncated.extend(length > max_length for length in full_lengths)
        encoded = {key: value.to(device) for key, value in encoded.items()}
        with torch.inference_mode():
            result = model(**encoded)
            pooled = last_token_pool(result.last_hidden_state, encoded["attention_mask"])
            raw_vectors = pooled.float()
        norms = raw_vectors.norm(dim=1)
        if not torch.isfinite(raw_vectors).all() or not torch.isfinite(norms).all() or torch.any(norms == 0):
            raise ValueError("model produced non-finite or zero embeddings")
        output.append(raw_vectors.cpu().numpy().astype(np.float32, copy=False))
    return np.concatenate(output, axis=0), truncated
