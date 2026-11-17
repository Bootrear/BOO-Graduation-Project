"""Evidence selection algorithms used by the baseline pipeline."""

from .mmr import (
    MMRStep,
    PreparedPool,
    SelectionResult,
    normalize_relevance,
    prepare_pool,
    reader_topk,
    select_mmr,
    select_mmr_reference,
    similarity_matrix,
)

__all__ = [
    "MMRStep",
    "PreparedPool",
    "SelectionResult",
    "normalize_relevance",
    "prepare_pool",
    "reader_topk",
    "select_mmr",
    "select_mmr_reference",
    "similarity_matrix",
]
