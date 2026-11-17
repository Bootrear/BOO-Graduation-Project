"""Run the fixed 12-question real smoke set and a fresh-process CLI reload."""
import argparse
import json
import math
from pathlib import Path
import subprocess
import sys

from cyber_qa.__main__ import write_result
from cyber_qa.pipeline.ordinary import QAPipeline


def equivalent(left, right):
    """Compare stable results; tolerate floating-point kernel variation, not ID changes."""
    if isinstance(left, float):
        assert math.isclose(left, right, rel_tol=1e-4, abs_tol=2e-4), (left, right)
    elif isinstance(left, dict):
        assert left.keys() == right.keys()
        for key in left:
            equivalent(left[key], right[key])
    elif isinstance(left, (tuple, list)):
        assert len(left) == len(right)
        for a, b in zip(left, right):
            equivalent(a, b)
    else:
        assert left == right, (left, right)


def validate_run(run, passages):
    assert run["status"] == "success", run.get("error")
    assert set(run["results"]) == {"reader_topk", "mmr"}
    candidates = {c["passage_id"]: c for c in run["candidates"]}
    assert len(candidates) == run["candidate_count"]
    assert run["candidate_count"] <= run["configuration"]["baseline"]["candidate_count"]
    for candidate in candidates.values():
        p = passages[candidate["passage_id"]]
        assert candidate["passage"] == p.to_dict()
        span = candidate["answer_span"]
        if span:
            assert p.text[span["start_char"]:span["end_char"]] == span["text"]
    for result in run["results"].values():
        selection, answer = result["selection"], result["answer"]
        assert len(set(selection["selected_order"])) == len(selection["selected_order"]) <= 5
        assert all(c == candidates[c["passage_id"]] for c in selection["evidence"])
        if answer["evidence_id"] is not None:
            assert answer["evidence_id"] in selection["selected_order"]
            assert answer["text"] in passages[answer["evidence_id"]].text
            assert answer["source"]["source_url"] == passages[answer["evidence_id"]].source_url
        assert answer["policy"]["calibration_status"] == "uncalibrated_structural_rules_only"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", default="data/annotations/baseline_smoke.v1.json")
    parser.add_argument("--snapshot", default="data/processed/cwe-v1")
    parser.add_argument("--index", default="data/processed/dpr-index-v1")
    parser.add_argument("--device", default="auto")
    parser.add_argument("--output", required=True, help="Directory for per-query JSON and summary")
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    fixture = json.loads(Path(args.questions).read_text())
    assert 10 <= len(fixture["questions"]) <= 20
    pipeline = QAPipeline.load(args.index, args.snapshot, device=args.device)
    assert fixture["snapshot_id"] == pipeline.index.metadata["snapshot_id"]
    passages = {p.passage_id: p for p in pipeline.index.passages}
    summary = []
    first = None
    for question in fixture["questions"]:
        support = question["support"]
        passage = passages[support["passage_id"]]
        for key in ("cwe_id", "field_name", "source_locator", "source_url", "content_sha256"):
            assert getattr(passage, key) == support[key]
        assert passage.text[support["start_char"]:support["end_char"]] == support["quote"]
        run = pipeline.query(question["question"], strategy="both")
        write_result(output / (question["question_id"] + ".json"), run)
        validate_run(run, passages)
        if first is None:
            first = run
        row = {"question_id": question["question_id"], "question": question["question"],
               "support_cwe_id": support["cwe_id"], "expected_quote": support["quote"],
               "retrieved_support": support["passage_id"] in {c["passage_id"] for c in run["candidates"]},
               "query_seconds": run["timings"]["query_total_seconds"], "strategies": {}}
        for strategy, result in run["results"].items():
            row["strategies"][strategy] = {"selected_support": support["passage_id"] in result["selection"]["selected_order"],
                "answer": result["answer"]["text"], "answer_cwe_id": result["answer"]["source"]["cwe_id"],
                "exact_quote_match": result["answer"]["text"] == support["quote"]}
        summary.append(row)
    reload_path = output / "fresh-process.json"
    command = [sys.executable, "-m", "cyber_qa", "query", "--snapshot", args.snapshot,
        "--index", args.index, "--device", args.device, "--question", fixture["questions"][0]["question"],
        "--strategy", "both", "--output", str(reload_path)]
    completed = subprocess.run(command, capture_output=True, text=True)
    (output / "fresh-process.log").write_text(completed.stdout + completed.stderr)
    assert completed.returncode == 0, f"fresh process failed; see {output / 'fresh-process.log'}"
    reloaded = json.loads(reload_path.read_text())
    validate_run(reloaded, passages)
    for key in ("configuration_sha256", "question_input", "candidates", "results", "model_provenance", "weight_sha256"):
        equivalent(first[key], reloaded[key])
    assert first["index"]["vectors_sha256"] == reloaded["index"]["vectors_sha256"]
    report = {"status": "passed", "technical_end_to_end_verified": True,
        "semantic_accuracy_calibrated": False, "independent_human_review": False,
        "snapshot_id": fixture["snapshot_id"], "count": len(summary),
        "retrieved_support_count": sum(r["retrieved_support"] for r in summary),
        "selected_support_count": {s: sum(r["strategies"][s]["selected_support"] for r in summary) for s in ("reader_topk", "mmr")},
        "fresh_process_equivalent": True, "questions": summary}
    write_result(output / "summary.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
