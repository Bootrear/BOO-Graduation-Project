"""Build and verify a Qwen3 cosine index for one frozen CWE snapshot."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

import torch
from transformers import AutoModel, AutoTokenizer

from cyber_qa.retrieval.crosslingual import encode_texts, sha256_file, write_index
from cyber_qa.crosslingual_resources import upstream_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, default=Path("data/processed/cwe-v1"))
    parser.add_argument("--model-dir", type=Path, default=Path(
        "models/crosslingual/Qwen--Qwen3-Embedding-0.6B/97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3"))
    parser.add_argument("--config", type=Path, default=Path("configs/crosslingual-models.v2.json"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/crosslingual-index-v2"))
    parser.add_argument("--device", choices=("cuda", "cpu"), default="cuda")
    parser.add_argument("--batch-size", type=int, default=16)
    args = parser.parse_args()
    if args.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable")

    config = json.loads(args.config.read_text(encoding="utf-8"))
    model_spec = config["models"]["embedding"]
    tokenizer = AutoTokenizer.from_pretrained(args.model_dir, local_files_only=True, padding_side="left")
    model = AutoModel.from_pretrained(args.model_dir, local_files_only=True,
                                      torch_dtype=torch.bfloat16 if args.device == "cuda" else torch.float32)
    model.to(args.device).eval()

    snapshot_manifest = json.loads((args.snapshot / "manifest.json").read_text(encoding="utf-8"))
    passage_path = args.snapshot / "passages.jsonl"
    records = [json.loads(line) for line in passage_path.read_text(encoding="utf-8").splitlines()]
    if len(records) != 5748:
        raise ValueError(f"expected the frozen 5748-passage CWE snapshot, found {len(records)}")
    if any(record.get("snapshot_id") != snapshot_manifest["snapshot_id"] for record in records):
        raise ValueError("passage snapshot IDs do not match snapshot manifest")
    vectors, truncated = encode_texts(model, tokenizer, (record["text"] for record in records),
                                      device=args.device, batch_size=args.batch_size)
    for record, is_truncated in zip(records, truncated, strict=True):
        record["embedding_truncated"] = is_truncated

    resource_manifest = json.loads((args.model_dir / "config.json").read_text(encoding="utf-8"))
    source_manifest = json.loads((args.snapshot / "manifest.json").read_text(encoding="utf-8"))
    metadata = {
        "config_version": config["version"],
        "dataset_name": source_manifest["dataset_name"],
        "dataset_version": source_manifest["dataset_version"],
        "snapshot_id": source_manifest["snapshot_id"],
        "corpus_sha256": sha256_file(passage_path),
        "model_id": model_spec["model_id"],
        "model_revision": model_spec["revision"],
        "tokenizer_id": model_spec["model_id"],
        "tokenizer_revision": model_spec["revision"],
        "upstream_weight_files": upstream_manifest(model_spec["model_id"], model_spec["revision"])["lfs_files"],
        "device": args.device,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "software": {"torch": torch.__version__, "transformers": __import__("transformers").__version__,
                     "numpy": __import__("numpy").__version__},
        "model_hidden_size": resource_manifest["hidden_size"],
        "truncated_passage_count": sum(truncated),
        "total_passages": len(records),
    }
    report = write_index(args.output, vectors, [record["passage_id"] for record in records], records, metadata)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
