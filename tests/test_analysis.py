import numpy as np
import pandas as pd

from swarmhazard.analysis import (E2_NONE_CELL, compare, confirmatory, descriptive, exploratory,
                                  holm, paired, wilcoxon_p)


def frame(rows):
    return pd.DataFrame(rows, columns=["experiment", "cell", "controller", "seed", "delivered", "robots_lost"])


def test_holm_values():
    assert np.allclose(holm([0.01, 0.04, 0.03]), [0.03, 0.06, 0.06])


def test_holm_propagates_nan():
    out = holm([0.01, float("nan"), 0.02])
    assert np.isnan(out[1])
    assert np.allclose(out[[0, 2]], [0.02, 0.02])


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

def test_descriptive_and_exploratory_on_synthetic_data():
    rng = np.random.default_rng(5)
    rows = []
    for s in range(30):
        base = rng.normal(40, 5)
        rows += [("E", 0, "C0", s, base, 3), ("E", 0, "C2", s, base + 2, 1), ("E", 0, "C4", s, base + 4, 0)]
    df = frame(rows)
    df["auc_final"] = np.nan
    df["hazard_area"] = 3.18
    d = descriptive(df, np.random.default_rng(1), n_boot=500).set_index("controller")
    assert np.isnan(d.loc["C4", "items_per_robot_lost"])
    assert d.loc["C0", "items_per_robot_lost"] > 0
    e = exploratory(df, np.random.default_rng(1), n_boot=500)
    assert set(e["x"]) == {"C0", "C4"} and set(e["metric"]) == {"delivered", "robots_lost"}
    assert e["p_holm"].between(0, 1).all()
