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

Heading convention (ENU: x=East, y=North, z=Up):
  0 = +x direction = East; π/2 = North; angles increase CCW viewed from above (+z).
  Compass reports north direction in robot-local frame; heading = atan2(n[0], n[1]).
  Left motor at y=+0.026 (North side); right motor at y=-0.026 (South side).
  v_right > v_left → turns LEFT (CCW); v_left > v_right → turns RIGHT (CW).

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

# IR obstacle avoidance.
# IR_THRESHOLD: sensors read ≈ 4095*(0.2-d)/0.2 at distance d (m).
# Distance where value = threshold:  d = 0.2*(1 - threshold/4095).
# threshold=80  → triggers at d=0.196 m (≈5 body radii – too sensitive).
# threshold=1500 → triggers at d=0.127 m (≈1.7 body radii – avoid contact).
# threshold=2500 → triggers at d=0.078 m (≈1.1 body radii – near-contact).
# We use 1500 so robots avoid but are not paralysed in the initial cluster.
IR_THRESHOLD = 1500.0        # sensor value above which avoidance kicks in
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
            # Right side obstacle (−y side in ENU): turn LEFT (CCW around +z).
            # Turn left = v_right > v_left → boost right, reduce left.
            delta_right += strength * MAX_WHEEL_SPEED * 1.0
            delta_left -= strength * MAX_WHEEL_SPEED * 0.3
        else:
            # Left side obstacle (+y side in ENU): turn RIGHT (CW around +z).
            # Turn right = v_left > v_right → boost left, reduce right.
            delta_left += strength * MAX_WHEEL_SPEED * 1.0
            delta_right -= strength * MAX_WHEEL_SPEED * 0.3
    return delta_left, delta_right


def compass_to_heading(north_vec: list[float]) -> float:
    """Convert Webots compass reading to heading in radians (ENU convention).

    The Webots Compass sensor returns a unit vector pointing toward 'north'
    in the sensor's LOCAL frame.

    With coordinateSystem "ENU": world north = +y direction.
    The robot faces +x (East) when heading = 0.

    Compass reading in robot local frame when robot has heading θ:
        reading[0] = sin(θ)   (north component along robot +x)
        reading[1] = cos(θ)   (north component along robot +y)
        reading[2] ≈ 0        (vertical, ignored)

    So heading = atan2(reading[0], reading[1]).

    Verification:
        heading=0 (facing East): reading≈[0,1,0] → atan2(0,1)=0 ✓
        heading=π/2 (facing North): reading≈[1,0,0] → atan2(1,0)=π/2 ✓
        heading=π (facing West): reading≈[0,-1,0] → atan2(0,-1)=π ✓
    """
    return math.atan2(north_vec[0], north_vec[1])


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
