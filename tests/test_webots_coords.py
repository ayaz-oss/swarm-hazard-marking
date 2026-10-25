"""Unit tests for ENU coordinate mappings in the Webots replication.

Tests cover:
  - webots_to_sim / sim_to_webots round-trip (supervisor.py helpers)
  - compass_to_heading (forager.py helper)
  - heading_to_wheels direction sanity (forager.py)
  - ir_avoidance signs (forager.py)

These tests import from the controllers directly without loading the Webots
library (controller imports are mocked).
"""
from __future__ import annotations

import importlib
import math
import sys
import types
import unittest
from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# Isolate imports: stub out 'controller' so forager/supervisor can be imported
# without the Webots Python library installed.
# ---------------------------------------------------------------------------

def _stub_webots():
    """Insert a stub 'controller' module so the imports don't fail."""
    if "controller" in sys.modules:
        return
    ctrl = types.ModuleType("controller")
    ctrl.Robot = MagicMock
    ctrl.Supervisor = MagicMock
    sys.modules["controller"] = ctrl


_stub_webots()

# We need to import the pure functions only.  The controllers use relative
# imports inside Webots; we load them as plain Python files using importlib.

import importlib.util
import os

_WT_ROOT = os.path.join(
    os.path.dirname(__file__), "..", "webots"
)


def _load_module(rel_path: str, name: str):
    path = os.path.normpath(os.path.join(_WT_ROOT, rel_path))
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    # Pre-register so that any internal imports find it
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_forager = _load_module("controllers/forager/forager.py", "forager_ctrl")
_supervisor = _load_module("controllers/supervisor/supervisor.py", "supervisor_ctrl")

webots_to_sim = _supervisor.webots_to_sim
sim_to_webots = _supervisor.sim_to_webots
compass_to_heading = _forager.compass_to_heading
heading_to_wheels = _forager.heading_to_wheels
ir_avoidance = _forager.ir_avoidance
MAX_WHEEL_SPEED = _forager.MAX_WHEEL_SPEED


class TestCoordinateMapping(unittest.TestCase):
    """webots_to_sim / sim_to_webots round-trip (ENU: x=East, y=North)."""

    def test_arena_centre(self):
        # Webots origin = sim (5, 5)
        sx, sy = webots_to_sim(0.0, 0.0)
        self.assertAlmostEqual(sx, 5.0)
        self.assertAlmostEqual(sy, 5.0)

    def test_arena_corners(self):
        # Webots (-5, -5) = sim (0, 0)  [SW corner]
        sx, sy = webots_to_sim(-5.0, -5.0)
        self.assertAlmostEqual(sx, 0.0)
        self.assertAlmostEqual(sy, 0.0)
        # Webots (5, 5) = sim (10, 10)  [NE corner]
        sx, sy = webots_to_sim(5.0, 5.0)
        self.assertAlmostEqual(sx, 10.0)
        self.assertAlmostEqual(sy, 10.0)

    def test_round_trip(self):
        for sx in [0.0, 2.5, 5.0, 7.5, 10.0]:
            for sy in [0.0, 3.3, 5.0, 9.9, 10.0]:
                wx, wy = sim_to_webots(sx, sy)
                sx2, sy2 = webots_to_sim(wx, wy)
                self.assertAlmostEqual(sx2, sx, places=9)
                self.assertAlmostEqual(sy2, sy, places=9)

    def test_nest_is_webots_origin(self):
        # Nest at sim (5, 5) → Webots (0, 0)
        wx, wy = sim_to_webots(5.0, 5.0)
        self.assertAlmostEqual(wx, 0.0)
        self.assertAlmostEqual(wy, 0.0)

    def test_patches(self):
        # NW patch: sim (2.5, 2.5) = Webots (-2.5, -2.5)
        wx, wy = sim_to_webots(2.5, 2.5)
        self.assertAlmostEqual(wx, -2.5)
        self.assertAlmostEqual(wy, -2.5)
        # SE patch: sim (7.5, 7.5) = Webots (2.5, 2.5)
        wx, wy = sim_to_webots(7.5, 7.5)
        self.assertAlmostEqual(wx, 2.5)
        self.assertAlmostEqual(wy, 2.5)


class TestCompassToHeading(unittest.TestCase):
    """compass_to_heading for ENU (world north = +y, robot forward = +x).

    Reading is the direction of world north in robot-local frame.
    heading = atan2(reading[0], reading[1]).
    """

    def _assert_heading(self, reading, expected_deg, places=4):
        h = compass_to_heading(reading)
        self.assertAlmostEqual(math.degrees(h), expected_deg, places=places)

    def test_facing_east_heading_zero(self):
        # Robot faces +x (East) → north (+y_world) appears at robot +y → reading≈[0,1,0]
        self._assert_heading([0.0, 1.0, 0.0], 0.0)

    def test_facing_north_heading_90(self):
        # Robot faces +y (North) → north appears at robot +x → reading≈[1,0,0]
        self._assert_heading([1.0, 0.0, 0.0], 90.0)

    def test_facing_west_heading_180(self):
        # Robot faces -x (West) → north appears at robot -y → reading≈[0,-1,0]
        self._assert_heading([0.0, -1.0, 0.0], 180.0)

    def test_facing_south_heading_minus90(self):
        # Robot faces -y (South) → north appears at robot -x → reading≈[-1,0,0]
        self._assert_heading([-1.0, 0.0, 0.0], -90.0)

    def test_northeast_45deg(self):
        # heading = π/4 (45°, between East and North)
        s = math.sqrt(2) / 2
        self._assert_heading([s, s, 0.0], 45.0, places=3)

    def test_z_component_ignored(self):
        # vertical component should not affect heading
        h1 = compass_to_heading([0.0, 1.0, 0.0])
        h2 = compass_to_heading([0.0, 1.0, 0.5])
        self.assertAlmostEqual(h1, h2, places=4)


class TestHeadingToWheels(unittest.TestCase):
    """heading_to_wheels sanity checks for ENU convention.

    In ENU: v_right > v_left → robot turns LEFT (CCW, positive omega around +z).
    """

    def test_equal_speeds_when_aligned(self):
        # Desired == current → no turn → equal speeds
        vl, vr = heading_to_wheels(0.0, 0.0)
        self.assertAlmostEqual(vl, vr, places=6)
        self.assertGreater(vl, 0.0)  # moving forward

    def test_turn_left_when_desired_gt_current(self):
        # Desired heading = π/2 (North), current = 0 (East): turn LEFT (CCW)
        # In ENU: CCW = v_right > v_left
        vl, vr = heading_to_wheels(math.pi / 2, 0.0)
        self.assertGreater(vr, vl, "ENU: turning left requires v_right > v_left")

    def test_turn_right_when_desired_lt_current(self):
        # Desired = 0 (East), current = π/2 (North): turn RIGHT (CW)
        # In ENU: CW = v_left > v_right
        vl, vr = heading_to_wheels(0.0, math.pi / 2)
        self.assertGreater(vl, vr, "ENU: turning right requires v_left > v_right")

    def test_speeds_clamped(self):
        # Large error should clamp both speeds
        vl, vr = heading_to_wheels(math.pi, 0.0)
        self.assertLessEqual(abs(vl), MAX_WHEEL_SPEED + 1e-9)
        self.assertLessEqual(abs(vr), MAX_WHEEL_SPEED + 1e-9)


class TestIrAvoidance(unittest.TestCase):
    """ir_avoidance sign convention for ENU.

    In ENU: v_right > v_left → turn LEFT (CCW, away from right-side obstacle).
    So delta_right should be positive for right-side obstacle.
    """

    def _mock_ps(self, active_idx: int, value: float = 3000.0) -> list[float]:
        """Return ps_values with only sensor `active_idx` above threshold."""
        return [value if i == active_idx else 0.0 for i in range(8)]

    def test_right_obstacle_boosts_right_wheel(self):
        # ps2 at 90° CW = directly right (-y side in ENU)
        ps = self._mock_ps(2, 3000.0)
        dl, dr = ir_avoidance(ps)
        # Should turn LEFT: delta_right > delta_left
        self.assertGreater(dr, dl,
            "right obstacle must give delta_right > delta_left (turn left/away)")
        self.assertGreater(dr, 0.0, "delta_right must be positive for right obstacle")

    def test_left_obstacle_boosts_left_wheel(self):
        # ps5 at 270° CW = directly left (+y side in ENU)
        ps = self._mock_ps(5, 3000.0)
        dl, dr = ir_avoidance(ps)
        # Should turn RIGHT: delta_left > delta_right
        self.assertGreater(dl, dr,
            "left obstacle must give delta_left > delta_right (turn right/away)")
        self.assertGreater(dl, 0.0, "delta_left must be positive for left obstacle")

    def test_no_obstacle_no_correction(self):
        ps = [0.0] * 8
        dl, dr = ir_avoidance(ps)
        self.assertAlmostEqual(dl, 0.0)
        self.assertAlmostEqual(dr, 0.0)

    def test_threshold_boundary(self):
        from forager_ctrl import IR_THRESHOLD
        # Exactly at threshold → no correction
        ps = [IR_THRESHOLD] * 8
        dl, dr = ir_avoidance(ps)
        self.assertAlmostEqual(dl, 0.0)
        self.assertAlmostEqual(dr, 0.0)


if __name__ == "__main__":
    unittest.main()


def test_oracle_steer_never_points_into_hazard():
    import importlib.util, sys, types
    from pathlib import Path
    import numpy as np
    from swarmhazard.config import Config
    from swarmhazard.world import make_world, in_hazard
    # import oracle_steer without the Webots controller library
    sys.modules.setdefault("controller", types.SimpleNamespace(Supervisor=object))
    p = Path(__file__).resolve().parents[1] / "webots/controllers/supervisor/supervisor.py"
    spec = importlib.util.spec_from_file_location("wb_supervisor", p)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    cfg = Config()
    world = make_world(cfg, np.random.default_rng(0))
    cx, cy, r = cfg.hazards[0]
    # robots just outside the hazard, all heading straight at its centre
    ang = np.linspace(0, 2 * np.pi, 12, endpoint=False)
    pos = np.column_stack((cx + (r + 0.1) * np.cos(ang), cy + (r + 0.1) * np.sin(ang)))
    heading = ang + np.pi
    alive = np.ones(12, dtype=bool)
    mod.oracle_steer(world, pos, heading, alive)
    ahead = pos + 0.05 * np.column_stack((np.cos(heading), np.sin(heading)))
    assert not in_hazard(world, ahead).any()
    # a robot inside heads outward
    pos_in = np.array([[cx + 0.5, cy]]); h = np.array([np.pi])
    mod.oracle_steer(world, pos_in, h, np.array([True]))
    assert abs(h[0]) < 1e-9
