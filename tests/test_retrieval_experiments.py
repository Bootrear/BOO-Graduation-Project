"""Retrieval ablation isolation, scoring and comparison regression tests."""
from copy import deepcopy
from dataclasses import replace
import importlib.util
import json
import math
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from test_retrieval import corpus
from cyber_qa.config import BaselineConfig
from cyber_qa.data.candidates import ScoredPassage
from cyber_qa.experiments.comparison import (compare_to_baseline, evaluate_question, historical_check,
    summarize, validate_questions)
from cyber_qa.experiments.retrieval import (BM25, METHODS, ExperimentRetriever,
    RetrievalExperimentConfig, lexical_tokens, reciprocal_rank_fusion, split_question)
from cyber_qa.retrieval.dpr import DPRIndex


@pytest.fixture
def setup(corpus):
    _, _, _, passages, _ = corpus
    passages = [replace(p, title=t) for p, t in zip(passages,
                ["Memory bounds checks", "SQL injection prevention", "SQL injection detection"])]
    vectors = np.zeros((3, 768), dtype=np.float32)
    vectors[:, :2] = [[10, 1], [2, 0], [1, 5]]
    index = DPRIndex(vectors, passages, {})
    queries = []
    def question_ids(q):
        if len(q.split()) > 30:
            raise ValueError("question too long")
        return list(range(len(q.split())))
    def encode(q):
        question_ids(q)
        queries.append(q)
        v = np.zeros(768, dtype=np.float32)
        v[1 if q.startswith("how") else 0] = 1
        return v
    runtime = SimpleNamespace(encode_question=encode, question_ids=question_ids)
    retriever = ExperimentRetriever(runtime, index, RetrievalExperimentConfig(entry_top_m=1))
    return runtime, index, retriever, queries


def test_bm25_formula_tokens_and_unknown_query():
    bm25 = BM25(["SQL SQL", "SQL", "memory"])
    idf = math.log1p(1.5 / 2.5)
    expected = idf * 2 * 2.5 / (2 + 1.5 * (.25 + .75 * 2 / (4 / 3)))
    assert bm25.scores("SQL")[0] == pytest.approx(expected)
    assert np.array_equal(bm25.scores("SQL SQL"), bm25.scores("SQL"))
    assert not bm25.scores("unknown").any()
    assert lexical_tokens("How is CWE-89 related to SQL?") == ["cwe", "89", "related", "sql"]
    assert BM25([]).scores("sql").size == 0


def test_rrf_duplicate_votes_and_ties():
    scores = reciprocal_rank_fusion([["a", "a", "b"], ["b", "a"]])
    assert scores["a"] == scores["b"] == 1 / 61 + 1 / 62


@pytest.mark.parametrize("question", ["What is SQL injection?", "What do architecture and design require?"])
def test_split_does_not_split_noun_conjunctions(question):
    assert split_question(question) == [question]


def test_split_preserves_original_and_context():
    q = "How does SQL injection occur, and how can it be detected?"
    parts = split_question(q)
    assert parts[0] == q and len(parts) == 3
    assert "SQL injection" in parts[1] and "SQL injection" in parts[2]


def test_dpr_is_identical_to_existing_retrieval_and_no_index_mutation(setup):
    runtime, index, retriever, _ = setup
    before = index.vectors.copy()
    expected = index.search(runtime.encode_question("SQL"), 2)
    assert retriever.retrieve("SQL", method="dpr", n=2).candidates == expected
    for method in METHODS:
        run = retriever.retrieve("SQL", method=method, n=5)
        assert len(run.candidates) == 3
        assert len({c.passage_id for c in run.candidates}) == 3
        assert [c.retrieval_rank for c in run.candidates] == [1, 2, 3]
        for c in run.candidates:
            i = retriever.positions[c.passage_id]
            assert np.array_equal(c.vector, before[i])
            assert c.retrieval_score == before[i, 0]
    assert np.array_equal(before, index.vectors) and not index.vectors.flags.writeable


def test_hybrid_improves_lexical_match_and_ignores_zero_bm25_scores(setup):
    _, index, retriever, _ = setup
    run = retriever.retrieve("SQL injection", method="hybrid", n=1)
    assert "SQL" in run.candidates[0].passage.title
    assert run.trace["ranking_score_semantics"] == "equal_weight_RRF"
    run = retriever.retrieve("unfindable", method="hybrid", n=2)
    assert run.trace["branches"]["bm25"] == []
    assert run.candidates[0].passage_id == index.passages[0].passage_id


def test_subquery_uses_only_dpr_and_falls_back_without_split(setup, monkeypatch):
    runtime, index, retriever, calls = setup
    monkeypatch.setattr(retriever.lexical, "scores", lambda q: pytest.fail("subquery used BM25"))
    run = retriever.retrieve("What is SQL injection?", method="subquery", n=2)
    assert run.candidates == index.search(runtime.encode_question("What is SQL injection?"), 2)
    assert not run.trace["split_applied"]
    calls.clear()
    run = retriever.retrieve("What is SQL injection, and how can it be detected?", method="subquery", n=2)
    assert len(calls) == run.trace["query_encoding_count"] == 3
    assert len(run.candidates) == 2


def test_subquery_records_over_budget_context_without_truncation(setup):
    _, _, retriever, _ = setup
    q = "What " + "word " * 24 + "means, and how?"
    # Original has 29 words; adding Context makes the second query too long.
    retriever.runtime.question_ids = lambda text: (_ for _ in ()).throw(ValueError("over budget"))
    # Original encoder fixture checks its own budget, generated query validator rejects.
    run = retriever.retrieve(q, method="subquery", n=2)
    assert not run.trace["split_applied"]
    assert len(run.trace["skipped_queries"]) == 2


def test_hierarchy_reserves_global_slots_and_only_encodes_original(setup):
    _, _, retriever, calls = setup
    run = retriever.retrieve("SQL injection", method="hierarchical", n=3)
    assert len(calls) == 1
    assert len(run.trace["chosen_entries"]) == 1
    assert run.trace["focused_count"] == 1  # one passage in the predicted entry
    assert run.trace["global_count"] == 2  # shortfall filled globally
    assert len(run.candidates) == 3


@pytest.mark.parametrize("kwargs", [{"branch_depth": 0}, {"rrf_k": 0}, {"entry_top_m": -1},
    {"focused_fraction": 1}, {"bm25_b": float("nan")}])
def test_invalid_experiment_parameters(kwargs):
    with pytest.raises(ValueError):
        RetrievalExperimentConfig(**kwargs)


class FakeScorer:
    def __init__(self, runtime=None):
        self.calls = []

    def score(self, question, candidates, **kwargs):
        self.calls.append(question)
        return SimpleNamespace(candidates=tuple(ScoredPassage(c.passage, c.retrieval_rank,
            c.retrieval_score, c.vector, c.retrieval_score) for c in candidates))


def sample_question(index):
    gold = [index.passages[0].passage_id, index.passages[1].passage_id]
    return {"question_id": "q1", "question": "SQL injection", "required_evidence_ids": gold,
            "record_ids": ["CWE-THIS-MUST-NOT-REACH-RETRIEVAL"], "intent": "fake_intent",
            "gold_facts": [{"text": "fact", "supported_by": gold[:1]}], "status": "synthetic"}


def test_one_reader_pass_metrics_and_annotation_isolation(setup):
    _, index, retriever, calls = setup
    scorer = FakeScorer()
    q = sample_question(index)
    validate_questions([q], index.passages)
    row = evaluate_question(q, retriever, scorer, BaselineConfig(candidate_count=3, max_passages=1), "dpr")
    assert row["status"] == "success"
    assert calls == scorer.calls == [q["question"]]
    assert row["retrieval"]["recall"] == 1
    assert row["results"]["reader_topk"]["metrics"]["recall"] == .5
    summary = summarize([row])
    assert summary["retrieval"]["recall"] == 1
    assert summary["selection"]["reader_topk"]["micro_recall"] == .5
    assert summary["selection"]["reader_topk"]["mean_pairwise"] is None
    assert summary["by_group"]["question_type"]["multi"]["questions"] == 1
    assert compare_to_baseline([row], [row])["retrieval_recall"]["ci95"] == [0, 0]
    altered = {**q, "record_ids": ["CWE-999"], "intent": "another_intent"}
    row2 = evaluate_question(altered, retriever, scorer, BaselineConfig(candidate_count=3, max_passages=1), "dpr")
    assert row2["pool_ids"] == row["pool_ids"]


def test_failure_retains_denominator_and_disables_ci(setup):
    _, index, retriever, _ = setup
    q = sample_question(index)
    scorer = FakeScorer()
    good = evaluate_question(q, retriever, scorer, BaselineConfig(), "dpr")
    bad = evaluate_question({**q, "question_id": "q2"}, retriever, scorer, BaselineConfig(), "missing")
    assert bad["error"]["stage"] == "retrieval"
    summary = summarize([good, bad])
    assert summary["retrieval"]["recall"] == .5 and summary["failed"] == 1
    assert summary["mmr_minus_topk"] is None
    assert not compare_to_baseline([good, bad], [good, bad])["valid"]


def test_unknown_gold_and_duplicate_questions_rejected(setup):
    _, index, _, _ = setup
    q = sample_question(index)
    for questions in ([], [q, q], [{**q, "required_evidence_ids": ["missing"]}]):
        with pytest.raises(ValueError):
            validate_questions(questions, index.passages)


def test_cli_runs_all_four_archives_old_results_and_refuses_overwrite(setup, tmp_path, monkeypatch):
    runtime, index, _, _ = setup
    spec = importlib.util.spec_from_file_location("compare_retrieval", "scripts/compare_retrieval.py")
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    runtime.load_model = lambda role: None
    runtime.provenance, runtime.weight_hashes, runtime.loading_info = {}, {}, {}
    runtime.budget = SimpleNamespace(to_dict=lambda: {})
    runtime.device = "cpu"
    runtime.torch = SimpleNamespace(get_num_threads=lambda: 1)
    monkeypatch.setattr(cli, "DPRRuntime", lambda **kw: runtime)
    monkeypatch.setattr(cli, "load_index", lambda *a: index)
    monkeypatch.setattr(cli, "DPRReaderScorer", FakeScorer)
    qa = tmp_path / "qa.jsonl"
    qa.write_text(json.dumps(sample_question(index)) + "\n")
    old = tmp_path / "old"
    old.mkdir()
    protected = old / "probe-eval-N20.json"
    protected.write_text('{"original":true}\n')
    out = tmp_path / "run"
    args = ["--qa", str(qa), "--n", "2", "--baseline-dir", str(old), "--output", str(out)]
    assert cli.main(args) == 0
    manifest = json.loads((out / "manifest.json").read_text())
    assert manifest["completed_runs"] == [f"{m}-N2" for m in METHODS]
    assert (out / "archived-baseline" / protected.name).read_bytes() == protected.read_bytes()
    assert (out / "comparison.csv").exists() and (out / "comparison.md").exists()
    runs = json.loads((out / "comparison.json").read_text())["runs"]
    assert len(runs) == 4 and all(r["summary"]["failed"] == 0 for r in runs)
    before = (out / "manifest.json").read_bytes()
    with pytest.raises(FileExistsError):
        cli.main(args)
    assert (out / "manifest.json").read_bytes() == before


def test_historical_replay_detects_selection_change(setup):
    _, index, retriever, _ = setup
    row = evaluate_question(sample_question(index), retriever, FakeScorer(), BaselineConfig(), "dpr")
    old = {"question_id": row["question_id"], "required_evidence_ids": row["required_evidence_ids"],
           "pool_ids": list(row["pool_ids"]), "reader_ranking": deepcopy(row["candidates"]),
           "topk_order": row["results"]["reader_topk"]["selected_order"],
           "mmr_order": row["results"]["mmr"]["selected_order"]}
    assert historical_check([row], {"rows": [old]})["status"] == "matched"
    old["reader_ranking"][0]["reader_logit"] += 1e-3
    changed_score = historical_check([row], {"rows": [old]})
    assert changed_score["structure_status"] == "matched"
    assert changed_score["status"] == "different"
    assert not changed_score["reader_logits_match_within_1e-6"]
    old["reader_ranking"][0]["reader_logit"] -= 1e-3
    old["mmr_order"] = []
    assert historical_check([row], {"rows": [old]})["status"] == "different"
