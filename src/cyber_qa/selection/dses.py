"""A minimal, explainable Domain-Structured Evidence Selection baseline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Mapping, Sequence

from cyber_qa.data import Evidence


@dataclass(frozen=True)
class Candidate:
    evidence: Evidence
    relevance: float
    entity_match: float = 0.0
    source_quality: float = 1.0
    covered_fields: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class DSESConfig:
    relevance_weight: float = 1.0
    entity_weight: float = 0.5
    source_quality_weight: float = 0.1
    coverage_weight: float = 0.5
    redundancy_weight: float = 0.3
    length_weight: float = 0.05
    stop_when_non_positive: bool = True


@dataclass(frozen=True)
class SelectionStep:
    evidence_id: str
    marginal_gain: float
    new_fields: tuple[str, ...]
    redundancy: float
    used_tokens: int


@dataclass(frozen=True)
class SelectionResult:
    selected: tuple[Candidate, ...]
    steps: tuple[SelectionStep, ...]
    covered_fields: frozenset[str]
    used_tokens: int


SimilarityFunction = Callable[[Candidate, Candidate], float]


def select_evidence(
    candidates: Sequence[Candidate],
    required_fields: set[str] | frozenset[str],
    max_items: int,
    token_budget: int,
    *,
    config: DSESConfig | None = None,
    field_weights: Mapping[str, float] | None = None,
    similarity: SimilarityFunction | None = None,
) -> SelectionResult:
    """Greedily select evidence by relevance, new coverage, and redundancy.

    Candidate scores are assumed to have been normalized by the caller. The
    function is intentionally model-agnostic so the same selector can consume
    dense, sparse, or QORE-produced candidate signals.
    """

    if max_items < 0:
        raise ValueError("max_items must be non-negative")
    if token_budget <= 0:
        raise ValueError("token_budget must be positive")

    cfg = config or DSESConfig()
    weights = field_weights or {}
    similarity_fn = similarity or (lambda _left, _right: 0.0)
    required = set(required_fields)
    remaining = list(candidates)
    selected: list[Candidate] = []
    steps: list[SelectionStep] = []
    covered: set[str] = set()
    used_tokens = 0

    while remaining and len(selected) < max_items:
        best_index: int | None = None
        best_score = float("-inf")
        best_new_fields: set[str] = set()
        best_redundancy = 0.0

        for index, candidate in enumerate(remaining):
            next_tokens = used_tokens + candidate.evidence.token_count
            if next_tokens > token_budget:
                continue

            new_fields = (set(candidate.covered_fields) & required) - covered
            coverage_gain = sum(weights.get(name, 1.0) for name in new_fields)
            redundancy = max(
                (similarity_fn(candidate, prior) for prior in selected),
                default=0.0,
            )
            length_ratio = candidate.evidence.token_count / token_budget
            score = (
                cfg.relevance_weight * candidate.relevance
                + cfg.entity_weight * candidate.entity_match
                + cfg.source_quality_weight * candidate.source_quality
                + cfg.coverage_weight * coverage_gain
                - cfg.redundancy_weight * redundancy
                - cfg.length_weight * length_ratio
            )

            if score > best_score:
                best_index = index
                best_score = score
                best_new_fields = new_fields
                best_redundancy = redundancy

        if best_index is None:
            break
        if cfg.stop_when_non_positive and best_score <= 0:
            break

        chosen = remaining.pop(best_index)
        selected.append(chosen)
        covered.update(best_new_fields)
        used_tokens += chosen.evidence.token_count
        steps.append(
            SelectionStep(
                evidence_id=chosen.evidence.evidence_id,
                marginal_gain=best_score,
                new_fields=tuple(sorted(best_new_fields)),
                redundancy=best_redundancy,
                used_tokens=used_tokens,
            )
        )

    return SelectionResult(
        selected=tuple(selected),
        steps=tuple(steps),
        covered_fields=frozenset(covered),
        used_tokens=used_tokens,
    )
