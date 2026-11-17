"""Validated, shared constants for the first ordinary-QA baseline.

This configuration deliberately does not claim any model or snapshot is ready.
Their immutable revisions and compatibility records belong to artifact manifests.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class BaselineConfig:
    version: str = "baseline-v1"
    candidate_count: int = 20
    max_passages: int = 5
    lambda_weight: float = 0.5
    parameter_status: str = "untuned"
    epsilon: float = 1e-12
    relevance_normalization: str = "candidate_pool_minmax_once"
    similarity: str = "max_zero_clipped_cosine"
    tie_break: str = "reader_logit_desc_retrieval_rank_asc_passage_id_asc"
    invalid_score_policy: str = "fail_query"

    def __post_init__(self) -> None:
        for key, minimum in (("candidate_count", 1), ("max_passages", 0)):
            value = getattr(self, key)
            if type(value) is not int or value < minimum:
                raise ValueError(f"{key} must be an integer >= {minimum}")
        for key in ("lambda_weight", "epsilon"):
            value = getattr(self, key)
            if type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError(f"{key} must be finite numeric data")
        if not 0 <= self.lambda_weight <= 1:
            raise ValueError("lambda_weight must be in [0, 1]")
        fixed = {
            "version": "baseline-v1",
            "parameter_status": "untuned",
            "epsilon": 1e-12,
            "relevance_normalization": "candidate_pool_minmax_once",
            "similarity": "max_zero_clipped_cosine",
            "tie_break": "reader_logit_desc_retrieval_rank_asc_passage_id_asc",
            "invalid_score_policy": "fail_query",
        }
        for key, expected in fixed.items():
            if getattr(self, key) != expected:
                raise ValueError(f"{key} is frozen in baseline-v1: {expected!r}")

    @classmethod
    def load(cls, path: str | Path) -> BaselineConfig:
        def reject_duplicates(pairs: list[tuple[str, object]]) -> dict:
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError(f"duplicate configuration key: {key}")
                result[key] = value
            return result

        data = json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=reject_duplicates)
        if not isinstance(data, dict):
            raise ValueError("baseline configuration must be a JSON object")
        unknown = data.keys() - cls.__dataclass_fields__.keys()
        if unknown:
            raise ValueError(f"unknown configuration keys: {sorted(unknown)}")
        return cls(**data)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ReaderConfig:
    """P06 span rules; scores remain uncalibrated logits, never probabilities."""

    version: str = "reader-v1"
    max_answer_tokens: int = 64
    span_score: str = "start_logit_plus_end_logit"
    span_tie_break: str = "start_token_asc_end_token_asc"

    def __post_init__(self):
        expected = {"version": "reader-v1", "max_answer_tokens": 64,
                    "span_score": "start_logit_plus_end_logit",
                    "span_tie_break": "start_token_asc_end_token_asc"}
        if type(self.max_answer_tokens) is not int or asdict(self) != expected:
            raise ValueError("Reader v1 span rules are frozen")

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class AnswerConfig:
    version: str = "ordinary-answer-v1"
    answer_order: str = "reader_logit_desc_retrieval_rank_asc_passage_id_asc"
    fallback_policy: str = "no_valid_span_related_text_no_selection_insufficient"
    calibration_status: str = "uncalibrated_structural_rules_only"

    def to_dict(self):
        return asdict(self)
