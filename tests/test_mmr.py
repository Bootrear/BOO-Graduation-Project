from dataclasses import replace
import math
import random

import pytest

from cyber_qa.config import BaselineConfig
from cyber_qa.data.candidates import AnswerSpan, ScoredPassage
from cyber_qa.data.contracts import SourceUnit, make_manifest, make_passage
from cyber_qa.selection.mmr import (
    normalize_relevance, prepare_pool, reader_topk, select_mmr, select_mmr_reference, similarity_matrix,
)


def candidate(label, logit, vector, rank=1):
    unit = SourceUnit(cwe_id=f"CWE-{ord(label)}", title=label, field_name="description",
        source_locator=f"/fixture/{label}", source_text=f"Text for {label}.",
        source_url=f"https://example.invalid/{label}", dataset_version="fixture", entry_status=None)
    manifest = make_manifest(dataset_name="CWE", dataset_version="fixture",
        source_download_url="https://example.invalid", raw_file_sha256="0" * 64,
        acquired_at=None, acquired_at_basis="unknown", registered_at="2026-11-13T00:00:00Z",
        processed_at="2026-11-13T00:00:00Z", parser_version="fixture", chunker_version="fixture",
        preprocessing_config={})
    passage = make_passage(unit, manifest, 0, unit.source_text)
    span = AnswerSpan(label, 9, 10, 12, 12, 1.0)
    return ScoredPassage(passage, rank, 100 - rank, tuple(vector), logit, span)


def labels(result):
    return [c.passage.title for c in result.selected]


@pytest.mark.parametrize("logits,expected", [
    ([-2, 0, 2], (0, .5, 1)), ([7, 7], (0, 0)), ([9], (0,)),
    ([0, 1e-12], (0, 0)), ([0, 2e-12], (0, 1)), ([], ()),
])
def test_normalization_contract(logits, expected):
    assert normalize_relevance(logits) == expected


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_reader_logits_fail_with_log(bad, caplog):
    with pytest.raises(ValueError, match="NaN or Inf"):
        normalize_relevance([1, bad])
    assert "query failed" in caplog.text


def test_nonfinite_range_is_not_silently_normalized():
    with pytest.raises(ValueError, match="overflow"):
        normalize_relevance([-1e308, 1e308])


def test_cosine_negative_and_clipping_and_no_vector_mutation():
    vectors = [[1., 0.], [-1., 0.], [1e-300, 0.]]
    before = [row[:] for row in vectors]
    matrix = similarity_matrix(vectors)
    assert matrix[0][1] == 0
    assert matrix[0][2] == pytest.approx(1)
    assert all(0 <= value <= 1 for row in matrix for value in row)
    assert vectors == before


@pytest.mark.parametrize("vectors", [
    [(0, 0)], [(float("nan"), 1)], [(float("inf"), 0)], [(1, 0), (1,)], [()],
])
def test_bad_vectors_fail_with_log(vectors, caplog):
    with pytest.raises(ValueError):
        similarity_matrix(vectors)
    assert "query failed" in caplog.text


def test_mmr_must_update_redundancy_after_first_selection():
    original = [candidate("A", 10, (1, 0, 0), 1),
                candidate("B", 9, (.99, math.sqrt(1 - .99**2), 0), 2),
                candidate("C", 8, (.1, 0, math.sqrt(.99)), 3)]
    pool = prepare_pool(list(reversed(original)))
    config = BaselineConfig(max_passages=2, lambda_weight=.5)
    top, mmr = reader_topk(pool, config), select_mmr(pool, config)
    assert labels(top) == ["A", "B"]
    assert labels(mmr) == ["A", "C"]
    assert mmr.steps[1].mmr_score == pytest.approx(-.05)
    assert mmr.steps[1].max_redundancy == pytest.approx(.1)
    assert mmr.steps[1].redundancy_passage_id == original[0].passage_id
    assert mmr.steps[1].selected_before == (original[0].passage_id,)
    assert mmr.selected[1].reader_relevance_normalized == 0  # no per-round renormalization
    assert mmr == select_mmr_reference(pool, config)
    assert [c.reader_relevance_normalized for c in original] == [None] * 3
    assert mmr.selected[1].answer_span.text == "C"
    assert mmr.selected[1].vector == original[2].vector
    assert mmr.selected[1].passage == original[2].passage


def test_empty_zero_k_and_fewer_than_k():
    assert select_mmr(prepare_pool([])).selected_order == ()
    assert reader_topk(prepare_pool([])).selected_order == ()
    pool = prepare_pool([candidate("A", 3, (1, 0))])
    zero = BaselineConfig(max_passages=0)
    assert not select_mmr(pool, zero).selected
    assert not reader_topk(pool, zero).selected
    assert len(select_mmr(pool).selected) == 1
    assert select_mmr(pool).steps[0].reader_relevance_normalized == 0


def test_lambda_endpoints_and_stable_tie_breaks():
    pool = prepare_pool([candidate("C", 1, (1, 0), 2), candidate("B", 1, (1, 0), 1), candidate("A", 2, (1, 0), 3)])
    assert labels(select_mmr(pool, BaselineConfig(lambda_weight=0))) == ["A", "B", "C"]
    assert select_mmr(pool, BaselineConfig(lambda_weight=1)).selected_order == reader_topk(pool).selected_order
    tied = [candidate("A", 2, (1, 0)), candidate("B", 2, (1, 0))]
    expected = tuple(sorted(c.passage_id for c in tied))
    assert select_mmr(prepare_pool(tied)).selected_order == expected
    assert select_mmr(prepare_pool(tied[::-1])).selected_order == expected


def test_candidate_duplicates_are_not_selected_twice_and_conflicts_fail():
    c = candidate("A", 2, (1, 0))
    assert len(select_mmr(prepare_pool([c, c])).selected) == 1
    with pytest.raises(ValueError, match="conflicting duplicate"):
        prepare_pool([c, replace(c, reader_relevance_logit=3)])
    with pytest.raises(ValueError, match="retrieval score"):
        prepare_pool([replace(c, retrieval_score=float("nan"))])


def test_random_incremental_reference_equivalence():
    rng = random.Random(731)
    for iteration in range(80):
        n = rng.randrange(1, 12)
        candidates = [candidate(chr(65 + i), rng.choice([0., 1., 1., rng.random()]),
                      [rng.uniform(-1, 1) for _ in range(5)], i + 1) for i in range(n)]
        rng.shuffle(candidates)
        pool = prepare_pool(candidates)
        cfg = BaselineConfig(max_passages=rng.randrange(0, n + 4), lambda_weight=rng.choice([0., .5, 1., rng.random()]))
        fast, direct = select_mmr(pool, cfg), select_mmr_reference(pool, cfg)
        assert fast == direct, iteration
        assert len(fast.selected_order) == len(set(fast.selected_order)) == min(cfg.max_passages, n)
        if cfg.lambda_weight == 1:
            assert fast.selected_order == reader_topk(pool, cfg).selected_order
