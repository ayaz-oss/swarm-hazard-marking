"""Run the pre-registered analysis (docs/hypotheses.md) on results/E1-E7.csv; E6/E7 are accepted
only if every golden case from E1's commit is unchanged at theirs.

Writes results/analysis/confirmatory.csv and, per experiment, *_descriptive.csv and
*_exploratory.csv. Each table uses its own bootstrap generator seeded 20261016, so every
table is reproducible on its own. Refuses to analyse an experiment whose CSV does not
match its spec (seed count, cells, controllers).

Usage: python scripts/analyse.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from swarmhazard.analysis import BOOT_SEED, confirmatory, descriptive, exploratory
from swarmhazard.experiment import build_cells, load_experiment

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
OUT = RESULTS / "analysis"
MAIN = ["E1", "E2", "E3", "E4", "E5", "E6", "E7"]


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
    for (cell, ctrl), g in df.groupby(["cell", "controller"]):
        if set(g["seed"].astype(int)) != set(range(spec["seeds"])):
            problems.append(f"{name}: cell {cell} {ctrl} seeds are not exactly 0..{spec['seeds'] - 1}")
    return problems


def _simulator_paths(root: Path) -> list[str]:
    src = root / "src" / "swarmhazard"
    files = sorted(f.relative_to(root).as_posix() for f in src.glob("**/*.py")
                   if f.name not in ("analysis.py", "figures.py"))
    return files + ["configs", "scripts/run_experiment.py"]


def _same_record(a: dict, b: dict) -> bool:
    if a.keys() != b.keys():
        return False
    for k in a:
        x, y = a[k], b[k]
        if isinstance(x, float) and isinstance(y, float) and x != x and y != y:
            continue
        if x != y:
            return False
    return True


def golden_unchanged(ref: dict, new: dict) -> bool:
    """Every golden case recorded at the reference commit is present and identical."""
    return all(name in new and _same_record(new[name], record) for name, record in ref.items())


def _golden_at(commit: str, root: Path) -> dict:
    text = subprocess.run(["git", "show", f"{commit}:tests/data/golden.json"], cwd=root,
                          capture_output=True, text=True, check=True).stdout
    return json.loads(text)


def provenance_problems(frames: dict[str, pd.DataFrame], root: Path) -> list[str]:
    """Every experiment must come from simulator code identical to the one used for E1."""
    problems: list[str] = []
    commits = {n: sorted(set(df["git_commit"].astype(str))) for n, df in frames.items()}
    for name, cs in commits.items():
        if len(cs) != 1:
            problems.append(f"{name}: {len(cs)} git_commit values {cs}")
        for c in cs:
            if c.endswith("-dirty") or c == "unknown":
                problems.append(f"{name}: git_commit {c!r} is not a clean commit")
    ref_list = commits.get("E1", [])
    if len(ref_list) != 1 or ref_list[0].endswith("-dirty") or ref_list[0] == "unknown":
        return problems
    ref = ref_list[0]
    paths = _simulator_paths(root)
    for name, cs in commits.items():
        if name == "E1" or len(cs) != 1 or cs[0].endswith("-dirty") or cs[0] == "unknown":
            continue
        c = cs[0]
        if c == ref:
            print(f"{name}: code {c} (same commit as E1)")
            continue
        r = subprocess.run(["git", "diff", "--quiet", ref, c, "--", *paths], cwd=root)
        if r.returncode == 0:
            print(f"{name}: code {c} (simulator identical to {ref})")
        else:
            try:
                same = golden_unchanged(_golden_at(ref, root), _golden_at(c, root))
            except subprocess.CalledProcessError:
                same = False
            if same:
                print(f"{name}: code {c} (simulator changed; every golden case from {ref} "
                      f"reproduced bit-identically)")
            else:
                problems.append(f"{name}: simulator code at {c} differs from E1's {ref} "
                                f"and the golden cases do not match")
    return problems


def main() -> int:
    missing = [n for n in MAIN if not (RESULTS / f"{n}.csv").exists()]
    if missing:
        print("missing: " + ", ".join(missing), file=sys.stderr)
        return 1
    frames = {n: pd.read_csv(RESULTS / f"{n}.csv") for n in MAIN}
    problems = provenance_problems(frames, ROOT)
    if problems:
        print("Provenance check failed, no tables written:", file=sys.stderr)
        for p in problems:
            print("  " + p, file=sys.stderr)
        return 1
    problems = [p for name, df in frames.items() for p in completeness_problems(name, df)]
    if problems:
        print("Incomplete results, no tables written:", file=sys.stderr)
        for p in problems:
            print("  " + p, file=sys.stderr)
        return 1
    OUT.mkdir(parents=True, exist_ok=True)

    conf = confirmatory(frames["E1"], frames["E2"], np.random.default_rng(BOOT_SEED))
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
