"""Frozen baseline scales, deterministic Reader Top-K, and iterative MMR."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import logging
import math
from typing import Sequence

from cyber_qa.config import BaselineConfig
from cyber_qa.data.candidates import ScoredPassage

logger = logging.getLogger(__name__)


def _fail(reason: str):
    logger.error("selection query failed: %s", reason)
    raise ValueError(reason)


def normalize_relevance(logits: Sequence[float], epsilon: float = 1e-12) -> tuple[float, ...]:
    if epsilon != 1e-12:
        _fail("baseline-v1 epsilon is fixed at 1e-12")
    values = tuple(float(x) for x in logits)
    if any(not math.isfinite(x) for x in values):
        _fail("Reader relevance contains NaN or Inf")
    if not values:
        return ()
    low, high = min(values), max(values)
    difference = high - low
    if not math.isfinite(difference):
        _fail("Reader relevance range overflow")
    if difference <= epsilon:
        return (0.0,) * len(values)
    return tuple((x - low) / difference for x in values)


def similarity_matrix(vectors: Sequence[Sequence[float]]) -> tuple[tuple[float, ...], ...]:
    if len(vectors) == 0:
        return ()
    dimension = len(vectors[0])
    if dimension == 0:
        _fail("empty paragraph vector")
    normalized = []
    for vector in vectors:
        if len(vector) != dimension or any(not math.isfinite(x) for x in vector):
            _fail("paragraph vector dimension mismatch or NaN/Inf")
        norm = math.hypot(*vector)
        if norm == 0 or not math.isfinite(norm):
            _fail("paragraph vector has zero or non-finite norm")
        normalized.append(tuple(float(x) / norm for x in vector))
    matrix = []
    for left in normalized:
        row = []
        for right in normalized:
            cosine = math.fsum(x * y for x, y in zip(left, right))
            row.append(max(0.0, max(-1.0, min(1.0, cosine))))
        matrix.append(tuple(row))
    return tuple(matrix)


@dataclass(frozen=True)
class PreparedPool:
    candidates: tuple[ScoredPassage, ...]
    similarities: tuple[tuple[float, ...], ...]


def prepare_pool(candidates: Sequence[ScoredPassage], config: BaselineConfig | None = None) -> PreparedPool:
    """Deduplicate and normalize the COMPLETE pool once for both strategies."""
    config = config or BaselineConfig()
    unique = {}
    for candidate in candidates:
        if type(candidate.retrieval_rank) is not int or candidate.retrieval_rank < 1:
            _fail("retrieval rank must be a positive integer")
        if not math.isfinite(candidate.retrieval_score):
            _fail("retrieval score is NaN or Inf")
        prior = unique.get(candidate.passage_id)
        if prior is not None and prior != candidate:
            _fail("conflicting duplicate candidate for " + candidate.passage_id)
        unique[candidate.passage_id] = candidate
    ordered = sorted(unique.values(), key=lambda c: (c.retrieval_rank, c.passage_id))
    relevance = normalize_relevance([c.reader_relevance_logit for c in ordered], config.epsilon)
    matrix = similarity_matrix([c.vector for c in ordered])
    scored = tuple(replace(c, reader_relevance_normalized=r) for c, r in zip(ordered, relevance))
    return PreparedPool(scored, matrix)


def _reader_key(candidate: ScoredPassage):
    return (-candidate.reader_relevance_logit, candidate.retrieval_rank, candidate.passage_id)


@dataclass(frozen=True)
class MMRStep:
    round: int
    selected_before: tuple[str, ...]
    passage_id: str
    reader_relevance_logit: float
    reader_relevance_normalized: float
    max_redundancy: float
    redundancy_passage_id: str | None
    mmr_score: float


@dataclass(frozen=True)
class SelectionResult:
    strategy: str
    selected: tuple[ScoredPassage, ...]
    steps: tuple[MMRStep, ...] = ()

    @property
    def selected_order(self) -> tuple[str, ...]:
        return tuple(c.passage_id for c in self.selected)

    def to_dict(self):
        return {"strategy": self.strategy, "selected_order": list(self.selected_order),
                "evidence": [c.to_dict() for c in self.selected],
                "steps": [asdict(step) for step in self.steps]}


def reader_topk(pool: PreparedPool, config: BaselineConfig | None = None) -> SelectionResult:
    config = config or BaselineConfig()
    return SelectionResult("reader_topk", tuple(sorted(pool.candidates, key=_reader_key)[:config.max_passages]))


def select_mmr(pool: PreparedPool, config: BaselineConfig | None = None) -> SelectionResult:
    config = config or BaselineConfig()
    candidates = pool.candidates
    selected, steps = [], []
    remaining = set(range(len(candidates)))
    redundancy = [0.0] * len(candidates)
    redundant_with = [None] * len(candidates)
    weight = config.lambda_weight
    while remaining and len(selected) < config.max_passages:
        scores = {i: weight * candidates[i].reader_relevance_normalized - (1 - weight) * redundancy[i] for i in remaining}
        chosen = min(remaining, key=lambda i: (-scores[i], *_reader_key(candidates[i])))
        candidate = candidates[chosen]
        steps.append(MMRStep(len(selected) + 1, tuple(candidates[j].passage_id for j in selected),
            candidate.passage_id, candidate.reader_relevance_logit, candidate.reader_relevance_normalized,
            redundancy[chosen], redundant_with[chosen], scores[chosen]))
        selected.append(chosen)
        remaining.remove(chosen)
        for i in remaining:
            similarity = pool.similarities[i][chosen]
            if redundant_with[i] is None or similarity > redundancy[i]:
                redundancy[i] = similarity
                redundant_with[i] = candidate.passage_id
    return SelectionResult("mmr", tuple(candidates[i] for i in selected), tuple(steps))


def select_mmr_reference(pool: PreparedPool, config: BaselineConfig | None = None) -> SelectionResult:
    """Simple oracle: traverse the entire selected set on EVERY round."""
    config = config or BaselineConfig()
    selected, steps = [], []
    candidates = pool.candidates
    while len(selected) < min(config.max_passages, len(candidates)):
        options = []
        for i, candidate in enumerate(candidates):
            if i in selected:
                continue
            nearest = max(selected, key=lambda j: pool.similarities[i][j]) if selected else None
            redundant = pool.similarities[i][nearest] if nearest is not None else 0.0
            score = config.lambda_weight * candidate.reader_relevance_normalized - (1 - config.lambda_weight) * redundant
            options.append(((-score, *_reader_key(candidate)), i, redundant, nearest, score))
        _, chosen, redundant, nearest, score = min(options)
        candidate = candidates[chosen]
        steps.append(MMRStep(len(selected) + 1, tuple(candidates[j].passage_id for j in selected),
            candidate.passage_id, candidate.reader_relevance_logit, candidate.reader_relevance_normalized,
            redundant, candidates[nearest].passage_id if nearest is not None else None, score))
        selected.append(chosen)
    return SelectionResult("mmr", tuple(candidates[i] for i in selected), tuple(steps))
