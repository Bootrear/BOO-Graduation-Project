import pytest

from cyber_qa.evaluation import evidence_precision, evidence_recall, field_coverage


def test_evidence_metrics() -> None:
    predicted = ["E1", "E2"]
    gold = ["E2", "E3"]

    assert evidence_precision(predicted, gold) == 0.5
    assert evidence_recall(predicted, gold) == 0.5


def test_field_coverage() -> None:
    result = field_coverage(
        {"description", "impact"},
        {"description", "impact", "mitigation"},
    )

    assert result == pytest.approx(2 / 3)
