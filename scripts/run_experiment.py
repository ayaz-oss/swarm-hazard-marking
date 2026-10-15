"""Run every (controller, seed) pair of an experiment and save one CSV row per run.

Usage:
    python scripts/run_experiment.py configs/experiments/gate.yaml
    python scripts/run_experiment.py configs/experiments/gate.yaml --seeds 2 --n-steps 500   # smoke test
"""

from __future__ import annotations

import argparse
import platform
import subprocess
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from swarmhazard.config import config_hash, load_config
from swarmhazard.seeding import make_rng
from swarmhazard.sim import run

ROOT = Path(__file__).resolve().parents[1]


def git_commit() -> str:
    try:
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                             capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                               capture_output=True, text=True, check=True).stdout.strip()
        return sha + ("-dirty" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def run_one(job: dict) -> dict:
    cfg = load_config(ROOT / job["base"], **job["overrides"], controller=job["controller"])
    rng = make_rng(job["experiment"], job["cell"], job["seed"])
    start = time.perf_counter()
    row = run(cfg, rng)
    row.update(
        experiment=job["experiment"],
        cell=job["cell"],
        controller=job["controller"],
        seed=job["seed"],
        config_hash=config_hash(cfg),
        wall_s=round(time.perf_counter() - start, 3),
    )
    return row


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("experiment", type=Path)
    parser.add_argument("--seeds", type=int, help="override the number of seeds (smoke tests)")
    parser.add_argument("--n-steps", type=int, help="override episode length (smoke tests)")
    parser.add_argument("--workers", type=int, default=None, help="parallel processes (default: all cores)")
    args = parser.parse_args()

    spec = yaml.safe_load(args.experiment.read_text())
    overrides = dict(spec.get("overrides") or {})
    smoke = args.seeds is not None or args.n_steps is not None
    if args.n_steps is not None:
        overrides["n_steps"] = args.n_steps
    n_seeds = args.seeds if args.seeds is not None else spec["seeds"]

    jobs = [
        {"experiment": spec["name"], "base": spec["base"], "overrides": overrides,
         "controller": c, "cell": 0, "seed": s}
        for c in spec["controllers"]
        for s in range(n_seeds)
    ]
    start = time.perf_counter()
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        rows = list(pool.map(run_one, jobs))

    df = pd.DataFrame(rows)
    df["git_commit"] = git_commit()
    df["numpy"] = np.__version__
    df["python"] = platform.python_version()
    out = ROOT / "results" / f"{spec['name']}{'_smoke' if smoke else ''}.csv"
    out.parent.mkdir(exist_ok=True)
    df.to_csv(out, index=False)

    print(f"{len(df)} runs in {time.perf_counter() - start:.1f} s -> {out}")
    print(df.groupby("controller")[["delivered", "robots_lost"]].median())


if __name__ == "__main__":
    main()
