"""Tests for pure-Python supervisor world logic (no Webots dependency).

These tests exercise the swarmhazard components that the supervisor reuses:
  - World initialisation (items, hazard)
  - Hazard failure logic
  - Pickup detection geometry
  - Delivery detection geometry
  - RepellentField deposit / decay / gradient
  - Seeding reproducibility

They complement the existing tests in tests/ and must not break them.
"""

from __future__ import annotations

import math
import os
import sys

import numpy as np
import pytest

# Add src to path
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, os.path.join(_ROOT, "src"))

from swarmhazard.config import load_config
from swarmhazard.geometry import norm
from swarmhazard.pheromone import RepellentField
from swarmhazard.seeding import make_rng
from swarmhazard.world import hazard_failures, in_hazard, make_world, respawn_item


# ── shared fixtures ───────────────────────────────────────────────────────────

CFG_PATH = os.path.join(_ROOT, "configs", "baseline.yaml")
TUNED_PATH = os.path.join(_ROOT, "configs", "tuned_params_fidelity.yaml")


def make_cfg(controller="C2", **overrides):
    import yaml
    tuned = yaml.safe_load(open(TUNED_PATH).read()) or {}
    tuned["controller"] = controller
    tuned.update(overrides)
    return load_config(CFG_PATH, **tuned)


def make_world_and_rng(seed=0):
    rng = make_rng("W1", 0, seed)
    (layout_rng, motion_rng, respawn_rng, hazard_rng, _, _) = rng.spawn(6)
    cfg = make_cfg()
    world = make_world(cfg, layout_rng)
    return cfg, world, motion_rng, respawn_rng, hazard_rng


# ── world initialisation ─────────────────────────────────────────────────────

class TestWorldInit:
    def test_items_count(self):
        cfg, world, *_ = make_world_and_rng()
        # 4 patches × 10 items = 40 items
        assert len(world.item_pos) == 40

    def test_items_in_arena(self):
        cfg, world, *_ = make_world_and_rng()
        assert (world.item_pos >= 0).all()
        assert (world.item_pos <= cfg.arena_size).all()

    def test_hazard_setup(self):
        cfg, world, *_ = make_world_and_rng()
        # baseline has one hazard at (8.81, 6.19, 1.0)
        assert len(world.hazard_r) == 1
        assert abs(world.hazard_xy[0, 0] - 8.81) < 1e-6
        assert abs(world.hazard_xy[0, 1] - 6.19) < 1e-6

    def test_seed_reproducibility(self):
        """Same seed gives identical world."""
        cfg, w1, *_ = make_world_and_rng(seed=42)
        cfg, w2, *_ = make_world_and_rng(seed=42)
        np.testing.assert_array_equal(w1.item_pos, w2.item_pos)

    def test_different_seeds_differ(self):
        """Different seeds give different layouts (with very high probability)."""
        _, w1, *_ = make_world_and_rng(seed=0)
        _, w2, *_ = make_world_and_rng(seed=1)
        # Almost certainly different; if not, increase seed gap
        assert not np.allclose(w1.item_pos, w2.item_pos)


# ── hazard failure logic ─────────────────────────────────────────────────────

class TestHazardFailures:
    def test_outside_hazard_no_deaths(self):
        """Robots outside the hazard never die from it."""
        cfg, world, _, _, hazard_rng = make_world_and_rng()
        n = 10
        pos = np.zeros((n, 2))  # nest at (5,5) is outside hazard at (8.81, 6.19)
        pos[:] = [5.0, 5.0]
        alive = np.ones(n, dtype=bool)
        dies = hazard_failures(world, pos, alive, cfg.lethality, hazard_rng)
        assert not dies.any()

    def test_inside_hazard_some_deaths(self):
        """Robots inside the hazard die with probability lethality per step."""
        rng = make_rng("W1", 0, 99)
        (layout_rng, _motion_rng, _respawn_rng, hazard_rng, _, _) = rng.spawn(6)
        cfg = make_cfg()
        world = make_world(cfg, layout_rng)

        n = 1000
        pos = np.tile([8.81, 6.19], (n, 1))  # hazard centre
        alive = np.ones(n, dtype=bool)
        # Run 50 steps and count expected deaths
        deaths = 0
        for _ in range(50):
            d = hazard_failures(world, pos, alive, cfg.lethality, hazard_rng)
            deaths += d.sum()
        # Expected ≈ 1000 × 50 × 0.02 = 1000; rough sanity check
        assert deaths > 500, f"Expected ~1000 deaths, got {deaths}"
        assert deaths < 1500, f"Expected ~1000 deaths, got {deaths}"

    def test_dead_robots_not_considered(self):
        """Already-dead robots (alive=False) are never counted as dying again."""
        rng = make_rng("W1", 0, 0)
        (layout_rng, _, _, hazard_rng, _, _) = rng.spawn(6)
        cfg = make_cfg()
        world = make_world(cfg, layout_rng)
        n = 100
        pos = np.tile([8.81, 6.19], (n, 1))
        alive = np.zeros(n, dtype=bool)  # all already dead
        dies = hazard_failures(world, pos, alive, cfg.lethality, hazard_rng)
        assert not dies.any()


# ── pickup detection ─────────────────────────────────────────────────────────

class TestPickupGeometry:
    def test_robot_at_item_position_picks_up(self):
        """A robot at exactly the item position is within pickup_radius."""
        cfg, world, *_ = make_world_and_rng()
        item_pos = world.item_pos[0].copy()
        d = norm(item_pos - item_pos)  # = 0
        assert d < cfg.pickup_radius

    def test_robot_far_from_items_no_pickup(self):
        """A robot far from all items is not within pickup_radius."""
        cfg, world, *_ = make_world_and_rng()
        far_pos = np.array([5.0, 5.0])  # nest centre
        d = norm(world.item_pos - far_pos)
        assert (d >= cfg.pickup_radius).all()

    def test_respawn_moves_item(self):
        """Respawned item lands in a new position (with very high probability)."""
        cfg, world, _, respawn_rng, _ = make_world_and_rng()
        old_pos = world.item_pos[0].copy()
        respawn_item(world, 0, respawn_rng)
        # Very unlikely to land at exactly the same spot
        new_pos = world.item_pos[0]
        assert not np.allclose(old_pos, new_pos, atol=1e-6)

    def test_respawn_stays_in_patch(self):
        """Respawned item stays inside its patch."""
        cfg, world, _, respawn_rng, _ = make_world_and_rng()
        patch_idx = int(world.item_patch[0])
        patch_centre = world.patch_xy[patch_idx]
        patch_r = world.patch_r[patch_idx]
        for _ in range(50):
            respawn_item(world, 0, respawn_rng)
            d = norm(world.item_pos[0] - patch_centre)
            assert d <= patch_r + 1e-9, f"Item outside patch: d={d:.4f} > r={patch_r}"


# ── delivery geometry ─────────────────────────────────────────────────────────

class TestDeliveryGeometry:
    def test_robot_at_nest_delivers(self):
        cfg, *_ = make_world_and_rng()
        nest = np.asarray(cfg.nest_center)
        robot_pos = nest.copy()
        d = norm(robot_pos - nest)
        assert d < cfg.nest_radius

    def test_robot_outside_nest_no_delivery(self):
        cfg, *_ = make_world_and_rng()
        nest = np.asarray(cfg.nest_center)
        robot_pos = nest + np.array([cfg.nest_radius + 0.1, 0.0])
        d = norm(robot_pos - nest)
        assert d >= cfg.nest_radius


# ── repellent field ───────────────────────────────────────────────────────────

class TestRepellentField:
    def test_deposit_increases_value(self):
        cfg, *_ = make_world_and_rng()
        f = RepellentField(cfg.arena_size, cfg.grid_cell)
        pt = np.array([[5.0, 5.0]])
        before = float(f.value(pt)[0])
        f.deposit(np.array([5.0, 5.0]), cfg.deposit_amount, cfg.deposit_sigma)
        after = float(f.value(pt)[0])
        assert after > before

    def test_decay_reduces_value(self):
        cfg, *_ = make_world_and_rng()
        f = RepellentField(cfg.arena_size, cfg.grid_cell)
        f.deposit(np.array([5.0, 5.0]), 1.0, cfg.deposit_sigma)
        before = float(f.value(np.array([[5.0, 5.0]]))[0])
        f.decay(cfg.decay)
        after = float(f.value(np.array([[5.0, 5.0]]))[0])
        assert after < before
        assert after == pytest.approx(before * (1 - cfg.decay), rel=1e-6)

    def test_gradient_points_toward_deposit(self):
        """Gradient at a point east of a deposit should point west (toward deposit).

        The RepellentField gradient points toward higher values (up-gradient),
        i.e., toward the deposit. Controllers apply -repel_weight * gradient,
        which pushes robots away (down-gradient).
        """
        cfg, *_ = make_world_and_rng()
        f = RepellentField(cfg.arena_size, cfg.grid_cell)
        deposit_pt = np.array([5.0, 5.0])
        f.deposit(deposit_pt, 10.0, 0.3)
        # Query point slightly to the east of deposit
        query = np.array([[5.5, 5.0]])
        grad = f.gradient(query, cfg.sense_range)
        # Gradient x component should be negative (pointing toward deposit at x=5)
        assert float(grad[0, 0]) < 0, f"Gradient x={grad[0,0]:.4f} should be < 0 (toward deposit)"

    def test_field_zero_after_init(self):
        cfg, *_ = make_world_and_rng()
        f = RepellentField(cfg.arena_size, cfg.grid_cell)
        pts = np.array([[1.0, 1.0], [5.0, 5.0], [9.0, 9.0]])
        vals = f.value(pts)
        assert (vals == 0.0).all()


# ── seeding reproducibility for W1 experiment ────────────────────────────────

class TestW1Seeding:
    def test_same_seed_same_world(self):
        """RNG stream "W1", cell=0, seed=42 gives identical worlds each call."""
        def build(seed):
            rng = make_rng("W1", 0, seed)
            (layout_rng, *_) = rng.spawn(6)
            cfg = make_cfg()
            return make_world(cfg, layout_rng)

        w1 = build(42)
        w2 = build(42)
        np.testing.assert_array_equal(w1.item_pos, w2.item_pos)

    def test_w1_seed_differs_from_e1f_seed(self):
        """W1 seeds should differ from E1F seeds (different experiment names)."""
        rng_w1 = make_rng("W1", 0, 0)
        rng_e1f = make_rng("E1F", 0, 0)
        (layout_w1, *_) = rng_w1.spawn(6)
        (layout_e1f, *_) = rng_e1f.spawn(6)
        cfg = make_cfg()
        world_w1 = make_world(cfg, layout_w1)
        world_e1f = make_world(cfg, layout_e1f)
        # Very unlikely to match; tests that experiment names are used
        assert not np.allclose(world_w1.item_pos, world_e1f.item_pos)
