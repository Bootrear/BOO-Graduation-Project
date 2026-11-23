"""Generate the probe-v1 annotation skeleton (40 questions).

Reads the fixed CWE 4.20 archive, picks 40 distinct entries that CAN support a
discriminative MMR-vs-Top-K probe, and emits a skeleton JSONL where:

  filled : entry, template, answer_type, intent, candidate_pool passage_ids
  empty  : question text, gold_facts, required_evidence_ids (the annotator's job)

Why these entries: MMR only beats Reader Top-K when the required evidence must
compete with sibling units of the same field (e.g. 5 Consequences, 10
Mitigations). Entries whose busiest field has >=2 safe units are therefore
preferred.

passage_id is recomputed with the frozen formula from cyber_qa/data/contracts.py
under the assumption chunk_index == 0, which holds only for units short enough to
fit one chunk. Units are capped at MAX_WORDS so that assumption is safe; the
generated IDs are re-verified against passages.jsonl after the first preprocessing
run (see README).

Usage:
  py scripts/make_probe_skeleton.py [--out data/annotations/probe-v1]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cyber_qa.data.cwe import parse_cwe  # noqa: E402

DEFAULT_ZIP = "data/raw/cwe/cwec_v4.20.xml.zip"
SNAPSHOT = "cwe:88e4eab3cc54f16611040a0e528d7a128253426e90ee5054327fd28449fee393"
MAX_WORDS = 120          # safe single-chunk assumption
MIN_POOL_WORDS = 8       # drop degenerate one-word units from pools
QUOTA = {"A": 12, "B": 8, "C": 8, "D": 4, "E": 8}

TEMPLATE = {
    "A": {
        "answer_type": "multi_passage",
        "intent": "cause_and_consequence",
        "fields": ["description", "common_consequences"],
        "needs": {"description": 1, "common_consequences": 2},
        "hint": "问：这个弱点是怎么产生的，会造成哪些（具体）后果？"
                "必需证据应包含 1 段 description + 至少 1 段 common_consequences。",
    },
    "B": {
        "answer_type": "multi_passage",
        "intent": "consequence_and_detection",
        "fields": ["common_consequences", "detection_methods"],
        "needs": {"common_consequences": 2, "detection_methods": 2},
        "hint": "问：这会造成什么影响，用什么手段能检测出来？"
                "必需证据应跨 common_consequences 与 detection_methods。",
    },
    "C": {
        "answer_type": "multi_passage",
        "intent": "detection_and_mitigation",
        "fields": ["detection_methods", "potential_mitigations"],
        "needs": {"detection_methods": 2, "potential_mitigations": 2},
        "hint": "问：怎么检测出这个问题，以及检测到之后该怎么修复/缓解？"
                "必需证据应跨 detection_methods 与 potential_mitigations。",
    },
    "D": {
        "answer_type": "multi_passage",
        "intent": "mitigation_by_phase",
        "fields": ["potential_mitigations"],
        "needs": {"potential_mitigations": 2},
        "hint": "问：在甲阶段和乙阶段分别该采取什么不同措施？"
                "两段必需证据应属于同一字段但 Phase 不同（本模板风险最高，见 README）。",
    },
    "E": {
        "answer_type": "single_span",
        "intent": "field_comprehension",
        "fields": ["common_consequences", "detection_methods", "potential_mitigations"],
        "needs": {},
        "hint": "对照题：只需 1 段非 description 证据即可回答，Top-K 应当赢。"
                "需补 answer_span（原文连续子串 + 起止字符）。",
    },
}
NON_DESC = ["common_consequences", "detection_methods", "potential_mitigations"]


def stable_hash(value):
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False,
                         separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def passage_id_for(unit):
    content = hashlib.sha256(unit.source_text.encode("utf-8")).hexdigest()
    return "cwe-passage:" + stable_hash({
        "snapshot_id": SNAPSHOT, "cwe_id": unit.cwe_id,
        "source_locator": unit.source_locator, "field_name": unit.field_name,
        "chunk_index": 0, "content_sha256": content,
    }), content


def first_phase(text):
    found = re.search(r"Phase:\s*(.+?)(?=\s+(?:Phase|Strategy|Description):|\s*$)", text)
    return found.group(1).strip() if found else None


def cwe_number(cwe_id):
    return int(cwe_id.split("-")[1])


def index_entries(units):
    by_cwe = {}
    for unit in units:
        words = len(unit.source_text.split())
        if words > MAX_WORDS or words < MIN_POOL_WORDS:
            continue
        by_cwe.setdefault(unit.cwe_id, {}).setdefault(unit.field_name, []).append(unit)
    for fields in by_cwe.values():
        for field_units in fields.values():
            field_units.sort(key=lambda u: u.source_locator)
    return by_cwe


def eligible(entry_fields, template_id):
    spec = TEMPLATE[template_id]
    if template_id == "D":
        pool = entry_fields.get("potential_mitigations", [])
        phases = {first_phase(u.source_text) for u in pool} - {None}
        return len(pool) >= 2 and len(phases) >= 2
    if template_id == "E":
        return any(entry_fields.get(f) for f in NON_DESC)
    return all(len(entry_fields.get(f, [])) >= n for f, n in spec["needs"].items())


def build_pool(entry_fields, template_id):
    """Per-field caps, so a rich field cannot crowd out its partner field.

    A total cap alone is not enough: for template C a 6-unit detection_methods
    list would consume the whole pool and leave potential_mitigations empty,
    silently destroying the cross-field condition the template exists to test.
    """
    if template_id == "E":
        # Control questions: one non-description field only, so the answer needs
        # exactly one passage and Top-K should win.
        rich = [f for f in NON_DESC if entry_fields.get(f)]
        chosen = max(rich, key=lambda f: (len(entry_fields[f]), f))
        return entry_fields[chosen][:4]
    caps = {
        "A": [("description", 1), ("common_consequences", 4)],
        "B": [("common_consequences", 3), ("detection_methods", 3)],
        "C": [("detection_methods", 3), ("potential_mitigations", 3)],
        "D": [("potential_mitigations", 6)],
    }[template_id]
    pool = []
    for field_name, cap in caps:
        pool.extend(entry_fields.get(field_name, [])[:cap])
    return pool


def assign(entries):
    """Fill the scarcest template first so rarer field combinations are not stolen."""
    availability = {}
    for template_id in TEMPLATE:
        availability[template_id] = sum(
            1 for fields in entries.values() if eligible(fields, template_id))
    order = sorted(TEMPLATE, key=lambda t: (availability[t], t))
    print("各模板可用条目数: " + ", ".join(f"{t}={availability[t]}" for t in TEMPLATE))
    print("填充顺序（最稀缺优先）: " + " -> ".join(order))

    used, chosen = set(), {}
    for template_id in order:
        picked = []
        ranked = sorted(
            (cwe for cwe, fields in entries.items()
             if cwe not in used and eligible(fields, template_id)),
            key=lambda c: (-sum(len(v) for v in entries[c].values()), cwe_number(c)))
        for cwe in ranked[:QUOTA[template_id]]:
            picked.append(cwe)
            used.add(cwe)
        chosen[template_id] = picked
        if len(picked) < QUOTA[template_id]:
            print(f"  ! {template_id} 只找到 {len(picked)}/{QUOTA[template_id]} 个条目")
    return chosen


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="data/annotations/probe-v1")
    parser.add_argument("--zip", default=DEFAULT_ZIP)
    args = parser.parse_args()

    parsed = parse_cwe(args.zip)
    entries = index_entries(parsed.units)
    print(f"源单元 {len(parsed.units)}，可用候选条目 {len(entries)}（每段 <= {MAX_WORDS} 词）")

    chosen = assign(entries)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    records, passage_index = [], {}
    counter = 0
    for template_id in ["A", "B", "C", "D", "E"]:
        for cwe in sorted(chosen[template_id], key=cwe_number):
            if counter >= 40:
                break
            counter += 1
            fields = entries[cwe]
            pool = build_pool(fields, template_id)
            pool_ids = []
            for unit in pool:
                pid, content = passage_id_for(unit)
                pool_ids.append(pid)
                passage_index[pid] = {
                    "cwe_id": unit.cwe_id,
                    "field_name": unit.field_name,
                    "source_locator": unit.source_locator,
                    "chunk_index": 0,
                    "words": len(unit.source_text.split()),
                    "content_sha256": content,
                    "preview": unit.source_text[:200].replace("\n", " "),
                }
            spec = TEMPLATE[template_id]
            records.append({
                "question_id": f"probe-{counter:03d}",
                "question": "",
                "language": "en",
                "split": "probe",
                "intent": spec["intent"],
                "record_ids": [cwe],
                "answer_type": spec["answer_type"],
                "required_evidence_ids": [],
                "optional_evidence_ids": [],
                "gold_facts": [],
                "answer_variants": [],
                "answer_span": None,
                "source_snapshot": SNAPSHOT,
                "annotator": "",
                "reviewer": None,
                "status": "skeleton",
                "scaffold": {
                    "template": template_id,
                    "candidate_pool": pool_ids,
                    "hint": spec["hint"],
                },
            })

    skeleton = out_dir / "skeleton.jsonl"
    with skeleton.open("w", encoding="utf-8", newline="\n") as fh:
        for record in records:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    index_path = out_dir / "passage_index.json"
    index_path.write_text(json.dumps(
        {"snapshot_id": SNAPSHOT, "chunk_index_assumption": 0,
         "max_words": MAX_WORDS, "passages": dict(sorted(passage_index.items()))},
        ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    with zipfile.ZipFile(args.zip) as zf:
        archive_sha = hashlib.sha256(Path(args.zip).read_bytes()).hexdigest()

    manifest = {
        "version": "probe-v1",
        "purpose": "probe_not_formal_dataset",
        "note": "40 题探针集，用于判定 MMR 是否值得继续；不属于正式 120 题，"
                "不进入开发集 80 / 冻结测试集 40。",
        "snapshot_id": SNAPSHOT,
        "cwe_archive_sha256": archive_sha,
        "generator": "scripts/make_probe_skeleton.py",
        "max_words_per_passage": MAX_WORDS,
        "chunk_index_assumption": 0,
        "quota": QUOTA,
        "filled": {"records": len(records)},
        "files": {"skeleton": "skeleton.jsonl", "passage_index": "passage_index.json"},
        "file_sha256": {
            "skeleton.jsonl": hashlib.sha256(skeleton.read_bytes()).hexdigest(),
            "passage_index.json": hashlib.sha256(index_path.read_bytes()).hexdigest(),
        },
        "entries": [{"question_id": r["question_id"], "cwe_id": r["record_ids"][0],
                     "template": r["scaffold"]["template"]} for r in records],
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    counts = {}
    for record in records:
        key = record["scaffold"]["template"]
        counts[key] = counts.get(key, 0) + 1
    print(f"\n生成 {len(records)} 条骨架 -> {skeleton}")
    print("模板分布: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    print(f"候选段落索引 {len(passage_index)} 条 -> {index_path}")
    print(f"清单 -> {out_dir / 'manifest.json'}")


if __name__ == "__main__":
    main()
