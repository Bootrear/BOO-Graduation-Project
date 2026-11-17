from dataclasses import replace
import math

import pytest

from cyber_qa.answering.ordinary import assemble_answer, failed_answer
from cyber_qa.config import BaselineConfig
from cyber_qa.selection.mmr import SelectionResult, prepare_pool, select_mmr
from test_mmr import candidate


def test_only_selected_evidence_can_supply_answer_and_keeps_sources():
    pool = prepare_pool([candidate("A", 10, (1, 0, 0)),
                         candidate("B", 9, (.99, math.sqrt(1-.99**2), 0)),
                         candidate("C", 8, (.1, 0, math.sqrt(.99)))])
    config = BaselineConfig(max_passages=2)
    chosen = select_mmr(pool, config)
    # MMR selected A/C; replacing A's span forces C, never unselected B.
    chosen = replace(chosen, selected=(replace(chosen.selected[0], answer_span=None), chosen.selected[1]))
    answer = assemble_answer(chosen, 3, config)
    assert answer.text == "C"
    assert answer.evidence_id == chosen.selected[1].passage_id
    assert answer.context == "Text for C."
    assert answer.source["source_url"] == "https://example.invalid/C"
    assert answer.source["snapshot_id"] == chosen.selected[1].passage.snapshot_id
    assert answer.evidence_sufficiency == "not_assessed"
    assert answer.policy.calibration_status == "uncalibrated_structural_rules_only"


def test_answer_order_does_not_mix_span_or_mmr_scores():
    a, b = candidate("A", -100, (1, 0), 2), candidate("B", -99, (0, 1), 3)
    a = replace(a, answer_span=replace(a.answer_span, span_score=99999))
    assert assemble_answer(SelectionResult("mmr", (a, b)), 2).text == "B"
    # Original relevance tie: retrieval rank, then ID, independent of selected order.
    b = replace(b, reader_relevance_logit=-100)
    assert assemble_answer(SelectionResult("mmr", (b, a)), 2).text == "A"
    a, b = replace(a, retrieval_rank=1), replace(b, retrieval_rank=1)
    expected = min((a, b), key=lambda c: c.passage_id)
    assert assemble_answer(SelectionResult("mmr", (b, a)), 2).evidence_id == expected.passage_id


def test_shortfall_is_not_evidence_sufficiency():
    c = candidate("A", -9999, (1, 0))
    for count in (1, 20):
        answer = assemble_answer(SelectionResult("reader_topk", (c,)), count)
        assert answer.output_type == "extractive_answer"
        assert answer.evidence_sufficiency == "not_assessed"
        assert answer.candidate_shortfall == (count == 1)


def test_related_text_no_candidates_and_disabled_selection_are_distinct():
    c = replace(candidate("A", 1, (1, 0)), answer_span=None)
    answer = assemble_answer(SelectionResult("mmr", (c,)), 20)
    assert answer.output_type == "related_text" and answer.text == c.passage.text
    assert answer.fallback_reason == "no_valid_answer_span"
    assert not answer.candidate_shortfall
    assert assemble_answer(SelectionResult("mmr", ()), 0).fallback_reason == "no_candidates"
    disabled = assemble_answer(SelectionResult("mmr", ()), 20, BaselineConfig(max_passages=0))
    assert disabled.fallback_reason == "no_selected_evidence"
    assert disabled.output_type == "insufficient_information"


def test_failures_have_explicit_reason_without_fabricated_evidence():
    answer = failed_answer("reader: invalid logits")
    assert answer.output_type == "processing_failure" and answer.fallback_reason == "reader: invalid logits"
    assert answer.evidence_id is None and answer.source is None
    assert answer.to_dict()["policy"]["version"] == "ordinary-answer-v1"
    with pytest.raises(ValueError):
        failed_answer("")


def test_invalid_counts_duplicates_and_nonfinite_scores_fail():
    c = candidate("A", 1, (1, 0))
    for selection, count in ((SelectionResult("mmr", (c,)), 0),
                              (SelectionResult("mmr", (c, c)), 2),
                              (SelectionResult("mmr", (replace(c, reader_relevance_logit=float("nan")),)), 1),
                              (SelectionResult("mmr", ()), -1)):
        with pytest.raises(ValueError):
            assemble_answer(selection, count)
