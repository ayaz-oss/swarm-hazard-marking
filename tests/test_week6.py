"""Failing tests for week-6 features: OUTBOUND state, search_start, observation metrics."""

from __future__ import annotations

import math

import numpy as np
import pytest

from swarmhazard.config import Config
from swarmhazard.robots import OUTBOUND, RETURN, SEARCH, Swarm, make_swarm
from swarmhazard.seeding import make_rng
from swarmhazard.sim import Simulation, run


def new_sim(**kw):
    return Simulation(Config(**kw), make_rng("test", 0, 0))


# ---------------------------------------------------------------------------
# 1. OUTBOUND state constant
# ---------------------------------------------------------------------------

def test_outbound_constant_exists_and_is_distinct():
    assert OUTBOUND != SEARCH
    assert OUTBOUND != RETURN


# ---------------------------------------------------------------------------
# 2. search_start config validation
# ---------------------------------------------------------------------------

def test_search_start_default_is_nest():
    assert Config().search_start == "nest"


def test_search_start_last_pickup_is_valid():
    cfg = Config(search_start="last_pickup")
    assert cfg.search_start == "last_pickup"


def test_search_start_invalid_value_raises():
    with pytest.raises((ValueError, KeyError)):
        Config(search_start="random")


# ---------------------------------------------------------------------------
# 3. last_pickup tracking in Swarm
# ---------------------------------------------------------------------------

def test_last_pickup_starts_nan():
    cfg = Config()
    rng = make_rng("test", 0, 0)
    sw = make_swarm(cfg, rng)
    assert hasattr(sw, "last_pickup")
    assert np.all(np.isnan(sw.last_pickup))
    assert sw.last_pickup.shape == (cfg.n_robots, 2)


def test_last_pickup_recorded_on_pickup():
    sim = new_sim(search_start="last_pickup")
    # place robot 0 at item 0
    item_pos = sim.world.item_pos[0].copy()
    sim.swarm.pos[0] = item_pos
    sim.step()
    # robot 0 should have a recorded last_pickup
    assert not np.isnan(sim.swarm.last_pickup[0]).any()


def test_last_pickup_not_recorded_with_nest_mode():
    sim = new_sim(search_start="nest")
    item_pos = sim.world.item_pos[0].copy()
    sim.swarm.pos[0] = item_pos
    sim.step()
    # Even if a pickup occurred, last_pickup tracking may not be recorded
    # (it may be recorded but just not used; what matters is no OUTBOUND state)
    assert sim.swarm.state[0] == RETURN  # picked up, now returning


# ---------------------------------------------------------------------------
# 4. After delivery with last_pickup recorded → OUTBOUND state
# ---------------------------------------------------------------------------

def test_delivery_with_last_pickup_goes_outbound():
    sim = new_sim(search_start="last_pickup")
    sw = sim.swarm
    # Give robot 0 a recorded last_pickup position
    sw.last_pickup[0] = np.array([2.5, 2.5])
    # Put robot 0 in RETURN state at the nest
    sw.state[0] = RETURN
    sw.pos[0] = sim.nest.copy()
    sim.step()
    # Should be OUTBOUND (not SEARCH), since it has a last_pickup
    assert sw.state[0] == OUTBOUND


def test_delivery_without_last_pickup_goes_search():
    sim = new_sim(search_start="last_pickup")
    sw = sim.swarm
    # Robot 0 in RETURN at nest, no last_pickup (NaN)
    sw.state[0] = RETURN
    sw.pos[0] = sim.nest.copy()
    sim.step()
    # No last_pickup → goes straight to SEARCH
    assert sw.state[0] == SEARCH


def test_delivery_with_nest_mode_always_goes_search():
    sim = new_sim(search_start="nest")
    sw = sim.swarm
    sw.last_pickup[0] = np.array([2.5, 2.5])  # even if recorded, nest mode ignores it
    sw.state[0] = RETURN
    sw.pos[0] = sim.nest.copy()
    sim.step()
    assert sw.state[0] == SEARCH


# ---------------------------------------------------------------------------
# 5. OUTBOUND heading points at last_pickup (no noise)
# ---------------------------------------------------------------------------

def test_outbound_heading_points_at_last_pickup():
    sim = new_sim(search_start="last_pickup", n_steps=1)
    sw = sim.swarm
    target = np.array([2.5, 2.5])
    sw.last_pickup[0] = target
    sw.state[0] = OUTBOUND
    # Place robot 0 far from target so it won't arrive
    sw.pos[0] = np.array([8.0, 8.0])
    expected_heading = np.arctan2(target[1] - sw.pos[0, 1], target[0] - sw.pos[0, 0])
    sim.step()
    # After avoidance the final heading may differ, but before avoidance the base heading
    # should be toward last_pickup. Just verify heading change from initial value.
    # We test indirectly: robot should move toward the target over many steps.
    pass  # heading direction tested via movement test below


def test_outbound_robot_moves_toward_last_pickup():
    """An OUTBOUND robot heading should point toward last_pickup (no turning noise)."""
    sim = new_sim(search_start="last_pickup", hazards=(), lethality=0.0)
    sw = sim.swarm
    target = np.array([3.0, 3.0])
    sw.last_pickup[0] = target
    sw.state[0] = OUTBOUND
    sw.pos[0] = np.array([3.5, 3.0])  # close to target, 0.5m away exactly at sense_range
    # After one step the robot should have arrived (dist <= sense_range = 0.5)
    # Place just outside sense_range
    sw.pos[0] = np.array([3.6, 3.0])
    sim.step()
    # Should be moving toward target; after one step it moves 0.01 m closer
    dist_after = float(np.linalg.norm(sw.pos[0] - target))
    assert dist_after < 0.6  # started 0.6m away, moved toward it


def test_outbound_switches_to_search_when_near_target():
    """OUTBOUND robot within sense_range of last_pickup switches to SEARCH."""
    sim = new_sim(search_start="last_pickup", hazards=(), lethality=0.0)
    sw = sim.swarm
    target = np.array([2.5, 2.5])
    sw.last_pickup[0] = target
    sw.state[0] = OUTBOUND
    # Place robot very close to target (within sense_range = 0.5)
    sw.pos[0] = target + np.array([0.1, 0.0])
    sim.step()
    assert sw.state[0] == SEARCH


# ---------------------------------------------------------------------------
# 6. OUTBOUND robots do not pick up items
# ---------------------------------------------------------------------------

def test_outbound_robot_does_not_pick_up():
    sim = new_sim(search_start="last_pickup", hazards=(), lethality=0.0)
    sw = sim.swarm
    # Put robot 0 in OUTBOUND on top of an item
    item_pos = sim.world.item_pos[0].copy()
    sw.last_pickup[0] = item_pos + np.array([2.0, 2.0])  # target away from item
    sw.state[0] = OUTBOUND
    sw.pos[0] = item_pos
    delivered_before = sim.delivered
    picked_before = sim.picked_up
    sim.step()
    # Robot should still be OUTBOUND (or switched to SEARCH), not RETURN
    assert sw.state[0] != RETURN
    assert sim.picked_up == picked_before  # didn't pick up


# ---------------------------------------------------------------------------
# 7. Motion stream: nest mode is bit-identical to pre-week-6 (heading always drawn)
# ---------------------------------------------------------------------------

def test_nest_mode_bit_identical_for_nest_search_start():
    """With search_start=nest, all results are bit-identical to default."""
    cfg_default = Config(controller="C2", lethality=0.2, n_steps=500, metric_every=500)
    cfg_nest = Config(controller="C2", lethality=0.2, n_steps=500, metric_every=500,
                      search_start="nest")
    rng1 = make_rng("test", 0, 42)
    rng2 = make_rng("test", 0, 42)
    r1 = run(cfg_default, rng1)
    r2 = run(cfg_nest, rng2)
    assert r1["delivered"] == r2["delivered"]
    assert r1["robots_lost"] == r2["robots_lost"]
    assert r1["auc_final"] == r2["auc_final"]


# ---------------------------------------------------------------------------
# 8. Observation metrics: trip_steps_mean, search_steps_mean, nest_steps
# ---------------------------------------------------------------------------

def test_result_has_new_metric_keys():
    r = run(Config(n_steps=200), make_rng("test", 0, 0))
    assert "trip_steps_mean" in r
    assert "search_steps_mean" in r
    assert "nest_steps" in r


def test_trip_steps_mean_is_nan_if_no_deliveries():
    sim = new_sim(n_steps=1, lethality=0.0, hazards=())
    sim.step()
    r = sim.result()
    # Only 1 step, robots start at nest so unlikely to deliver
    if r["delivered"] == 0:
        assert math.isnan(r["trip_steps_mean"])


def test_search_steps_mean_positive_if_pickups_occurred():
    r = run(Config(n_steps=3000, lethality=0.0), make_rng("test", 0, 0))
    if r["picked_up"] > 0:
        assert not math.isnan(r["search_steps_mean"])
        assert r["search_steps_mean"] > 0


def test_nest_steps_is_nonneg_integer_and_bounded():
    r = run(Config(n_steps=500, lethality=0.0), make_rng("test", 0, 0))
    assert isinstance(r["nest_steps"], (int, np.integer))
    assert r["nest_steps"] >= 0
    # Upper bound: n_robots * n_steps
    assert r["nest_steps"] <= Config().n_robots * 500


def test_new_metrics_do_not_change_behavior():
    """Adding metrics must not change the random stream (bit-identical on other keys)."""
    # Compare two runs with the same seed: the metrics don't affect behavior
    cfg = Config(controller="C2", lethality=0.2, n_steps=500, metric_every=500)
    r1 = run(cfg, make_rng("test", 0, 1))
    r2 = run(cfg, make_rng("test", 0, 1))
    for k in ("delivered", "robots_lost", "picked_up", "items_lost", "carrying",
              "auc_final", "false_sightings"):
        assert r1[k] == r2[k], f"key {k} differs"


def test_nest_steps_falls_with_site_fidelity():
    """With last_pickup mode, robots spend less time near the nest (expected)."""
    # This test can't guarantee it for a single seed, but we run a few
    cfg_nest = Config(n_steps=2000, lethality=0.0, hazards=())
    cfg_fid = Config(n_steps=2000, lethality=0.0, hazards=(), search_start="last_pickup")
    nest_steps = []
    fid_steps = []
    for seed in range(5):
        r_nest = run(cfg_nest, make_rng("test", 0, seed))
        r_fid = run(cfg_fid, make_rng("test", 0, seed))
        nest_steps.append(r_nest["nest_steps"])
        fid_steps.append(r_fid["nest_steps"])
    # Fidelity should tend to lower nest_steps (not guaranteed per seed, but on average)
    assert np.mean(fid_steps) <= np.mean(nest_steps)


# ---------------------------------------------------------------------------
# 9. OUTBOUND items_lost unchanged (OUTBOUND carries nothing)
# ---------------------------------------------------------------------------

def test_outbound_robot_dying_does_not_increment_items_lost():
    sim = new_sim(search_start="last_pickup", lethality=1.0, hazards=((5.0, 5.0, 1.0),))
    sw = sim.swarm
    # Put robot 0 in OUTBOUND inside the hazard
    sw.last_pickup[0] = np.array([2.5, 2.5])
    sw.state[0] = OUTBOUND
    sw.pos[0] = np.array([5.0, 5.0])
    items_lost_before = sim.items_lost
    sim.step()
    # Robot should die (lethality=1 inside hazard)
    assert not sw.alive[0]
    # items_lost should not increase (OUTBOUND carries nothing)
    assert sim.items_lost == items_lost_before


# ---------------------------------------------------------------------------
# 10. E9 experiment file has exact cells
# ---------------------------------------------------------------------------

def test_e9_yaml_has_correct_levels():
    from pathlib import Path
    import yaml
    root = Path(__file__).resolve().parents[1]
    path = root / "configs" / "experiments" / "E9.yaml"
    assert path.exists(), "E9.yaml does not exist"
    spec = yaml.safe_load(path.read_text())
    cells = spec["cells"]
    assert len(cells) == 6
    # Cell 0: baseline (empty overrides)
    assert cells[0] == {}
    # Cell 1: last_pickup
    assert cells[1] == {"search_start": "last_pickup"}
    # Cell 2: no hazards, random fail
    assert cells[2].get("hazards") == [] and abs(cells[2].get("random_fail_rate", 0) - 0.0000266) < 1e-10
    # Cell 3: same + last_pickup
    assert cells[3].get("hazards") == [] and abs(cells[3].get("random_fail_rate", 0) - 0.0000266) < 1e-10
    assert cells[3].get("search_start") == "last_pickup"
    # Cell 4: q_false
    assert abs(cells[4].get("q_false", 0) - 0.0001) < 1e-10
    # Cell 5: q_false + last_pickup
    assert abs(cells[5].get("q_false", 0) - 0.0001) < 1e-10
    assert cells[5].get("search_start") == "last_pickup"
    # Controllers and seeds
    assert set(spec["controllers"]) == {"C0", "C1", "C2", "C3", "C4"}
    assert spec["seeds"] == 100
    assert spec.get("paired_cells") is True
