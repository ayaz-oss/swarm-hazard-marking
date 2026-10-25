import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import analyse_webots as aw  # noqa: E402


def _fake(n=60, seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for s in range(n):
        base = rng.integers(100, 140)
        for c, dd, lost in (("C0", 0, 4), ("C1", 1, 3), ("C2", 3, 2), ("C4", 8, 0)):
            rows.append(dict(controller=c, seed=s, steps=10000, delivered=base + dd + rng.integers(0, 3),
                             robots_lost=max(0, lost + rng.integers(-1, 2)),
                             auc_final=0.7 if c == "C2" else np.nan))
    return pd.DataFrame(rows)


def test_confirmatory_has_two_holm_corrected_tests():
    out = aw.confirmatory_w(_fake(), np.random.default_rng(1), n_boot=200)
    assert list(out["hypothesis"]) == ["H1W", "H2W"]
    assert (out["p_holm"] >= out["p"]).all()
    assert out["supported"].all()


def test_completeness_flags_missing_and_duplicates():
    df = _fake(n=100)
    assert aw.completeness_problems(df) == []
    bad = pd.concat([df[df.seed != 5], df.iloc[[0]]])
    probs = aw.completeness_problems(bad)
    assert any("duplicate" in p for p in probs) and any("missing" in p for p in probs)
