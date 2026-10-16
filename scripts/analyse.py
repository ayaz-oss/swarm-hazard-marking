"""Run the pre-registered analysis (docs/hypotheses.md) on results/E*.csv.

Writes results/analysis/confirmatory.csv and, per experiment, *_descriptive.csv and
*_exploratory.csv. Each table uses its own bootstrap generator seeded 20261016, so every
table is reproducible on its own. Refuses to analyse an experiment whose CSV does not
match its spec (seed count, cells, controllers).

Usage: python scripts/analyse.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

from swarmhazard.analysis import BOOT_SEED, confirmatory, descriptive, exploratory
from swarmhazard.experiment import build_cells, load_experiment

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
OUT = RESULTS / "analysis"
MAIN = ["E1", "E2", "E3", "E4", "E5"]


def completeness_problems(name: str, df: pd.DataFrame) -> list[str]:
    spec = load_experiment(ROOT / "configs" / "experiments" / f"{name}.yaml", ROOT)
    problems = []
    want_cells = set(range(len(build_cells(spec))))
    want_ctrl = set(spec["controllers"])
    have_cells = set(df["cell"].astype(int))
    have_ctrl = set(df["controller"])
    if have_cells != want_cells:
        problems.append(f"{name}: cells missing {sorted(want_cells - have_cells)}, "
                        f"unexpected {sorted(have_cells - want_cells)}")
    if have_ctrl != want_ctrl:
        problems.append(f"{name}: controllers missing {sorted(want_ctrl - have_ctrl)}, "
                        f"unexpected {sorted(have_ctrl - want_ctrl)}")
    counts = df.groupby(["cell", "controller"]).size()
    for cell in sorted(want_cells):
        for ctrl in sorted(want_ctrl):
            n = int(counts.get((cell, ctrl), 0))
            if n != spec["seeds"]:
                problems.append(f"{name}: cell {cell} {ctrl} has {n} rows, expected {spec['seeds']}")
    return problems


def main() -> int:
    frames = {n: pd.read_csv(RESULTS / f"{n}.csv") for n in MAIN if (RESULTS / f"{n}.csv").exists()}
    if "E1" not in frames:
        print("results/E1.csv not found", file=sys.stderr)
        return 1
    problems = [p for name, df in frames.items() for p in completeness_problems(name, df)]
    if problems:
        print("Incomplete results, no tables written:", file=sys.stderr)
        for p in problems:
            print("  " + p, file=sys.stderr)
        return 1
    for name, df in frames.items():
        commits = sorted(set(df["git_commit"].astype(str)))
        if len(commits) != 1 or commits[0].endswith("-dirty"):
            print(f"WARNING {name}: git_commit values {commits}", file=sys.stderr)
    OUT.mkdir(parents=True, exist_ok=True)

    conf = confirmatory(frames["E1"], frames.get("E2"), np.random.default_rng(BOOT_SEED))
    conf.to_csv(OUT / "confirmatory.csv", index=False)
    pd.set_option("display.width", 200)
    print(conf[["hypothesis", "x", "y", "metric", "median_x", "median_y", "median_diff",
                "a12", "a12_lo", "a12_hi", "p", "p_holm", "supported"]].round(4).to_string(index=False))

    for name, df in frames.items():
        descriptive(df, np.random.default_rng(BOOT_SEED)).to_csv(
            OUT / f"{name}_descriptive.csv", index=False)
        exploratory(df, np.random.default_rng(BOOT_SEED)).to_csv(
            OUT / f"{name}_exploratory.csv", index=False)
        print(f"wrote {name} tables")
    return 0


if __name__ == "__main__":
    sys.exit(main())
