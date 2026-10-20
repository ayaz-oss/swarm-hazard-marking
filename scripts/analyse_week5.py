"""Exploratory analysis of the week-5 experiments (docs/hypotheses.md, "Week-5 experiments").

Reads results/E6b.csv, E7b.csv and E8.csv. Each is accepted only if it ran from a clean commit
whose golden file reproduces every golden case recorded at E1's commit (fe78c66), from that
commit's frozen worktree, with the full set of cells, controllers and seeds. Writes
results/analysis/week5/<name>_tests.csv (Holm within each experiment), <name>_descriptive.csv
and identity_checks.csv.

Usage: python scripts/analyse_week5.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyse import _golden_at, _golden_branch_problems, completeness_problems, golden_unchanged  # noqa: E402

from swarmhazard.analysis import BOOT_SEED, identity_checks, week5_descriptive, week5_tests  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
OUT = RESULTS / "analysis" / "week5"
E1_COMMIT = "fe78c66"
WEEK5 = ["E6b", "E7b", "E8"]


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


def main() -> int:
    missing = [n for n in WEEK5 if not (RESULTS / f"{n}.csv").exists()]
    if missing:
        print("missing: " + ", ".join(missing), file=sys.stderr)
        return 1
    frames = {n: pd.read_csv(RESULTS / f"{n}.csv") for n in WEEK5}
    problems = [p for n, df in frames.items() for p in provenance_problems(n, df) + completeness_problems(n, df)]
    if problems:
        print("Checks failed, no tables written:", file=sys.stderr)
        for p in problems:
            print("  " + p, file=sys.stderr)
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    checks = []
    for name, df in frames.items():
        week5_tests(name, df, np.random.default_rng(BOOT_SEED)).to_csv(OUT / f"{name}_tests.csv", index=False)
        week5_descriptive(df, np.random.default_rng(BOOT_SEED)).to_csv(OUT / f"{name}_descriptive.csv", index=False)
        checks.append(identity_checks(name, df))
        print(f"wrote {name} tables")
    ids = pd.concat(checks, ignore_index=True)
    ids.to_csv(OUT / "identity_checks.csv", index=False)
    print(ids.to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
