"""Index contract tests with synthetic embeddings, independent of real inference."""
from dataclasses import asdict
import json
from types import SimpleNamespace

import pytest

np = pytest.importorskip("numpy")
from cyber_qa.data.chunking import InputBudget
from cyber_qa.data.contracts import SourceUnit, make_manifest, make_passage
from cyber_qa.models import DPRRuntime, file_sha256, validate_vectors
from cyber_qa.retrieval import dpr


@pytest.fixture
def corpus(tmp_path, monkeypatch):
    budget = InputBudget()
    manifest = make_manifest(dataset_name="CWE", dataset_version="fixture",
        source_download_url="https://example.invalid", raw_file_sha256="0" * 64,
        acquired_at=None, acquired_at_basis="unknown", registered_at="2026-11-16T00:00:00Z",
        processed_at="2026-11-16T00:00:00Z", parser_version="fixture", chunker_version="fixture",
        preprocessing_config={"input_budget": budget.to_dict(), "tokenizers": {}})
    passages = []
    for i in range(3):
        unit = SourceUnit(cwe_id=f"CWE-{i+1}", title=f"Title {i}", field_name="description",
            source_locator=f"/fixture/{i}", source_text=f"Source text {i}.",
            source_url=f"https://example.invalid/{i}", dataset_version="fixture", entry_status=None)
        passages.append(make_passage(unit, manifest, 0, unit.source_text))
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    (snapshot / "manifest.json").write_text(json.dumps(manifest.to_dict()))
    (snapshot / "passages.jsonl").write_text("".join(json.dumps(asdict(p)) + "\n" for p in passages))
    (snapshot / "statistics.json").write_text(json.dumps({"final_passages": 3,
        "passages_sha256": file_sha256(snapshot / "passages.jsonl")}))
    vectors = np.zeros((3, 768), dtype=np.float32)
    vectors[:, :2] = [[10, 1], [2, 0], [2, 0]]
    runtime = SimpleNamespace(budget=budget, provenance={}, weight_hashes={"context": "a" * 64},
        model_load_seconds=0, device="fixture", loading_info={"context": {}}, verify_weights=lambda role: "a" * 64,
        assert_snapshot_compatible=lambda m: None, encode_context=lambda *a, **kw: vectors.copy())
    monkeypatch.setattr(dpr, "version", lambda name: "fixture")
    output = tmp_path / "index"
    dpr.build_index(snapshot, output, runtime)
    return snapshot, output, runtime, passages, vectors


def test_roundtrip_raw_inner_product_ties_and_sources(corpus):
    snapshot, folder, runtime, passages, vectors = corpus
    index = dpr.load_index(folder, snapshot, runtime)
    query = np.zeros(768, dtype=np.float32)
    query[0] = 1
    result = index.search(query, n=20)
    assert len(result) == 3
    assert result[0].passage == passages[0]
    assert result[0].retrieval_score == 10  # cosine would favor the other two
    assert [c.passage_id for c in result[1:]] == sorted(p.passage_id for p in passages[1:])
    assert [c.retrieval_rank for c in result] == [1, 2, 3]
    assert len({c.passage_id for c in result}) == 3
    assert np.array_equal(vectors, index.vectors)
    assert not index.vectors.flags.writeable
    assert index.search(query, 1) == result[:1]
    assert dpr.load_index(folder, snapshot).search(query) == result
    with pytest.raises(FileExistsError):
        dpr.build_index(snapshot, folder, runtime)


@pytest.mark.parametrize("key,value", [
    ("snapshot_id", "wrong"), ("dimension", 2), ("metric", "cosine"),
    ("normalized", True), ("model_provenance", {"question": "wrong"}),
    ("input_budget", {}), ("context_weight_sha256", "b" * 64),
])
def test_incompatible_metadata_rejected(corpus, key, value):
    snapshot, folder, runtime, _, _ = corpus
    path = folder / "index_manifest.json"
    meta = json.loads(path.read_text())
    meta[key] = value
    path.write_text(json.dumps(meta))
    with pytest.raises(ValueError):
        dpr.load_index(folder, snapshot, runtime)


def test_mapping_order_rejected_even_if_checksum_updated(corpus):
    snapshot, folder, runtime, _, _ = corpus
    path = folder / "passage_ids.json"
    path.write_text(json.dumps(json.loads(path.read_text())[::-1]))
    meta_path = folder / "index_manifest.json"
    meta = json.loads(meta_path.read_text())
    meta["passage_ids_sha256"] = file_sha256(path)
    meta_path.write_text(json.dumps(meta))
    with pytest.raises(ValueError, match="mapping"):
        dpr.load_index(folder, snapshot, runtime)


def test_corrupt_vectors_fail_checksum(corpus):
    snapshot, folder, runtime, _, _ = corpus
    path = folder / "vectors.npy"
    with path.open("ab") as stream:
        stream.write(b"corruption")
    with pytest.raises(ValueError, match="checksum"):
        dpr.load_index(folder, snapshot, runtime)


@pytest.mark.parametrize("array", [np.zeros((1, 2)), np.array([[np.nan, 1]]), np.array([[np.inf, 1]]), np.ones(2)])
def test_bad_vectors_fail(array):
    with pytest.raises(ValueError):
        validate_vectors(array)


def test_search_invalid_queries_and_empty_index(corpus):
    _, _, _, passages, vectors = corpus
    with pytest.raises(ValueError, match="duplicate"):
        dpr.DPRIndex(vectors, [passages[0]] * 3, {})
    index = dpr.DPRIndex(vectors.copy(), passages, {})
    for query, n in [(np.ones(3), 20), (np.zeros(768), 20), (np.ones(768), 0)]:
        with pytest.raises(ValueError):
            index.search(query, n)
    empty = dpr.DPRIndex(np.empty((0, 768), dtype=np.float32), [], {})
    assert empty.search(np.ones(768)) == ()


def test_runtime_rejects_unverified_legacy_weights(tmp_path):
    runtime = DPRRuntime.__new__(DPRRuntime)
    runtime.model_root = tmp_path
    runtime.provenance = {"question": {"revision": "a" * 40}}
    folder = tmp_path / "question" / ("a" * 40)
    folder.mkdir(parents=True)
    (folder / "resources.json").write_text('{"sha256":{}}')
    with pytest.raises(ValueError, match="upstream-verified"):
        runtime.verify_weights("question")


def test_runtime_verifies_cached_weight_size_and_hash(tmp_path):
    runtime = DPRRuntime.__new__(DPRRuntime)
    runtime.model_root = tmp_path
    runtime.provenance = {"context": {"revision": "a" * 40}}
    folder = tmp_path / "context" / ("a" * 40)
    folder.mkdir(parents=True)
    weight = folder / "pytorch_model.bin"
    weight.write_bytes(b"synthetic fixture weights")
    digest = file_sha256(weight)
    (folder / "resources.json").write_text(json.dumps({"upstream_weights": {
        "size": weight.stat().st_size, "sha256": digest}, "sha256": {"pytorch_model.bin": digest}}))
    assert runtime.verify_weights("context") == digest
    weight.write_bytes(b"broken")
    with pytest.raises(ValueError, match="size/checksum"):
        runtime.verify_weights("context")


def test_checkpoint_only_ignores_confirmed_unused_parameters():
    from cyber_qa.models import validate_loading_info
    allowed = ['ctx_encoder.bert_model.pooler.dense.weight', 'ctx_encoder.bert_model.pooler.dense.bias']
    validate_loading_info('context', {'unexpected_keys': allowed})
    for bad in ({'unexpected_keys': ['ctx_encoder.bert_model.encoder.layer.0.unknown']},
                {'missing_keys': ['ctx_encoder.bert_model.encoder.layer.0.attention.self.query.weight']},
                {'mismatched_keys': ['anything']}, {'error_msgs': ['failed']}):
        with pytest.raises(ValueError, match='did not load completely'):
            validate_loading_info('context', bad)
