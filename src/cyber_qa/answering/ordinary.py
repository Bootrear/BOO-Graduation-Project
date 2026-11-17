"""Structural answer/fallback rules, not a semantic confidence estimator."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math

from cyber_qa.config import AnswerConfig, BaselineConfig
from cyber_qa.selection.mmr import SelectionResult


@dataclass(frozen=True)
class OrdinaryAnswer:
    output_type: str
    text: str | None
    evidence_id: str | None
    context: str | None
    source: dict | None
    fallback_reason: str | None
    candidate_count: int
    selected_count: int
    candidate_shortfall: bool
    evidence_sufficiency: str
    policy: AnswerConfig

    def to_dict(self):
        return asdict(self)


def assemble_answer(selection: SelectionResult, candidate_count: int,
                    config: BaselineConfig | None = None) -> OrdinaryAnswer:
    config = config or BaselineConfig()
    if type(candidate_count) is not int or candidate_count < 0:
        raise ValueError("candidate_count must be a nonnegative integer")
    selected = selection.selected
    if len(selected) > min(config.max_passages, candidate_count):
        raise ValueError("selection exceeds candidate count or evidence budget")
    if len({c.passage_id for c in selected}) != len(selected):
        raise ValueError("duplicate selected evidence")
    if any(not math.isfinite(c.reader_relevance_logit) for c in selected):
        raise ValueError("non-finite Reader relevance")
    common = dict(candidate_count=candidate_count, selected_count=len(selected),
                  candidate_shortfall=candidate_count < config.max_passages,
                  policy=AnswerConfig())
    if not selected:
        return OrdinaryAnswer("insufficient_information", None, None, None, None,
            "no_candidates" if candidate_count == 0 else "no_selected_evidence",
            evidence_sufficiency="insufficient", **common)
    # Match the frozen Reader order. span_score is used only within a passage;
    # never add retrieval, relevance or MMR scores to it.
    ordered = sorted(selected, key=lambda c: (-c.reader_relevance_logit, c.retrieval_rank, c.passage_id))
    usable = [c for c in ordered if c.answer_span is not None]
    chosen = usable[0] if usable else ordered[0]
    passage = chosen.passage
    source = {"cwe_id": passage.cwe_id, "title": passage.title,
              "field_name": passage.field_name, "source_url": passage.source_url,
              "source_locator": passage.source_locator, "snapshot_id": passage.snapshot_id,
              "dataset_version": passage.dataset_version, "content_sha256": passage.content_sha256,
              "acquired_at": passage.acquired_at}
    return OrdinaryAnswer("extractive_answer" if usable else "related_text",
        chosen.answer_span.text if usable else passage.text, chosen.passage_id, passage.text, source,
        None if usable else "no_valid_answer_span", evidence_sufficiency="not_assessed",
        **common)


def failed_answer(reason: str) -> OrdinaryAnswer:
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("processing failure needs a reason")
    return OrdinaryAnswer("processing_failure", None, None, None, None, reason,
                          0, 0, False, "not_assessed", AnswerConfig())
