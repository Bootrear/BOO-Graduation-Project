"""Load pinned local DPR tokenizer assets without implicit network requests."""

import hashlib
import json
from pathlib import Path
import re


def load_tokenizers(config_path="configs/dpr-models.v1.json", model_root="models/dpr"):
    from transformers import (
        DPRContextEncoderTokenizerFast, DPRQuestionEncoderTokenizerFast, DPRReaderTokenizerFast,
    )

    classes = {"question": DPRQuestionEncoderTokenizerFast,
               "context": DPRContextEncoderTokenizerFast, "reader": DPRReaderTokenizerFast}

    specs = json.loads(Path(config_path).read_text())
    if set(specs) != {"question", "context", "reader"}:
        raise ValueError("question/context/reader resource specs required")
    tokenizers, provenance = {}, {}
    for role, spec in specs.items():
        if not re.fullmatch(r"[0-9a-f]{40}", spec["revision"]):
            raise ValueError("immutable model revision required")
        path = Path(model_root) / role / spec["revision"]
        receipt = json.loads((path / "resources.json").read_text())
        if any(receipt[k] != spec[k] for k in ("model_id", "revision")):
            raise ValueError("resource receipt identity mismatch")
        hashes = {}
        for filename in ("config.json", "tokenizer.json", "tokenizer_config.json", "vocab.txt"):
            hashes[filename] = hashlib.sha256((path / filename).read_bytes()).hexdigest()
            if hashes[filename] != receipt["sha256"][filename]:
                raise ValueError(f"resource checksum mismatch: {path / filename}")
        # These legacy repos all advertise the question-tokenizer class. Select
        # the actual role explicitly, especially Reader's three-part layout.
        tokenizer = classes[role].from_pretrained(path, local_files_only=True)
        if not tokenizer.is_fast:
            raise ValueError("fast tokenizer with character offsets required")
        model_config = json.loads((path / "config.json").read_text())
        if model_config["max_position_embeddings"] != 512:
            raise ValueError("unverified model position limit")
        tokenizers[role] = tokenizer
        provenance[role] = {**spec, "tokenizer_class": type(tokenizer).__name__, "sha256": hashes}
    if not tokenizers["context"].get_vocab() == tokenizers["reader"].get_vocab() == tokenizers["question"].get_vocab():
        raise ValueError("chunking requires the verified shared DPR vocabulary")
    return tokenizers, provenance
