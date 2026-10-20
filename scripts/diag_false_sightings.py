"""Small descriptive diagnostic (not pre-registered) for E7b cell 5: why do false sightings
raise C2's deliveries? C2 with E7b's paired streams, seeds 0-19, five variants (no noise; q_false
1e-4; q_false with repel_weight 0; q_false without the hazard; no noise without the hazard).
Variants a and b re-run E7b cells 0 and 5 exactly. Reports the share of the final repellent field
within 1.5 m of the nest and robot-steps spent within 1.5 m of the nest. Observes only.

Usage: python scripts/diag_false_sightings.py [OUT_CSV]   (default results/mechanism/false_sightings_diag.csv)
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

VARIANTS = {
    "a_no_noise": {},
    "b_qfalse": {"q_false": 0.0001},
    "c_qfalse_no_steer": {"q_false": 0.0001, "repel_weight": 0.0},
    "d_qfalse_no_hazard": {"q_false": 0.0001, "hazards": []},
    "e_no_noise_no_hazard": {"hazards": []},
}


def one(args):
    name, seed = args
    spec = load_experiment(ROOT / "configs/experiments/E7b.yaml", ROOT)
    job = next(j for j in build_jobs(spec, seeds=1) if j["controller"] == "C2" and j["cell"] == 0)
    cfg = load_config(ROOT / job["base"], **{**job["overrides"], **VARIANTS[name]}, controller="C2")
    sim = Simulation(cfg, make_rng("E7b", 0, seed))
    nest = np.asarray(cfg.nest_center)
    nest_time = 0
    for _ in range(cfg.n_steps):
        sim.step()
        nest_time += int((np.linalg.norm(sim.swarm.pos[sim.swarm.alive] - nest, axis=1) < 1.5).sum())
    r = sim.result()
    g = sim.field.grid
    c = sim.field.centres
    gx, gy = np.meshgrid(c, c, indexing="ij")
    near = np.hypot(gx - nest[0], gy - nest[1]) < 1.5
    return {"variant": name, "seed": seed, "delivered": r["delivered"], "robots_lost": r["robots_lost"],
            "false_sightings": r["false_sightings"],
            "field_share_near_nest": float(g[near].sum() / g.sum()) if g.sum() > 0 else np.nan,
            "robot_steps_near_nest": nest_time}


if __name__ == "__main__":
    jobs = [(v, s) for v in VARIANTS for s in range(20)]
    with ProcessPoolExecutor(4) as pool:
        rows = list(pool.map(one, jobs))
    df = pd.DataFrame(rows)
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "results" / "mechanism" / "false_sightings_diag.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    pd.set_option("display.width", 200)
    print(df.groupby("variant")[["delivered", "robots_lost", "false_sightings", "field_share_near_nest",
                                  "robot_steps_near_nest"]].median())
