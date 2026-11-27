"""Exploratory bilingual retrieval gate metrics and stopping rules."""

import numpy as np
import pytest

from cyber_qa.experiments.crosslingual_gate import mean_pairwise_cosine, recall_at, summarize


def test_recall_at_counts_required_evidence_fraction():
    assert recall_at(["a", "b", "c"], ["b", "x"]) == pytest.approx(1 / 3)
    with pytest.raises(ValueError, match="non-empty"):
        recall_at([], [])


def test_pairwise_cosine_uses_unordered_pairs():
    vectors = np.array([[1.0, 0.0], [1.0, 0.0], [0.0, 1.0]])
    assert mean_pairwise_cosine(vectors) == pytest.approx(1 / 3)
    assert mean_pairwise_cosine(vectors[:1]) is None


def rows(en_recall, zh_recall):
    return [
        {"language": language, "recall_at": {"20": value, "50": value, "100": value},
         "mean_pairwise_cosine": {"20": 0.8, "50": 0.7, "100": 0.6}}
        for language, value in (("en", en_recall), ("zh", zh_recall))
    ]


def test_gate_pass_requires_equivalence_and_english_baselines():
    result = summarize(rows(0.5, 0.45), [20, 50, 100])
    assert result["equivalence"] == pytest.approx(0.9)
    assert result["verdict"] == "retrieval_gate_pass_exploratory_only"
    assert all(item["pass"] for item in result["english_dpr_gate"].values())


@pytest.mark.parametrize(("zh", "verdict"), [
    (0.2, "stop_p2_p3_equivalence_below_0.60"),
    (0.35, "pause_p2_p3_equivalence_below_0.85"),
])
def test_equivalence_gate_pause_and_stop_thresholds(zh, verdict):
    assert summarize(rows(0.5, zh), [20, 50, 100])["verdict"] == verdict


def test_english_dpr_recall_gate_is_independent():
    result = summarize(rows(0.2, 0.19), [20, 50, 100])
    assert result["verdict"] == "pause_english_recall_gate_failed"
    assert not result["english_dpr_gate"]["20"]["pass"]
