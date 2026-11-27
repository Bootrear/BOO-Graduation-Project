import numpy as np

from cyber_qa.experiments import crosslingual_mmr_eval as evaluation
from test_mmr import candidate


def test_summary_reports_paired_ci_and_disagreement():
    rows = []
    for language in ("en", "zh"):
        for scale in ("pool_minmax", "raw"):
            for lam in (0.0, 1.0):
                for index, difference in enumerate((.5, 0., -.5)):
                    top = .5
                    mmr = top + difference
                    rows.append({"language": language, "similarity_scale": scale, "lambda": lam,
                        "topk_recall": top, "mmr_recall": mmr,
                        "topk_full_coverage": False, "mmr_full_coverage": False,
                        "topk_hit": True, "mmr_hit": mmr > 0,
                        "topk_selected_pairwise_cosine": .8, "mmr_selected_pairwise_cosine": .7,
                        "candidate_pool_pairwise_cosine": .6,
                        "set_disagreement": index == 0, "order_disagreement": index < 2})
    result = evaluation.summarize(rows, (0., 1.))
    stats = result["languages"]["en"]["raw"]["0.0"]
    assert stats["recall_wins_losses_ties"] == {"wins": 1, "losses": 1, "ties": 1}
    assert stats["paired_recall_difference_mmr_minus_topk"] == 0
    assert len(stats["paired_bootstrap_95_ci"]) == 2
    assert stats["set_disagreement_rate"] == 1 / 3
    assert result["interpretation"].startswith("40-question")


def test_eval_reuses_same_pool_and_lambda_one_matches_topk(monkeypatch):
    pool = [candidate("A", 0, (1., 0.), 1), candidate("B", 0, (.8, .6), 2),
            candidate("C", 0, (0., 1.), 3)]
    passages = [{**item.passage.to_dict(), "embedding_truncated": False} for item in pool]
    vectors = np.asarray([item.vector for item in pool], dtype=np.float32)
    records = [{"question_id": "q1", "question": "question", "required_evidence_ids": [pool[0].passage_id]}]
    monkeypatch.setattr(evaluation, "embed_query", lambda *args, **kwargs: np.asarray([1., 0.]))
    rows, summary = evaluation.evaluate_records(records, records, vectors,
        [item.passage_id for item in pool], passages, None, None, device="cpu",
        n_candidates=3, k=2, lambdas=(0., 1.))
    assert len(rows) == 8
    for row in rows:
        if row["lambda"] == 1:
            assert row["mmr_ids"] == row["topk_ids"]
    assert summary["lambda_grid"] == [0., 1.]
    assert {row["language"] for row in rows} == {"en", "zh"}


def test_empty_selection_redundancy_is_null_and_serializable(monkeypatch, tmp_path):
    import json
    pool = [candidate("A", 0, (1., 0.), 1)]
    monkeypatch.setattr(evaluation, "embed_query", lambda *args, **kwargs: np.asarray([1., 0.]))
    records = [{"question_id": "q1", "question": "question", "required_evidence_ids": [pool[0].passage_id]}]
    rows, summary = evaluation.evaluate_records(records, records,
        np.asarray([pool[0].vector]), [pool[0].passage_id], [pool[0].passage.to_dict()], None, None,
        device="cpu", n_candidates=1, k=0, lambdas=(0.,))
    assert rows[0]["topk_selected_pairwise_cosine"] is None
    assert summary["languages"]["en"]["pool_minmax"]["0.0"]["mmr_selected_pairwise_cosine"] is None
    output = tmp_path / "result"
    evaluation.write_results(output, rows, summary, {})
    json.loads((output / "summary.json").read_text())
