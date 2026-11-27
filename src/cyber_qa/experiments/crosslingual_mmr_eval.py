"""Exploratory paired evaluation of retrieval Top-K and cross-lingual MMR."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from cyber_qa.data.candidates import ScoredPassage
from cyber_qa.data.contracts import Passage
from cyber_qa.experiments.crosslingual_gate import embed_query
from cyber_qa.retrieval.crosslingual import search
from cyber_qa.selection.crosslingual_mmr import CrosslingualMMRConfig, prepare_crosslingual_pool, select_crosslingual_mmr
from cyber_qa.selection.mmr import reader_topk

LAMBDA_GRID = tuple(round(i / 10, 1) for i in range(11))


def _recall(ids: tuple[str, ...], required: list[str]) -> float:
    return len(set(ids).intersection(required)) / len(set(required))


def _mean_pairwise(vectors: list[np.ndarray]) -> float | None:
    if len(vectors) < 2:
        return None
    matrix = np.asarray(vectors, dtype=np.float64)
    norms = np.linalg.norm(matrix, axis=1)
    if not np.isfinite(matrix).all() or np.any(norms == 0):
        raise ValueError("redundancy vectors must be finite and non-zero")
    similarities = (matrix / norms[:, None]) @ (matrix / norms[:, None]).T
    values = similarities[np.triu_indices(len(matrix), k=1)]
    return float(np.mean(np.clip(values, -1, 1)))


def _mean_available(values: list[float | None]) -> float | None:
    present = [value for value in values if value is not None]
    return float(np.mean(present)) if present else None


def _bootstrap_ci(differences: list[float], *, seed: int, replicates: int = 4000) -> tuple[float, float] | None:
    if not differences:
        return None
    values = np.asarray(differences, dtype=np.float64)
    rng = np.random.default_rng(seed)
    sampled = rng.integers(0, len(values), size=(replicates, len(values)))
    means = values[sampled].mean(axis=1)
    low, high = np.quantile(means, (0.025, 0.975))
    return float(low), float(high)


def evaluate_records(english_records: list[dict], chinese_records: list[dict], vectors: np.ndarray,
                     passage_ids: list[str], passage_records: list[dict], model, tokenizer, *, device: str,
                     n_candidates: int = 20, k: int = 5, lambdas=LAMBDA_GRID) -> tuple[list[dict], dict]:
    if not english_records or not chinese_records:
        raise ValueError("both English and Chinese records are required")
    if {r["question_id"] for r in english_records} != {r["question_id"] for r in chinese_records}:
        raise ValueError("English and Chinese question ID sets differ")
    if any(lam < 0 or lam > 1 for lam in lambdas):
        raise ValueError("lambda values must be in [0, 1]")
    by_id = {pid: i for i, pid in enumerate(passage_ids)}
    records_by_id = {r["passage_id"]: r for r in passage_records}
    if set(by_id) != set(records_by_id):
        raise ValueError("index passage IDs do not match passage records")
    output = []
    for language, questions in (("en", english_records), ("zh", chinese_records)):
        for question in questions:
            q_vector = embed_query(model, tokenizer, question["question"], device=device)
            hits = search(vectors, passage_ids, q_vector, n_candidates)
            candidates = []
            for hit in hits:
                pid = hit["passage_id"]
                passage_fields = Passage.__dataclass_fields__
                passage = Passage(**{key: value for key, value in records_by_id[pid].items()
                                     if key in passage_fields})
                candidates.append(ScoredPassage(
                    passage=passage, retrieval_rank=hit["retrieval_rank"],
                    retrieval_score=hit["retrieval_score"], vector=tuple(vectors[by_id[pid]].tolist()),
                    reader_relevance_logit=hit["retrieval_score"]))
            required = question["required_evidence_ids"]
            top_pool = prepare_crosslingual_pool(candidates)
            top = reader_topk(top_pool, CrosslingualMMRConfig(max_passages=k))
            pool_redundancy = _mean_pairwise([np.asarray(c.vector) for c in candidates])
            for scale in ("pool_minmax", "raw"):
                for lam in lambdas:
                    config = CrosslingualMMRConfig(max_passages=k, lambda_weight=float(lam))
                    selected_pool = prepare_crosslingual_pool(candidates, similarity_scale=scale)
                    # Re-enter the frozen selector with this already prepared pool.
                    from types import SimpleNamespace
                    from cyber_qa.selection.mmr import select_mmr
                    mmr = select_mmr(selected_pool, SimpleNamespace(lambda_weight=float(lam), max_passages=k))
                    if lam == 1 and mmr.selected_order != top.selected_order:
                        raise AssertionError("lambda=1 MMR order differs from retrieval Top-K")
                    selected_vectors = [np.asarray(c.vector) for c in mmr.selected]
                    top_vectors = [np.asarray(c.vector) for c in top.selected]
                    top_recall = _recall(top.selected_order, required)
                    mmr_recall = _recall(mmr.selected_order, required)
                    output.append({
                        "language": language, "question_id": question["question_id"],
                        "candidate_ids": [c.passage_id for c in candidates],
                        "required_evidence_ids": required,
                        "lambda": float(lam), "similarity_scale": scale,
                        "topk_ids": list(top.selected_order), "mmr_ids": list(mmr.selected_order),
                        "topk_recall": top_recall, "mmr_recall": mmr_recall,
                        "topk_full_coverage": top_recall == 1.0, "mmr_full_coverage": mmr_recall == 1.0,
                        "topk_hit": top_recall > 0, "mmr_hit": mmr_recall > 0,
                        "topk_selected_pairwise_cosine": _mean_pairwise(top_vectors),
                        "mmr_selected_pairwise_cosine": _mean_pairwise(selected_vectors),
                        "candidate_pool_pairwise_cosine": pool_redundancy,
                        "set_disagreement": set(top.selected_order) != set(mmr.selected_order),
                        "order_disagreement": top.selected_order != mmr.selected_order,
                        "mmr_steps": [step.__dict__ for step in mmr.steps],
                    })
    summary = summarize(output, lambdas)
    return output, summary


def summarize(rows: list[dict], lambdas=LAMBDA_GRID) -> dict:
    results = {}
    for language in ("en", "zh"):
        results[language] = {}
        for scale in ("pool_minmax", "raw"):
            results[language][scale] = {}
            for lam in lambdas:
                subset = [r for r in rows if r["language"] == language and r["similarity_scale"] == scale and r["lambda"] == lam]
                if not subset:
                    continue
                diffs = [r["mmr_recall"] - r["topk_recall"] for r in subset]
                wins = sum(d > 0 for d in diffs)
                losses = sum(d < 0 for d in diffs)
                ties = len(diffs) - wins - losses
                ci = _bootstrap_ci(diffs, seed=27112026 + (0 if language == "en" else 100) + int(lam * 10) + (0 if scale == "pool_minmax" else 1000))
                results[language][scale][str(lam)] = {
                    "questions": len(subset),
                    "topk_recall_at_5": float(np.mean([r["topk_recall"] for r in subset])),
                    "mmr_recall_at_5": float(np.mean([r["mmr_recall"] for r in subset])),
                    "topk_full_coverage": float(np.mean([r["topk_full_coverage"] for r in subset])),
                    "mmr_full_coverage": float(np.mean([r["mmr_full_coverage"] for r in subset])),
                    "topk_hit_at_5": float(np.mean([r["topk_hit"] for r in subset])),
                    "mmr_hit_at_5": float(np.mean([r["mmr_hit"] for r in subset])),
                    "recall_wins_losses_ties": {"wins": wins, "losses": losses, "ties": ties},
                    "paired_recall_difference_mmr_minus_topk": float(np.mean(diffs)),
                    "paired_bootstrap_95_ci": list(ci) if ci else None,
                    "ci_excludes_zero_positive": bool(ci and ci[0] > 0),
                    "topk_selected_pairwise_cosine": _mean_available([r["topk_selected_pairwise_cosine"] for r in subset]),
                    "mmr_selected_pairwise_cosine": _mean_available([r["mmr_selected_pairwise_cosine"] for r in subset]),
                    "candidate_pool_pairwise_cosine": _mean_available([r["candidate_pool_pairwise_cosine"] for r in subset]),
                    "set_disagreement_rate": float(np.mean([r["set_disagreement"] for r in subset])),
                    "order_disagreement_rate": float(np.mean([r["order_disagreement"] for r in subset])),
                    "interpretation": "MMR superiority may be claimed only when the paired recall CI excludes zero in the positive direction; probe remains exploratory",
                }
    return {"languages": results, "lambda_grid": list(lambdas),
            "interpretation": "40-question machine-translated probe; exploratory diagnostic, not paper test evidence"}


def write_results(output_dir: Path, rows: list[dict], summary: dict, provenance: dict) -> None:
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite MMR evaluation output: {output_dir}")
    output_dir.mkdir(parents=True)
    with (output_dir / "per_question.jsonl").open("x", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n")
    (output_dir / "summary.json").write_text(json.dumps({**summary, "provenance": provenance},
        ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")
