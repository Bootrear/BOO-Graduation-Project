"""Chinese parallel set must preserve every source annotation except question."""

import hashlib

import pytest

from cyber_qa.experiments.chinese_probe import (
    make_parallel_record, question_sha256, translate_question, validate_parallel,
)


def source_record():
    return {"question_id": "probe-001", "question": "What is CWE-89?", "language": "en",
            "required_evidence_ids": ["p1"], "gold_facts": [{"fact_id": "f1", "text": "fact"}],
            "source_snapshot": "snap", "reviewer": None}


def test_parallel_record_preserves_source_fields_and_adds_translation_provenance():
    source = source_record()
    translated = make_parallel_record(source, "CWE-89 是什么？")
    validate_parallel([source], [translated])
    assert translated["question"] == "CWE-89 是什么？"
    assert translated["source_question_sha256"] == hashlib.sha256(b"What is CWE-89?").hexdigest()
    for key, value in source.items():
        if key != "question":
            assert translated[key] == value


@pytest.mark.parametrize("mutate", [
    lambda r: r.update(required_evidence_ids=["wrong"]),
    lambda r: r.update(gold_facts=[]),
    lambda r: r.update(source_snapshot="wrong"),
    lambda r: r.update(source_question_sha256="0" * 64),
    lambda r: r.update(translation_status="human_reviewed"),
    lambda r: r.update(question=""),
])
def test_parallel_validation_rejects_changed_or_unmarked_fields(mutate):
    source = source_record()
    translated = make_parallel_record(source, "CWE-89 是什么？")
    mutate(translated)
    with pytest.raises(ValueError):
        validate_parallel([source], [translated])


def test_question_hash_is_stable_utf8():
    assert question_sha256("问题") == hashlib.sha256("问题".encode()).hexdigest()


def test_translation_returns_only_decoded_answer():
    class Batch(dict):
        def to(self, device):
            return self

    class Tokenizer:
        def apply_chat_template(self, messages, **kwargs):
            return "prompt"

        def __call__(self, prompt, **kwargs):
            return Batch(input_ids=__import__("torch").tensor([[1, 2]]))

        def decode(self, tokens, **kwargs):
            return '  “CWE-89 是什么？”\n'

    class Model:
        def eval(self):
            return self

        def generate(self, input_ids, **kwargs):
            import torch
            return torch.tensor([[1, 2, 3]])

    assert translate_question(Model(), Tokenizer(), "What is CWE-89?", device="cpu") == "CWE-89 是什么？"
