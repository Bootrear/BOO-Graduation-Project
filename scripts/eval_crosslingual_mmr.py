"""Run the exploratory bilingual retrieval Top-K/MMR scale and lambda sweep."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import torch
from transformers import AutoModel, AutoTokenizer

from cyber_qa.experiments.chinese_probe import read_jsonl, validate_parallel
from cyber_qa.experiments.crosslingual_mmr_eval import LAMBDA_GRID, evaluate_records, write_results
from cyber_qa.retrieval.crosslingual import load_index


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--english", type=Path, default=Path("data/annotations/probe-v1/qa.v1.jsonl"))
    parser.add_argument("--chinese", type=Path, default=Path("data/annotations/probe-v1-zh/qa.v1.zh.jsonl"))
    parser.add_argument("--index", type=Path, default=Path("data/processed/crosslingual-index-v2-final"))
    parser.add_argument("--model-dir", type=Path, default=Path(
        "models/crosslingual/Qwen--Qwen3-Embedding-0.6B/97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3"))
    parser.add_argument("--snapshot", type=Path, default=Path("data/processed/cwe-v1"))
    parser.add_argument("--output", type=Path, default=Path("outputs/crosslingual-mmr-v2"))
    parser.add_argument("--n", type=int, default=20)
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--device", choices=("cuda", "cpu"), default="cuda")
    args = parser.parse_args()
    if args.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable")
    if args.n < 1 or args.k < 0:
        raise ValueError("N must be >= 1 and K must be >= 0")
    english, chinese = read_jsonl(args.english), read_jsonl(args.chinese)
    validate_parallel(english, chinese)
    snapshot_id = json.loads((args.snapshot / "manifest.json").read_text(encoding="utf-8"))["snapshot_id"]
    manifest, vectors, passage_ids, passages = load_index(
        args.index, expected_snapshot_id=snapshot_id,
        expected_model_revision="97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3")
    tokenizer = AutoTokenizer.from_pretrained(args.model_dir, local_files_only=True, padding_side="left")
    model = AutoModel.from_pretrained(args.model_dir, local_files_only=True,
                                      dtype=torch.bfloat16 if args.device == "cuda" else torch.float32)
    model.to(args.device).eval()
    rows, summary = evaluate_records(english, chinese, vectors, passage_ids, passages,
                                     model, tokenizer, device=args.device,
                                     n_candidates=args.n, k=args.k, lambdas=LAMBDA_GRID)
    provenance = {
        "config_version": "crosslingual-rag-v2", "index_manifest_sha256": hashlib.sha256(
            (args.index / "manifest.json").read_bytes()).hexdigest(),
        "snapshot_id": manifest["snapshot_id"], "model_id": "Qwen/Qwen3-Embedding-0.6B",
        "model_revision": "97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3",
        "english_dataset_sha256": hashlib.sha256(args.english.read_bytes()).hexdigest(),
        "chinese_dataset_sha256": hashlib.sha256(args.chinese.read_bytes()).hexdigest(),
        "question_count_per_language": len(english), "candidate_count": args.n,
        "max_passages": args.k, "lambda_grid": list(LAMBDA_GRID),
        "similarity_scales": ["pool_minmax", "raw"], "device": args.device,
        "translation_in_online_retrieval": False,
        "chinese_translation_status": "machine_translated_needs_human_review",
        "exploratory_only": True,
    }
    write_results(args.output, rows, summary, provenance)
    print(json.dumps({"summary": summary, "provenance": provenance,
                      "output": str(args.output)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
