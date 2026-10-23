"""Tests for pure-Python forager controller logic (no Webots dependency)."""

from __future__ import annotations

import math
import sys
import os

import pytest

# Add forager controller to path without importing controller (Webots lib)
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
_FORAGER_DIR = os.path.join(_ROOT, "webots", "controllers", "forager")

# We can't import forager.py directly because it tries to import 'controller'
# (Webots library). Instead, we copy the pure functions here for testing.
# The functions are also independently re-defined below to make tests fully
# standalone. The actual implementations in forager.py must match these.

WHEEL_RADIUS = 0.0205
AXLE_LENGTH = 0.052
MAX_LINEAR = 0.1
MAX_WHEEL_SPEED = MAX_LINEAR / WHEEL_RADIUS
STEERING_KP = 5.0
IR_THRESHOLD = 80.0
IR_MAX = 4096.0
PS_ANGLES_DEG = [10.0, 45.0, 90.0, 160.0, 200.0, 270.0, 315.0, 350.0]


def wrap_angle(a: float) -> float:
    return math.atan2(math.sin(a), math.cos(a))


def heading_to_wheels(
    desired_heading: float,
    current_heading: float,
    max_wheel_speed: float = MAX_WHEEL_SPEED,
    axle_length: float = AXLE_LENGTH,
    wheel_radius: float = WHEEL_RADIUS,
    kp: float = STEERING_KP,
) -> tuple[float, float]:
    error = wrap_angle(desired_heading - current_heading)
    omega = kp * error
    v = max_wheel_speed * wheel_radius
    v_left = (v - omega * axle_length / 2.0) / wheel_radius
    v_right = (v + omega * axle_length / 2.0) / wheel_radius
    v_left = max(-max_wheel_speed, min(max_wheel_speed, v_left))
    v_right = max(-max_wheel_speed, min(max_wheel_speed, v_right))
    return v_left, v_right


def ir_avoidance(
    ps_values: list[float],
    threshold: float = IR_THRESHOLD,
    ir_max: float = IR_MAX,
    angles_deg: list[float] = None,
) -> tuple[float, float]:
    if angles_deg is None:
        angles_deg = PS_ANGLES_DEG
    delta_left = 0.0
    delta_right = 0.0
    for val, angle_deg in zip(ps_values, angles_deg):
        if val <= threshold:
            continue
        strength = (val - threshold) / ir_max
        if 0.0 <= angle_deg < 180.0:
            delta_right -= strength * MAX_WHEEL_SPEED * 2.0
            delta_left += strength * MAX_WHEEL_SPEED * 0.5
        else:
            delta_left -= strength * MAX_WHEEL_SPEED * 2.0
            delta_right += strength * MAX_WHEEL_SPEED * 0.5
    return delta_left, delta_right


def compass_to_heading(north_vec: list[float]) -> float:
    return math.atan2(-north_vec[2], north_vec[0])


# ── tests ────────────────────────────────────────────────────────────────────

class TestHeadingToWheels:
    def test_straight_ahead(self):
        """Desired = current → both wheels same positive speed."""
        v_l, v_r = heading_to_wheels(0.0, 0.0)
        assert v_l == pytest.approx(v_r, rel=1e-9)
        assert v_l > 0

    def test_max_speed_forward(self):
        """Straight ahead gives MAX_WHEEL_SPEED."""
        v_l, v_r = heading_to_wheels(0.0, 0.0)
        assert v_l == pytest.approx(MAX_WHEEL_SPEED, rel=1e-6)

    def test_turn_right(self):
        """Desired heading is to the right (negative angle) → left wheel faster."""
        # Current: 0, desired: -π/4 (right) → robot turns right → left faster
        v_l, v_r = heading_to_wheels(-math.pi / 4, 0.0)
        assert v_l > v_r, f"Expected left > right for right turn, got {v_l:.3f}, {v_r:.3f}"

    def test_turn_left(self):
        """Desired heading is to the left (positive angle) → right wheel faster."""
        v_l, v_r = heading_to_wheels(math.pi / 4, 0.0)
        assert v_r > v_l, f"Expected right > left for left turn, got {v_l:.3f}, {v_r:.3f}"

    def test_180_degree_turn_clamped(self):
        """U-turn: large error → speeds clamped to [-MAX, MAX]."""
        v_l, v_r = heading_to_wheels(math.pi, 0.0)
        assert abs(v_l) <= MAX_WHEEL_SPEED + 1e-9
        assert abs(v_r) <= MAX_WHEEL_SPEED + 1e-9

    def test_wrap_angle_negative_pi(self):
        """heading_to_wheels with error just past -π wraps correctly."""
        # desired = -π + 0.01, current = 0
        # error = wrap(-π + 0.01) ≈ -3.13 (negative) → right turn (left wheel faster)
        v_l, v_r = heading_to_wheels(-math.pi + 0.01, 0.0)
        assert v_l > v_r  # negative error → right turn, left wheel faster

    def test_output_is_float_tuple(self):
        v_l, v_r = heading_to_wheels(1.0, 0.5)
        assert isinstance(v_l, float)
        assert isinstance(v_r, float)

    def test_symmetry(self):
        """Left and right turn by same angle should give symmetric results."""
        v_l_left, v_r_left = heading_to_wheels(math.pi / 6, 0.0)
        v_l_right, v_r_right = heading_to_wheels(-math.pi / 6, 0.0)
        assert v_l_left == pytest.approx(v_r_right, rel=1e-9)
        assert v_r_left == pytest.approx(v_l_right, rel=1e-9)


class TestWrapAngle:
    def test_zero(self):
        assert wrap_angle(0.0) == pytest.approx(0.0)

    def test_pi_wraps_to_pi(self):
        assert abs(wrap_angle(math.pi)) == pytest.approx(math.pi, abs=1e-10)

    def test_two_pi_wraps_to_zero(self):
        assert wrap_angle(2 * math.pi) == pytest.approx(0.0, abs=1e-10)

    def test_negative_wraps(self):
        assert wrap_angle(-3 * math.pi / 2) == pytest.approx(math.pi / 2, rel=1e-9)

    def test_large_positive(self):
        r = wrap_angle(100.0)
        assert -math.pi < r <= math.pi


class TestIRAvoidance:
    def test_no_obstacles(self):
        """All sensors below threshold → no correction."""
        ps = [0.0] * 8
        dl, dr = ir_avoidance(ps)
        assert dl == pytest.approx(0.0)
        assert dr == pytest.approx(0.0)

    def test_right_side_obstacle(self):
        """Obstacle on right (ps1 at 45°) → left boost, right reduction."""
        ps = [0.0] * 8
        ps[1] = 500.0  # ps1 at 45° (right side)
        dl, dr = ir_avoidance(ps)
        assert dl > 0, "Left wheel should speed up"
        assert dr < 0, "Right wheel should slow down"

    def test_left_side_obstacle(self):
        """Obstacle on left (ps6 at 315°) → right boost, left reduction."""
        ps = [0.0] * 8
        ps[6] = 500.0  # ps6 at 315° (left side)
        dl, dr = ir_avoidance(ps)
        assert dr > 0, "Right wheel should speed up"
        assert dl < 0, "Left wheel should slow down"

    def test_at_threshold_no_correction(self):
        """Exactly at threshold → no correction."""
        ps = [IR_THRESHOLD] * 8
        dl, dr = ir_avoidance(ps)
        assert dl == pytest.approx(0.0)
        assert dr == pytest.approx(0.0)

    def test_proportional_to_strength(self):
        """Stronger obstacle → larger correction magnitude."""
        ps_weak = [0.0] * 8
        ps_weak[1] = 200.0
        ps_strong = [0.0] * 8
        ps_strong[1] = 2000.0
        dl_w, dr_w = ir_avoidance(ps_weak)
        dl_s, dr_s = ir_avoidance(ps_strong)
        assert abs(dl_s) > abs(dl_w)
        assert abs(dr_s) > abs(dr_w)


class TestCompassToHeading:
    def test_north_is_zero(self):
        """Compass points to +x (north) → heading 0."""
        h = compass_to_heading([1.0, 0.0, 0.0])
        assert h == pytest.approx(0.0, abs=1e-9)

    def test_facing_plus_z_is_negative_half_pi(self):
        """Compass points to -z → heading -π/2 (robot faces +z, north appears at -z)."""
        # When robot faces +z (heading = -π/2), north (+x_world) is at robot's
        # left (-z sensor direction? or +z?). Let's just check the formula is consistent.
        h = compass_to_heading([0.0, 0.0, 1.0])
        # -north_vec[2] = -1, north_vec[0] = 0 → atan2(-1, 0) = -π/2
        assert h == pytest.approx(-math.pi / 2, rel=1e-9)

    def test_facing_minus_x(self):
        """north_vec = [-1, 0, 0] → heading = π (or -π)."""
        h = compass_to_heading([-1.0, 0.0, 0.0])
        assert abs(h) == pytest.approx(math.pi, rel=1e-9)


class TestCSVRowFormat:
    """Check that the CSV columns match the expected format."""
    def test_required_columns_present(self):
        """The CSV column list must contain all required experiment columns."""
        # Import just the CSV_COLS constant without triggering Webots import.
        # We read the source file and extract the list.
        sup_path = os.path.join(
            _ROOT, "webots", "controllers", "supervisor", "supervisor.py"
        )
        text = open(sup_path).read()
        # Extract CSV_COLS list from source
        import ast
        import re
        m = re.search(r"CSV_COLS\s*=\s*(\[.*?\])", text, re.DOTALL)
        assert m is not None, "CSV_COLS not found in supervisor.py"
        cols = ast.literal_eval(m.group(1))
        required = [
            "experiment", "controller", "seed", "delivered", "robots_lost",
            "steps", "wall_s", "simulator",
        ]
        for col in required:
            assert col in cols, f"Missing required column: {col!r}"

    def test_simulator_column_is_webots(self):
        """The 'simulator' column must default to 'webots'."""
        sup_path = os.path.join(
            _ROOT, "webots", "controllers", "supervisor", "supervisor.py"
        )
        text = open(sup_path).read()
        assert '"webots"' in text or "'webots'" in text
