"""Small descriptive diagnostic (not pre-registered) for E2 cell 3, the random-failure control
behind H3: where did the random wrecks fall relative to the nest, and could marks near the nest
explain why C2 delivered slightly more than C0 there (note 03, item 5)? Week 5's E7b diagnostic
found that phantom marks near the nest raised C2's deliveries.

Re-runs C0 and C2 on E2 cell 3 with E2's random streams, seeds 0-99, and observes only: the
wreck positions at the end of the run, the share of C2's final repellent within 1.5 m of the
nest centre, and robot-steps spent within 1.5 m of the nest. Delivered and robots lost must
match E2.csv row for row (checked in main).

Usage: python scripts/diag_e2_random_wrecks.py [OUT_CSV]   (default results/mechanism/e2_random_wrecks.csv)
"""
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
from swarmhazard.experiment import build_jobs, load_experiment
from swarmhazard.config import load_config
from swarmhazard.seeding import make_rng
from swarmhazard.sim import Simulation

NEAR = 1.5  # m from the nest centre, as in diag_false_sightings.py
CELL = 3


def one(args):
    controller, seed = args
    spec = load_experiment(ROOT / "configs/experiments/E2.yaml", ROOT)
    job = next(j for j in build_jobs(spec, seeds=1) if j["controller"] == controller and j["cell"] == CELL)
    cfg = load_config(ROOT / job["base"], **job["overrides"], controller=controller)
    sim = Simulation(cfg, make_rng("E2", CELL, seed))
    nest = np.asarray(cfg.nest_center)
    nest_time = 0
    for _ in range(cfg.n_steps):
        sim.step()
        nest_time += int((np.linalg.norm(sim.swarm.pos[sim.swarm.alive] - nest, axis=1) < NEAR).sum())
    r = sim.result()
    d = np.linalg.norm(sim.swarm.pos[~sim.swarm.alive] - nest, axis=1)
    row = {"controller": controller, "seed": seed, "delivered": r["delivered"],
           "robots_lost": r["robots_lost"], "wrecks_near_nest": int((d < NEAR).sum()),
           "wreck_dist_median": float(np.median(d)) if d.size else np.nan,
           "wreck_dists": ";".join(f"{x:.3f}" for x in d),
           "robot_steps_near_nest": nest_time, "field_share_near_nest": np.nan}
    if controller == "C2":
        g, c = sim.field.grid, sim.field.centres
        gx, gy = np.meshgrid(c, c, indexing="ij")
        near = np.hypot(gx - nest[0], gy - nest[1]) < NEAR
        row["field_share_near_nest"] = float(g[near].sum() / g.sum()) if g.sum() > 0 else np.nan
    return row


if __name__ == "__main__":
    jobs = [(c, s) for c in ("C0", "C2") for s in range(100)]
    with ProcessPoolExecutor(4) as pool:
        df = pd.DataFrame(list(pool.map(one, jobs)))
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "results" / "mechanism" / "e2_random_wrecks.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(df.groupby("controller")[["delivered", "robots_lost", "wrecks_near_nest", "wreck_dist_median",
                                     "robot_steps_near_nest", "field_share_near_nest"]].median())
