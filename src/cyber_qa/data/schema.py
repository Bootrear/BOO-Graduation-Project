"""Stable data structures shared by retrieval, selection, and evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Evidence:
    """One traceable evidence unit derived from a source record field."""

    evidence_id: str
    source: str
    record_id: str
    record_type: str
    field_name: str
    text: str
    url: str
    source_version: str
    modified: str | None = None
    token_count: int = 0
    relations: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        required = {
            "evidence_id": self.evidence_id,
            "source": self.source,
            "record_id": self.record_id,
            "record_type": self.record_type,
            "field_name": self.field_name,
            "text": self.text,
            "url": self.url,
            "source_version": self.source_version,
        }
        missing = [name for name, value in required.items() if not value.strip()]
        if missing:
            raise ValueError(f"Evidence fields must not be empty: {', '.join(missing)}")
        if self.token_count < 0:
            raise ValueError("token_count must be non-negative")
