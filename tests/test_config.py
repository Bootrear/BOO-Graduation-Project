import json
from pathlib import Path

import pytest

from cyber_qa.config import BaselineConfig


def test_checked_in_config_matches_frozen_defaults():
    path = Path(__file__).resolve().parents[1] / "configs" / "baseline.v1.json"
    assert BaselineConfig.load(path) == BaselineConfig()


@pytest.mark.parametrize("changes", [
    {"candidate_count": 0}, {"candidate_count": True},
    {"max_passages": -1}, {"max_passages": 1.5},
    {"lambda_weight": -0.1}, {"lambda_weight": 1.1},
    {"lambda_weight": float("nan")}, {"lambda_weight": float("inf")},
    {"lambda_weight": True}, {"epsilon": 0}, {"epsilon": 1e-6},
    {"similarity": "raw_cosine"}, {"parameter_status": "tuned"},
    {"relevance_normalization": "per_round_minmax"},
])
def test_rejects_invalid_or_silently_changed_baseline(changes):
    with pytest.raises(ValueError):
        BaselineConfig(**changes)


def test_zero_k_and_lambda_endpoints_are_legal():
    assert BaselineConfig(max_passages=0, lambda_weight=0).max_passages == 0
    assert BaselineConfig(lambda_weight=1).lambda_weight == 1
    assert BaselineConfig(candidate_count=1, max_passages=5).max_passages == 5


@pytest.mark.parametrize("payload", ['[]', '{"max_passages":1,"max_passages":2}', '{"lamda":0.5}'])
def test_bad_config_fails_before_running_models(tmp_path, payload):
    path = tmp_path / "config.json"
    path.write_text(payload)
    with pytest.raises(ValueError):
        BaselineConfig.load(path)


def test_config_round_trip(tmp_path):
    original = BaselineConfig(candidate_count=3, max_passages=0, lambda_weight=1)
    path = tmp_path / "config.json"
    path.write_text(json.dumps(original.to_dict()))
    assert BaselineConfig.load(path) == original
