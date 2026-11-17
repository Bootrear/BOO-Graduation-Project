"""Traceable baseline records for the CWE pipeline."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import asdict, dataclass
from datetime import datetime


def normalize_text(text: str) -> str:
    """NFC, LF, collapsed horizontal whitespace; preserve semantic line breaks."""
    text = unicodedata.normalize("NFC", text.replace("\r\n", "\n").replace("\r", "\n"))
    lines = [re.sub(r"[^\S\n]+", " ", line).strip() for line in text.split("\n")]
    return "\n".join(line for line in lines if line)


def text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def stable_hash(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return text_sha256(encoded)


def validate_timestamp(value: str | None, name: str, *, nullable: bool = False) -> None:
    if value is None and nullable:
        return
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a timezone-aware ISO 8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"invalid {name}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{name} must include a timezone")


def validate_sha256(value: str, name: str) -> None:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError(f"invalid {name}")


def validate_nonempty(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-empty text")


@dataclass(frozen=True)
class SourceUnit:
    cwe_id: str
    title: str
    field_name: str
    source_locator: str
    source_text: str
    source_url: str
    dataset_version: str
    entry_status: str | None

    def __post_init__(self) -> None:
        for key in ("cwe_id", "title", "field_name", "source_locator", "source_text", "source_url", "dataset_version"):
            validate_nonempty(getattr(self, key), key)
        if re.fullmatch(r"CWE-[1-9][0-9]*", self.cwe_id) is None:
            raise ValueError("cwe_id must be canonical CWE-<positive integer>")
        if normalize_text(self.source_text) != self.source_text:
            raise ValueError("source_text is not normalized")


@dataclass(frozen=True)
class Passage(SourceUnit):
    passage_id: str
    chunk_index: int
    text: str
    snapshot_id: str
    acquired_at: str | None
    content_sha256: str

    def __post_init__(self) -> None:
        super().__post_init__()
        for key in ("passage_id", "text", "snapshot_id"):
            validate_nonempty(getattr(self, key), key)
        if type(self.chunk_index) is not int or self.chunk_index < 0:
            raise ValueError("chunk_index must be a non-negative integer")
        if normalize_text(self.text) != self.text or self.text not in self.source_text:
            raise ValueError("text must be a normalized contiguous slice of source_text")
        validate_timestamp(self.acquired_at, "acquired_at", nullable=True)
        validate_sha256(self.content_sha256, "content_sha256")
        if self.content_sha256 != text_sha256(self.text):
            raise ValueError("content_sha256 must hash the exact UTF-8 text")
        if re.fullmatch(r"cwe:[0-9a-f]{64}", self.snapshot_id) is None:
            raise ValueError("invalid snapshot_id")
        expected = "cwe-passage:" + stable_hash({
            "snapshot_id": self.snapshot_id, "cwe_id": self.cwe_id,
            "source_locator": self.source_locator, "field_name": self.field_name,
            "chunk_index": self.chunk_index, "content_sha256": self.content_sha256,
        })
        if self.passage_id != expected:
            raise ValueError("passage_id does not match stable source and content")

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class SnapshotManifest:
    dataset_name: str
    dataset_version: str
    snapshot_id: str
    source_download_url: str
    raw_file_sha256: str
    acquired_at: str | None
    acquired_at_basis: str
    registered_at: str
    processed_at: str
    parser_version: str
    chunker_version: str
    preprocessing_config: dict
    preprocessing_config_sha256: str

    def __post_init__(self) -> None:
        for key in ("dataset_name", "dataset_version", "snapshot_id", "source_download_url", "parser_version", "chunker_version", "acquired_at_basis"):
            validate_nonempty(getattr(self, key), key)
        validate_sha256(self.raw_file_sha256, "raw_file_sha256")
        validate_sha256(self.preprocessing_config_sha256, "preprocessing_config_sha256")
        if not isinstance(self.preprocessing_config, dict):
            raise ValueError("preprocessing_config must be an object")
        if stable_hash(self.preprocessing_config) != self.preprocessing_config_sha256:
            raise ValueError("preprocessing configuration hash mismatch")
        validate_timestamp(self.acquired_at, "acquired_at", nullable=True)
        validate_timestamp(self.registered_at, "registered_at")
        validate_timestamp(self.processed_at, "processed_at")
        if (self.acquired_at is None) != (self.acquired_at_basis == "unknown"):
            raise ValueError("unknown acquisition time requires null acquired_at and unknown basis")
        if self.snapshot_id != self.expected_snapshot_id():
            raise ValueError("snapshot_id does not match stable source and configuration")

    def expected_snapshot_id(self) -> str:
        return "cwe:" + stable_hash({
            "dataset_name": self.dataset_name, "dataset_version": self.dataset_version,
            "raw_file_sha256": self.raw_file_sha256,
            "parser_version": self.parser_version, "chunker_version": self.chunker_version,
            "preprocessing_config_sha256": self.preprocessing_config_sha256,
        })

    def to_dict(self) -> dict:
        return asdict(self)


def make_manifest(**values) -> SnapshotManifest:
    """Build stable identity without acquisition, registration or processing time."""
    values = dict(values)
    values["preprocessing_config_sha256"] = stable_hash(values["preprocessing_config"])
    identity = {key: values[key] for key in (
        "dataset_name", "dataset_version", "raw_file_sha256", "parser_version",
        "chunker_version", "preprocessing_config_sha256",
    )}
    values["snapshot_id"] = "cwe:" + stable_hash(identity)
    return SnapshotManifest(**values)


def make_passage(unit: SourceUnit, manifest: SnapshotManifest, chunk_index: int, text: str) -> Passage:
    if unit.dataset_version != manifest.dataset_version:
        raise ValueError("source unit and snapshot version mismatch")
    content_hash = text_sha256(text)
    passage_id = "cwe-passage:" + stable_hash({
        "snapshot_id": manifest.snapshot_id, "cwe_id": unit.cwe_id,
        "source_locator": unit.source_locator, "field_name": unit.field_name,
        "chunk_index": chunk_index, "content_sha256": content_hash,
    })
    return Passage(**asdict(unit), passage_id=passage_id, chunk_index=chunk_index,
                   text=text, snapshot_id=manifest.snapshot_id,
                   acquired_at=manifest.acquired_at, content_sha256=content_hash)
