"""Exact raw-inner-product DPR index with strict snapshot/artifact validation."""

from __future__ import annotations

from datetime import datetime, timezone
from importlib.metadata import version
import json
from pathlib import Path
import re
import tempfile
import time

import numpy as np

from cyber_qa.data.candidates import RetrievedPassage
from cyber_qa.data.preprocess import load_snapshot
from cyber_qa.models import DPRRuntime, file_sha256, validate_vectors


class DPRIndex:
    def __init__(self, vectors, passages, metadata):
        validate_vectors(vectors)
        if len(vectors) != len(passages) or len({p.passage_id for p in passages}) != len(passages):
            raise ValueError("vector/passages count mismatch or duplicate passage IDs")
        self.vectors = vectors
        self.vectors.setflags(write=False)
        self.passages = tuple(passages)
        self.metadata = metadata

    def search(self, question_vector, n=20):
        if type(n) is not int or n <= 0:
            raise ValueError("candidate count must be a positive integer")
        q = np.asarray(question_vector, dtype=np.float32)
        if q.shape != (self.vectors.shape[1],):
            raise ValueError("question/index dimension mismatch")
        validate_vectors(q.reshape(1, -1))
        scores = self.vectors @ q  # Deliberately no L2 normalization.
        if not np.isfinite(scores).all():
            raise ValueError("non-finite DPR retrieval scores")
        order = sorted(range(len(scores)), key=lambda i: (-float(scores[i]), self.passages[i].passage_id))[:n]
        return tuple(RetrievedPassage(self.passages[i], rank, float(scores[i]), tuple(float(x) for x in self.vectors[i]))
                     for rank, i in enumerate(order, 1))


def build_index(snapshot_path, output_path, runtime: DPRRuntime, *, batch_size=32):
    output = Path(output_path)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite index: {output}")
    started = time.perf_counter()
    previous_load_seconds = runtime.model_load_seconds
    manifest, passages = load_snapshot(snapshot_path)
    runtime.assert_snapshot_compatible(manifest)
    vectors = runtime.encode_context(passages, batch_size=batch_size)
    metadata = {
        "schema_version": "dpr-index-v1", "index_type": "numpy_exact_inner_product",
        "snapshot_id": manifest.snapshot_id, "dataset_version": manifest.dataset_version,
        "corpus_sha256": file_sha256(Path(snapshot_path) / "passages.jsonl"),
        "count": len(passages), "dimension": 768, "dtype": "float32",
        "metric": "inner_product", "normalized": False,
        "context_token_type_ids": "all_zero",
        "model_provenance": runtime.provenance, "input_budget": runtime.budget.to_dict(),
        "context_weight_sha256": runtime.weight_hashes["context"],
        "batch_size": batch_size, "device": runtime.device,
        "environment": {name: version(name) for name in ("torch", "transformers", "tokenizers", "numpy")},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".index-", dir=output.parent) as temp:
        folder = Path(temp) / "index"
        folder.mkdir()
        np.save(folder / "vectors.npy", vectors, allow_pickle=False)
        (folder / "passage_ids.json").write_text(json.dumps([p.passage_id for p in passages]) + "\n")
        metadata["vectors_sha256"] = file_sha256(folder / "vectors.npy")
        metadata["passage_ids_sha256"] = file_sha256(folder / "passage_ids.json")
        metadata["model_load_seconds"] = runtime.model_load_seconds
        metadata["offline_build_seconds"] = time.perf_counter() - started - (runtime.model_load_seconds - previous_load_seconds)
        (folder / "index_manifest.json").write_text(json.dumps(metadata, indent=2) + "\n")
        load_index(folder, snapshot_path, runtime)
        folder.rename(output)
    return metadata


def load_index(index_path, snapshot_path, runtime: DPRRuntime | None = None):
    folder = Path(index_path)
    meta = json.loads((folder / "index_manifest.json").read_text())
    manifest, passages = load_snapshot(snapshot_path)
    expected = {"schema_version": "dpr-index-v1", "index_type": "numpy_exact_inner_product",
                "metric": "inner_product", "normalized": False,
                "context_token_type_ids": "all_zero",
                "snapshot_id": manifest.snapshot_id, "dataset_version": manifest.dataset_version,
                "corpus_sha256": file_sha256(Path(snapshot_path) / "passages.jsonl"),
                "count": len(passages), "dimension": 768, "dtype": "float32",
                "model_provenance": manifest.preprocessing_config["tokenizers"],
                "input_budget": manifest.preprocessing_config["input_budget"]}
    for key, value in expected.items():
        if meta.get(key) != value:
            raise ValueError(f"incompatible index metadata: {key}")
    if runtime is not None:
        runtime.assert_snapshot_compatible(manifest)
        if runtime.verify_weights("context") != meta.get("context_weight_sha256"):
            raise ValueError("index context weights do not match the runtime")
    if not re.fullmatch(r"[0-9a-f]{64}", str(meta.get("context_weight_sha256", ""))):
        raise ValueError("invalid context weight hash")
    for name, key in (("vectors.npy", "vectors_sha256"), ("passage_ids.json", "passage_ids_sha256")):
        if file_sha256(folder / name) != meta[key]:
            raise ValueError(f"index artifact checksum mismatch: {name}")
    ids = json.loads((folder / "passage_ids.json").read_text())
    if ids != [p.passage_id for p in passages]:
        raise ValueError("passage ID mapping does not match corpus order")
    vectors = np.load(folder / "vectors.npy", mmap_mode="r", allow_pickle=False)
    if vectors.shape != (len(passages), 768) or vectors.dtype != np.float32:
        raise ValueError("index vector shape/dtype mismatch")
    return DPRIndex(vectors, passages, meta)
