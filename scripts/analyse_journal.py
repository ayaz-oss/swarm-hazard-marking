"""Exploratory analysis of the journal-package experiments (E10, E11, E12).

Reads results/E10.csv, E11.csv, E12.csv. Accepted only if each CSV ran from a clean commit
that reproduces every golden case (same check as analyse_week7.py). Writes:
  results/analysis/journal/
    <name>_descriptive.csv       per cell × controller
    <name>_tests.csv             per experiment tests (one Holm family per experiment)
    e10_c7_vs_c1.csv             E10: C7 vs C1 robots_lost per cell

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
    compare,
    holm,
    wilcoxon_p,
    week7_descriptive,
    exploratory,
    paired,
)

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
OUT = RESULTS / "analysis" / "journal"

# Same baseline commit as week-7 (or the journal-package one once data is run)
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


def journal_tests(name: str, df: pd.DataFrame, rng: np.random.Generator,
                  n_boot: int = 10_000) -> pd.DataFrame:
    """One Holm family per experiment.

    For all experiments: Friedman per cell + two-sided Wilcoxon vs C2 on delivered and robots_lost.
    E10 additionally: C7 vs C1 on robots_lost in every cell.
    """
    # Standard exploratory (Friedman + vs C2)
    parts = [exploratory(df, rng, n_boot).assign(kind="vs_C2")]

    # E10 extra: C7 vs C1 robots_lost in every cell
    if name == "E10" and "C7" in df["controller"].unique() and "C1" in df["controller"].unique():
        for cell in sorted(df["cell"].unique()):
            try:
                x, y = paired(df, "robots_lost", "C7", "C1", cell=cell)
            except (KeyError, ValueError):
                continue
            row = compare(x, y, rng, n_boot)
            row.update(kind="C7_vs_C1", cell=int(cell), metric="robots_lost",
                       x="C7", y="C1",
                       p=wilcoxon_p(x, y, "two-sided"),
                       friedman_p=float("nan"))
            parts.append(pd.DataFrame([row]))

    out = pd.concat(parts, ignore_index=True)
    out["p_holm"] = holm(out["p"].to_numpy())
    return out


def journal_descriptive(name: str, df: pd.DataFrame, rng: np.random.Generator,
                        n_boot: int = 10_000) -> pd.DataFrame:
    """week7_descriptive, which already handles alerts_sent and known_frac gracefully."""
    return week7_descriptive(df, rng, n_boot)


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
    rng = np.random.default_rng(BOOT_SEED)

    for name, df in frames.items():
        # Descriptive table
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            desc = journal_descriptive(name, df, np.random.default_rng(BOOT_SEED))
        desc.to_csv(OUT / f"{name}_descriptive.csv", index=False)

        # Tests
        tests = journal_tests(name, df, np.random.default_rng(BOOT_SEED))
        tests.to_csv(OUT / f"{name}_tests.csv", index=False)
        print(f"wrote {name} tables")

    # E10 C7 vs C1 robots_lost table (separate file for clarity)
    if "E10" in frames:
        e10_c7c1 = journal_tests("E10", frames["E10"], np.random.default_rng(BOOT_SEED))
        c7c1 = e10_c7c1[e10_c7c1.get("kind", pd.Series()) == "C7_vs_C1"]
        if not c7c1.empty:
            c7c1.to_csv(OUT / "e10_c7_vs_c1.csv", index=False)
            print("wrote e10_c7_vs_c1.csv")

    return 0


if __name__ == "__main__":
    sys.exit(main())
