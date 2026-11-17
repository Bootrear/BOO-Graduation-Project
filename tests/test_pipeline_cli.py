import json
from types import SimpleNamespace

import pytest

from test_reader import setup
from cyber_qa.__main__ import main, write_result
from cyber_qa.pipeline.ordinary import QAPipeline


@pytest.fixture
def pipeline(setup):
    runtime, candidates, calls = setup
    runtime.provenance, runtime.weight_hashes, runtime.loading_info = {}, {}, {}
    runtime.encode_question = lambda question: (1., 0.)
    index = SimpleNamespace(metadata={"snapshot_id": candidates[0].passage.snapshot_id},
                            search=lambda vector, n: candidates[:n])
    return QAPipeline(runtime, index), calls


def test_both_strategies_share_one_reader_pass_and_one_normalization(pipeline, monkeypatch):
    pipe, calls = pipeline
    from cyber_qa.pipeline import ordinary
    prepare = ordinary.prepare_pool
    prepared = []
    def counted(*args):
        prepared.append(1)
        return prepare(*args)
    monkeypatch.setattr(ordinary, "prepare_pool", counted)
    result = pipe.query("What?", strategy="both", batch_size=2)
    assert result["status"] == "success"
    assert len(calls) == 2 and len(prepared) == 1  # three candidates, two batches total
    assert set(result["results"]) == {"reader_topk", "mmr"}
    assert all(c["reader_relevance_normalized"] is not None for c in result["candidates"])
    for run in result["results"].values():
        assert run["answer"]["evidence_id"] in run["selection"]["selected_order"]
    assert "model_load_seconds" in result["timings"] and "reader_seconds" in result["timings"]
    assert len(result["configuration_sha256"]) == 64
    assert result["question_input"]["truncated"] is False


def test_empty_pool_is_success_with_insufficient_answer(pipeline):
    pipe, calls = pipeline
    pipe.index.search = lambda *a, **kw: ()
    result = pipe.query("What?", strategy="both")
    assert result["status"] == "success" and result["candidate_count"] == 0
    assert not calls
    assert all(r["answer"]["fallback_reason"] == "no_candidates" for r in result["results"].values())


@pytest.mark.parametrize("stage", ["retrieval", "reader"])
def test_stage_failure_is_structured_no_partial_answers(pipeline, stage):
    pipe, _ = pipeline
    def fail(*args, **kwargs):
        raise ValueError("synthetic invalid output")
    if stage == "retrieval":
        pipe.index.search = fail
    else:
        pipe.scorer.score = fail
    result = pipe.query("What?", strategy="both")
    assert result["status"] == "failed" and result["error"]["stage"] == stage
    assert result["results"] == {}
    assert result["failure_answer"]["output_type"] == "processing_failure"


def test_long_question_and_bad_strategy_fail_without_model(pipeline):
    pipe, calls = pipeline
    for question, strategy in (("what " * 65, "both"), ("What?", "unknown")):
        result = pipe.query(question, strategy=strategy)
        assert result["status"] == "failed" and result["error"]["stage"] == "validation"
    assert not calls


def test_cli_success_failure_and_atomic_json(tmp_path, monkeypatch, pipeline):
    pipe, _ = pipeline
    monkeypatch.setattr(QAPipeline, "load", lambda *a, **kw: pipe)
    path = tmp_path / "nested" / "run.json"
    command = ["query", "--question", "What?", "--strategy", "both", "--output", str(path)]
    assert main(command) == 0
    assert json.loads(path.read_text())["status"] == "success"
    before = path.read_bytes()
    with pytest.raises(ValueError):
        write_result(path, {"bad": float("nan")})
    assert path.read_bytes() == before
    def fail(*args, **kwargs):
        raise FileNotFoundError("missing index")
    monkeypatch.setattr(QAPipeline, "load", fail)
    assert main(command) == 1
    failed = json.loads(path.read_text())
    assert failed["status"] == "failed" and failed["error"]["stage"] == "query_initialization"
    assert failed["failure_answer"]["fallback_reason"].startswith("query_initialization")
    assert main(["query", "--question", "What?", "--output", str(tmp_path)]) == 1


@pytest.mark.parametrize("argv,code", [(["--help"], 0), (["preprocess", "--help"], 0),
    (["build-index", "--help"], 0), (["query", "--help"], 0), (["query"], 2),
    (["query", "--question", "q", "--output", "unused", "--strategy", "bad"], 2)])
def test_cli_help_and_argument_errors(argv, code):
    with pytest.raises(SystemExit) as exc:
        main(argv)
    assert exc.value.code == code
