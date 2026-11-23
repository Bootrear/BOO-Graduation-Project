"""Re-verify probe-v1 passage_ids against a real processed snapshot.

The skeleton IDs were computed offline under the assumption chunk_index == 0.
That assumption depends on the real DPR tokenizer, so it must be confirmed once
`passages.jsonl` exists. Any mismatch is reported with the authoritative ID.

Usage:
  py scripts/verify_probe_ids.py --passages data/processed/cwe-v1/passages.jsonl
Exit code 0: all IDs confirmed. 1: mismatches found (fix passage_index/skeleton).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def load_passages(path):
    index = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            index[record["passage_id"]] = record
            index[(record["cwe_id"], record["source_locator"], record["chunk_index"])] = record
    return index


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--passages", default="data/processed/cwe-v1/passages.jsonl")
    parser.add_argument("--probe", default="data/annotations/probe-v1/passage_index.json")
    args = parser.parse_args()

    passages_path = Path(args.passages)
    if not passages_path.exists():
        print(f"未找到 {passages_path}；请先预处理或指定 --passages", file=sys.stderr)
        return 2
    probe = json.loads(Path(args.probe).read_text(encoding="utf-8"))
    if probe.get("snapshot_id") != next(iter(
            load_passages(passages_path).values()), {}).get("snapshot_id"):
        print("警告：probe 与 passages 的 snapshot_id 可能不一致", file=sys.stderr)

    index = load_passages(passages_path)
    ok, fixed, missing = 0, [], []
    for passage_id, meta in probe["passages"].items():
        record = index.get(passage_id)
        if record and record["snapshot_id"] == probe["snapshot_id"]:
            ok += 1
            continue
        candidate = index.get((meta["cwe_id"], meta["source_locator"], 0))
        if candidate:
            fixed.append((passage_id, candidate["passage_id"], meta["source_locator"]))
        else:
            missing.append((passage_id, meta["source_locator"]))

    total = len(probe["passages"])
    print(f"核对 {total} 条：一致 {ok}，需修正 {len(fixed)}，未找到 {len(missing)}")
    for old, new, locator in fixed:
        print(f"  FIX  {locator}\n       old {old}\n       new {new}")
    for passage_id, locator in missing:
        print(f"  MISS {locator}  {passage_id}")
    return 0 if ok == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
