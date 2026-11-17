"""Real Reader alignment acceptance; does not claim ordinary-answer E2E acceptance."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path

import numpy as np

from cyber_qa.models import DPRRuntime
from cyber_qa.reader.dpr import DPRReaderScorer
from cyber_qa.retrieval.dpr import load_index
from cyber_qa.selection.mmr import prepare_pool, reader_topk, select_mmr, select_mmr_reference


def assert_aligned(expected, actual):
    assert len(expected) == len(actual)
    for left, right in zip(expected, actual):
        assert (left.passage, left.vector, left.retrieval_rank, left.retrieval_score) == (right.passage, right.vector, right.retrieval_rank, right.retrieval_score)
        np.testing.assert_allclose(left.reader_relevance_logit, right.reader_relevance_logit, rtol=1e-4, atol=2e-4)
        np.testing.assert_allclose(left.reader_start_logits, right.reader_start_logits, rtol=1e-4, atol=2e-4)
        np.testing.assert_allclose(left.reader_end_logits, right.reader_end_logits, rtol=1e-4, atol=2e-4)
        assert left.answer_span is not None and right.answer_span is not None
        a, b = asdict(left.answer_span), asdict(right.answer_span)
        np.testing.assert_allclose(a.pop("span_score"), b.pop("span_score"), rtol=1e-4, atol=4e-4)
        assert a == b


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", default="data/processed/cwe-v1")
    parser.add_argument("--index", default="data/processed/dpr-index-v1")
    parser.add_argument("--device", default="auto")
    parser.add_argument("--question", default="What is SQL injection?")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    runtime = DPRRuntime(device=args.device)
    index = load_index(args.index, args.snapshot, runtime)
    candidates = index.search(runtime.encode_question(args.question))
    original_vectors = index.vectors.copy()
    scorer = DPRReaderScorer(runtime)
    result = scorer.score(args.question, candidates, batch_size=8)
    # These extra forwards are acceptance comparisons only, not per-strategy scoring.
    single = scorer.score(args.question, candidates[:1], batch_size=1)
    singles = scorer.score(args.question, candidates, batch_size=1)
    reverse = scorer.score(args.question, candidates[::-1], batch_size=7)
    assert_aligned(result.candidates[:1], single.candidates)
    assert_aligned(result.candidates, singles.candidates)
    assert_aligned(result.candidates, reverse.candidates[::-1])
    for candidate, row in zip(result.candidates, result.inputs):
        span = candidate.answer_span
        assert row.passage_id == candidate.passage_id
        assert candidate.passage.text[span.start_char:span.end_char] == span.text
        assert all(row.offsets[i] is not None for i in range(span.start_token, span.end_token+1))
        assert span.end_token-span.start_token+1 <= result.config.max_answer_tokens
        np.testing.assert_allclose(span.span_score,
            candidate.reader_start_logits[span.start_token] + candidate.reader_end_logits[span.end_token], atol=1e-12)
    pool = prepare_pool(result.candidates)
    topk, mmr = reader_topk(pool), select_mmr(pool)
    assert mmr == select_mmr_reference(pool)
    assert all(c in pool.candidates for c in (*topk.selected, *mmr.selected))
    assert np.array_equal(index.vectors, original_vectors)
    output = {"question": args.question, "snapshot_id": index.metadata["snapshot_id"],
        "model_provenance": runtime.provenance, "weight_sha256": runtime.weight_hashes,
        "reader_loading_info": runtime.loading_info["reader"], "input_budget": runtime.budget.to_dict(),
        "device": runtime.device, "model_load_seconds_total": runtime.model_load_seconds,
        "reader": result.to_dict(), "prepared_candidates": [c.to_dict() for c in pool.candidates],
        "reader_topk": topk.to_dict(), "mmr": mmr.to_dict(),
        "checks": ["single_candidate_shape", "single_batch_alignment", "cross_batch_reorder_alignment",
                   "original_passage_span_mapping", "passage_only_span_mask", "span_score_and_length",
                   "shared_pool_reader_result", "real_mmr_reference_equivalence", "raw_vectors_unchanged"],
        "reader_inference_verified": True, "ordinary_answer_verified": False, "end_to_end_verified": False}
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"output": str(path), "candidates": len(result.candidates),
        "batch_shapes": result.batch_shapes, "reader_seconds": result.reader_seconds,
        "checks": output["checks"], "top_reader": {"cwe_id": topk.selected[0].passage.cwe_id,
            "field_name": topk.selected[0].passage.field_name, "span": asdict(topk.selected[0].answer_span)},
        "end_to_end_verified": False}, indent=2))


if __name__ == "__main__":
    main()
