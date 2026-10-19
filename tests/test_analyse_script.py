import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from analyse import (completeness_problems, golden_unchanged, package_root_ok,  # noqa: E402
                     provenance_problems)

from swarmhazard.experiment import load_experiment  # noqa: E402


def complete_e1_frame():
    spec = load_experiment(ROOT / "configs" / "experiments" / "E1.yaml", ROOT)
    return pd.DataFrame([{"cell": 0, "controller": c, "seed": s}
                         for c in spec["controllers"] for s in range(spec["seeds"])])


def test_completeness_problems_detects_missing_rows():
    df = complete_e1_frame()
    assert completeness_problems("E1", df) == []
    assert completeness_problems("E1", df.iloc[1:]) != []


def test_provenance_problems():
    head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True,
                          text=True, check=True).stdout.strip()
    ok = {"E1": pd.DataFrame({"git_commit": [head] * 2}), "E2": pd.DataFrame({"git_commit": [head] * 2})}
    assert provenance_problems(ok, ROOT) == []
    bad = {"E1": ok["E1"], "E2": pd.DataFrame({"git_commit": ["abc-dirty"] * 2})}
    assert provenance_problems(bad, ROOT) != []


def test_completeness_requires_the_exact_seed_set():
    df = complete_e1_frame()
    df.loc[df.index[0], "seed"] = 100   # right count, wrong identity
    assert completeness_problems("E1", df)


def test_golden_unchanged_allows_added_cases_only():
    ref = {"C0": {"delivered": 13, "state_digest": "a"}}
    assert golden_unchanged(ref, {"C0": {"delivered": 13, "state_digest": "a"}, "C5": {"delivered": 9}})
    assert not golden_unchanged(ref, {"C0": {"delivered": 14, "state_digest": "a"}})
    assert not golden_unchanged(ref, {"C5": {"delivered": 9}})


def test_package_root_ok():
    assert package_root_ok("C:/x/Research Project/.batch/5d8ca9e/src", "5d8ca9e")
    assert package_root_ok(r"C:\x\Research Project\.batch\5d8ca9e\src", "5d8ca9e")
    assert not package_root_ok("C:/x/Research Project/src", "5d8ca9e")
    assert not package_root_ok(".batch/abcdef1/src", "5d8ca9e")
