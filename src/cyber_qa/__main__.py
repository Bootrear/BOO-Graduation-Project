"""Unified reproducible baseline CLI: python -m cyber_qa --help."""

import argparse
import json
from pathlib import Path
import sys
import tempfile
import time


def write_result(path, result):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Serialize before opening a temporary file: NaN/Inf cannot become JSON artifacts.
    content = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    with tempfile.TemporaryDirectory(prefix=".result-", dir=path.parent) as temp:
        staged = Path(temp) / "result.json"
        staged.write_text(content, encoding="utf-8")
        staged.replace(path)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Fixed CWE / DPR / Reader / Top-K or MMR ordinary QA")
    commands = parser.add_subparsers(dest="command", required=True)
    preprocess = commands.add_parser("preprocess", help="Build a deterministic CWE snapshot")
    preprocess.add_argument("--raw", required=True)
    preprocess.add_argument("--receipt")
    build = commands.add_parser("build-index", help="Encode and save an exact raw-inner-product index")
    build.add_argument("--snapshot", required=True)
    build.add_argument("--batch-size", type=int, default=32)
    query = commands.add_parser("query", help="Load a compatible index and save a structured query result")
    query.add_argument("--snapshot", default="data/processed/cwe-v1")
    query.add_argument("--index", default="data/processed/dpr-index-v1")
    query.add_argument("--question", required=True)
    query.add_argument("--strategy", choices=("reader_topk", "mmr", "both"), default="mmr")
    query.add_argument("--batch-size", type=int, default=8)
    query.add_argument("--config", default="configs/baseline.v1.json")
    for command in (preprocess, build, query):
        command.add_argument("--output", required=True, help="Artifact directory, or JSON file for query")
        command.add_argument("--model-config", default="configs/dpr-models.v1.json")
        command.add_argument("--model-root", default="models/dpr")
    for command in (build, query):
        command.add_argument("--device", default="auto")
    args = parser.parse_args(argv)
    try:
        if args.command == "preprocess":
            from cyber_qa.data.preprocess import build_snapshot
            started = time.perf_counter()
            manifest, stats = build_snapshot(args.raw, args.output, receipt_path=args.receipt,
                model_config=args.model_config, model_root=args.model_root)
            result = {"status": "success", "snapshot_id": manifest.snapshot_id, "statistics": stats,
                      "offline_preprocessing_seconds": time.perf_counter() - started}
        elif args.command == "build-index":
            from cyber_qa.models import DPRRuntime
            from cyber_qa.retrieval.dpr import build_index
            runtime = DPRRuntime(device=args.device, model_config=args.model_config, model_root=args.model_root)
            result = build_index(args.snapshot, args.output, runtime, batch_size=args.batch_size)
        else:
            from cyber_qa.config import BaselineConfig
            from cyber_qa.pipeline.ordinary import QAPipeline
            pipeline = QAPipeline.load(args.index, args.snapshot, config=BaselineConfig.load(args.config),
                device=args.device, model_config=args.model_config, model_root=args.model_root)
            result = pipeline.query(args.question, strategy=args.strategy, batch_size=args.batch_size)
    except Exception as exc:
        result = {"schema_version": "ordinary-run-v1", "status": "failed",
                  "error": {"stage": args.command + "_initialization", "type": type(exc).__name__, "message": str(exc)}}
        if args.command == "query":
            from cyber_qa.answering.ordinary import failed_answer
            result["question"] = args.question
            result["failure_answer"] = failed_answer(f"query_initialization: {type(exc).__name__}: {exc}").to_dict()
    if args.command == "query":
        try:
            write_result(args.output, result)
        except Exception as exc:
            print(json.dumps({"status": "failed", "error": {"stage": "output_write", "type": type(exc).__name__,
                              "message": str(exc)}}, ensure_ascii=False), file=sys.stderr)
            return 1
        summary = {"status": result["status"], "output": args.output, "error": result.get("error"),
                   "answers": {key: value["answer"] for key, value in result.get("results", {}).items()}}
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result.get("status") == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
