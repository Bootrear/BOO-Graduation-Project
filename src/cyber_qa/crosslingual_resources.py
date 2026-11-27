"""Upstream Hugging Face pinned-revision LFS metadata access."""

import json
import re
import urllib.request


def upstream_manifest(model_id: str, revision: str, *, opener=urllib.request.urlopen) -> dict:
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("model revision must be an immutable commit hash")
    url = f"https://huggingface.co/api/models/{model_id}/revision/{revision}?blobs=true"
    with opener(url, timeout=30) as response:
        info = json.load(response)
    if info.get("id") != model_id or info.get("sha") != revision:
        raise ValueError("upstream model identity or revision mismatch")
    files = []
    for item in info.get("siblings", []):
        lfs = item.get("lfs")
        if lfs is None:
            continue
        size, digest = lfs.get("size"), lfs.get("sha256")
        if (type(size) is not int or size <= 0 or item.get("size") != size
                or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)):
            raise ValueError(f"invalid upstream LFS metadata: {item.get('rfilename')}")
        files.append({"path": item["rfilename"], "size": size, "sha256": digest})
    if not files:
        raise ValueError("upstream revision has no LFS files")
    return {"model_id": model_id, "revision": revision, "lfs_files": files,
            "lfs_bytes": sum(item["size"] for item in files)}
