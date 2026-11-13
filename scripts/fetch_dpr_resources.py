"""Fetch public DPR resources at pinned revisions, with resumable verified caches."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import re
import time
import urllib.request


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
    if weights:
        files.append("pytorch_model.bin")
    for name in files:
        output = target / name
        if output.exists() and name in receipt["sha256"]:
            cached_hash = hashlib.sha256()
            with output.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    cached_hash.update(block)
            digest = cached_hash.hexdigest()
            if digest != receipt["sha256"][name]:
                raise ValueError(f"cached file hash mismatch: {output}; remove this corrupt file and retry")
            continue
        url = f"https://huggingface.co/{model}/resolve/{revision}/{name}"
        partial = output.with_suffix(output.suffix + ".part")
        for attempt in range(3):
            try:
                digest = hashlib.sha256()
                with urllib.request.urlopen(url, timeout=30) as response, partial.open("wb") as stream:
                    for block in iter(lambda: response.read(1024 * 1024), b""):
                        stream.write(block)
                        digest.update(block)
                partial.replace(output)
                receipt["sha256"][name] = digest.hexdigest()
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
