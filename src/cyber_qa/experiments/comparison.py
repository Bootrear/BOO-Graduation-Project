"""Shared, annotation-aware evaluation outside the retrieval interfaces."""
from __future__ import annotations

from dataclasses import asdict
import random
import time

from cyber_qa.answering.ordinary import assemble_answer
from cyber_qa.evaluation.metrics import evidence_precision, evidence_recall
from cyber_qa.selection.mmr import prepare_pool, reader_topk, select_mmr

SEED = 20261123


def mean(values):
    return sum(values) / len(values) if values else None


def paired_difference(differences, rounds=2000):
    """Paired question-level percentile bootstrap; not a formal p-value."""
    if not differences:
        return None
    rng = random.Random(SEED)
    samples = sorted(mean([rng.choice(differences) for _ in differences]) for _ in range(rounds))
    return {"mean": mean(differences), "ci95": [samples[int(.025 * rounds)], samples[int(.975 * rounds) - 1]],
            "wins": sum(x > 0 for x in differences), "losses": sum(x < 0 for x in differences),
            "ties": sum(x == 0 for x in differences), "rounds": rounds, "seed": SEED}


def validate_questions(questions, passages):
    if not questions:
        raise ValueError("empty evaluation set")
    corpus_ids = {p.passage_id for p in passages}
    seen = set()
    for q in questions:
        qid = q["question_id"]
        if not isinstance(qid, str) or not qid.strip() or qid in seen:
            raise ValueError("question IDs must be nonempty and unique")
        seen.add(qid)
        if not isinstance(q["question"], str) or not q["question"].strip():
            raise ValueError(f"empty question: {qid}")
        gold = q["required_evidence_ids"]
        optional = q.get("optional_evidence_ids") or []
        if not gold or len(set(gold)) != len(gold) or not set(gold + optional) <= corpus_ids:
            raise ValueError(f"missing/duplicate gold or unknown passage IDs: {qid}")
        for fact in q.get("gold_facts", []):
            support = fact.get("supported_by", [])
            if not support or not set(support) <= set(gold + optional):
                raise ValueError(f"invalid fact support: {qid}")


def evidence_metrics(selected, question):
    selected, gold = set(selected), set(question["required_evidence_ids"])
    facts = question.get("gold_facts", [])
    return {"recall": evidence_recall(selected, gold),
            "gold_id_precision": evidence_precision(selected, gold),
            "full_coverage": float(gold <= selected), "hit": float(bool(gold & selected)),
            "gold_selected": len(gold & selected), "gold_total": len(gold),
            # This is availability of annotated support, NOT semantic answer grading.
            "annotated_fact_support": mean([float(bool(selected & set(f["supported_by"]))) for f in facts])}


def pairwise_similarity(pool, selected):
    indices = {c.passage_id: i for i, c in enumerate(pool.candidates)}
    return mean([pool.similarities[indices[a]][indices[b]]
                 for i, a in enumerate(selected) for b in selected[i + 1:]])


def evaluate_question(question, retriever, scorer, config, method, batch_size=8):
    started = time.perf_counter()
    row = {"question_id": question["question_id"], "question": question["question"],
           "intent": question.get("intent", "unknown"),
           "question_type": "multi" if len(question["required_evidence_ids"]) > 1 else "single",
           "required_evidence_ids": question["required_evidence_ids"],
           "annotation_status": question.get("status", "unknown"), "status": "running", "timings": {}}
    stage = "retrieval"
    try:
        tick = time.perf_counter()
        retrieved = retriever.retrieve(question["question"], method=method, n=config.candidate_count)
        row["timings"]["retrieval_seconds"] = time.perf_counter() - tick
        ids = [c.passage_id for c in retrieved.candidates]
        if len(ids) > config.candidate_count or len(set(ids)) != len(ids):
            raise ValueError("retrieval returned duplicate IDs or exceeded N")
        row.update(pool_ids=ids, retrieval_trace=retrieved.trace,
                   retrieval=evidence_metrics(ids, question), candidate_count=len(ids))
        stage = "reader"
        tick = time.perf_counter()
        reader = scorer.score(question["question"], retrieved.candidates, batch_size=batch_size)
        row["timings"]["reader_seconds"] = time.perf_counter() - tick
        stage = "selection_and_answer"
        tick = time.perf_counter()
        pool = prepare_pool(reader.candidates, config)
        row["candidates"] = [{"passage_id": c.passage_id, "cwe_id": c.passage.cwe_id,
            "field_name": c.passage.field_name, "text": c.passage.text, "source_url": c.passage.source_url,
            "source_locator": c.passage.source_locator, "retrieval_rank": c.retrieval_rank,
            "retrieval_score": c.retrieval_score, "reader_logit": c.reader_relevance_logit,
            "reader_normalized": c.reader_relevance_normalized,
            "answer_span": asdict(c.answer_span) if c.answer_span else None,
            "answer_span_reason": c.answer_span_reason} for c in pool.candidates]
        row["pool_mean_pairwise"] = pairwise_similarity(pool, ids)
        row["results"] = {}
        for name, select in (("reader_topk", reader_topk), ("mmr", select_mmr)):
            selection = select(pool, config)
            selected = list(selection.selected_order)
            row["results"][name] = {"selected_order": selected, "metrics": evidence_metrics(selected, question),
                "mean_pairwise": pairwise_similarity(pool, selected),
                "steps": [asdict(step) for step in selection.steps],
                "answer": assemble_answer(selection, len(ids), config).to_dict()}
        row["timings"]["selection_and_answer_seconds"] = time.perf_counter() - tick
        row["status"] = "success"
    except Exception as exc:
        row["status"] = "failed"
        row["results"] = {}
        row["error"] = {"stage": stage, "type": type(exc).__name__, "message": str(exc)}
    row["timings"]["total_seconds"] = time.perf_counter() - started
    return row


def metric_at(row, path):
    # Conservatively count a failed query as zero, retaining it in the denominator.
    if row["status"] != "success":
        return 0.0
    result = row
    for part in path.split("."):
        result = result[part]
    return result


def summarize(rows):
    successful = [r for r in rows if r["status"] == "success"]
    summary = {"questions": len(rows), "succeeded": len(successful), "failed": len(rows) - len(successful),
               "comparison_valid": len(rows) == len(successful),
               "failure_policy": "zero_credit_all_questions_denominator; no_CI_if_any_failure",
               "answer_quality": "not_assessed", "retrieval": {}, "selection": {}}
    for label, prefix in (("retrieval", "retrieval"), ("reader_topk", "results.reader_topk.metrics"),
                          ("mmr", "results.mmr.metrics")):
        metrics = {name: mean([metric_at(r, prefix + "." + name) for r in rows])
                   for name in ("recall", "full_coverage", "hit", "gold_id_precision")}
        support = [metric_at(r, prefix + ".annotated_fact_support") for r in rows]
        metrics["annotated_fact_support"] = mean([s for s in support if s is not None])
        metrics["gold_selected"] = sum(metric_at(r, prefix + ".gold_selected") for r in rows)
        metrics["gold_total"] = sum(len(r["required_evidence_ids"]) for r in rows)
        metrics["micro_recall"] = metrics["gold_selected"] / metrics["gold_total"]
        if label == "retrieval":
            summary[label] = metrics
        else:
            metrics["mean_pairwise"] = mean([r["results"][label]["mean_pairwise"] for r in successful
                                             if r["results"][label]["mean_pairwise"] is not None])
            summary["selection"][label] = metrics
    summary["timings"] = {key: sum(r["timings"].get(key, 0) for r in rows)
                          for key in ("retrieval_seconds", "reader_seconds", "selection_and_answer_seconds", "total_seconds")}
    summary["timings"]["mean_question_seconds"] = summary["timings"]["total_seconds"] / len(rows)
    summary["mmr_minus_topk"] = paired_difference([
        metric_at(r, "results.mmr.metrics.recall") - metric_at(r, "results.reader_topk.metrics.recall")
        for r in rows]) if summary["comparison_valid"] else None
    summary["set_differs"] = sum(set(r["results"]["reader_topk"]["selected_order"]) !=
                                  set(r["results"]["mmr"]["selected_order"]) for r in successful)
    summary["by_group"] = {}
    for field in ("question_type", "intent"):
        summary["by_group"][field] = {}
        for value in sorted({r[field] or "unknown" for r in rows}):
            group = [r for r in rows if (r[field] or "unknown") == value]
            summary["by_group"][field][value] = {"questions": len(group),
                "retrieval_recall": mean([metric_at(r, "retrieval.recall") for r in group]),
                **{name: mean([metric_at(r, f"results.{name}.metrics.recall") for r in group])
                   for name in ("reader_topk", "mmr")}}
    return summary


def compare_to_baseline(rows, baseline):
    if [r["question_id"] for r in rows] != [r["question_id"] for r in baseline]:
        raise ValueError("paired comparison question order mismatch")
    if any(r["status"] != "success" for r in rows + baseline):
        return {"valid": False, "reason": "query_failure"}
    paths = {"retrieval_recall": "retrieval.recall", "reader_topk_recall": "results.reader_topk.metrics.recall",
             "mmr_recall": "results.mmr.metrics.recall"}
    return {"valid": True, **{name: paired_difference([metric_at(r, path) - metric_at(b, path)
            for r, b in zip(rows, baseline)]) for name, path in paths.items()}}


def historical_check(rows, historic):
    """Numerical replay check, not proof of historical question/model provenance."""
    old = {r["question_id"]: r for r in historic["rows"]}
    result = {"scope": "IDs, pools and selections, plus Reader logit comparison; historic question/model hashes unavailable",
              "questions": len(rows), "mismatched_questions": [], "max_reader_logit_delta": 0.0,
              "reader_logits_match_within_1e-6": True}
    if set(old) != {r["question_id"] for r in rows}:
        return {**result, "status": "not_comparable", "reason": "question_ids_differ"}
    for row in rows:
        previous = old[row["question_id"]]
        if row["status"] != "success":
            result["mismatched_questions"].append(row["question_id"])
            continue
        matches = (set(row["required_evidence_ids"]) == set(previous["required_evidence_ids"])
                   and row["pool_ids"] == previous["pool_ids"])
        for name, old_key in (("reader_topk", "topk_order"), ("mmr", "mmr_order")):
            matches &= row["results"][name]["selected_order"] == previous[old_key]
        logits = {c["passage_id"]: c["reader_logit"] for c in previous["reader_ranking"]}
        for c in row["candidates"]:
            if c["passage_id"] in logits:
                delta = abs(c["reader_logit"] - logits[c["passage_id"]])
                result["max_reader_logit_delta"] = max(result["max_reader_logit_delta"], delta)
                if delta > 1e-6:
                    result["reader_logits_match_within_1e-6"] = False
        if not matches:
            result["mismatched_questions"].append(row["question_id"])
    result["structure_status"] = "matched" if not result["mismatched_questions"] else "different"
    result["status"] = "matched" if result["structure_status"] == "matched" and result["reader_logits_match_within_1e-6"] else "different"
    return result
