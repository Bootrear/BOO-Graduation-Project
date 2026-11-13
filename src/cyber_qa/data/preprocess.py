"""Build and validate atomic CWE passage snapshots with pinned tokenizers."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from importlib.metadata import version
import hashlib
import json
from pathlib import Path
import tempfile

from .chunking import CHUNKER_VERSION, InputBudget, split_text, token_ids
from .contracts import Passage, SnapshotManifest, make_manifest, make_passage
from .cwe import PARSER_VERSION, parse_cwe
from cyber_qa.resources import load_tokenizers


def build_snapshot(raw_path, output_path, *, receipt_path=None,
                   model_config="configs/dpr-models.v1.json", model_root="models/dpr",
                   budget: InputBudget | None = None):
    output = Path(output_path)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite snapshot: {output}")
    budget = budget or InputBudget()
    parsed = parse_cwe(raw_path)
    tokenizers, provenance = load_tokenizers(model_config, model_root)
    now = datetime.now(timezone.utc).isoformat()
    receipt = json.loads(Path(receipt_path).read_text()) if receipt_path else {}
    if receipt and receipt.get("raw_file_sha256") != parsed.raw_file_sha256:
        raise ValueError("download receipt does not match raw file")
    config = {"input_budget": budget.to_dict(), "passage_max_tokens": budget.passage_max_tokens,
              "normalization": "NFC-LF-horizontal-collapse-v1", "cross_source_duplicates": "keep_all",
              "chunk_overlap": 0, "tokenizers": provenance,
              "transformers_version": version("transformers"), "tokenizers_version": version("tokenizers")}
    manifest = make_manifest(dataset_name="CWE", dataset_version=parsed.dataset_version,
        source_download_url=receipt.get("source_download_url", "https://cwe.mitre.org/data/xml/cwec_v4.20.xml.zip"),
        raw_file_sha256=parsed.raw_file_sha256, acquired_at=receipt.get("acquired_at"),
        acquired_at_basis=receipt.get("acquired_at_basis", "unknown"),
        registered_at=receipt.get("registered_at", now), processed_at=now,
        parser_version=PARSER_VERSION, chunker_version=CHUNKER_VERSION, preprocessing_config=config)
    passages = []
    truncated_titles = set()
    for unit in parsed.units:
        if len(token_ids(tokenizers["context"], unit.title)) > budget.title_max_tokens:
            truncated_titles.add(unit.cwe_id)
        for index, text in enumerate(split_text(unit.source_text, tokenizers["context"], budget.passage_max_tokens)):
            passages.append(make_passage(unit, manifest, index, text))
    if len({p.passage_id for p in passages}) != len(passages):
        raise ValueError("duplicate passage IDs")
    statistics = {**parsed.statistics, "final_passages": len(passages),
                  "title_truncation_required_cwe_ids": sorted(truncated_titles),
                  "xml_member": parsed.xml_member, "namespace": parsed.namespace,
                  "passage_max_tokens": budget.passage_max_tokens}
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".snapshot-", dir=output.parent) as temp:
        temp_path = Path(temp) / "snapshot"
        temp_path.mkdir()
        (temp_path / "manifest.json").write_text(json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        with (temp_path / "passages.jsonl").open("w", encoding="utf-8", newline="\n") as stream:
            for passage in passages:
                stream.write(json.dumps(asdict(passage), ensure_ascii=False, sort_keys=True) + "\n")
        statistics["passages_sha256"] = hashlib.sha256((temp_path / "passages.jsonl").read_bytes()).hexdigest()
        (temp_path / "statistics.json").write_text(json.dumps(statistics, indent=2) + "\n", encoding="utf-8")
        load_snapshot(temp_path)
        temp_path.rename(output)
    return manifest, statistics


def load_snapshot(path):
    path = Path(path)
    manifest = SnapshotManifest(**json.loads((path / "manifest.json").read_text(encoding="utf-8")))
    statistics = json.loads((path / "statistics.json").read_text(encoding="utf-8"))
    if hashlib.sha256((path / "passages.jsonl").read_bytes()).hexdigest() != statistics["passages_sha256"]:
        raise ValueError("corpus file checksum mismatch")
    passages = []
    seen = set()
    with (path / "passages.jsonl").open(encoding="utf-8") as stream:
        for line in stream:
            p = Passage(**json.loads(line))
            if p.snapshot_id != manifest.snapshot_id or p.dataset_version != manifest.dataset_version or p.acquired_at != manifest.acquired_at:
                raise ValueError("passage/snapshot provenance mismatch")
            if p.passage_id in seen:
                raise ValueError("duplicate passage_id in corpus")
            seen.add(p.passage_id)
            passages.append(p)
    if len(passages) != statistics["final_passages"]:
        raise ValueError("corpus passage count mismatch")
    return manifest, tuple(passages)
