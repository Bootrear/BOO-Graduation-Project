"""Gate evaluation: can MMR beat Reader Top-K on the probe set?

For every probe question this runs ONE shared retrieval + Reader pass, then compares
Reader Top-5 against iterative MMR on the same PreparedPool, and reports:

  Evidence Recall@5      fraction of required evidence selected (macro average)
  Full coverage          all required evidence selected
  Hit@5                  at least one required passage selected
  Selected-set redundancy mean pairwise cosine among the 5 chosen passages (lower = more diverse)
  Pool redundancy        mean pairwise cosine of all 20 candidates
  Retrieval ceiling      whether required evidence entered the candidate pool at all
  Strategy divergence    questions where the two ordered selections differ

Paired bootstrap gives a 95% CI for the Recall@5 difference (MMR - Top-K).

Usage:
  .venv\\Scripts\\python.exe scripts/eval_probe.py --index data/processed/dpr-index-v1 ^
      --snapshot data/processed/cwe-v1 --device cpu --out outputs/probe-eval.json
"""
from __future__ import annotations

import argparse
import json
import random
from dataclasses import replace
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cyber_qa.config import BaselineConfig  # noqa: E402
from cyber_qa.models import DPRRuntime  # noqa: E402
from cyber_qa.reader.dpr import DPRReaderScorer  # noqa: E402
from cyber_qa.retrieval.dpr import load_index  # noqa: E402
from cyber_qa.selection.mmr import prepare_pool, reader_topk, select_mmr  # noqa: E402

BOOTSTRAP = 2000
SEED = 20261123


def mean_pairwise(similarities, indices):
    values = []
    for a in range(len(indices)):
        for b in range(a + 1, len(indices)):
            values.append(similarities[indices[a]][indices[b]])
    return sum(values) / len(values) if values else None


def macro(values):
    return sum(values) / len(values) if values else None


def percentile_ci(diffs, seed=SEED, rounds=BOOTSTRAP, alpha=0.05):
    if not diffs:
        return None
    rng = random.Random(seed)
    n = len(diffs)
    stats = []
    for _ in range(rounds):
        stats.append(sum(diffs[rng.randrange(n)] for _ in range(n)) / n)
    stats.sort()
    lo = stats[int((alpha / 2) * rounds)]
    hi = stats[int((1 - alpha / 2) * rounds) - 1]
    below = sum(1 for value in stats if value <= 0) / rounds
    return {"mean": sum(diffs) / n, "ci95": [lo, hi], "p_not_better": below}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--qa", default="data/annotations/probe-v1/qa.v1.jsonl")
    parser.add_argument("--snapshot", default="data/processed/cwe-v1")
    parser.add_argument("--index", default="data/processed/dpr-index-v1")
    parser.add_argument("--config", default="configs/baseline.v1.json")
    parser.add_argument("--n", type=int, default=None,
                        help="覆盖 candidate_count（扫 N 用，不改配置文件）")
    parser.add_argument("--lam", type=float, default=None,
                        help="覆盖 lambda_weight（扫 λ 用，不改配置文件）")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--out", default="outputs/probe-eval.json")
    args = parser.parse_args()

    questions = [json.loads(l) for l in Path(args.qa).open(encoding="utf-8") if l.strip()]
    config = BaselineConfig.load(args.config)
    if args.n is not None or args.lam is not None:
        changes = {}
        if args.n is not None:
            changes["candidate_count"] = args.n
        if args.lam is not None:
            changes["lambda_weight"] = args.lam
        config = replace(config, **changes)
        print(f"运行期覆盖（不改配置文件）：{changes}", flush=True)
    print(f"加载模型/索引（device={args.device}, N={config.candidate_count}, "
          f"K={config.max_passages}, λ={config.lambda_weight}）…", flush=True)
    started = time.perf_counter()
    runtime = DPRRuntime(device=args.device, model_config="configs/dpr-models.v1.json",
                         model_root="models/dpr")
    index = load_index(args.index, args.snapshot, runtime)
    scorer = DPRReaderScorer(runtime)
    print(f"加载完成 {time.perf_counter() - started:.1f}s", flush=True)

    rows = []
    for order, question in enumerate(questions, 1):
        tick = time.perf_counter()
        qid = question["question_id"]
        gold = set(question["required_evidence_ids"])
        optional = set(question.get("optional_evidence_ids") or [])
        vector = runtime.encode_question(question["question"])
        candidates = index.search(vector, n=config.candidate_count)
        reader = scorer.score(question["question"], candidates, batch_size=args.batch_size)
        pool = prepare_pool(reader.candidates, config)
        topk = reader_topk(pool, config)
        mmr = select_mmr(pool, config)

        pool_ids = [c.passage_id for c in pool.candidates]
        position = {pid: i for i, pid in enumerate(pool_ids)}
        topk_set, mmr_set = set(topk.selected_order), set(mmr.selected_order)
        all_cos = mean_pairwise(pool.similarities, list(range(len(pool_ids))))

        def selected_cos(selected):
            idx = [position[pid] for pid in selected if pid in position]
            return mean_pairwise(pool.similarities, idx)

        row = {
            "question_id": qid,
            "intent": question.get("intent"),
            "cwe_id": question["record_ids"][0],
            "required_evidence_ids": sorted(gold),
            "optional_evidence_ids": sorted(optional),
            "pool_ids": pool_ids,
            "topk_order": list(topk.selected_order),
            "mmr_order": list(mmr.selected_order),
            "reader_ranking": [
                {"passage_id": c.passage_id,
                 "is_gold": c.passage_id in gold,
                 "reader_logit": c.reader_relevance_logit,
                 "reader_normalized": c.reader_relevance_normalized}
                for c in sorted(pool.candidates,
                                key=lambda c: -c.reader_relevance_logit)
            ],
            "retrieval": {
                "gold_in_pool": sorted(gold & set(pool_ids)),
                "gold_recall_in_pool": len(gold & set(pool_ids)) / len(gold),
                "optional_in_pool": sorted(optional & set(pool_ids)),
            },
            "evidence_recall_5": {
                "reader_topk": len(topk_set & gold) / len(gold),
                "mmr": len(mmr_set & gold) / len(gold),
            },
            "full_coverage": {
                "reader_topk": gold <= topk_set,
                "mmr": gold <= mmr_set,
            },
            "hit_5": {"reader_topk": bool(topk_set & gold), "mmr": bool(mmr_set & gold)},
            "redundancy": {
                "pool_mean_pairwise": all_cos,
                "reader_topk_selected": selected_cos(topk.selected_order),
                "mmr_selected": selected_cos(mmr.selected_order),
            },
            "order_differs": list(topk.selected_order) != list(mmr.selected_order),
            "set_differs": topk_set != mmr_set,
            "seconds": time.perf_counter() - tick,
        }
        rows.append(row)
        print(f"  [{order:02d}/{len(questions)}] {qid} {row['cwe_id']:<9s} "
              f"pool_gold={row['retrieval']['gold_recall_in_pool']:.2f} "
              f"R@5 topk={row['evidence_recall_5']['reader_topk']:.2f} "
              f"mmr={row['evidence_recall_5']['mmr']:.2f} "
              f"diff={row['order_differs']} {row['seconds']:.1f}s", flush=True)

    def values(strategy):
        return [row["evidence_recall_5"][strategy] for row in rows]

    def gold_ranks(row):
        gold = set(row["required_evidence_ids"])
        ranks = []
        for position, item in enumerate(row["reader_ranking"], 1):
            if item["is_gold"]:
                ranks.append(position)
        return ranks, gold

    in_pool_complete = [r for r in rows if r["retrieval"]["gold_recall_in_pool"] == 1.0]
    gold_rank_all = []
    for row in rows:
        ranks, _ = gold_ranks(row)
        gold_rank_all.extend(ranks)

    diffs = [row["evidence_recall_5"]["mmr"] - row["evidence_recall_5"]["reader_topk"] for row in rows]
    summary = {
        "questions": len(rows),
        "config": config.to_dict(),
        "overrides": {"n": args.n, "lam": args.lam},
        "evidence_recall_5": {"reader_topk": macro(values("reader_topk")),
                              "mmr": macro(values("mmr")),
                              "paired_diff": percentile_ci(diffs)},
        "per_question_outcome": {
            "mmr_better": sum(1 for d in diffs if d > 0),
            "mmr_worse": sum(1 for d in diffs if d < 0),
            "tie": sum(1 for d in diffs if d == 0),
        },
        "gold_reader_rank": {
            "mean": macro(gold_rank_all),
            "median": sorted(gold_rank_all)[len(gold_rank_all) // 2] if gold_rank_all else None,
            "top5": sum(1 for r in gold_rank_all if r <= 5),
            "total": len(gold_rank_all),
        },
        "on_questions_with_full_gold_in_pool": {
            "n": len(in_pool_complete),
            "recall_5_topk": macro([r["evidence_recall_5"]["reader_topk"] for r in in_pool_complete]),
            "recall_5_mmr": macro([r["evidence_recall_5"]["mmr"] for r in in_pool_complete]),
        },
        "full_coverage_rate": macro([float(r["full_coverage"]["reader_topk"]) for r in rows]),
        "full_coverage_rate_mmr": macro([float(r["full_coverage"]["mmr"]) for r in rows]),
        "hit_5_rate": macro([float(r["hit_5"]["reader_topk"]) for r in rows]),
        "hit_5_rate_mmr": macro([float(r["hit_5"]["mmr"]) for r in rows]),
        "retrieval_ceiling": macro([r["retrieval"]["gold_recall_in_pool"] for r in rows]),
        "pool_mean_pairwise": macro([r["redundancy"]["pool_mean_pairwise"] for r in rows
                                     if r["redundancy"]["pool_mean_pairwise"] is not None]),
        "selected_pairwise": {
            "reader_topk": macro([r["redundancy"]["reader_topk_selected"] for r in rows
                                  if r["redundancy"]["reader_topk_selected"] is not None]),
            "mmr": macro([r["redundancy"]["mmr_selected"] for r in rows
                          if r["redundancy"]["mmr_selected"] is not None]),
        },
        "strategy_divergence": {
            "order_differs": sum(1 for r in rows if r["order_differs"]),
            "set_differs": sum(1 for r in rows if r["set_differs"]),
        },
        "by_intent": {},
        "total_seconds": sum(r["seconds"] for r in rows),
    }
    for intent in sorted({r["intent"] or "unknown" for r in rows}):
        group = [r for r in rows if (r["intent"] or "unknown") == intent]
        summary["by_intent"][intent] = {
            "n": len(group),
            "recall_5_topk": macro([r["evidence_recall_5"]["reader_topk"] for r in group]),
            "recall_5_mmr": macro([r["evidence_recall_5"]["mmr"] for r in group]),
            "order_differs": sum(1 for r in group if r["order_differs"]),
        }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")

    print("\n================ 门禁结果 ================")
    print(f"题目数                {summary['questions']}")
    print(f"检索天花板            {summary['retrieval_ceiling']:.3f}  （必选证据进入 N=20 候选池的比例）")
    print(f"Evidence Recall@5     Top-K {summary['evidence_recall_5']['reader_topk']:.3f} | "
          f"MMR {summary['evidence_recall_5']['mmr']:.3f}")
    diff = summary["evidence_recall_5"]["paired_diff"]
    print(f"配对差值 (MMR-TopK)   {diff['mean']:+.3f}  95%CI [{diff['ci95'][0]:+.3f}, {diff['ci95'][1]:+.3f}]  "
          f"P(差值<=0)={diff['p_not_better']:.3f}")
    print(f"全覆盖率              Top-K {summary['full_coverage_rate']:.3f} | MMR {summary['full_coverage_rate_mmr']:.3f}")
    print(f"Hit@5                 Top-K {summary['hit_5_rate']:.3f} | MMR {summary['hit_5_rate_mmr']:.3f}")
    print(f"池内平均两两余弦      {summary['pool_mean_pairwise']:.3f}")
    print(f"选中 5 段平均余弦     Top-K {summary['selected_pairwise']['reader_topk']:.3f} | "
          f"MMR {summary['selected_pairwise']['mmr']:.3f}")
    print(f"策略分歧              order {summary['strategy_divergence']['order_differs']}/{len(rows)} | "
          f"set {summary['strategy_divergence']['set_differs']}/{len(rows)}")
    outcome = summary["per_question_outcome"]
    print(f"逐题胜负              MMR 更好 {outcome['mmr_better']} | 更差 {outcome['mmr_worse']} | 平 {outcome['tie']}")
    rank = summary["gold_reader_rank"]
    print(f"正确段 Reader 排名    mean {rank['mean']:.1f} (median {rank['median']}) | "
          f"进前5的 {rank['top5']}/{rank['total']}")
    full = summary["on_questions_with_full_gold_in_pool"]
    print(f"仅看必选证据全部入池  n={full['n']} | Top-K {full['recall_5_topk']:.3f} | MMR {full['recall_5_mmr']:.3f}")
    print(f"\n完整结果 -> {out}")
    print(f"总耗时 {summary['total_seconds']:.1f}s")


if __name__ == "__main__":
    main()
