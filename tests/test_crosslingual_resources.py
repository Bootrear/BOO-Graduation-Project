"""Upstream metadata and local LFS checks; not model inference validation."""

import hashlib
import io
import json
from pathlib import Path

import pytest

from scripts.check_crosslingual_resources import download_snapshot, inspect_local
from cyber_qa.crosslingual_resources import upstream_manifest


class Response(io.BytesIO):
    pass


def open_response(payload):
    body = json.dumps(payload).encode()
    return lambda *args, **kwargs: Response(body)


def api_payload(revision="a" * 40, *, lfs=None):
    lfs = lfs or {"size": 4, "sha256": hashlib.sha256(b"data").hexdigest()}
    return {"id": "Qwen/test", "sha": revision,
            "siblings": [{"rfilename": "model.safetensors", "size": lfs["size"], "lfs": lfs}]}


def test_upstream_metadata_is_bound_to_pinned_revision():
    result = upstream_manifest("Qwen/test", "a" * 40, opener=open_response(api_payload()))
    assert result["lfs_bytes"] == 4
    assert result["lfs_files"] == [{"path": "model.safetensors", "size": 4,
                                     "sha256": hashlib.sha256(b"data").hexdigest()}]


def test_upstream_revision_mismatch_is_rejected():
    with pytest.raises(ValueError, match="identity or revision"):
        upstream_manifest("Qwen/test", "a" * 40, opener=open_response(api_payload("b" * 40)))


@pytest.mark.parametrize("lfs", [
    {"size": 0, "sha256": "a" * 64},
    {"size": 4, "sha256": "bad"},
])
def test_malformed_upstream_lfs_metadata_is_rejected(lfs):
    with pytest.raises(ValueError, match="invalid upstream LFS"):
        upstream_manifest("Qwen/test", "a" * 40, opener=open_response(api_payload(lfs=lfs)))


def test_local_lfs_files_are_checked_against_upstream_digest(tmp_path):
    digest = hashlib.sha256(b"data").hexdigest()
    manifest = {"model_id": "Qwen/test", "revision": "a" * 40,
                "lfs_files": [{"path": "model.safetensors", "size": 4, "sha256": digest}]}
    folder = tmp_path / "Qwen--test" / ("a" * 40)
    folder.mkdir(parents=True)
    (folder / "model.safetensors").write_bytes(b"data")
    assert inspect_local(manifest, tmp_path)["verified_local_files"] == ["model.safetensors"]
    (folder / "model.safetensors").write_bytes(b"fake")
    with pytest.raises(ValueError, match="upstream LFS"):
        inspect_local(manifest, tmp_path)


def test_download_uses_immutable_revision_and_revision_scoped_path(tmp_path, monkeypatch):
    seen = {}

    def fake_download(**kwargs):
        seen.update(kwargs)

    import huggingface_hub
    monkeypatch.setattr(huggingface_hub, "snapshot_download", fake_download)
    folder = download_snapshot("Qwen/test", "a" * 40, tmp_path)
    assert folder == tmp_path / "Qwen--test" / ("a" * 40)
    assert seen == {"repo_id": "Qwen/test", "revision": "a" * 40, "local_dir": str(folder)}


def test_download_rejects_moving_revision(tmp_path):
    with pytest.raises(ValueError, match="immutable commit hash"):
        download_snapshot("Qwen/test", "main", tmp_path)
