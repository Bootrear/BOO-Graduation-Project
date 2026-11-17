"""One Reader pass per unique candidate; reuse the result for both selectors."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import logging
import math
import time

import numpy as np

from cyber_qa.config import ReaderConfig
from cyber_qa.data.candidates import AnswerSpan, ScoredPassage
from cyber_qa.data.chunking import token_ids
from cyber_qa.models import validate_vectors

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReaderInput:
    passage_id: str
    input_ids: tuple[int, ...]
    # None excludes question/title/separators and any special token in the body.
    offsets: tuple[tuple[int, int] | None, ...]
    question_tokens: int
    title_tokens_original: int
    title_tokens_used: int
    passage_tokens: int

    @property
    def title_truncated(self):
        return self.title_tokens_used < self.title_tokens_original


def prepare_input(question, candidate, tokenizer, budget):
    if not isinstance(question, str) or not question.strip():
        raise ValueError("question must be non-empty text")
    question_ids = token_ids(tokenizer, question.strip())
    if not 0 < len(question_ids) <= budget.question_max_tokens:
        raise ValueError(f"Reader question token count {len(question_ids)} outside 1..{budget.question_max_tokens}; rejected without truncation")
    title = token_ids(tokenizer, candidate.passage.title)
    used_title = title[:budget.title_max_tokens]
    body = tokenizer(candidate.passage.text, add_special_tokens=False, truncation=False,
                     return_offsets_mapping=True, verbose=False)
    body_ids, offsets = body["input_ids"], body["offset_mapping"]
    if not 0 < len(body_ids) <= budget.passage_max_tokens:
        raise ValueError("Reader passage does not fit the frozen tokenizer budget")
    if len(offsets) != len(body_ids):
        raise ValueError("Reader token/offset count mismatch")
    prefix = [tokenizer.cls_token_id] + question_ids + [tokenizer.sep_token_id] + used_title + [tokenizer.sep_token_id]
    ids = prefix + body_ids  # DPR Reader has no final SEP after the passage.
    if len(ids) > budget.reader_max_tokens:
        raise ValueError("Reader input exceeds position budget")
    valid_offsets = [None] * len(prefix)
    special = set(tokenizer.all_special_ids)
    previous_start = 0
    for token, (start, end) in zip(body_ids, offsets):
        if token in special:
            valid_offsets.append(None)
            continue
        if not 0 <= previous_start <= start < end <= len(candidate.passage.text):
            raise ValueError("Reader body offset cannot map to original passage")
        previous_start = start
        valid_offsets.append((start, end))
    return ReaderInput(candidate.passage_id, tuple(ids), tuple(valid_offsets),
                       len(question_ids), len(title), len(used_title), len(body_ids))


def best_span(text, offsets, start_logits, end_logits, max_tokens=64):
    """Maximize start+end over contiguous valid tokens; ties use earliest positions."""
    if type(max_tokens) is not int or max_tokens < 1:
        raise ValueError("max_tokens must be a positive integer")
    starts, ends = np.asarray(start_logits, dtype=np.float64), np.asarray(end_logits, dtype=np.float64)
    if starts.shape != (len(offsets),) or ends.shape != starts.shape:
        raise ValueError("span logits/offset shape mismatch")
    if not np.isfinite(starts).all() or not np.isfinite(ends).all():
        raise ValueError("span logits contain NaN or Inf")
    best = None
    for start, offset in enumerate(offsets):
        if offset is None:
            continue
        for end in range(start, min(start + max_tokens, len(offsets))):
            if offsets[end] is None:
                break
            char_start, char_end = offset[0], offsets[end][1]
            if not 0 <= char_start < char_end <= len(text):
                raise ValueError("invalid answer character offsets")
            score = float(starts[start]) + float(ends[end])
            if not math.isfinite(score):
                raise ValueError("span score overflow")
            if best is None or score > best[0]:
                best = (score, start, end, char_start, char_end)
    if best is None:
        return None
    score, start, end, char_start, char_end = best
    return AnswerSpan(text[char_start:char_end], char_start, char_end, start, end, score)


def validate_outputs(result, count, width):
    arrays = []
    for name, shape in (("relevance_logits", (count,)),
                        ("start_logits", (count, width)), ("end_logits", (count, width))):
        tensor = getattr(result, name)
        if tuple(tensor.shape) != shape:
            raise ValueError(f"Reader {name} shape {tuple(tensor.shape)} != {shape}")
        array = tensor.detach().float().cpu().numpy()
        if not np.isfinite(array).all():
            raise ValueError(f"Reader {name} contains NaN or Inf")
        arrays.append(array)
    return arrays  # never squeeze a single-candidate batch


@dataclass(frozen=True)
class ReaderResult:
    candidates: tuple[ScoredPassage, ...]
    inputs: tuple[ReaderInput, ...]
    batch_shapes: tuple[tuple[int, int], ...]
    model_load_seconds: float
    reader_seconds: float
    config: ReaderConfig

    def to_dict(self):
        return {"candidates": [c.to_dict() for c in self.candidates],
                "inputs": [asdict(row) for row in self.inputs],
                "batch_shapes": self.batch_shapes,
                "model_load_seconds": self.model_load_seconds,
                "reader_seconds": self.reader_seconds, "config": self.config.to_dict()}


class DPRReaderScorer:
    def __init__(self, runtime, config=None):
        self.runtime = runtime
        self.config = config or ReaderConfig()

    def score(self, question, candidates, *, batch_size=8):
        try:
            return self._score(question, candidates, batch_size)
        except Exception as exc:
            logger.error("Reader query failed (%s): %s", type(exc).__name__, exc)
            raise

    def _score(self, question, candidates, batch_size):
        started = time.perf_counter()
        if type(batch_size) is not int or batch_size < 1:
            raise ValueError("batch_size must be a positive integer")
        # Validate the question even for an empty pool, using the retrieval policy.
        self.runtime.question_ids(question)
        unique = {}
        for candidate in candidates:
            if type(candidate.retrieval_rank) is not int or candidate.retrieval_rank < 1:
                raise ValueError("retrieval rank must be a positive integer")
            if not math.isfinite(candidate.retrieval_score):
                raise ValueError("retrieval score is NaN or Inf")
            prior = unique.get(candidate.passage_id)
            if prior is not None and prior != candidate:
                raise ValueError("conflicting duplicate Reader candidate")
            unique[candidate.passage_id] = candidate
        candidates = tuple(unique.values())
        if candidates:
            validate_vectors(np.asarray([c.vector for c in candidates], dtype=np.float64))
            if len({c.passage.snapshot_id for c in candidates}) != 1:
                raise ValueError("Reader candidates mix snapshots")
        tokenizer = self.runtime.tokenizers["reader"]
        inputs = tuple(prepare_input(question, c, tokenizer, self.runtime.budget) for c in candidates)
        before_load = self.runtime.model_load_seconds
        model = self.runtime.load_model("reader") if candidates else None
        load_seconds = self.runtime.model_load_seconds - before_load
        scored, shapes = [], []
        for start in range(0, len(inputs), batch_size):
            rows = inputs[start:start + batch_size]
            batch = tokenizer.pad({"input_ids": [list(row.input_ids) for row in rows],
                "attention_mask": [[int(i != tokenizer.pad_token_id) for i in row.input_ids] for row in rows]},
                padding=True, return_tensors="pt").to(self.runtime.device)
            shape = tuple(batch["input_ids"].shape)
            with self.runtime.torch.inference_mode():
                result = model(**batch)
            relevance, starts, ends = validate_outputs(result, *shape)
            shapes.append(shape)
            for i, row in enumerate(rows):
                candidate = candidates[start + i]
                width = len(row.input_ids)
                start_scores = tuple(float(x) for x in starts[i, :width])
                end_scores = tuple(float(x) for x in ends[i, :width])
                span = best_span(candidate.passage.text, row.offsets, start_scores, end_scores,
                                 self.config.max_answer_tokens)
                scored.append(ScoredPassage(passage=candidate.passage, vector=candidate.vector,
                    retrieval_rank=candidate.retrieval_rank, retrieval_score=candidate.retrieval_score,
                    reader_relevance_logit=float(relevance[i]), answer_span=span,
                    title_truncated=row.title_truncated, reader_start_logits=start_scores,
                    reader_end_logits=end_scores, answer_span_reason=None if span else "no_valid_passage_tokens"))
        return ReaderResult(tuple(scored), inputs, tuple(shapes), load_seconds,
                            time.perf_counter() - started - load_seconds, self.config)
