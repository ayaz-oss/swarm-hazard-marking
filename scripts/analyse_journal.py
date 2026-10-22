"""Analysis of the journal-package experiments (E10, E11, E12).

Reads results/E10.csv, E11.csv, E12.csv.  Accepted only if each CSV ran from a
clean commit that reproduces every golden case (same provenance check as
analyse_week7.py).  Writes:
  results/analysis/journal/
    <name>_descriptive.csv       per cell x controller
    <name>_tests.csv             per experiment tests (one Holm family per experiment)

Usage: python scripts/analyse_journal.py
"""

from __future__ import annotations

import subprocess
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyse import _golden_at, _golden_branch_problems, completeness_problems, golden_unchanged  # noqa: E402

from swarmhazard.analysis import (  # noqa: E402
    BOOT_SEED,
    journal_tests,
    journal_descriptive,
    J_FAMILY_SIZES,
)

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
OUT = RESULTS / "analysis" / "journal"

# Baseline commit to verify golden-case reproducibility against
E1_COMMIT = "fe78c66"

J_NAMES = ["E10", "E11", "E12"]


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
    missing = [n for n in J_NAMES if not (RESULTS / f"{n}.csv").exists()]
    if missing:
        print("missing: " + ", ".join(missing), file=sys.stderr)
        return 1

    frames = {n: pd.read_csv(RESULTS / f"{n}.csv") for n in J_NAMES}

    # Provenance and completeness checks
    problems = []
    for name, df in frames.items():
        problems.extend(provenance_problems(name, df))
        problems.extend(completeness_problems(name, df))
    if problems:
        print("Checks failed, no tables written:", file=sys.stderr)
        for p in problems:
            print("  " + p, file=sys.stderr)
        return 1

    OUT.mkdir(parents=True, exist_ok=True)

    for name, df in frames.items():
        rng = np.random.default_rng(BOOT_SEED)

        # Descriptive table
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            desc = journal_descriptive(name, df, rng)
        desc.to_csv(OUT / f"{name}_descriptive.csv", index=False)

        # Tests: one Holm family per experiment
        rng = np.random.default_rng(BOOT_SEED)
        tests = journal_tests(name, df, rng)
        tests.to_csv(OUT / f"{name}_tests.csv", index=False)

        n_tests = len(tests)
        expected = J_FAMILY_SIZES.get(name)
        status = "" if expected is None else (
            f" (expected {expected}{'  OK' if n_tests == expected else '  MISMATCH'})")
        print(f"wrote {name}: {n_tests} tests{status}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
