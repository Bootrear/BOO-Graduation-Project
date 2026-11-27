"""Translate probe-v1 questions offline with the pinned Qwen2.5 model."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from cyber_qa.experiments.chinese_probe import (
    make_parallel_record, read_jsonl, translate_question, validate_parallel, write_jsonl,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data/annotations/probe-v1/qa.v1.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("data/annotations/probe-v1-zh/qa.v1.zh.jsonl"))
    parser.add_argument("--model-dir", type=Path, default=Path(
        "models/crosslingual/Qwen--Qwen2.5-7B-Instruct/a09a35458c702b33eeacc393d103063234e8bc28"))
    parser.add_argument("--device", choices=("cuda", "cpu"), default="cuda")
    parser.add_argument("--max-new-tokens", type=int, default=128)
    args = parser.parse_args()
    if args.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable")
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite translated dataset: {args.output}")

    tokenizer = AutoTokenizer.from_pretrained(args.model_dir, local_files_only=True)
    model = AutoModelForCausalLM.from_pretrained(
        args.model_dir, local_files_only=True,
        dtype=torch.bfloat16 if args.device == "cuda" else torch.float32).to(args.device).eval()
    sources = read_jsonl(args.input)
    translated = []
    for index, source in enumerate(sources, start=1):
        question = translate_question(model, tokenizer, source["question"],
                                      device=args.device, max_new_tokens=args.max_new_tokens)
        translated.append(make_parallel_record(source, question))
        print(json.dumps({"question_id": source["question_id"], "translated_question": question},
                         ensure_ascii=False), flush=True)
    validate_parallel(sources, translated)
    write_jsonl(args.output, translated)
    print(json.dumps({"records": len(translated), "output": str(args.output),
                      "translation_status": "machine_translated_needs_human_review",
                      "reviewer": None, "model": str(args.model_dir),
                      "device": args.device, "max_new_tokens": args.max_new_tokens},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
