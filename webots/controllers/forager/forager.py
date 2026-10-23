"""Forager robot controller for the swarm-hazard Webots replication.

Reads a JSON payload from customData each control step:
  {"h": <desired_heading_radians>, "alive": <bool>}

If alive=false: stop both motors (robot is a wreck / physical obstacle).
If alive=true:
  1. Read desired heading from customData.
  2. Read own heading from compass sensor.
  3. Compute differential wheel speeds (heading-based steering).
  4. Read 8 IR proximity sensors and add Braitenberg obstacle-avoidance
     correction so robots do not get stuck on each other or walls.
  5. Set left/right motor velocities.

Physical constants (e-puck):
  Wheel radius r  = 0.0205 m
  Axle length  L  = 0.052  m
  Max linear speed = 0.1 m/s  → MAX_WHEEL_SPEED = 0.1 / 0.0205 ≈ 4.878 rad/s

Heading convention:
  0 = +x direction in Webots (east in the arena, corresponds to sim +x).
  Angles increase counter-clockwise (standard mathematical convention).
  The compass provides a bearing; we convert it to this convention below.

IR proximity sensors (8, named ps0..ps7, mounted around the e-puck):
  Approximate angles from robot-forward (+x in robot frame):
    ps0:  10° (right of front)
    ps1:  45° (front-right)
    ps2:  90° (right)
    ps3: 160° (rear-right)
    ps4: 200° (rear-left)
    ps5: 270° (left)
    ps6: 315° (front-left)
    ps7: 350° (left of front)
  Range: 0 (no obstacle) to ~4096 (very close obstacle).
  We activate correction above IR_THRESHOLD = 80.
"""

from __future__ import annotations

import json
import math
import os
import sys

# ── Webots controller library path ───────────────────────────────────────────
_WEBOTS_HOME = os.environ.get(
    "WEBOTS_HOME",
    r"C:\Users\toaya\AppData\Local\Programs\Webots",
)
sys.path.insert(0, os.path.join(_WEBOTS_HOME, "lib", "controller", "python"))

from controller import Robot  # noqa: E402

# ── constants ────────────────────────────────────────────────────────────────
CTRL_STEP_MS = 100           # must match supervisor CTRL_STEP_MS

WHEEL_RADIUS = 0.0205        # metres (e-puck)
AXLE_LENGTH = 0.052          # metres (e-puck wheel-to-wheel distance)
MAX_LINEAR = 0.1             # m/s (spec)
MAX_WHEEL_SPEED = MAX_LINEAR / WHEEL_RADIUS  # ≈ 4.878 rad/s

# Heading steering proportional gain.
# At error = π/2 (90°): ω = Kp * π/2 ≈ 5 * 1.57 ≈ 7.85 → clamped
STEERING_KP = 5.0

# IR obstacle avoidance
IR_THRESHOLD = 80.0          # sensor value above which avoidance kicks in
IR_MAX = 4096.0

# Approximate angles (deg) of the 8 IR sensors in robot-local frame
# (0° = robot forward = +x in robot frame).
# Positive = CCW from forward.
PS_ANGLES_DEG = [10.0, 45.0, 90.0, 160.0, 200.0, 270.0, 315.0, 350.0]


# ── pure functions (tested in tests/webots/test_forager_logic.py) ────────────

def wrap_angle(a: float) -> float:
    """Wrap angle to (−π, π]."""
    return math.atan2(math.sin(a), math.cos(a))


def heading_to_wheels(
    desired_heading: float,
    current_heading: float,
    max_wheel_speed: float = MAX_WHEEL_SPEED,
    axle_length: float = AXLE_LENGTH,
    wheel_radius: float = WHEEL_RADIUS,
    kp: float = STEERING_KP,
) -> tuple[float, float]:
    """Convert a desired heading (radians) to left/right motor speeds (rad/s).

    Uses proportional steering:
        error = wrap(desired - current)
        omega = Kp * error          # angular velocity (rad/s)
        v     = MAX_LINEAR (m/s)    # forward speed
        v_L   = (v - omega * L/2) / r
        v_R   = (v + omega * L/2) / r
    Both speeds are clamped to [−max_wheel_speed, max_wheel_speed].

    Returns (left_speed, right_speed) in rad/s.
    """
    error = wrap_angle(desired_heading - current_heading)
    omega = kp * error
    v = max_wheel_speed * wheel_radius  # = MAX_LINEAR m/s
    v_left = (v - omega * axle_length / 2.0) / wheel_radius
    v_right = (v + omega * axle_length / 2.0) / wheel_radius
    v_left = max(-max_wheel_speed, min(max_wheel_speed, v_left))
    v_right = max(-max_wheel_speed, min(max_wheel_speed, v_right))
    return v_left, v_right


def ir_avoidance(
    ps_values: list[float],
    threshold: float = IR_THRESHOLD,
    ir_max: float = IR_MAX,
    angles_deg: list[float] = PS_ANGLES_DEG,
) -> tuple[float, float]:
    """Compute (delta_left, delta_right) wheel-speed corrections for IR avoidance.

    When an obstacle is detected on one side, slow the wheel on that side
    and slightly speed up the opposite wheel, making the robot turn away.
    Returns deltas in rad/s to be added to the base wheel speeds.

    The correction magnitude is proportional to (value - threshold) / ir_max.
    """
    delta_left = 0.0
    delta_right = 0.0
    for val, angle_deg in zip(ps_values, angles_deg):
        if val <= threshold:
            continue
        strength = (val - threshold) / ir_max
        angle_rad = math.radians(angle_deg)
        # Obstacle at `angle_deg` in robot frame.
        # If the obstacle is in the right semicircle (0°–180°): turn left.
        # If in the left semicircle (180°–360°): turn right.
        if 0.0 <= angle_deg < 180.0:
            # Right side: reduce right wheel, boost left
            delta_right -= strength * MAX_WHEEL_SPEED * 2.0
            delta_left += strength * MAX_WHEEL_SPEED * 0.5
        else:
            # Left side: reduce left wheel, boost right
            delta_left -= strength * MAX_WHEEL_SPEED * 2.0
            delta_right += strength * MAX_WHEEL_SPEED * 0.5
    return delta_left, delta_right


def compass_to_heading(north_vec: list[float]) -> float:
    """Convert Webots compass reading to heading in radians (Webots convention).

    The Webots Compass sensor returns a unit vector pointing toward 'north'.
    With the default WorldInfo coordinateSystem "NUE":
      north = +x  → reading ≈ [1, 0, 0]
    We interpret heading as the angle of the robot's forward (+x robot-axis)
    relative to world +x, measured CCW (looking down from +y).

    The compass reads the direction OF north in the sensor's LOCAL frame.
    If the robot faces +x (heading=0) the compass reads [1, 0, 0] (approx).
    If the robot faces +z (heading = -π/2 in our CCW convention) the compass
    forward (sensor x-axis) points to +z, so north (+x_world) appears at
    sensor -z direction → reading [-0, 0, 1]? This depends on sensor mounting.

    Webots compass for e-puck (facing default +x):
        reading = [cos(heading), 0, -sin(heading)]  (approximately)
    so heading = atan2(-reading[2], reading[0]).
    """
    return math.atan2(-north_vec[2], north_vec[0])


# ── controller entry point ────────────────────────────────────────────────────

def main() -> None:
    robot = Robot()

    # Enable motors
    left_motor = robot.getDevice("left wheel motor")
    right_motor = robot.getDevice("right wheel motor")
    left_motor.setPosition(float("inf"))   # velocity mode
    right_motor.setPosition(float("inf"))
    left_motor.setVelocity(0.0)
    right_motor.setVelocity(0.0)

    # Enable compass for heading estimation
    compass = robot.getDevice("compass")
    compass.enable(CTRL_STEP_MS)

    # Enable IR proximity sensors
    ps = [robot.getDevice(f"ps{i}") for i in range(8)]
    for sensor in ps:
        sensor.enable(CTRL_STEP_MS)

    # Main control loop
    while robot.step(CTRL_STEP_MS) != -1:
        # Read supervisor message
        raw = robot.getCustomData()
        if not raw:
            continue
        try:
            msg = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            continue

        robot_alive = bool(msg.get("alive", True))
        desired_heading = float(msg.get("h", 0.0))

        if not robot_alive:
            # Wreck: stop motors and stay still (physical obstacle for others)
            left_motor.setVelocity(0.0)
            right_motor.setVelocity(0.0)
            continue

        # Get current heading from compass
        compass_reading = compass.getValues()  # [x, y, z]
        current_heading = compass_to_heading(compass_reading)

        # Base wheel speeds from desired heading
        v_left, v_right = heading_to_wheels(desired_heading, current_heading)

        # IR proximity obstacle avoidance
        ps_vals = [s.getValue() for s in ps]
        dl, dr = ir_avoidance(ps_vals)

        # Apply and clamp
        v_left = max(-MAX_WHEEL_SPEED, min(MAX_WHEEL_SPEED, v_left + dl))
        v_right = max(-MAX_WHEEL_SPEED, min(MAX_WHEEL_SPEED, v_right + dr))

        left_motor.setVelocity(v_left)
        right_motor.setVelocity(v_right)


if __name__ == "__main__":
    main()
