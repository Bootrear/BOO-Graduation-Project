"""Synthetic Reader output regression; real model acceptance is a separate script."""
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest

torch = pytest.importorskip("torch")
from transformers import DPRReaderTokenizerFast

from cyber_qa.config import ReaderConfig
from cyber_qa.data.candidates import RetrievedPassage
from cyber_qa.data.chunking import InputBudget
from cyber_qa.data.contracts import SourceUnit, make_manifest, make_passage
from cyber_qa.models import DPRRuntime
from cyber_qa.reader.dpr import DPRReaderScorer, best_span, prepare_input, validate_outputs
from cyber_qa.selection.mmr import prepare_pool, reader_topk, select_mmr


def changed_passage(passage, *, text=None, title=None, snapshot_id=None):
    text = passage.text if text is None else text.strip()
    unit = SourceUnit(**{name: getattr(passage, name) for name in SourceUnit.__dataclass_fields__})
    unit = replace(unit, source_text=text, title=title or passage.title)
    manifest = SimpleNamespace(dataset_version=passage.dataset_version, snapshot_id=snapshot_id or passage.snapshot_id, acquired_at=passage.acquired_at)
    return make_passage(unit, manifest, passage.chunk_index, text)


@pytest.fixture
def setup(tmp_path):
    vocab = tmp_path / "vocab.txt"
    vocab.write_text("\n".join(["[PAD]", "[UNK]", "[CLS]", "[SEP]", "[MASK]", "what", "is", "sql", "injection", "?", "title", "source", ".", "alpha", "beta", "cafe"]))
    tokenizer = DPRReaderTokenizerFast(vocab_file=str(vocab), do_lower_case=True)
    manifest = make_manifest(dataset_name="CWE", dataset_version="fixture",
        source_download_url="https://example.invalid", raw_file_sha256="0" * 64,
        acquired_at=None, acquired_at_basis="unknown", registered_at="2026-11-17T00:00:00Z",
        processed_at="2026-11-17T00:00:00Z", parser_version="fixture", chunker_version="fixture",
        preprocessing_config={})
    candidates = []
    for i, text in enumerate(["SQL injection.", "Alpha source.", "Café beta source."]):
        unit = SourceUnit(cwe_id=f"CWE-{i+1}", title="Title", field_name="description",
            source_locator=f"/fixture/{i}", source_text=text, source_url=f"https://example.invalid/{i}",
            dataset_version="fixture", entry_status=None)
        candidates.append(RetrievedPassage(make_passage(unit, manifest, 0, text), i+1, 10-i, (1., float(i))))
    calls = []

    def model(**batch):
        ids = batch["input_ids"]
        calls.append(tuple(ids.shape))
        # Deterministic synthetic values tied to token content, independent of padding/order.
        starts = ids.float()
        return SimpleNamespace(relevance_logits=starts.sum(dim=1), start_logits=starts, end_logits=-starts)

    runtime = DPRRuntime.__new__(DPRRuntime)
    runtime.tokenizers = {"question": tokenizer, "reader": tokenizer}
    runtime.budget = InputBudget()
    runtime.torch, runtime.device = torch, "cpu"
    runtime.model_load_seconds = 0.
    runtime.load_model = lambda role: model
    return runtime, tuple(candidates), calls


def test_single_multiple_batches_reorder_and_reuse(setup):
    runtime, candidates, calls = setup
    scorer = DPRReaderScorer(runtime)
    batch = scorer.score("What is SQL injection?", candidates, batch_size=2)
    assert calls == [(2, 12), (1, 13)]
    singles = scorer.score("What is SQL injection?", candidates, batch_size=1)
    reordered = scorer.score("What is SQL injection?", candidates[::-1], batch_size=3)
    assert batch.candidates == singles.candidates
    assert batch.candidates == reordered.candidates[::-1]
    assert batch.candidates[0].reader_relevance_normalized is None
    for old, scored, row in zip(candidates, batch.candidates, batch.inputs):
        assert (old.passage, old.vector, old.retrieval_score, old.retrieval_rank) == (scored.passage, scored.vector, scored.retrieval_score, scored.retrieval_rank)
        span = scored.answer_span
        assert old.passage.text[span.start_char:span.end_char] == span.text
        assert row.offsets[span.start_token] is not None
        assert len(scored.reader_start_logits) == len(row.input_ids)
        assert span.span_score == scored.reader_start_logits[span.start_token] + scored.reader_end_logits[span.end_token]
    before = len(calls)
    pool = prepare_pool(batch.candidates)
    for selection in (reader_topk(pool), select_mmr(pool)):
        assert set(selection.selected_order) == {c.passage_id for c in candidates}
        assert all(c.reader_relevance_normalized is not None for c in selection.selected)
        assert all(c in pool.candidates for c in selection.selected)
    assert len(calls) == before
    assert "reader_start_logits" in batch.to_dict()["candidates"][0]


def test_layout_offsets_unicode_title_truncation_and_special_mask(setup):
    runtime, candidates, _ = setup
    tokenizer = runtime.tokenizers["reader"]
    candidate = candidates[2]
    row = prepare_input("What is SQL injection?", candidate, tokenizer, runtime.budget)
    assert list(row.input_ids) == tokenizer("What is SQL injection?", candidate.passage.title, candidate.passage.text)["input_ids"][0]
    first = next(o for o in row.offsets if o is not None)
    assert candidate.passage.text[slice(*first)] == "Café"
    candidate = replace(candidate, passage=changed_passage(candidate.passage, title="title " * 70, text="[SEP] SQL [PAD] injection [CLS]"))
    row = prepare_input("What?", candidate, tokenizer, runtime.budget)
    assert row.title_truncated and row.title_tokens_used == 64 and row.title_tokens_original == 70
    assert all(o is None for token, o in zip(row.input_ids, row.offsets) if token in tokenizer.all_special_ids)
    assert sum(o is not None for o in row.offsets) == 2


def test_span_excludes_nonpassage_tokens_padding_and_crossing_holes():
    offsets = (None, None, (0, 5), None, (6, 10), None)
    # Invalid positions dominate; valid endpoints cannot cross the special-token hole.
    answer = best_span("alpha beta", offsets, [999, 999, 10, 999, 1, 999], [999, 999, 0, 999, 10, 999])
    assert answer.text == "beta" and answer.span_score == 11
    assert best_span("", (None,), [1], [1]) is None


def test_span_limits_reversed_peaks_and_ties():
    text = "a b c d"
    offsets = ((0, 1), (2, 3), (4, 5), (6, 7))
    limited = best_span(text, offsets, [9, 0, 0, 0], [0, 0, 0, 10], max_tokens=2)
    assert limited.text == "c d"  # earliest valid start among equal-score spans
    reversed_peak = best_span(text, offsets, [0, 0, 10, 0], [10, 0, 0, 0])
    assert reversed_peak.text == "a"
    assert best_span(text, offsets, [0]*4, [0]*4).text == "a"
    # The runtime rule accepts 64 tokens but never 65.
    long_text = "a" * 65
    long_offsets = tuple((i, i+1) for i in range(65))
    span = best_span(long_text, long_offsets, [10]+[0]*64, [0]*64+[11])
    assert span.start_token == 1 and span.end_token == 64


@pytest.mark.parametrize("field,shape", [("relevance_logits", ()), ("relevance_logits", (1, 1)), ("start_logits", (2, 3)), ("end_logits", (1, 2))])
def test_wrong_output_shapes_rejected(field, shape):
    result = SimpleNamespace(relevance_logits=torch.ones(1), start_logits=torch.ones(1, 3), end_logits=torch.ones(1, 3))
    setattr(result, field, torch.ones(shape))
    with pytest.raises(ValueError, match="shape"):
        validate_outputs(result, 1, 3)


@pytest.mark.parametrize("field", ["relevance_logits", "start_logits", "end_logits"])
@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_nonfinite_outputs_fail_even_in_padding(field, bad):
    result = SimpleNamespace(relevance_logits=torch.ones(1), start_logits=torch.ones(1, 3), end_logits=torch.ones(1, 3))
    getattr(result, field).reshape(-1)[-1] = bad
    with pytest.raises(ValueError, match="NaN or Inf"):
        validate_outputs(result, 1, 3)


def test_empty_duplicate_and_conflicting_pool(setup):
    runtime, candidates, calls = setup
    scorer = DPRReaderScorer(runtime)
    assert scorer.score("What?", []).candidates == ()
    assert not calls
    assert len(scorer.score("What?", [candidates[0], candidates[0]]).candidates) == 1
    assert len(calls) == 1
    with pytest.raises(ValueError, match="conflicting duplicate"):
        scorer.score("What?", [candidates[0], replace(candidates[0], retrieval_score=99)])
    assert len(calls) == 1


@pytest.mark.parametrize("question", ["", "   ", "what " * 65])
def test_invalid_question_fails_before_model(setup, question):
    runtime, candidates, calls = setup
    with pytest.raises(ValueError, match="question"):
        DPRReaderScorer(runtime).score(question, candidates)
    assert not calls


def test_bad_candidate_and_batch_are_logged_and_fail_before_model(setup, caplog):
    runtime, candidates, calls = setup
    scorer = DPRReaderScorer(runtime)
    for changes in ({"vector": (0., 0.)}, {"retrieval_score": float("nan")}, {"retrieval_rank": 0}):
        with pytest.raises(ValueError):
            scorer.score("What?", [replace(candidates[0], **changes)])
    with pytest.raises(ValueError, match="mix snapshots"):
        scorer.score("What?", [candidates[0], replace(candidates[1], passage=changed_passage(candidates[1].passage, snapshot_id="cwe:" + "f" * 64))])
    for size in (0, -1, True):
        with pytest.raises(ValueError, match="batch_size"):
            scorer.score("What?", candidates, batch_size=size)
    assert "Reader query failed" in caplog.text
    assert not calls


def test_oversize_body_no_valid_span_and_config(setup):
    runtime, candidates, calls = setup
    scorer = DPRReaderScorer(runtime)
    candidate = replace(candidates[0], passage=changed_passage(candidates[0].passage, text="source " * 190))
    with pytest.raises(ValueError, match="budget"):
        scorer.score("What?", [candidate])
    assert not calls
    candidate = replace(candidate, passage=changed_passage(candidate.passage, text="[SEP] [PAD]"))
    record = scorer.score("What?", [candidate]).candidates[0]
    assert record.answer_span is None and record.answer_span_reason == "no_valid_passage_tokens"
    with pytest.raises(ValueError, match="frozen"):
        ReaderConfig(max_answer_tokens=65)
