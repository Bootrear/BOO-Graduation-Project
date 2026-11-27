"""Check pinned Hugging Face revisions, LFS metadata, and any local LFS files."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

from cyber_qa.crosslingual_resources import upstream_manifest


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def inspect_local(manifest: dict, model_root: Path) -> dict:
    folder = model_root / manifest["model_id"].replace("/", "--") / manifest["revision"]
    local, missing = [], []
    for item in manifest["lfs_files"]:
        path = folder / item["path"]
        if not path.exists():
            missing.append(item["path"])
            continue
        actual_size = path.stat().st_size
        actual_hash = file_sha256(path)
        if actual_size != item["size"] or actual_hash != item["sha256"]:
            raise ValueError(f"local file does not match upstream LFS metadata: {path}")
        local.append(item["path"])
    return {"model_root": str(folder), "verified_local_files": local, "missing_lfs_files": missing}


def download_snapshot(model_id: str, revision: str, model_root: Path) -> Path:
    """Download one immutable public model snapshot into its revision-scoped folder."""
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("model revision must be an immutable commit hash")
    from huggingface_hub import snapshot_download

    folder = model_root / model_id.replace("/", "--") / revision
    snapshot_download(repo_id=model_id, revision=revision, local_dir=str(folder))
    return folder


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/crosslingual-models.v2.json"))
    parser.add_argument("--model-root", type=Path, default=Path("models/crosslingual"))
    parser.add_argument("--download", action="store_true",
                        help="download each pinned model snapshot before checking its LFS files")
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    if config.get("version") != "crosslingual-rag-v2" or set(config.get("models", {})) != {"embedding", "generation"}:
        raise ValueError("crosslingual-rag-v2 embedding and generation models are required")
    report = {"config_version": config["version"], "models": {}}
    for role, spec in config["models"].items():
        metadata = upstream_manifest(spec["model_id"], spec["revision"])
        if args.download:
            download_snapshot(spec["model_id"], spec["revision"], args.model_root)
        report["models"][role] = {**metadata, **inspect_local(metadata, args.model_root)}
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
