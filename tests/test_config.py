from pathlib import Path

import pytest

from swarmhazard.config import Config, config_hash, from_dict, load_config

BASELINE = Path(__file__).resolve().parents[1] / "configs" / "baseline.yaml"


def test_baseline_yaml_matches_defaults():
    assert load_config(BASELINE) == Config()


def test_overrides_apply():
    cfg = load_config(BASELINE, controller="C2", n_robots=5)
    assert cfg.controller == "C2"
    assert cfg.n_robots == 5


def test_unknown_key_rejected():
    with pytest.raises(KeyError):
        from_dict({"n_robot": 5})


def test_unknown_controller_rejected():
    with pytest.raises(ValueError):
        Config(controller="C9")


def test_patch_overlapping_hazard_rejected():
    with pytest.raises(ValueError):
        Config(hazards=((7.5, 7.5, 1.0),))


def test_hash_stable_and_sensitive():
    assert config_hash(Config()) == config_hash(Config())
    assert config_hash(Config()) != config_hash(Config(n_robots=21))
    assert len(config_hash(Config())) == 12


@pytest.mark.parametrize("field, value", [("q_miss", -0.1), ("q_false", 1.5)])
def test_noise_probabilities_validated(field, value):
    with pytest.raises(ValueError):
        Config(**{field: value})


@pytest.mark.parametrize("field, value", [("share_every", 0), ("comm_range", -1.0)])
def test_c5_settings_validated(field, value):
    with pytest.raises(ValueError):
        Config(**{field: value})


@pytest.mark.parametrize("field, value", [("risk_k", -0.5), ("metric_every", 0)])
def test_more_settings_validated(field, value):
    with pytest.raises(ValueError):
        Config(**{field: value})
