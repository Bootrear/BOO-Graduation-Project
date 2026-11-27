"""Adapt Qwen retrieval scores and embeddings to the frozen iterative MMR."""

from __future__ import annotations

from dataclasses import dataclass, replace
import math
from types import SimpleNamespace
from typing import Sequence

from cyber_qa.data.candidates import ScoredPassage
from cyber_qa.selection.mmr import PreparedPool, SelectionResult, normalize_relevance, select_mmr, similarity_matrix


@dataclass(frozen=True)
class CrosslingualMMRConfig:
    version: str = "crosslingual-rag-v2"
    candidate_count: int = 20
    max_passages: int = 5
    lambda_weight: float = 0.5
    parameter_status: str = "untuned"
    epsilon: float = 1e-12
    relevance_normalization: str = "retrieval_cosine_pool_minmax_once"
    similarity: str = "qwen_cosine_nonnegative_pool_minmax"
    tie_break: str = "retrieval_score_desc_rank_asc_passage_id_asc"
    invalid_score_policy: str = "fail_query"

    def __post_init__(self):
        if self.version != "crosslingual-rag-v2" or self.parameter_status != "untuned":
            raise ValueError("crosslingual v2 version and parameter status are fixed")
        if type(self.candidate_count) is not int or self.candidate_count < 1:
            raise ValueError("candidate_count must be an integer >= 1")
        if type(self.max_passages) is not int or self.max_passages < 0:
            raise ValueError("max_passages must be an integer >= 0")
        if type(self.lambda_weight) not in (int, float) or not math.isfinite(self.lambda_weight) or not 0 <= self.lambda_weight <= 1:
            raise ValueError("lambda_weight must be finite and in [0, 1]")
        if self.epsilon != 1e-12:
            raise ValueError("crosslingual v2 epsilon is fixed at 1e-12")
        if self.relevance_normalization != "retrieval_cosine_pool_minmax_once":
            raise ValueError("crosslingual v2 relevance normalization is fixed")
        if self.similarity != "qwen_cosine_nonnegative_pool_minmax":
            raise ValueError("crosslingual v2 similarity is fixed")
        if self.tie_break != "retrieval_score_desc_rank_asc_passage_id_asc":
            raise ValueError("crosslingual v2 tie-break is fixed")
        if self.invalid_score_policy != "fail_query":
            raise ValueError("crosslingual v2 invalid-score policy is fixed")


def prepare_crosslingual_pool(candidates: Sequence[ScoredPassage], *, epsilon: float = 1e-12,
                              similarity_scale: str = "pool_minmax") -> PreparedPool:
    """Build the frozen selector's pool, using retrieval scores as its relevance fields."""
    if epsilon != 1e-12:
        raise ValueError("crosslingual v2 epsilon is fixed at 1e-12")
    if similarity_scale not in {"pool_minmax", "raw"}:
        raise ValueError("similarity_scale must be 'pool_minmax' or 'raw'")
    unique = {}
    for candidate in candidates:
        if type(candidate.retrieval_rank) is not int or candidate.retrieval_rank < 1:
            raise ValueError("retrieval rank must be a positive integer")
        if not math.isfinite(candidate.retrieval_score):
            raise ValueError("retrieval score is NaN or Inf")
        prior = unique.get(candidate.passage_id)
        if prior is not None and prior != candidate:
            raise ValueError("conflicting duplicate candidate for " + candidate.passage_id)
        unique[candidate.passage_id] = candidate
    ordered = sorted(unique.values(), key=lambda c: (c.retrieval_rank, c.passage_id))

    # Reuse the v1 numerical guard and fixed epsilon, but supply explicit retrieval scores.
    relevance = normalize_relevance([c.retrieval_score for c in ordered], epsilon)
    raw = similarity_matrix([c.vector for c in ordered])
    pair_values = [raw[i][j] for i in range(len(ordered)) for j in range(i + 1, len(ordered))]
    if similarity_scale == "raw":
        normalized_pairs = pair_values
    elif pair_values:
        low, high = min(pair_values), max(pair_values)
        span = high - low
        if not math.isfinite(span):
            raise ValueError("similarity range overflow")
        normalized_pairs = [0.0] * len(pair_values) if span <= epsilon else [(x - low) / span for x in pair_values]
    else:
        normalized_pairs = []
    matrix = [[0.0] * len(ordered) for _ in ordered]
    pair_index = 0
    for i in range(len(ordered)):
        for j in range(i + 1, len(ordered)):
            value = normalized_pairs[pair_index]
            pair_index += 1
            matrix[i][j] = matrix[j][i] = value

    # The frozen selector's documented tie key reads this field; keep all original
    # evidence attached while carrying retrieval relevance explicitly into its API.
    selector_candidates = tuple(replace(c, reader_relevance_logit=c.retrieval_score,
                                        reader_relevance_normalized=r)
                                for c, r in zip(ordered, relevance))
    return PreparedPool(selector_candidates, tuple(tuple(row) for row in matrix))


def select_crosslingual_mmr(candidates: Sequence[ScoredPassage], config: CrosslingualMMRConfig | None = None) -> SelectionResult:
    config = config or CrosslingualMMRConfig()
    pool = prepare_crosslingual_pool(candidates, epsilon=config.epsilon)
    # select_mmr only consumes these two documented fields; no baseline-v1 config is
    # passed or rewritten, preserving its implementation and iterative behavior.
    selector_config = SimpleNamespace(lambda_weight=float(config.lambda_weight),
                                       max_passages=config.max_passages)
    return select_mmr(pool, selector_config)
