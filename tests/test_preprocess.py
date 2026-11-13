import json
from pathlib import Path
import re

import pytest

from cyber_qa.data.chunking import InputBudget, split_text, token_ids
from cyber_qa.data.preprocess import build_snapshot, load_snapshot
from cyber_qa.resources import load_tokenizers


@pytest.fixture(scope="module")
def real_tokenizers():
    pytest.importorskip("transformers", reason="real tokenizer validation requires tokenization extra")
    root = Path(__file__).resolve().parents[1]
    config = root / "configs/dpr-models.v1.json"
    models = root / "models/dpr"
    specs = json.loads(config.read_text())
    if not all((models / role / spec["revision"] / "resources.json").exists() for role, spec in specs.items()):
        pytest.skip("pinned real tokenizer files missing; run scripts/fetch_dpr_resources.py")
    return load_tokenizers(config, models)[0]


@pytest.mark.parametrize("changes", [
    {"context_max_tokens": 0}, {"reader_max_tokens": 513}, {"special_tokens": 4},
    {"title_max_tokens": 300}, {"long_question_policy": "silently_truncate"},
])
def test_invalid_input_budget(changes):
    with pytest.raises(ValueError):
        InputBudget(**changes)


def test_actual_reader_layout_and_context_budget(real_tokenizers):
    q, title, text = "What is the condition?", "A title", "A short source."
    context, reader = real_tokenizers["context"], real_tokenizers["reader"]
    q_ids, title_ids, body_ids = (token_ids(reader, s) for s in (q, title, text))
    assert reader(q, title, text)["input_ids"][0] == [reader.cls_token_id] + q_ids + [reader.sep_token_id] + title_ids + [reader.sep_token_id] + body_ids
    assert context(title, text)["input_ids"] == [context.cls_token_id] + title_ids + [context.sep_token_id] + body_ids + [context.sep_token_id]
    assert InputBudget().passage_max_tokens == 189


def test_real_tokenizer_chunks_preserve_text_and_budget(real_tokenizers):
    tokenizer = real_tokenizers["context"]
    text = "A condition applies to this example.\n" * 100 + "Unusuallylongwordpieceexample" * 20 + "."
    chunks = split_text(text, tokenizer, 20)
    assert len(chunks) > 1
    assert all(c in text and 0 < len(token_ids(tokenizer, c)) <= 20 for c in chunks)
    assert re.sub(r"\s", "", "".join(chunks)) == re.sub(r"\s", "", text)
    assert split_text(text, tokenizer, 20) == chunks
    assert split_text("", tokenizer, 20) == []
    with pytest.raises(ValueError):
        split_text(text, tokenizer, 0)


def test_snapshot_reproducibility_atomicity_and_tampering(tmp_path, real_tokenizers):
    # Authored synthetic CWE structure; real DPR tokenizer, no fake model inference.
    raw = tmp_path / "fixture.xml"
    raw.write_text('<Weakness_Catalog xmlns="http://cwe.mitre.org/cwe-7" Version="4.20">'
                   '<Weaknesses><Weakness ID="1" Name="Fixture"><Description>'
                   + "A very long fixture source with an explicit condition. " * 100
                   + '</Description></Weakness></Weaknesses></Weakness_Catalog>')
    root = Path(__file__).resolve().parents[1]
    kwargs = {"model_config": root / "configs/dpr-models.v1.json", "model_root": root / "models/dpr"}
    a, b = tmp_path / "a", tmp_path / "b"
    first, stats = build_snapshot(raw, a, **kwargs)
    second, _ = build_snapshot(raw, b, **kwargs)
    assert first.snapshot_id == second.snapshot_id
    assert (a / "passages.jsonl").read_bytes() == (b / "passages.jsonl").read_bytes()
    loaded, passages = load_snapshot(a)
    assert loaded == first
    assert len(passages) == stats["final_passages"] > 1
    assert first.acquired_at is None and first.acquired_at_basis == "unknown"
    with pytest.raises(FileExistsError):
        build_snapshot(raw, a, **kwargs)
    corpus = a / "passages.jsonl"
    corpus.write_text(corpus.read_text().splitlines()[0] + "\n")
    with pytest.raises(ValueError, match="checksum"):
        load_snapshot(a)


def test_wrong_download_receipt_rejected(tmp_path, real_tokenizers):
    raw = tmp_path / "fixture.xml"
    raw.write_text('<Weakness_Catalog xmlns="http://cwe.mitre.org/cwe-7" Version="4.20"><Weaknesses/></Weakness_Catalog>')
    receipt = tmp_path / "receipt.json"
    receipt.write_text('{"raw_file_sha256":"wrong"}')
    root = Path(__file__).resolve().parents[1]
    with pytest.raises(ValueError, match="receipt"):
        build_snapshot(raw, tmp_path / "out", receipt_path=receipt,
                       model_config=root / "configs/dpr-models.v1.json", model_root=root / "models/dpr")
    assert not (tmp_path / "out").exists()
