"""Deterministic contiguous slices with a real fast-tokenizer budget."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re

CHUNKER_VERSION = "dpr-contiguous-sentence-v1"


@dataclass(frozen=True)
class InputBudget:
    context_max_tokens: int = 256
    reader_max_tokens: int = 512
    question_max_tokens: int = 64
    title_max_tokens: int = 64
    special_tokens: int = 3
    long_question_policy: str = "reject"
    long_title_policy: str = "truncate_token_ids_keep_original_title"

    def __post_init__(self):
        for key in ("context_max_tokens", "reader_max_tokens", "question_max_tokens", "title_max_tokens", "special_tokens"):
            value = getattr(self, key)
            if type(value) is not int or value <= 0:
                raise ValueError(f"{key} must be a positive integer")
        if self.special_tokens != 3 or self.context_max_tokens > 512 or self.reader_max_tokens > 512:
            raise ValueError("unsupported DPR input layout or model position limit")
        if self.long_question_policy != "reject" or self.long_title_policy != "truncate_token_ids_keep_original_title":
            raise ValueError("unsupported truncation policy")
        if self.passage_max_tokens <= 0:
            raise ValueError("no token budget remains for the passage")

    @property
    def passage_max_tokens(self) -> int:
        return min(self.context_max_tokens - self.title_max_tokens - self.special_tokens,
                   self.reader_max_tokens - self.question_max_tokens - self.title_max_tokens - self.special_tokens)

    def to_dict(self):
        return asdict(self)


def token_ids(tokenizer, text: str) -> list[int]:
    return tokenizer(text, add_special_tokens=False, truncation=False, verbose=False)["input_ids"]


def split_text(text: str, tokenizer, max_tokens: int) -> list[str]:
    if type(max_tokens) is not int or max_tokens <= 0:
        raise ValueError("max_tokens must be a positive integer")
    if not getattr(tokenizer, "is_fast", False):
        raise ValueError("offset-aware fast tokenizer required")
    if not text.strip():
        return []
    chunks = []
    start = 0
    while start < len(text):
        remainder = text[start:]
        encoded = tokenizer(remainder, add_special_tokens=False, truncation=False,
                            return_offsets_mapping=True, verbose=False)
        offsets = encoded["offset_mapping"]
        if not offsets:
            raise ValueError("non-empty source has no encodable tokens")
        if len(offsets) <= max_tokens:
            chunks.append(remainder.strip())
            break
        end = offsets[max_tokens - 1][1]
        # Prefer a sentence/line end in the latter half of the available span.
        boundaries = [m.end() for m in re.finditer(r"[.!?](?=\s)|\n", remainder[:end]) if m.end() >= end / 2]
        if boundaries:
            end = boundaries[-1]
        candidate = remainder[:end].strip()
        # Splitting within a WordPiece word can change tokenization; recheck it.
        while candidate and len(token_ids(tokenizer, candidate)) > max_tokens:
            end -= 1
            candidate = remainder[:end].strip()
        if not candidate or end <= 0:
            raise ValueError("cannot produce a non-empty chunk within token budget")
        chunks.append(candidate)
        start += end
        while start < len(text) and text[start].isspace():
            start += 1
    return chunks
