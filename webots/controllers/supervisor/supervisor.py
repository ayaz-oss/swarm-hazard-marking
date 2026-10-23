"""Supervisor controller for the swarm-hazard Webots replication.

Command-line args (controllerArgs in the WBT):
  argv[1] : controller name, one of C0, C1, C2, C4   (default: C2)
  argv[2] : integer seed                               (default: 0)
  argv[3] : output CSV path (default: auto, in results/)
  argv[4] : n_steps override (default: 10000)

Coordinate conventions
  Sim coords    : x, y ∈ [0, 10] (matches swarmhazard Config)
  Webots coords : x_w = x_s - 5, z_w = y_s - 5 (y_w = up, near 0 for floor)

Time-step design
  basicTimeStep = 20 ms (set in the WBT)
  CTRL_STEP_MS  = 100 ms → call supervisor.step(100) each iteration
  This equals 5 physics sub-steps per control step (= model dt 0.1 s).

The supervisor owns all virtual state:
  - World (item patches, respawning, hazard & lethality)
  - RepellentField (shared repellent, deposit & decay)
  - Per-robot state: SEARCH / RETURN / OUTBOUND, alive, last_pickup
  - Desired headings (updated by the same behavioural logic as the 2-D sim)
  - Seen matrix (for C2 wreck marking)

Each control step:
  1. Read robot positions from Webots via Supervisor API.
  2. Update desired headings using behavioral logic (same RNG as 2-D sim).
  3. Check hazard deaths, pickups, deliveries.
  4. Deposit / decay the repellent field.
  5. Write customData JSON to each robot (desired_heading, alive).
  6. After n_steps: write a CSV row and call simulationQuit(0).
"""

from __future__ import annotations

import csv
import json
import math
import os
import sys
import time
from pathlib import Path

import numpy as np

# ── locate the Webots Python controller library ──────────────────────────────
_WEBOTS_HOME = os.environ.get(
    "WEBOTS_HOME",
    r"C:\Users\toaya\AppData\Local\Programs\Webots",
)
sys.path.insert(0, os.path.join(_WEBOTS_HOME, "lib", "controller", "python"))

# ── locate swarmhazard package ───────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))   # .../supervisor/
_WEBOTS_DIR = os.path.dirname(os.path.dirname(_HERE))  # .../webots/
_ROOT = os.path.dirname(_WEBOTS_DIR)                    # worktree root
sys.path.insert(0, os.path.join(_ROOT, "src"))

from controller import Supervisor  # noqa: E402  (Webots controller lib)

from swarmhazard.config import Config, config_hash, load_config  # noqa: E402
from swarmhazard.controllers import avoidance  # noqa: E402
from swarmhazard.geometry import norm  # noqa: E402
from swarmhazard.pheromone import RepellentField  # noqa: E402
from swarmhazard.robots import OUTBOUND, RETURN, SEARCH, make_swarm  # noqa: E402
from swarmhazard.seeding import make_rng  # noqa: E402
from swarmhazard.world import (  # noqa: E402
    hazard_failures,
    in_hazard,
    make_world,
    respawn_item,
)

# ── constants ────────────────────────────────────────────────────────────────
CTRL_STEP_MS = 100          # control step in milliseconds (= model dt 0.1 s)
ARENA_HALF = 5.0            # sim arena centre is at Webots origin
N_ROBOTS = 20
VALID_CONTROLLERS = ("C0", "C1", "C2", "C4")


# ── coordinate helpers ───────────────────────────────────────────────────────

def webots_to_sim(wx: float, wz: float) -> tuple[float, float]:
    """Webots (x_w, z_w) → sim (x_s, y_s)."""
    return wx + ARENA_HALF, wz + ARENA_HALF


def sim_to_webots(xs: float, ys: float) -> tuple[float, float]:
    """Sim (x_s, y_s) → Webots (x_w, z_w)."""
    return xs - ARENA_HALF, ys - ARENA_HALF


# ── heading helpers ──────────────────────────────────────────────────────────

def wrap(angle: float) -> float:
    """Wrap angle to (−π, π]."""
    return math.atan2(math.sin(angle), math.cos(angle))


def unit_vec(theta: np.ndarray) -> np.ndarray:
    return np.column_stack((np.cos(theta), np.sin(theta)))


# ── CSV columns (match existing results/*.csv) ────────────────────────────────
CSV_COLS = [
    "experiment", "cell", "controller", "seed", "config_hash",
    "delivered", "picked_up", "items_lost", "carrying", "robots_lost",
    "first_loss_step", "steps", "false_sightings", "alerts_sent",
    "auc_final", "auc_mean", "auc_series", "hazard_area",
    "repellent_in_hazard", "trip_steps_mean", "search_steps_mean",
    "nest_steps", "wall_s",
    # Webots-specific extras
    "simulator",
]


def _row_defaults() -> dict:
    return dict(
        false_sightings=0, alerts_sent=0,
        auc_final=float("nan"), auc_mean=float("nan"), auc_series="",
        repellent_in_hazard=float("nan"),
        trip_steps_mean=float("nan"), search_steps_mean=float("nan"),
        simulator="webots",
    )


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    # --- parse args -----------------------------------------------------------
    argv = sys.argv
    controller_name = argv[1] if len(argv) > 1 else "C2"
    seed = int(argv[2]) if len(argv) > 2 else 0
    out_path = argv[3] if len(argv) > 3 else None
    n_steps_override = int(argv[4]) if len(argv) > 4 else None

    if controller_name not in VALID_CONTROLLERS:
        raise ValueError(f"Controller {controller_name!r} not in {VALID_CONTROLLERS}")

    # --- load config ----------------------------------------------------------
    cfg_path = Path(_ROOT) / "configs" / "baseline.yaml"
    tuned_path = Path(_ROOT) / "configs" / "tuned_params_fidelity.yaml"
    cfg = load_config(cfg_path, controller=controller_name)
    # Apply tuned parameters (same as E1F)
    import yaml
    tuned = yaml.safe_load(tuned_path.read_text()) or {}
    tuned["controller"] = controller_name
    cfg = load_config(cfg_path, **tuned)

    n_steps = n_steps_override if n_steps_override is not None else cfg.n_steps

    # --- default output path --------------------------------------------------
    if out_path is None:
        results_dir = Path(_ROOT) / "results"
        results_dir.mkdir(exist_ok=True)
        out_path = str(results_dir / "W1.csv")

    # --- RNG (same seeding as experiment.py: experiment="W1", cell=0, seed) --
    rng = make_rng("W1", 0, seed)
    (layout_rng, motion_rng, respawn_rng, hazard_rng,
     _background_rng, _noise_rng) = rng.spawn(6)

    # --- swarmhazard world model ---------------------------------------------
    world = make_world(cfg, layout_rng)
    swarm = make_swarm(cfg, layout_rng)
    field = RepellentField(cfg.arena_size, cfg.grid_cell)
    seen = np.zeros((N_ROBOTS, N_ROBOTS), dtype=bool)
    nest = np.asarray(cfg.nest_center, dtype=float)

    # Per-robot state tracked by supervisor
    alive = swarm.alive.copy()         # (N,) bool
    state = swarm.state.copy()         # (N,) SEARCH/RETURN/OUTBOUND
    pos = swarm.pos.copy()             # (N, 2) sim coords (read from Webots)
    heading = swarm.heading.copy()     # (N,) desired heading (radians)
    last_pickup = swarm.last_pickup.copy()  # (N, 2) or NaN

    # Metrics
    delivered = 0
    picked_up = 0
    items_lost = 0
    first_loss_step = -1
    nest_steps = 0
    trip_steps_total = 0
    trip_count = 0
    search_steps_total = 0
    search_count = 0
    pickup_step = np.full(N_ROBOTS, -1, dtype=np.int64)
    last_event_step = np.zeros(N_ROBOTS, dtype=np.int64)

    # --- Webots supervisor setup ---------------------------------------------
    sv = Supervisor()
    # Collect robot nodes
    robot_nodes = []
    cd_fields = []
    for i in range(N_ROBOTS):
        node = sv.getFromDef(f"ROBOT{i}")
        if node is None:
            raise RuntimeError(f"DEF ROBOT{i} not found in the world file")
        robot_nodes.append(node)
        cd_fields.append(node.getField("customData"))

    def _read_positions() -> np.ndarray:
        """Read Webots robot positions → sim coordinates (N, 2)."""
        out = np.empty((N_ROBOTS, 2))
        for i, node in enumerate(robot_nodes):
            p = node.getPosition()   # [x_w, y_w, z_w]
            out[i] = webots_to_sim(p[0], p[2])
        return out

    def _send_customdata(i: int, desired_heading: float, robot_alive: bool) -> None:
        payload = json.dumps({"h": round(desired_heading, 6), "alive": robot_alive})
        cd_fields[i].setSFString(payload)

    # --- simulation loop -----------------------------------------------------
    t_wall_start = time.perf_counter()
    sim_step = 0

    # Initial customData broadcast (all robots alive, heading 0)
    for i in range(N_ROBOTS):
        _send_customdata(i, float(heading[i]), True)

    while sv.step(CTRL_STEP_MS) != -1:
        # 1. Read actual positions from Webots physics
        pos[:] = _read_positions()

        # 2. Clip positions to arena bounds (physics rounding)
        pos[:] = np.clip(pos, 0.0, cfg.arena_size)

        # 3. Heading noise for searchers (same RNG call structure as sim.py)
        noise = motion_rng.normal(0.0, cfg.turn_noise, N_ROBOTS)
        heading[alive & (state == SEARCH)] += noise[alive & (state == SEARCH)]

        # 4. Choose desired headings
        _choose_headings(
            cfg, pos, heading, alive, state, last_pickup, world, field, nest,
            seen, cfg.sense_range,
        )

        # 5. Observation: nest proximity steps (before pickup/delivery)
        dist_to_nest = norm(pos - nest)
        nest_steps += int((alive & (dist_to_nest < 1.5)).sum())

        # 6. Pickup (SEARCH robot within pickup_radius of an item)
        idx_search = np.flatnonzero(alive & (state == SEARCH))
        if len(idx_search) and len(world.item_pos):
            items = world.item_pos
            dist = norm(items[None, :, :] - pos[idx_search][:, None, :])  # (S, M)
            close = np.flatnonzero(dist.min(axis=1) < cfg.pickup_radius)
            changed = False
            for row in range(close[0] if len(close) else len(idx_search), len(idx_search)):
                i = idx_search[row]
                d = norm(items - pos[i]) if changed else dist[row]
                j = int(d.argmin())
                if d[j] < cfg.pickup_radius:
                    state[i] = RETURN
                    picked_up += 1
                    search_steps_total += sim_step - int(last_event_step[i])
                    search_count += 1
                    pickup_step[i] = sim_step
                    last_pickup[i] = pos[i].copy()
                    respawn_item(world, j, respawn_rng)
                    changed = True

        # 7. Delivery (RETURN robot inside nest)
        returning = alive & (state == RETURN)
        at_nest = returning & (dist_to_nest < cfg.nest_radius)
        fresh = motion_rng.uniform(-np.pi, np.pi, N_ROBOTS)  # always drawn
        if at_nest.any():
            for i in np.flatnonzero(at_nest):
                if pickup_step[i] >= 0:
                    trip_steps_total += sim_step - int(pickup_step[i])
                    trip_count += 1
                last_event_step[i] = sim_step
            if cfg.search_start == "last_pickup":
                has_pickup = at_nest & ~np.isnan(last_pickup[:, 0])
                state[has_pickup] = OUTBOUND
                no_pickup = at_nest & ~has_pickup
                state[no_pickup] = SEARCH
                heading[no_pickup] = fresh[no_pickup]
            else:
                state[at_nest] = SEARCH
                heading[at_nest] = fresh[at_nest]
        delivered += int(at_nest.sum())

        # 8. Hazard deaths
        dies = hazard_failures(world, pos, alive, cfg.lethality, hazard_rng)
        if dies.any():
            items_lost += int((dies & (state == RETURN)).sum())
            alive[dies] = False
            if first_loss_step < 0:
                first_loss_step = sim_step

        # 9. C2 marking: deposit on newly seen wrecks
        if cfg.controller == "C2":
            dead_idx = np.flatnonzero(~alive)
            if len(dead_idx):
                dist_wd = norm(pos[:, None, :] - pos[None, dead_idx, :])  # (N, D)
                visible = alive[:, None] & (dist_wd < cfg.sense_range)
                new_sightings = visible & ~seen[:, dead_idx]
                for col in np.flatnonzero(new_sightings.any(axis=0)):
                    amount = cfg.deposit_amount * new_sightings[:, col].sum()
                    field.deposit(pos[dead_idx[col]], amount, cfg.deposit_sigma)
                seen[:, dead_idx] |= visible

        # 10. Field decay
        if cfg.controller in ("C2",):
            field.decay(cfg.decay)

        # 11. Write customData to each robot
        dead_pos = pos[~alive]
        dead_arr = dead_pos if len(dead_pos) else np.zeros((0, 2))
        for i in range(N_ROBOTS):
            _send_customdata(i, float(heading[i]), bool(alive[i]))

        sim_step += 1
        if sim_step >= n_steps:
            break

    wall_s = round(time.perf_counter() - t_wall_start, 3)

    # --- write CSV row --------------------------------------------------------
    c_hash = config_hash(cfg)
    hazard_area = float(
        np.pi * sum(r**2 for r in cfg.hazards[:][2::3])
        if hasattr(cfg.hazards, '__iter__') else 0.0
    )
    # Compute hazard area correctly
    hazard_area = float(sum(math.pi * h[2]**2 for h in cfg.hazards))

    row = {
        **_row_defaults(),
        "experiment": "W1",
        "cell": 0,
        "controller": controller_name,
        "seed": seed,
        "config_hash": c_hash,
        "delivered": delivered,
        "picked_up": picked_up,
        "items_lost": items_lost,
        "carrying": int((alive & (state == RETURN)).sum()),
        "robots_lost": int((~alive).sum()),
        "first_loss_step": first_loss_step,
        "steps": sim_step,
        "nest_steps": nest_steps,
        "hazard_area": hazard_area,
        "trip_steps_mean": (float(trip_steps_total) / float(trip_count)
                            if trip_count > 0 else float("nan")),
        "search_steps_mean": (float(search_steps_total) / float(search_count)
                              if search_count > 0 else float("nan")),
        "wall_s": wall_s,
    }

    out_file = Path(out_path)
    write_header = not out_file.exists() or out_file.stat().st_size == 0
    with open(out_file, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLS, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        writer.writerow(row)

    print(f"[supervisor] done: {delivered} delivered, {(~alive).sum()} lost, "
          f"{sim_step} steps, {wall_s:.1f}s wall", flush=True)

    sv.simulationQuit(0)


# ── heading logic (adapted from sim.py _choose_headings) ─────────────────────

def _choose_headings(
    cfg: Config,
    pos: np.ndarray,
    heading: np.ndarray,
    alive: np.ndarray,
    state: np.ndarray,
    last_pickup: np.ndarray,
    world,
    field: RepellentField,
    nest: np.ndarray,
    seen: np.ndarray,
    sense_range: float,
) -> None:
    """Update heading[] in-place: desired heading for next control step."""
    n = len(pos)

    # Items: searchers head toward nearest visible item
    if len(world.item_pos):
        to_items = world.item_pos[None, :, :] - pos[:, None, :]
        dist = norm(to_items)
        nearest = dist.argmin(axis=1)
        rows = np.arange(n)
        sees_item = alive & (state == SEARCH) & (dist[rows, nearest] < sense_range)
        v = to_items[rows, nearest]
        heading[sees_item] = np.arctan2(v[sees_item, 1], v[sees_item, 0])

    # Returners head toward nest
    returning = alive & (state == RETURN)
    if returning.any():
        v = nest - pos
        heading[returning] = np.arctan2(v[returning, 1], v[returning, 0])

    # OUTBOUND: head toward last_pickup; switch to SEARCH when close enough
    outbound = alive & (state == OUTBOUND)
    if outbound.any():
        idx = np.flatnonzero(outbound)
        v_ob = last_pickup[idx] - pos[idx]
        dist_ob = norm(v_ob)
        arrived = dist_ob < sense_range
        state[idx[arrived]] = SEARCH
        still_out = ~arrived
        if still_out.any():
            i_out = idx[still_out]
            heading[i_out] = np.arctan2(v_ob[still_out, 1], v_ob[still_out, 0])

    # Avoidance push (wreck repulsion and/or field gradient)
    dead_idx = np.flatnonzero(~alive)
    dead_pos = pos[dead_idx] if len(dead_idx) else np.zeros((0, 2))

    push = avoidance(
        cfg, pos, dead_pos, field, world,
        detected=None, maps=None, records=None, t=0,
        alive=alive, alert_positions=None,
    )

    steer = unit_vec(heading) + push
    heading[:] = np.where(alive, np.arctan2(steer[:, 1], steer[:, 0]), heading)


def unit_vec(theta: np.ndarray) -> np.ndarray:
    return np.column_stack((np.cos(theta), np.sin(theta)))


if __name__ == "__main__":
    main()
