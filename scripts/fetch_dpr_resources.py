"""Fetch pinned DPR resources; verify upstream weight hashes and resume partial files."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import re
import time
import urllib.request


def weight_metadata(model, revision):
    url = f"https://huggingface.co/api/models/{model}/revision/{revision}?blobs=true"
    with urllib.request.urlopen(url, timeout=30) as response:
        info = json.load(response)
    if info.get("sha") != revision:
        raise ValueError("upstream revision mismatch")
    entry = next(item for item in info["siblings"] if item["rfilename"] == "pytorch_model.bin")
    lfs = entry["lfs"]
    if (type(lfs["size"]) is not int or lfs["size"] <= 0
            or lfs["size"] != entry["size"] or not re.fullmatch(r"[0-9a-f]{64}", lfs["sha256"])):
        raise ValueError("invalid upstream weight metadata")
    return {"size": lfs["size"], "sha256": lfs["sha256"]}


def file_digest(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def download_file(url, partial, expected=None):
    offset = partial.stat().st_size if expected and partial.exists() else 0
    if offset == (expected or {}).get("size") and file_digest(partial) == expected["sha256"]:
        return expected["sha256"]
    if expected and offset >= expected["size"]:
        offset = 0
    request = urllib.request.Request(url, headers={"Range": f"bytes={offset}-"} if offset else {})
    with urllib.request.urlopen(request, timeout=30) as response:
        append = offset > 0 and response.status == 206
        if response.status == 206:
            match = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)", response.headers.get("Content-Range", ""))
            if (not match or int(match[1]) != offset or not expected
                    or int(match[3]) != expected["size"]):
                raise ValueError("invalid partial response range")
        elif response.status != 200:
            raise ValueError("unexpected download response status")
        content_length = response.headers.get("Content-Length")
        received = 0
        with partial.open("ab" if append else "wb") as stream:
            for block in iter(lambda: response.read(1024 * 1024), b""):
                stream.write(block)
                received += len(block)
    if content_length is not None and received != int(content_length):
        raise ValueError("incomplete HTTP response")
    digest = file_digest(partial)
    if expected and (partial.stat().st_size != expected["size"] or digest != expected["sha256"]):
        raise ValueError("upstream weight size/SHA-256 mismatch")
    return digest


def fetch_role(role, spec, root, weights):
    revision = spec["revision"]
    model = spec["model_id"]
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("model revision must be an immutable commit hash")
    if role not in {"question", "context", "reader"} or not re.fullmatch(r"facebook/dpr-[a-z_-]+-nq-base", model):
        raise ValueError("unsupported resource identity")
    target = root / role / revision
    target.mkdir(parents=True, exist_ok=True)
    receipt_path = target / "resources.json"
    receipt = json.loads(receipt_path.read_text()) if receipt_path.exists() else {**spec, "sha256": {}}
    if any(receipt[key] != spec[key] for key in ("model_id", "revision")):
        raise ValueError("cached resource identity mismatch")
    files = ["config.json", "tokenizer.json", "tokenizer_config.json", "vocab.txt"]
    upstream = None
    if weights:
        upstream = weight_metadata(model, revision)
        files.append("pytorch_model.bin")
    for name in files:
        output = target / name
        expected = upstream if name == "pytorch_model.bin" else None
        if output.exists() and name in receipt["sha256"]:
            digest = file_digest(output)
            if expected and (output.stat().st_size != expected["size"] or digest != expected["sha256"]):
                # Keep the rejected cache for diagnosis, never accept its self-recorded hash.
                output.replace(output.with_suffix(".bin.invalid"))
                print(f"{role}: rejected incomplete/corrupt cached weights; downloading again", flush=True)
            elif digest != receipt["sha256"][name]:
                raise ValueError(f"cached file hash mismatch: {output}; remove this corrupt file and retry")
            else:
                if expected:
                    receipt["upstream_weights"] = expected
                    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
                continue
        url = f"https://huggingface.co/{model}/resolve/{revision}/{name}"
        partial = output.with_suffix(output.suffix + ".part")
        for attempt in range(3):
            try:
                digest = download_file(url, partial, expected)
                partial.replace(output)
                receipt["sha256"][name] = digest
                if expected:
                    receipt["upstream_weights"] = expected
                temp = receipt_path.with_suffix(".json.part")
                temp.write_text(json.dumps(receipt, indent=2) + "\n")
                temp.replace(receipt_path)
                break
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(1 + attempt)
    return f"{role}: verified {len(files)} files at {target}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/dpr-models.v1.json"))
    parser.add_argument("--output", type=Path, default=Path("models/dpr"))
    parser.add_argument("--weights", action="store_true", help="Also fetch real PyTorch weights (~1.3 GB total)")
    args = parser.parse_args()
    specs = json.loads(args.config.read_text())
    if set(specs) != {"question", "context", "reader"}:
        raise ValueError("exactly question/context/reader are required")
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = [pool.submit(fetch_role, role, spec, args.output, args.weights) for role, spec in specs.items()]
        for result in results:
            print(result.result(), flush=True)


if __name__ == "__main__":
    main()
