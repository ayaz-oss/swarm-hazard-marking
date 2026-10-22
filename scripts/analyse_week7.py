"""Exploratory and confirmatory analysis of the week-7 F experiments.

Reads results/E1F.csv … E8F.csv (and their nest-restart counterparts for
model_comparison.csv). Accepted only if each F CSV ran from a clean commit
whose golden file reproduces every golden case from E1's commit (fe78c66).
Writes results/analysis/week7/:
  confirmatory_F.csv           H1F-H4F (same tests as H1-H4, on E1F and E2F cell 3)
  <name>_descriptive.csv       per experiment, per cell × controller
  <name>_exploratory.csv       E2F-E5F: within-cell + cross-cell C2 tests (one Holm family)
  <name>_tests.csv             E6bF, E7bF, E8F: week-5 family (one Holm family per experiment)
  identity_checks.csv          E7bF and E8F
  model_comparison.csv         medians of delivered and robots_lost, F vs nest-restart, descriptive

Usage: python scripts/analyse_week7.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyse import _golden_at, _golden_branch_problems, completeness_problems, golden_unchanged  # noqa: E402

from swarmhazard.analysis import (  # noqa: E402
    BOOT_SEED,
    confirmatory,
    identity_checks,
    week5_tests,
    week7_descriptive,
    week7_e2e5_tests,
)

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
OUT = RESULTS / "analysis" / "week7"
E1_COMMIT = "fe78c66"

F_NAMES = ["E1F", "E2F", "E3F", "E4F", "E5F", "E6bF", "E7bF", "E8F"]
# Nest-restart counterparts for model_comparison.csv
COUNTERPARTS = {"E1F": "E1", "E2F": "E2", "E3F": "E3", "E4F": "E4",
                "E5F": "E5", "E6bF": "E6b", "E7bF": "E7b", "E8F": "E8"}


def provenance_problems(name: str, df: pd.DataFrame) -> list[str]:
    commits = sorted(set(df["git_commit"].astype(str)))
    if len(commits) != 1 or commits[0].endswith("-dirty") or commits[0] == "unknown":
        return [f"{name}: git_commit values {commits} are not one clean commit"]
    if "package_root" in df and df["package_root"].astype(str).nunique() != 1:
        return [f"{name}: package_root must hold a single value, found "
                f"{sorted(set(df['package_root'].astype(str)))}"]
    c = commits[0]
    try:
        same = golden_unchanged(_golden_at(E1_COMMIT, ROOT), _golden_at(c, ROOT))
    except subprocess.CalledProcessError:
        same = False
    if not same:
        return [f"{name}: golden cases from {E1_COMMIT} are not reproduced at {c}"]
    print(f"{name}: code {c} (every golden case from {E1_COMMIT} reproduced bit-identically)")
    return _golden_branch_problems(name, df, E1_COMMIT, c, ROOT)


def _medians(df: pd.DataFrame, name: str) -> pd.DataFrame:
    """Per cell × controller: median delivered and robots_lost."""
    rows = []
    for (cell, ctrl), sub in df.groupby(["cell", "controller"]):
        rows.append({
            "experiment": name,
            "cell": int(cell),
            "controller": ctrl,
            "delivered_median": float(sub["delivered"].median()),
            "robots_lost_median": float(sub["robots_lost"].median()),
        })
    return pd.DataFrame(rows)


def model_comparison(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Descriptive medians of each F experiment next to its nest-restart counterpart."""
    parts = []
    for fname, cname in COUNTERPARTS.items():
        if fname not in frames:
            continue
        f_med = _medians(frames[fname], fname)
        if cname in frames:
            c_med = _medians(frames[cname], cname)
            merged = f_med.merge(
                c_med.rename(columns={
                    "delivered_median": "delivered_median_nest",
                    "robots_lost_median": "robots_lost_median_nest",
                }),
                on=["cell", "controller"], how="left",
            )
        else:
            merged = f_med
            merged["delivered_median_nest"] = float("nan")
            merged["robots_lost_median_nest"] = float("nan")
        merged["counterpart"] = cname
        parts.append(merged)
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def main() -> int:
    missing = [n for n in F_NAMES if not (RESULTS / f"{n}.csv").exists()]
    if missing:
        print("missing: " + ", ".join(missing), file=sys.stderr)
        return 1
    frames_f = {n: pd.read_csv(RESULTS / f"{n}.csv") for n in F_NAMES}

    # Provenance and completeness checks
    problems = []
    for name, df in frames_f.items():
        problems.extend(provenance_problems(name, df))
        problems.extend(completeness_problems(name, df))
    if problems:
        print("Checks failed, no tables written:", file=sys.stderr)
        for p in problems:
            print("  " + p, file=sys.stderr)
        return 1

    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(BOOT_SEED)

    # Confirmatory: H1F, H2F, H4F on E1F; H3F on E2F cell 3 (reuse analysis.confirmatory)
    conf = confirmatory(
        frames_f["E1F"],
        frames_f["E2F"],
        np.random.default_rng(BOOT_SEED),
    )
    # Relabel hypothesis IDs to F variants
    conf["hypothesis"] = conf["hypothesis"].str.replace(r"^(H\d)$", r"\1F", regex=True)
    conf.to_csv(OUT / "confirmatory_F.csv", index=False)
    pd.set_option("display.width", 200)
    print(conf[["hypothesis", "x", "y", "metric", "median_x", "median_y",
                "a12", "p", "p_holm", "supported"]].round(4).to_string(index=False))

    # Descriptive tables for all F experiments
    for name, df in frames_f.items():
        week7_descriptive(df, np.random.default_rng(BOOT_SEED)).to_csv(
            OUT / f"{name}_descriptive.csv", index=False)

    # Exploratory tests for E2F-E5F (within-cell + across-cell C2, one Holm family)
    for name in ("E2F", "E3F", "E4F", "E5F"):
        week7_e2e5_tests(name, frames_f[name], np.random.default_rng(BOOT_SEED)).to_csv(
            OUT / f"{name}_exploratory.csv", index=False)

    # Week-5 families for E6bF, E7bF, E8F
    for name in ("E6bF", "E7bF", "E8F"):
        week5_tests(name, frames_f[name], np.random.default_rng(BOOT_SEED)).to_csv(
            OUT / f"{name}_tests.csv", index=False)

    # Identity checks for E7bF and E8F
    ids_rows = []
    for name in ("E7bF", "E8F"):
        ids = identity_checks(name, frames_f[name])
        if len(ids):
            ids_rows.append(ids)
    if ids_rows:
        ids_all = pd.concat(ids_rows, ignore_index=True)
        ids_all.to_csv(OUT / "identity_checks.csv", index=False)
        print(ids_all.to_string(index=False))

    # Model comparison: F experiments vs nest-restart counterparts
    frames_nest = {}
    for cname in set(COUNTERPARTS.values()):
        path = RESULTS / f"{cname}.csv"
        if path.exists():
            frames_nest[cname] = pd.read_csv(path)
    model_comparison({**frames_f, **frames_nest}).to_csv(OUT / "model_comparison.csv", index=False)

    for name in F_NAMES:
        print(f"wrote {name} tables")
    return 0


if __name__ == "__main__":
    sys.exit(main())
