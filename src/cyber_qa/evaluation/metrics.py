"""Small deterministic metrics used by early selection experiments."""

from __future__ import annotations

from collections.abc import Collection


def evidence_precision(predicted: Collection[str], gold: Collection[str]) -> float:
    """Fraction of selected evidence IDs that are gold evidence."""

    predicted_set = set(predicted)
    if not predicted_set:
        return 0.0
    return len(predicted_set & set(gold)) / len(predicted_set)


def evidence_recall(predicted: Collection[str], gold: Collection[str]) -> float:
    """Fraction of gold evidence IDs present in the selected set."""

    gold_set = set(gold)
    if not gold_set:
        raise ValueError("evidence_recall is undefined when gold is empty")
    return len(set(predicted) & gold_set) / len(gold_set)


def field_coverage(selected_fields: Collection[str], required_fields: Collection[str]) -> float:
    """Fraction of required answer fields covered by selected evidence."""

    required_set = set(required_fields)
    if not required_set:
        raise ValueError("field_coverage is undefined when required_fields is empty")
    return len(set(selected_fields) & required_set) / len(required_set)
