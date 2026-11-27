"""Index integrity and cosine retrieval contracts (no model inference)."""

import json

import numpy as np
import pytest

from cyber_qa.retrieval.crosslingual import load_index, search, validate_index_arrays, write_index


def test_validation_rejects_nonfinite_zero_and_duplicate_ids():
    with pytest.raises(ValueError, match="NaN or Inf"):
        validate_index_arrays(np.array([[float("nan")]], dtype=np.float32), ["a"])
    with pytest.raises(ValueError, match="zero vector"):
        validate_index_arrays(np.array([[0.0, 0.0]], dtype=np.float32), ["a"])
    with pytest.raises(ValueError, match="unique"):
        validate_index_arrays(np.array([[1.0], [2.0]], dtype=np.float32), ["a", "a"])


def test_write_load_search_and_compatibility_checks(tmp_path):
    output = tmp_path / "idx"
    vectors = np.array([[1, 0], [0.8, 0.6], [0, 1]], dtype=np.float32)
    ids = ["p-a", "p-b", "p-c"]
    records = [{"passage_id": pid, "text": pid} for pid in ids]
    write_index(output, vectors, ids, records,
                {"snapshot_id": "snap", "model_revision": "rev"})
    manifest, loaded, loaded_ids, loaded_records = load_index(
        output, expected_snapshot_id="snap", expected_model_revision="rev")
    assert manifest["count"] == 3
    assert loaded.dtype == np.float32
    assert loaded_ids == ids
    assert loaded_records == records
    assert [row["passage_id"] for row in search(loaded, loaded_ids, np.array([1.0, 0.0]), 2)] == ["p-a", "p-b"]
    with pytest.raises(ValueError, match="snapshot"):
        load_index(output, expected_snapshot_id="other")
    with pytest.raises(ValueError, match="model revision"):
        load_index(output, expected_model_revision="other")


def test_load_detects_tampering_and_write_refuses_overwrite(tmp_path):
    output = tmp_path / "idx"
    vectors = np.array([[1.0, 0.0]], dtype=np.float32)
    write_index(output, vectors, ["p"], [{"passage_id": "p"}],
                {"snapshot_id": "s", "model_revision": "r"})
    with pytest.raises(FileExistsError):
        write_index(output, vectors, ["p"], [{"passage_id": "p"}], {})
    with (output / "passage_ids.json").open("a") as stream:
        stream.write(" ")
    with pytest.raises(ValueError, match="hash mismatch"):
        load_index(output)


@pytest.mark.parametrize("query, top_n, message", [
    (np.array([0.0, 0.0]), 1, "non-zero"),
    (np.array([float("inf"), 0.0]), 1, "finite"),
    (np.array([1.0]), 1, "dimension"),
    (np.array([1.0, 0.0]), -1, "non-negative"),
])
def test_search_rejects_invalid_query_or_limit(query, top_n, message):
    with pytest.raises(ValueError, match=message):
        search(np.array([[1.0, 0.0]], dtype=np.float32), ["p"], query, top_n)
