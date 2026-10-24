"""Minimal motion diagnostic supervisor (ENU: x=East, y=North, z=Up).

Commands ALL forager robots with heading=0 (East, +x in ENU) at constant
max speed.  Logs Webots positions every 10 steps for 100 steps so we can
verify:
  - z stays at ~0.024 (body height, no flying/falling in ENU z=Up)
  - Robots translate in +x (East) at ~0.01 m/step (0.1 m/s × 0.1 s)
  - y stays approximately constant (no lateral drift)

Run via the run_motion_test.py helper (creates a temp WBT pointing here).
"""
from __future__ import annotations
import json
import math
import os
import sys

_WEBOTS_HOME = os.environ.get("WEBOTS_HOME",
                               r"C:\Users\toaya\AppData\Local\Programs\Webots")
sys.path.insert(0, os.path.join(_WEBOTS_HOME, "lib", "controller", "python"))

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))  # worktree root
sys.path.insert(0, os.path.join(_ROOT, "src"))

from controller import Supervisor  # noqa: E402

N_ROBOTS = 20
CTRL_STEP_MS = 100
N_STEPS = 100          # short diagnostic run
LOG_EVERY = 10         # log positions every N steps
HEADING = 0.0          # face north (+x in NUE)

def main() -> None:
    sv = Supervisor()

    # Get all robot nodes and their customData fields
    robot_nodes = []
    cd_fields = []
    for i in range(N_ROBOTS):
        node = sv.getFromDef(f"ROBOT{i}")
        if node is None:
            raise RuntimeError(f"DEF ROBOT{i} not found")
        robot_nodes.append(node)
        cd_fields.append(node.getField("customData"))

    # Send heading=0, alive=True to all robots
    msg = json.dumps({"h": HEADING, "alive": True})
    for f in cd_fields:
        f.setSFString(msg)

    print(f"[motion_test] initial positions (Webots x, y, z):", flush=True)
    for i, node in enumerate(robot_nodes):
        p = node.getPosition()
        print(f"  ROBOT{i}: x={p[0]:.4f} y={p[1]:.4f} z={p[2]:.4f}", flush=True)

    step = 0
    while sv.step(CTRL_STEP_MS) != -1:
        step += 1
        if step % LOG_EVERY == 0:
            print(f"[motion_test] step={step}", flush=True)
            for i, node in enumerate(robot_nodes):
                p = node.getPosition()
                print(f"  ROBOT{i}: x={p[0]:.4f} y={p[1]:.4f} z={p[2]:.4f}", flush=True)
        if step >= N_STEPS:
            break

    print("[motion_test] DONE", flush=True)
    sv.simulationQuit(0)

if __name__ == "__main__":
    main()
