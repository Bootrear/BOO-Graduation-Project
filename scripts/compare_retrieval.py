"""Run DPR, hybrid, subquery and hierarchical retrieval in that order.

Example: python scripts/compare_retrieval.py --device cuda
New output directory per run; never replaces the original probe-eval files.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from dataclasses import replace
from datetime import datetime, timezone
from importlib.metadata import version
import json
from pathlib import Path
import platform
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cyber_qa.__main__ import write_result
from cyber_qa.config import BaselineConfig
from cyber_qa.experiments.comparison import (compare_to_baseline, evaluate_question,
    historical_check, summarize, validate_questions)
from cyber_qa.experiments.retrieval import METHODS, ExperimentRetriever, RetrievalExperimentConfig
from cyber_qa.models import DPRRuntime, file_sha256
from cyber_qa.reader.dpr import DPRReaderScorer
from cyber_qa.retrieval.dpr import load_index


def git_output(*args):
    try:
        return subprocess.check_output(["git", *args], text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unavailable"


def write_comparison(output, runs, manifest):
    flat = []
    for run in runs:
        s = run["summary"]
        flat.append({"n": run["n"], "method": run["method"], "questions": s["questions"], "failed": s["failed"],
            "retrieval_recall": s["retrieval"]["recall"], "retrieval_full_coverage": s["retrieval"]["full_coverage"],
            "retrieval_hit": s["retrieval"]["hit"],
            "topk_recall": s["selection"]["reader_topk"]["recall"], "mmr_recall": s["selection"]["mmr"]["recall"],
            "topk_full_coverage": s["selection"]["reader_topk"]["full_coverage"],
            "mmr_full_coverage": s["selection"]["mmr"]["full_coverage"],
            "topk_fact_support": s["selection"]["reader_topk"]["annotated_fact_support"],
            "mmr_fact_support": s["selection"]["mmr"]["annotated_fact_support"],
            "topk_pairwise": s["selection"]["reader_topk"]["mean_pairwise"],
            "mmr_pairwise": s["selection"]["mmr"]["mean_pairwise"],
            "retrieval_seconds": s["timings"]["retrieval_seconds"],
            "mean_question_seconds": s["timings"]["mean_question_seconds"]})
    write_result(output / "comparison.json", {"status": manifest["status"], "runs": runs,
                 "metric_notes": manifest["metric_notes"], "manifest": "manifest.json"})
    if flat:
        with (output / "comparison.csv").open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(flat[0]))
            writer.writeheader()
            writer.writerows(flat)
    lines = ["# 检索四方案对照", "", f"运行状态：{manifest['status']}。标注状态：{manifest['annotation_status']}。",
        "", "固定同一题集、快照、N、K、λ、Reader；三个实验独立，不叠加。参数未调优。",
        "Recall 是按题宏平均。事实支持表示标注支持段已入选，不是答案正确率。失败题按零计入，存在失败时不计算配对区间。",
        "模型加载与 BM25 建表独立记录；耗时包含每种方法实际查询编码，不跨方法复用查询缓存，单次顺序运行不是稳定性能基准。", "",
        "| N | 方法 | Recall@N | 全证据入池 | Top-K Recall@K | MMR Recall@K | Top-K 全覆盖 | MMR 全覆盖 | 秒/题 | 失败 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for r in flat:
        lines.append(f"| {r['n']} | {r['method']} | {r['retrieval_recall']:.2%} | {r['retrieval_full_coverage']:.2%} | "
            f"{r['topk_recall']:.2%} | {r['mmr_recall']:.2%} | {r['topk_full_coverage']:.2%} | "
            f"{r['mmr_full_coverage']:.2%} | {r['mean_question_seconds']:.3f} | {r['failed']} |")
    lines.extend(["", "## 相对同 N 的 DPR：配对差值与 95% bootstrap 区间", "",
                  "| N | 方法 | Recall@N 差值 [区间] | Top-K 差值 [区间] | MMR 差值 [区间] |",
                  "| --- | --- | --- | --- | --- |"])
    for run in runs:
        if run["method"] == "dpr":
            continue
        delta = run["versus_dpr"]
        cells = []
        for key in ("retrieval_recall", "reader_topk_recall", "mmr_recall"):
            if not delta["valid"]:
                cells.append("无效：有失败题")
            else:
                item = delta[key]
                cells.append(f"{item['mean']:+.2%} [{item['ci95'][0]:+.2%}, {item['ci95'][1]:+.2%}]")
        lines.append(f"| {run['n']} | {run['method']} | " + " | ".join(cells) + " |")
    lines.extend(["", "分组指标、逐题胜负、MMR 相对 Top-K 的区间见 comparison.json；单题候选、子查询、条目定位、分数、MMR 轮次、普通答案见各方法 JSON。",
        "", "历史结果保存在 archived-baseline/；baseline_replay 只核对可观测数值，旧文件未保存问题文本/模型哈希，不能补造历史 provenance。"])
    (output / "comparison.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qa", default="data/annotations/probe-v1/qa.v1.jsonl")
    parser.add_argument("--snapshot", default="data/processed/cwe-v1")
    parser.add_argument("--index", default="data/processed/dpr-index-v1")
    parser.add_argument("--config", default="configs/baseline.v1.json")
    parser.add_argument("--device", default="auto")
    parser.add_argument("--model-config", default="configs/dpr-models.v1.json")
    parser.add_argument("--model-root", default="models/dpr")
    parser.add_argument("--n", nargs="+", type=int, default=[20, 50, 100])
    parser.add_argument("--lam", type=float, default=None)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--branch-depth", type=int, default=100)
    parser.add_argument("--rrf-k", type=int, default=60)
    parser.add_argument("--entry-top-m", type=int, default=3)
    parser.add_argument("--focused-fraction", type=float, default=.75)
    parser.add_argument("--baseline-dir", default="outputs", help="Read-only old probe-eval-N*.json directory")
    parser.add_argument("--output", help="New directory; defaults to outputs/retrieval-comparison-<UTC timestamp>")
    args = parser.parse_args(argv)
    if args.batch_size < 1 or any(n < 1 for n in args.n) or len(set(args.n)) != len(args.n):
        parser.error("batch-size and N must be positive; N values must be unique")
    config = BaselineConfig.load(args.config)
    if args.lam is not None:
        config = replace(config, lambda_weight=args.lam)
    experiment_config = RetrievalExperimentConfig(branch_depth=args.branch_depth, rrf_k=args.rrf_k,
        entry_top_m=args.entry_top_m, focused_fraction=args.focused_fraction)
    output = Path(args.output or ("outputs/retrieval-comparison-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")))
    # Refuse even an empty existing directory, so repeat runs cannot erase evidence.
    output.mkdir(parents=True, exist_ok=False)
    manifest = {"schema_version": "retrieval-comparison-v1", "status": "running",
        "started_at": datetime.now(timezone.utc).isoformat(), "arguments": vars(args), "output": str(output),
        "git_head": git_output("rev-parse", "HEAD"), "git_status": git_output("status", "--short"),
        "baseline_config": config.to_dict(), "experiment_config": experiment_config.to_dict(),
        "method_order": METHODS, "n_grid": args.n, "parameter_status": "untuned",
        "annotation_status": {}, "archived_baseline": {}, "completed_runs": [],
        "metric_notes": {"recall": "macro per question, exact required passage IDs",
            "gold_id_precision": "exact gold IDs, not judged semantic relevance",
            "annotated_fact_support": "fraction of facts with any annotated support selected; not answer correctness",
            "answer_quality": "not_assessed", "failures": "zero credit in aggregate; paired CI disabled",
            "statistics": "paired question bootstrap, 2000 rounds, no multiple-comparison correction"}}
    write_result(output / "manifest.json", manifest)
    runs = []
    try:
        questions = [json.loads(line) for line in Path(args.qa).read_text(encoding="utf-8").splitlines() if line.strip()]
        manifest["annotation_status"] = dict(Counter(q.get("status", "unknown") for q in questions))
        manifest["qa_sha256"] = file_sha256(args.qa)
        manifest["source_sha256"] = {str(p): file_sha256(p) for p in
            [Path(__file__), *sorted(Path("src/cyber_qa").rglob("*.py")), Path(args.config), Path(args.model_config)]}
        archive = output / "archived-baseline"
        archive.mkdir()
        for path in sorted(Path(args.baseline_dir).glob("probe-eval-N*.json")):
            (archive / path.name).write_bytes(path.read_bytes())
            manifest["archived_baseline"][path.name] = {"source": str(path), "sha256": file_sha256(path)}
        tick = time.perf_counter()
        runtime = DPRRuntime(device=args.device, model_config=args.model_config, model_root=args.model_root)
        index = load_index(args.index, args.snapshot, runtime)
        validate_questions(questions, index.passages)
        runtime.load_model("question")
        runtime.load_model("reader")
        manifest["startup_seconds"] = time.perf_counter() - tick
        manifest.update(index=index.metadata, model_provenance=runtime.provenance,
            weight_sha256=runtime.weight_hashes, model_loading_info=runtime.loading_info,
            input_budget=runtime.budget.to_dict(), device=runtime.device,
            environment={"python": platform.python_version(), "platform": platform.platform(),
                **{name: version(name) for name in ("torch", "transformers", "tokenizers", "numpy")}},
            hardware={"gpu": runtime.torch.cuda.get_device_name() if runtime.device.startswith("cuda") else None,
                      "torch_threads": runtime.torch.get_num_threads()})
        tick = time.perf_counter()
        retriever = ExperimentRetriever(runtime, index, experiment_config)
        manifest["lexical_index_build_seconds"] = time.perf_counter() - tick
        scorer = DPRReaderScorer(runtime)
        write_result(output / "manifest.json", manifest)
        for n in args.n:
            current_config = replace(config, candidate_count=n)
            baseline_rows = None
            for method in METHODS:
                print(f"\nN={n} method={method} ({len(questions)} questions)", flush=True)
                rows = []
                stem = f"{method}-N{n}"
                with (output / (stem + ".jsonl")).open("x", encoding="utf-8") as stream:
                    for i, q in enumerate(questions, 1):
                        row = evaluate_question(q, retriever, scorer, current_config, method, args.batch_size)
                        rows.append(row)
                        stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
                        stream.flush()
                        print(f"  [{i:02}/{len(questions)}] {q['question_id']} {row['status']} "
                              f"Recall@N={row.get('retrieval', {}).get('recall', 0):.3f}", flush=True)
                summary = summarize(rows)
                run = {"method": method, "n": n, "summary": summary, "artifact": stem + ".json"}
                if method == "dpr":
                    baseline_rows = rows
                    prior = archive / f"probe-eval-N{n}.json"
                    run["baseline_replay"] = historical_check(rows, json.loads(prior.read_text(encoding="utf-8"))) if prior.exists() else {"status": "not_available"}
                run["versus_dpr"] = compare_to_baseline(rows, baseline_rows)
                write_result(output / run["artifact"], {**run, "configuration": current_config.to_dict(), "rows": rows})
                runs.append(run)
                manifest["completed_runs"].append(stem)
                write_result(output / "manifest.json", manifest)
                write_comparison(output, runs, manifest)
        manifest["status"] = "completed_with_failures" if any(r["summary"]["failed"] for r in runs) else "completed"
    except Exception as exc:
        manifest["status"] = "failed"
        manifest["error"] = {"type": type(exc).__name__, "message": str(exc)}
        print(f"Failed: {type(exc).__name__}: {exc}", file=sys.stderr)
    finally:
        manifest["finished_at"] = datetime.now(timezone.utc).isoformat()
        write_result(output / "manifest.json", manifest)
        write_comparison(output, runs, manifest)
    print(f"\n{manifest['status']}: {output / 'comparison.md'}", flush=True)
    return 0 if manifest["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
