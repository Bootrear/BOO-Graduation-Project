"""Keep passage, vector, retrieval and Reader outputs attached during reordering."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math

from .contracts import Passage


@dataclass(frozen=True)
class RetrievedPassage:
    passage: Passage
    retrieval_rank: int
    retrieval_score: float
    vector: tuple[float, ...]

    @property
    def passage_id(self) -> str:
        return self.passage.passage_id


@dataclass(frozen=True)
class AnswerSpan:
    text: str
    start_char: int
    end_char: int  # exclusive, relative to passage.text
    start_token: int
    end_token: int  # inclusive, relative to the Reader input
    span_score: float

    def __post_init__(self):
        if not self.text or not math.isfinite(self.span_score):
            raise ValueError("non-empty answer and finite span score required")
        for key in ("start_char", "end_char", "start_token", "end_token"):
            if type(getattr(self, key)) is not int or getattr(self, key) < 0:
                raise ValueError("span positions must be non-negative integers")
        if self.start_char >= self.end_char or self.start_token > self.end_token:
            raise ValueError("invalid span order")


@dataclass(frozen=True)
class ScoredPassage(RetrievedPassage):
    reader_relevance_logit: float
    answer_span: AnswerSpan | None = None
    reader_relevance_normalized: float | None = None
    title_truncated: bool = False

    def __post_init__(self):
        if self.answer_span is not None:
            span = self.answer_span
            if span.end_char > len(self.passage.text) or self.passage.text[span.start_char:span.end_char] != span.text:
                raise ValueError("answer span cannot be mapped back to passage text")

    def to_dict(self, *, include_vector: bool = False) -> dict:
        record = asdict(self)
        record["passage_id"] = self.passage_id
        if not include_vector:
            record.pop("vector")
        return record
