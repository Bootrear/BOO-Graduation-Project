import math
import random

import pytest

from cyber_qa.config import BaselineConfig
from cyber_qa.selection.crosslingual_mmr import (
    CrosslingualMMRConfig, prepare_crosslingual_pool, select_crosslingual_mmr,
)
from cyber_qa.selection.mmr import select_mmr_reference
from test_mmr import candidate


def rows():
    return [candidate("A", -50, (1, 0, 0), 1),
            candidate("B", 999, (.99, math.sqrt(1 - .99**2), 0), 2),
            candidate("C", 0, (0, 0, 1), 3)]


def test_retrieval_relevance_and_pool_pair_minmax_are_explicit():
    source = rows()
    # Scores are retrieval scores; the deliberately unrelated Reader values are ignored.
    from dataclasses import replace
    source = [replace(c, retrieval_score=s) for c, s in zip(source, (.2, .8, .5))]
    pool = prepare_crosslingual_pool(source)
    assert [c.reader_relevance_normalized for c in pool.candidates] == pytest.approx((0, 1, .5))
    assert [c.reader_relevance_logit for c in pool.candidates] == pytest.approx((.2, .8, .5))
    assert pool.similarities[0][1] == pytest.approx(1)
    assert pool.similarities[0][2] == pytest.approx(0)
    assert pool.similarities[1][2] == pytest.approx(0)
    raw = prepare_crosslingual_pool(source, similarity_scale="raw")
    assert raw.similarities[0][1] == pytest.approx(.99)
    assert raw.similarities[0][2] == pytest.approx(0)


def test_empty_k_short_single_ties_and_lambda_one_topk():
    assert select_crosslingual_mmr([]).selected_order == ()
    assert select_crosslingual_mmr(rows(), CrosslingualMMRConfig(max_passages=0)).steps == ()
    assert len(select_crosslingual_mmr(rows(), CrosslingualMMRConfig(max_passages=9)).selected) == 3
    single = select_crosslingual_mmr(rows()[:1])
    assert len(single.selected) == 1 and single.steps[0].reader_relevance_normalized == 0
    from dataclasses import replace
    tied = [replace(candidate("A", 1, (1, 0), 2), retrieval_score=1),
            replace(candidate("B", 1, (0, 1), 1), retrieval_score=1)]
    assert select_crosslingual_mmr(tied).selected_order == tuple(c.passage_id for c in sorted(tied, key=lambda c: (c.retrieval_rank, c.passage_id)))
    cfg = CrosslingualMMRConfig(lambda_weight=1, max_passages=2)
    selected = select_crosslingual_mmr(rows(), cfg)
    assert selected.selected_order == tuple(c.passage_id for c in sorted(rows(), key=lambda c: (-c.retrieval_score, c.retrieval_rank, c.passage_id))[:2])


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_retrieval_fails(bad):
    from dataclasses import replace
    with pytest.raises(ValueError):
        prepare_crosslingual_pool([replace(rows()[0], retrieval_score=bad)])


def test_zero_vectors_and_overflow_fail():
    from dataclasses import replace
    with pytest.raises(ValueError, match="zero"):
        prepare_crosslingual_pool([replace(rows()[0], vector=(0, 0, 0))])
    for invalid in ((float("nan"), 0, 1), (float("inf"), 0, 1)):
        with pytest.raises(ValueError):
            prepare_crosslingual_pool([replace(rows()[0], vector=invalid)])
    huge = [replace(rows()[0], retrieval_score=-1e308), replace(rows()[1], retrieval_score=1e308)]
    with pytest.raises(ValueError, match="overflow"):
        prepare_crosslingual_pool(huge)


def test_selector_incremental_steps_equal_frozen_reference():
    rng = random.Random(20027)
    for _ in range(50):
        pool_rows = [candidate(chr(65 + i), rng.uniform(-1, 1),
                               [rng.uniform(-1, 1) for _ in range(4)], i + 1)
                     for i in range(rng.randrange(1, 8))]
        pool = prepare_crosslingual_pool(pool_rows)
        cfg = CrosslingualMMRConfig(max_passages=rng.randrange(0, 10),
                                    lambda_weight=rng.choice((0, .25, .5, 1)))
        # Both calls enter the existing selector contract, so its incremental updates
        # and round logs must remain equivalent to a full selected-set recomputation.
        from cyber_qa.selection.crosslingual_mmr import select_crosslingual_mmr
        actual = select_crosslingual_mmr(pool_rows, cfg)
        expected = select_mmr_reference(pool, BaselineConfig(max_passages=cfg.max_passages,
                                                              lambda_weight=cfg.lambda_weight))
        assert actual.selected_order == expected.selected_order
        assert [s.mmr_score for s in actual.steps] == pytest.approx([s.mmr_score for s in expected.steps])
