"""Exploratory analysis of the week-6 experiment (docs/hypotheses.md, "Week-6 experiment").

Reads results/E9.csv. Accepted only if it ran from a clean commit whose golden file
reproduces every golden case recorded at E1's commit (fe78c66), from that commit's
frozen worktree, with the full set of cells, controllers and seeds. Writes
results/analysis/week6/: E9_descriptive.csv, E9_tests.csv (82 tests; ONE Holm pass),
identity_checks.csv.

Usage: python scripts/analyse_week6.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyse import _golden_at, _golden_branch_problems, completeness_problems, golden_unchanged  # noqa: E402

from swarmhazard.analysis import BOOT_SEED, identity_checks, week6_descriptive, week6_tests  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
OUT = RESULTS / "analysis" / "week6"
E1_COMMIT = "fe78c66"


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
    name = "E9"
    path = RESULTS / f"{name}.csv"
    if not path.exists():
        print(f"missing: {path}", file=sys.stderr)
        return 1
    df = pd.read_csv(path)
    problems = provenance_problems(name, df) + completeness_problems(name, df)
    if problems:
        print("Checks failed, no tables written:", file=sys.stderr)
        for p in problems:
            print("  " + p, file=sys.stderr)
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(BOOT_SEED)
    week6_tests(df, rng).to_csv(OUT / f"{name}_tests.csv", index=False)
    week6_descriptive(df, np.random.default_rng(BOOT_SEED)).to_csv(
        OUT / f"{name}_descriptive.csv", index=False)
    ids = identity_checks(name, df)
    ids.to_csv(OUT / "identity_checks.csv", index=False)
    print(ids.to_string(index=False))
    print(f"wrote {name} tables")
    return 0


if __name__ == "__main__":
    sys.exit(main())
