"""Offline transport regressions; these do not constitute model validation."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("fetch_dpr_resources", Path(__file__).parents[1] / "scripts/fetch_dpr_resources.py")
fetch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch)


class Response(io.BytesIO):
    def __init__(self, body, status=200, **headers):
        super().__init__(body)
        self.status = status
        self.headers = headers


def metadata(body):
    return {"size": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def test_truncated_http_body_not_promoted(tmp_path, monkeypatch):
    partial = tmp_path / "weights.part"
    monkeypatch.setattr(fetch.urllib.request, "urlopen", lambda *a, **kw: Response(b"short", **{"Content-Length": "10"}))
    with pytest.raises(ValueError, match="incomplete HTTP"):
        fetch.download_file("https://example.invalid/weights", partial, metadata(b"0123456789"))
    assert partial.read_bytes() == b"short"


@pytest.mark.parametrize("data", [b"short", b"wrong byte"])
def test_upstream_size_and_hash_are_required(tmp_path, monkeypatch, data):
    monkeypatch.setattr(fetch.urllib.request, "urlopen", lambda *a, **kw: Response(data))
    with pytest.raises(ValueError, match="upstream weight"):
        fetch.download_file("https://example.invalid/w", tmp_path / "w.part", metadata(b"0123456789"))


@pytest.mark.parametrize("supports_range", [True, False])
def test_resume_or_restart_on_server_ignoring_range(tmp_path, monkeypatch, supports_range):
    partial = tmp_path / "w.part"
    partial.write_bytes(b"0123")
    body = b"0123456789"
    def response(request, **kwargs):
        assert request.get_header("Range") == "bytes=4-"
        if supports_range:
            return Response(body[4:], 206, **{"Content-Range": "bytes 4-9/10", "Content-Length": "6"})
        return Response(body)
    monkeypatch.setattr(fetch.urllib.request, "urlopen", response)
    assert fetch.download_file("https://example.invalid/w", partial, metadata(body)) == metadata(body)["sha256"]
    assert partial.read_bytes() == body


def test_bad_range_does_not_modify_partial(tmp_path, monkeypatch):
    partial = tmp_path / "w.part"
    partial.write_bytes(b"0123")
    monkeypatch.setattr(fetch.urllib.request, "urlopen", lambda *a, **kw: Response(b"wrong", 206, **{"Content-Range": "bytes 0-4/10"}))
    with pytest.raises(ValueError, match="range"):
        fetch.download_file("https://example.invalid/w", partial, metadata(b"0123456789"))
    assert partial.read_bytes() == b"0123"


def test_self_consistent_truncated_cache_is_replaced(tmp_path, monkeypatch):
    identity = {"model_id": "facebook/dpr-question_encoder-single-nq-base", "revision": "a" * 40}
    folder = tmp_path / "question" / identity["revision"]
    folder.mkdir(parents=True)
    receipt = {**identity, "sha256": {}}
    for name in ("config.json", "tokenizer.json", "tokenizer_config.json", "vocab.txt", "pytorch_model.bin"):
        (folder / name).write_bytes(b"old")
        receipt["sha256"][name] = metadata(b"old")["sha256"]
    (folder / "resources.json").write_text(json.dumps(receipt))
    body = b"complete weights"
    monkeypatch.setattr(fetch, "weight_metadata", lambda *a: metadata(body))
    monkeypatch.setattr(fetch.urllib.request, "urlopen", lambda *a, **kw: Response(body))
    fetch.fetch_role("question", identity, tmp_path, True)
    assert (folder / "pytorch_model.bin").read_bytes() == body
    assert (folder / "pytorch_model.bin.invalid").read_bytes() == b"old"
    saved = json.loads((folder / "resources.json").read_text())
    assert saved["upstream_weights"] == metadata(body)
    assert saved["sha256"]["pytorch_model.bin"] == metadata(body)["sha256"]


def test_upstream_revision_mismatch_rejected(monkeypatch):
    monkeypatch.setattr(fetch.urllib.request, "urlopen", lambda *a, **kw: Response(b'{"sha":"wrong"}'))
    with pytest.raises(ValueError, match="revision"):
        fetch.weight_metadata("facebook/dpr-question_encoder-single-nq-base", "a" * 40)
