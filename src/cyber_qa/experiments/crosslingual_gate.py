"""Metrics for the exploratory bilingual Qwen retrieval gate."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from cyber_qa.retrieval.crosslingual import QUERY_INSTRUCTION, search

HISTORICAL_DPR_RECALL = {20: 0.275, 50: 0.4375, 100: 0.5}


def recall_at(required_ids: list[str], retrieved_ids: list[str]) -> float:
    if not required_ids:
        raise ValueError("required evidence IDs must be non-empty")
    found = set(required_ids).intersection(retrieved_ids)
    return len(found) / len(set(required_ids))


def mean_pairwise_cosine(vectors: np.ndarray) -> float | None:
    if vectors.ndim != 2:
        raise ValueError("candidate embeddings must be a matrix")
    if len(vectors) < 2:
        return None
    matrix = vectors.astype(np.float64)
    norms = np.linalg.norm(matrix, axis=1)
    if not np.isfinite(matrix).all() or np.any(norms == 0):
        raise ValueError("candidate embeddings must be finite and non-zero")
    normalized = matrix / norms[:, None]
    similarities = normalized @ normalized.T
    upper = similarities[np.triu_indices(len(vectors), k=1)]
    return float(np.mean(np.clip(upper, -1.0, 1.0)))


def summarize(rows: list[dict], n_values: list[int]) -> dict:
    by_language = {}
    for language in ("en", "zh"):
        language_rows = [row for row in rows if row["language"] == language]
        if not language_rows:
            raise ValueError(f"no rows for language {language}")
        by_n = {}
        for n in n_values:
            recalls = [row["recall_at"][str(n)] for row in language_rows]
            cosines = [row["mean_pairwise_cosine"][str(n)] for row in language_rows]
            by_n[str(n)] = {"recall_at": float(np.mean(recalls)),
                            "mean_pairwise_cosine": float(np.mean(cosines))}
        by_language[language] = {"questions": len(language_rows), "by_n": by_n}
    equivalence = float(np.mean([by_language["zh"]["by_n"][str(n)]["recall_at"] for n in n_values]) /
                        np.mean([by_language["en"]["by_n"][str(n)]["recall_at"] for n in n_values]))
    english_gate = {
        str(n): {"new_recall": by_language["en"]["by_n"][str(n)]["recall_at"],
                 "dpr_baseline": HISTORICAL_DPR_RECALL[n],
                 "minimum_90_percent": 0.9 * HISTORICAL_DPR_RECALL[n],
                 "pass": by_language["en"]["by_n"][str(n)]["recall_at"] >= 0.9 * HISTORICAL_DPR_RECALL[n]}
        for n in n_values
    }
    if equivalence < 0.60:
        verdict = "stop_p2_p3_equivalence_below_0.60"
    elif equivalence < 0.85:
        verdict = "pause_p2_p3_equivalence_below_0.85"
    elif not all(item["pass"] for item in english_gate.values()):
        verdict = "pause_english_recall_gate_failed"
    else:
        verdict = "retrieval_gate_pass_exploratory_only"
    return {"languages": by_language, "equivalence": equivalence,
            "english_dpr_gate": english_gate, "verdict": verdict,
            "comparison_reference_mean_pairwise_cosine": 0.857,
            "interpretation": "40-question machine-translated probe; exploratory diagnostic, not paper test evidence"}


def embed_query(model, tokenizer, question: str, *, device: str, max_length: int = 8192) -> np.ndarray:
    import torch

    tokenizer.padding_side = "left"
    text = f"Instruct: {QUERY_INSTRUCTION}\nQuery:{question}"
    batch = tokenizer(text, return_tensors="pt", truncation=True, max_length=max_length).to(device)
    with torch.inference_mode():
        hidden = model(**batch).last_hidden_state
        vector = hidden[:, -1, :].float()[0].cpu().numpy()
    if not np.isfinite(vector).all() or np.linalg.norm(vector) == 0:
        raise ValueError("query embedding is non-finite or zero")
    return vector


def run_gate(english_records: list[dict], chinese_records: list[dict], vectors: np.ndarray,
             passage_ids: list[str], model, tokenizer, *, device: str,
             n_values: list[int]) -> tuple[list[dict], dict]:
    if {row["question_id"] for row in english_records} != {row["question_id"] for row in chinese_records}:
        raise ValueError("English and Chinese question ID sets differ")
    records = {"en": english_records, "zh": chinese_records}
    passage_positions = {pid: index for index, pid in enumerate(passage_ids)}
    rows = []
    max_n = max(n_values)
    for language, items in records.items():
        for record in items:
            vector = embed_query(model, tokenizer, record["question"], device=device)
            hits = search(vectors, passage_ids, vector, max_n)
            hit_ids = [hit["passage_id"] for hit in hits]
            hit_vectors = np.stack([vectors[passage_positions[pid]] for pid in hit_ids])
            recalls, redundancies = {}, {}
            for n in n_values:
                pool_ids = hit_ids[:n]
                recalls[str(n)] = recall_at(record["required_evidence_ids"], pool_ids)
                pool_vectors = hit_vectors[:n]
                redundancies[str(n)] = mean_pairwise_cosine(pool_vectors)
            rows.append({"language": language, "question_id": record["question_id"],
                         "retrieved": hits, "required_evidence_ids": record["required_evidence_ids"],
                         "recall_at": recalls, "mean_pairwise_cosine": redundancies})
    return rows, summarize(rows, n_values)


def write_results(output_dir: Path, rows: list[dict], summary: dict, provenance: dict) -> None:
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite gate output: {output_dir}")
    output_dir.mkdir(parents=True)
    with (output_dir / "per_question.jsonl").open("x", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    (output_dir / "summary.json").write_text(
        json.dumps({**summary, "provenance": provenance}, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
