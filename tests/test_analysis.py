import numpy as np
import pandas as pd
import pytest

from swarmhazard.analysis import E2_NONE_CELL, compare, confirmatory, holm, paired, wilcoxon_p


def frame(rows):
    return pd.DataFrame(rows, columns=["experiment", "cell", "controller", "seed", "delivered", "robots_lost"])


def test_holm_values():
    assert np.allclose(holm([0.01, 0.04, 0.03]), [0.03, 0.06, 0.06])


def test_paired_aligns_by_seed():
    df = frame([("E1", 0, "C2", 1, 10, 0), ("E1", 0, "C0", 0, 5, 0),
                ("E1", 0, "C2", 0, 7, 0), ("E1", 0, "C0", 1, 3, 0)])
    x, y = paired(df, "delivered", "C2", "C0")
    assert x.tolist() == [7, 10] and y.tolist() == [5, 3]


def test_wilcoxon_detects_a_clear_shift_and_ignores_none():
    rng = np.random.default_rng(1)
    y = rng.normal(40, 5, 30)
    assert wilcoxon_p(y + 1.0, y, "greater") < 0.001
    assert wilcoxon_p(y, y, "greater") == 1.0


def test_compare_is_deterministic_and_brackets_the_estimate():
    rng = np.random.default_rng(2)
    x, y = rng.normal(45, 5, 40), rng.normal(42, 5, 40)
    a = compare(x, y, np.random.default_rng(20261016), n_boot=2000)
    b = compare(x, y, np.random.default_rng(20261016), n_boot=2000)
    assert a == b
    assert a["a12_lo"] <= a["a12"] <= a["a12_hi"]
    assert a["median_diff_lo"] <= a["median_diff"] <= a["median_diff_hi"]


def test_confirmatory_on_synthetic_data():
    rng = np.random.default_rng(3)
    rows = []
    for s in range(40):
        base = rng.normal(40, 5)
        rows += [("E1", 0, "C0", s, base, 5), ("E1", 0, "C1", s, base + 1, 4),
                 ("E1", 0, "C2", s, base + 3, 2), ("E1", 0, "C3", s, base + 3, 2),
                 ("E1", 0, "C4", s, base + 5, 0)]
    e1 = frame(rows)
    e2 = frame([("E2", E2_NONE_CELL, c, s, d, 0) for (_, _, c, s, d, _) in rows if c in ("C0", "C2")])
    out = confirmatory(e1, e2, np.random.default_rng(20261016), n_boot=2000).set_index("hypothesis")
    assert out.loc["H1", "supported"] and out.loc["H2", "supported"]
    assert not out.loc["H4", "supported"]
    assert out.loc["H3", "supported"]
