"""Run every (cell, controller, seed) of an experiment and save one CSV row per run.

Usage:
    python scripts/run_experiment.py configs/experiments/gate.yaml
    python scripts/run_experiment.py configs/experiments/gate.yaml --seeds 2 --n-steps 500   # smoke test

Refuses to run on uncommitted changes or an unknown git commit (unless a smoke
test or --allow-dirty), so every row's git_commit names the code that produced it.
"""

from __future__ import annotations

import os

os.environ.setdefault("OMP_NUM_THREADS", "1")  # one numpy thread per worker process

import argparse
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from functools import partial
from pathlib import Path

import pandas as pd

from swarmhazard.experiment import build_jobs, load_experiment, run_one
from swarmhazard.provenance import provenance

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("experiment", type=Path)
    parser.add_argument("--seeds", type=int, help="override the number of seeds (smoke tests)")
    parser.add_argument("--n-steps", type=int, help="override episode length (smoke tests)")
    parser.add_argument("--workers", type=int, default=4,
                        help="parallel processes (default 4: measured fastest on the development laptop)")
    parser.add_argument("--allow-dirty", action="store_true", help="run despite uncommitted changes")
    args = parser.parse_args()

    spec = load_experiment(args.experiment, ROOT)
    smoke = args.seeds is not None or args.n_steps is not None
    info = provenance(ROOT)  # recorded before running, so edits during the run cannot mislabel rows
    commit = info["git_commit"]
    if (commit.endswith("-dirty") or commit == "unknown") and not (smoke or args.allow_dirty):
        sys.exit(f"Refusing to run: code version is {commit!r}. Commit first, or pass --allow-dirty.")

    jobs = build_jobs(spec, seeds=args.seeds, n_steps=args.n_steps)
    start = time.perf_counter()
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        rows = list(pool.map(partial(run_one, root=ROOT), jobs, chunksize=4))

    df = pd.DataFrame(rows)
    for key, value in info.items():
        df[key] = value
    out = ROOT / "results" / f"{spec['name']}{'_smoke' if smoke else ''}.csv"
    out.parent.mkdir(exist_ok=True)
    df.to_csv(out, index=False)

    print(f"{len(df)} runs in {time.perf_counter() - start:.1f} s -> {out}")
    print(df.groupby(["cell", "controller"])[["delivered", "robots_lost"]].median())


if __name__ == "__main__":
    main()
