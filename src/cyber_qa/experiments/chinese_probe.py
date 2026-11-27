"""Create an explicitly unreviewed Chinese question parallel set."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

TRANSLATION_STATUS = "machine_translated_needs_human_review"
TRANSLATED_LANGUAGE = "zh"


def question_sha256(question: str) -> str:
    return hashlib.sha256(question.encode("utf-8")).hexdigest()


def translate_question(model, tokenizer, question: str, *, device: str, max_new_tokens: int = 128) -> str:
    if not question.strip():
        raise ValueError("source question must be non-empty")
    messages = [
        {"role": "system", "content": (
            "Translate the user's cybersecurity question into Simplified Chinese. "
            "Preserve CWE identifiers, product names, and technical terms in English where appropriate. "
            "Return only the translated question, with no explanation or quotation marks."
        )},
        {"role": "user", "content": question},
    ]
    prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=8192).to(device)
    model.eval()
    import torch

    with torch.inference_mode():
        output = model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False)
    result = tokenizer.decode(output[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True).strip()
    result = result.strip("\"'“”「」『』 \t\r\n")
    if not result:
        raise ValueError("translation model returned an empty question")
    return result


def make_parallel_record(source: dict, translated_question: str) -> dict:
    if not translated_question.strip():
        raise ValueError("translated question must be non-empty")
    record = dict(source)
    record["question"] = translated_question
    record["translation_status"] = TRANSLATION_STATUS
    record["translated_language"] = TRANSLATED_LANGUAGE
    record["reviewer"] = None
    record["source_question_sha256"] = question_sha256(source["question"])
    return record


def validate_parallel(source_records: list[dict], translated_records: list[dict]) -> None:
    if len(source_records) != len(translated_records):
        raise ValueError("parallel set record count mismatch")
    seen = set()
    allowed_changes = {"question", "translation_status", "translated_language",
                       "source_question_sha256"}
    for source, translated in zip(source_records, translated_records, strict=True):
        question_id = source.get("question_id")
        if not question_id or question_id in seen or translated.get("question_id") != question_id:
            raise ValueError("question IDs must be unique and aligned")
        seen.add(question_id)
        if not isinstance(translated.get("question"), str) or not translated["question"].strip():
            raise ValueError(f"empty translated question: {question_id}")
        if re.search(r"[\u3400-\u9fff]", translated["question"]) is None:
            raise ValueError(f"translated question has no Simplified Chinese characters: {question_id}")
        if translated.get("translation_status") != TRANSLATION_STATUS:
            raise ValueError(f"missing unreviewed translation marker: {question_id}")
        if translated.get("translated_language") != TRANSLATED_LANGUAGE or translated.get("reviewer") is not None:
            raise ValueError(f"invalid translation metadata: {question_id}")
        if translated.get("source_question_sha256") != question_sha256(source["question"]):
            raise ValueError(f"source question hash mismatch: {question_id}")
        source_fields = {key: value for key, value in source.items() if key != "question"}
        translated_fields = {key: value for key, value in translated.items() if key not in allowed_changes}
        if translated_fields != source_fields:
            raise ValueError(f"source annotation fields changed: {question_id}")


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        for record in records:
            stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
