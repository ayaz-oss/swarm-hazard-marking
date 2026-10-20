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


@pytest.mark.parametrize("kw", [dict(miss_run=-1.0), dict(miss_run=0.5, q_miss=0.2),
                                dict(miss_run=10.0, q_miss=1.0), dict(miss_run=2.0, q_miss=0.8)])
def test_bad_miss_run_rejected(kw):
    with pytest.raises(ValueError):
        Config(**kw)


def test_good_miss_run_accepted():
    Config(miss_run=100.0, q_miss=0.8)
    Config(miss_run=4.0, q_miss=0.8)  # entry probability exactly 1


def test_hazard_move_validation():
    with pytest.raises(ValueError):
        Config(hazards_after=((1.19, 3.81, 1.0),))            # no move step
    with pytest.raises(ValueError):
        Config(hazard_move_step=-2)
    with pytest.raises(ValueError):
        Config(hazard_move_step=10, hazards_after=((2.5, 2.5, 1.0),))  # overlaps a patch
    Config(hazard_move_step=10, hazards_after=((1.19, 3.81, 1.0),))
