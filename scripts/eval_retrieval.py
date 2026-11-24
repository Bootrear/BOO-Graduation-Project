"""Retrieval-only diagnosis: where does the required evidence actually rank?

No Reader is involved, so this isolates the retrieval ceiling from the ranking step.
For each probe question it encodes the question, scores all 5748 passages, and reports
the rank of every required passage plus Recall@N for a grid of N.

Usage:
  .venv\\Scripts\\python.exe scripts/eval_retrieval.py --device cpu ^
      --index data/processed/dpr-index-v1 --snapshot data/processed/cwe-v1 ^
      --out outputs/probe-retrieval.json
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cyber_qa.models import DPRRuntime  # noqa: E402
from cyber_qa.retrieval.dpr import load_index  # noqa: E402

GRID = (5, 10, 20, 50, 100, 200)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--qa", default="data/annotations/probe-v1/qa.v1.jsonl")
    parser.add_argument("--snapshot", default="data/processed/cwe-v1")
    parser.add_argument("--index", default="data/processed/dpr-index-v1")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--out", default="outputs/probe-retrieval.json")
    parser.add_argument("--depth", type=int, default=max(GRID))
    args = parser.parse_args()

    questions = [json.loads(l) for l in Path(args.qa).open(encoding="utf-8") if l.strip()]
    runtime = DPRRuntime(device=args.device, model_config="configs/dpr-models.v1.json",
                         model_root="models/dpr")
    index = load_index(args.index, args.snapshot, runtime)
    print(f"索引 {args.index}，问题 {len(questions)} 道", flush=True)

    rows = []
    for question in questions:
        gold = set(question["required_evidence_ids"])
        vector = runtime.encode_question(question["question"])
        hits = index.search(vector, n=args.depth)
        order = [c.passage_id for c in hits]
        ranks = {pid: order.index(pid) + 1 for pid in gold if pid in order}
        missing = sorted(gold - set(order))
        rows.append({
            "question_id": question["question_id"],
            "cwe_id": question["record_ids"][0],
            "intent": question.get("intent"),
            "gold_count": len(gold),
            "gold_ranks": ranks,
            "gold_never_found": missing,
            "found_in_depth": len(ranks),
        })
        shown = {pid[:12]: rank for pid, rank in ranks.items()}
        print(f"  {question['question_id']} {question['record_ids'][0]:<9s} "
              f"ranks={shown} missing={len(missing)}", flush=True)

    def recall_at(n):
        total = 0.0
        for row in rows:
            found = sum(1 for rank in row["gold_ranks"].values() if rank <= n)
            total += found / row["gold_count"]
        return total / len(rows)

    all_ranks = [rank for row in rows for rank in row["gold_ranks"].values()]
    all_ranks_sorted = sorted(all_ranks)
    summary = {
        "questions": len(rows),
        "index": args.index,
        "recall_at": {f"recall@{n}": recall_at(n) for n in GRID},
        "gold_rank": {
            "count": len(all_ranks),
            "mean": sum(all_ranks) / len(all_ranks) if all_ranks else None,
            "median": all_ranks_sorted[len(all_ranks_sorted) // 2] if all_ranks else None,
            "min": all_ranks_sorted[0] if all_ranks else None,
            "max": all_ranks_sorted[-1] if all_ranks else None,
            "within_20": sum(1 for r in all_ranks if r <= 20),
            "within_100": sum(1 for r in all_ranks if r <= 100),
            "beyond_200": sum(1 for r in all_ranks if r > 200),
            "never_in_top_depth": sum(len(row["gold_never_found"]) for row in rows),
        },
        "questions_with_any_gold_in_top20": sum(
            1 for row in rows if any(rank <= 20 for rank in row["gold_ranks"].values())),
        "questions_with_all_gold_in_top20": sum(
            1 for row in rows if row["found_in_depth"] >= row["gold_count"]
            and all(rank <= 20 for rank in row["gold_ranks"].values())),
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")

    print("\n============ 检索诊断 ============")
    for n in GRID:
        print(f"  Recall@{n:<4d} {recall_at(n):.3f}")
    stat = summary["gold_rank"]
    print(f"正确段排名  mean {stat['mean']:.0f} | median {stat['median']} | "
          f"{stat['min']}–{stat['max']}")
    print(f"  进前20 {stat['within_20']}/{stat['count']} | 进前100 {stat['within_100']}/{stat['count']} | "
          f"超200 {stat['beyond_200']}/{stat['count']}")
    print(f"至少一段进前20的题: {summary['questions_with_any_gold_in_top20']}/{len(rows)}")
    print(f"全部正确段进前20的题: {summary['questions_with_all_gold_in_top20']}/{len(rows)}")
    print(f"\n完整结果 -> {out}")


if __name__ == "__main__":
    main()
