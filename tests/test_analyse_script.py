import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from analyse import completeness_problems, provenance_problems  # noqa: E402

from swarmhazard.experiment import load_experiment  # noqa: E402


def test_completeness_problems_detects_missing_rows():
    spec = load_experiment(ROOT / "configs" / "experiments" / "E1.yaml", ROOT)
    df = pd.DataFrame([{"cell": 0, "controller": c, "seed": s}
                       for c in spec["controllers"] for s in range(spec["seeds"])])
    assert completeness_problems("E1", df) == []
    assert completeness_problems("E1", df.iloc[1:]) != []


def test_provenance_problems():
    head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True,
                          text=True, check=True).stdout.strip()
    ok = {"E1": pd.DataFrame({"git_commit": [head] * 2}), "E2": pd.DataFrame({"git_commit": [head] * 2})}
    assert provenance_problems(ok, ROOT) == []
    bad = {"E1": ok["E1"], "E2": pd.DataFrame({"git_commit": ["abc-dirty"] * 2})}
    assert provenance_problems(bad, ROOT) != []
