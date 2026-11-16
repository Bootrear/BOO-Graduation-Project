"""Validate real DPR encoding, persisted index reload and raw-vector retrieval."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import time

import numpy as np

from cyber_qa.models import DPRRuntime, file_sha256
from cyber_qa.retrieval.dpr import load_index
from cyber_qa.selection.mmr import similarity_matrix


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", default="data/processed/cwe-v1")
    parser.add_argument("--index", default="data/processed/dpr-index-v1")
    parser.add_argument("--device", default="auto")
    parser.add_argument("--question", default="What is SQL injection?")
    parser.add_argument("--output", required=True)
    parser.add_argument("--compare", help="Require identical retrieval results from an earlier process")
    args = parser.parse_args()
    runtime = DPRRuntime(device=args.device)
    index = load_index(args.index, args.snapshot, runtime)
    context_batch = runtime.encode_context(index.passages[:2], batch_size=2)
    context_single = runtime.encode_context(index.passages[:1], batch_size=1)
    np.testing.assert_allclose(context_single[0], context_batch[0], rtol=1e-4, atol=2e-4)
    np.testing.assert_allclose(context_batch, index.vectors[:2], rtol=1e-4, atol=2e-4)
    runtime.load_model("question")
    started = time.perf_counter()
    q = runtime.encode_question(args.question)
    candidates = index.search(q)
    query_seconds = time.perf_counter() - started
    original = index.vectors.copy()
    similarity_matrix([c.vector for c in candidates])
    assert np.array_equal(index.vectors, original), "MMR similarity mutated the raw index"
    assert candidates == load_index(args.index, args.snapshot, runtime).search(q)
    records = []
    for candidate in candidates:
        record = asdict(candidate)
        record.pop("vector")
        records.append(record)
    stable = {"question": args.question, "snapshot_id": index.metadata["snapshot_id"],
              "vectors_sha256": file_sha256(Path(args.index) / "vectors.npy"),
              "question_weight_sha256": runtime.weight_hashes["question"],
              "candidates": records}
    if args.compare:
        previous = json.loads(Path(args.compare).read_text())
        if stable != previous["retrieval"]:
            raise ValueError("retrieval differs from the earlier process")
    output = {"retrieval": stable, "context_shape": list(context_batch.shape),
              "question_shape": list(q.shape), "device": runtime.device,
              "query_seconds": query_seconds, "model_load_seconds": runtime.model_load_seconds,
              "checks": ["single_batch_context_alignment", "persisted_vectors_match_encoder",
                         "raw_vectors_unchanged_by_similarity", "index_reload_exact_match"],
              "reader_inference_verified": False, "end_to_end_verified": False}
    if args.compare:
        output["checks"].append("fresh_process_exact_match")
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"output": str(path), "candidates": len(candidates), "checks": output["checks"],
                      "top3": [{"cwe_id": c.passage.cwe_id, "field_name": c.passage.field_name,
                                "score": c.retrieval_score} for c in candidates[:3]]}, indent=2))


if __name__ == "__main__":
    main()
