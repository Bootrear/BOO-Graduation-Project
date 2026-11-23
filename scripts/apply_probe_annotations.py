"""Merge the drafted questions and gold facts into probe-v1/qa.v1.jsonl.

Reads:
  data/annotations/probe-v1/skeleton.jsonl     machine scaffold (candidate pools)
  data/annotations/probe-v1/passage_index.json candidate metadata
  data/annotations/probe-v1/draft.v1.json      drafted question / evidence / facts
  outputs/probe_fulltext.jsonl                 original passage text (for answer_span)

Writes:
  data/annotations/probe-v1/qa.v1.jsonl        annotated dataset (no scaffold)
  data/annotations/probe-v1/manifest.json      refreshed hashes + annotation record

Validation is strict on purpose: a bad draft must fail loudly rather than produce a
dataset that silently scores the wrong thing.

Usage: py scripts/apply_probe_annotations.py
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cyber_qa.data.cwe import parse_cwe  # noqa: E402

STATUS = "auto_drafted_needs_human_review"
ANNOTATOR = "deepseek-auto-draft"
SNAPSHOT = "cwe:88e4eab3cc54f16611040a0e528d7a128253426e90ee5054327fd28449fee393"
KEEP = ("question_id", "question", "language", "split", "intent", "record_ids",
        "answer_type", "required_evidence_ids", "optional_evidence_ids",
        "gold_facts", "answer_variants", "answer_span", "source_snapshot",
        "annotator", "reviewer", "status")


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def stable_hash(value):
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False,
                         separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def load_texts(zip_path, snapshot):
    """Rebuild passage_id -> source text without any model or cached artifact."""
    texts = {}
    for unit in parse_cwe(zip_path).units:
        content = hashlib.sha256(unit.source_text.encode("utf-8")).hexdigest()
        pid = "cwe-passage:" + stable_hash({
            "snapshot_id": snapshot, "cwe_id": unit.cwe_id,
            "source_locator": unit.source_locator, "field_name": unit.field_name,
            "chunk_index": 0, "content_sha256": content,
        })
        texts[pid] = unit.source_text
    return texts


def locate(text, quote):
    """Whitespace-tolerant search; returns (start, end) offsets into text."""
    pattern = r"\s+".join(re.escape(part) for part in quote.split())
    match = re.search(pattern, text)
    return (match.start(), match.end()) if match else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", default="data/annotations/probe-v1")
    parser.add_argument("--zip", default="data/raw/cwe/cwec_v4.20.xml.zip")
    args = parser.parse_args()

    base = Path(args.dir)
    skeleton = [json.loads(l) for l in (base / "skeleton.jsonl").open(encoding="utf-8") if l.strip()]
    draft = json.loads((base / "draft.v1.json").read_text(encoding="utf-8"))
    if draft.get("review_status") != STATUS:
        print(f"draft review_status must be {STATUS}", file=sys.stderr)
        return 2

    texts = load_texts(args.zip, SNAPSHOT)

    problems, out = [], []
    for record in skeleton:
        qid = record["question_id"]
        entry = draft["questions"].get(qid)
        if entry is None:
            problems.append(f"{qid}: draft missing")
            continue
        pool = set(record["scaffold"]["candidate_pool"])
        required = entry.get("required", [])
        optional = entry.get("optional", [])
        facts = entry.get("facts", [])
        question = entry.get("question", "").strip()

        if not question or not question.endswith("?"):
            problems.append(f"{qid}: question must be non-empty and end with '?'")
        if record["answer_type"] == "single_span":
            if len(required) != 1:
                problems.append(f"{qid}: single_span needs exactly 1 required id, got {len(required)}")
        elif not 2 <= len(required) <= 3:
            problems.append(f"{qid}: required must have 2-3 ids, got {len(required)}")
        if len(set(required)) != len(required):
            problems.append(f"{qid}: duplicate required ids")
        for pid in required + optional:
            if pid not in pool:
                problems.append(f"{qid}: {pid} not in candidate_pool")
        allowed = set(required) | set(optional)
        for fact in facts:
            if not fact.get("text", "").strip():
                problems.append(f"{qid}/{fact.get('id')}: empty fact text")
            for pid in fact.get("support", []):
                if pid not in allowed:
                    problems.append(f"{qid}/{fact.get('id')}: support {pid} not in required/optional")

        distinct = {pid for fact in facts for pid in fact.get("support", [])}
        if record["answer_type"] == "multi_passage":
            if not 2 <= len(facts) <= 3:
                problems.append(f"{qid}: multi_passage needs 2-3 facts, got {len(facts)}")
            if not distinct >= set(required):
                problems.append(f"{qid}: facts do not cover every required passage")
        else:
            if len(facts) != 1:
                problems.append(f"{qid}: single_span needs exactly 1 fact, got {len(facts)}")

        answer_span = None
        if record["answer_type"] == "single_span":
            quote = entry.get("answer_quote", "").strip()
            pid = required[0]
            if not quote:
                problems.append(f"{qid}: single_span needs answer_quote")
            elif pid not in texts:
                problems.append(f"{qid}: no source text for {pid}")
            else:
                span = locate(texts[pid], quote)
                if span is None:
                    problems.append(f"{qid}: answer_quote not found in passage text")
                else:
                    start, end = span
                    answer_span = {"quote": texts[pid][start:end],
                                   "start_char": start, "end_char": end}

        row = dict(record)
        row["question"] = question
        row["required_evidence_ids"] = required
        row["optional_evidence_ids"] = optional
        row["gold_facts"] = [{"fact_id": f["id"], "text": f["text"].strip(),
                              "supported_by": f["support"]} for f in facts]
        row["answer_span"] = answer_span
        row["answer_variants"] = []
        row["annotator"] = ANNOTATOR
        row["reviewer"] = None
        row["status"] = STATUS
        row.pop("scaffold", None)
        out.append({key: row[key] for key in KEEP})

    if problems:
        print(f"校验失败 {len(problems)} 项：", file=sys.stderr)
        for item in problems:
            print("  - " + item, file=sys.stderr)
        return 1

    target = base / "qa.v1.jsonl"
    with target.open("w", encoding="utf-8", newline="\n") as fh:
        for row in out:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    manifest_path = base / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"] = {"skeleton": "skeleton.jsonl", "passage_index": "passage_index.json",
                         "draft": "draft.v1.json", "annotated": "qa.v1.jsonl"}
    manifest["file_sha256"] = {name: sha256_file(base / name) for name in
                               ("skeleton.jsonl", "passage_index.json",
                                "draft.v1.json", "qa.v1.jsonl")}
    manifest["annotations"] = {
        "version": "probe-qa-v1",
        "count": len(out),
        "drafted_by": draft["drafted_by"],
        "review_status": STATUS,
        "independent_human_review": False,
        "note": "机器起草，未经人工复核；question 与 gold_facts 必须由人工逐条核对后才能"
                "用于门禁统计。",
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8")

    facts_total = sum(len(row["gold_facts"]) for row in out)
    singles = sum(1 for row in out if row["answer_type"] == "single_span")
    print(f"写出 {len(out)} 条 -> {target}")
    print(f"gold_facts 合计 {facts_total} 条；single_span {singles} 条（含 answer_span）")
    print(f"清单已更新 -> {manifest_path}")


if __name__ == "__main__":
    raise SystemExit(main())
