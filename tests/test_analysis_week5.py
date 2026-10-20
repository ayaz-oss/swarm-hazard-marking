import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import analyse_week5  # noqa: E402

from swarmhazard.analysis import cross_cell, identity_checks, week5_descriptive, week5_tests  # noqa: E402

COLS = ("delivered", "robots_lost", "delivered_pre", "lost_pre", "delivered_post", "lost_post")


def fake(controllers, n_cells, seeds=12, same=()):
    rng = np.random.default_rng(0)
    rows = []
    for cell in range(n_cells):
        for c in controllers:
            for s in range(seeds):
                base = {k: int(rng.integers(0, 50)) for k in COLS}
                rows.append({"cell": cell, "controller": c, "seed": s, **base,
                             "first_loss_step": 100 + s, "picked_up": 60,
                             "auc_final": 0.5 if s == 0 else 0.7, "auc_series": "0.5000;0.7000",
                             "auc_pre": 0.6, "auc_old_final": 0.55, "known_frac": 0.9,
                             "false_sightings": 0})
    df = pd.DataFrame(rows)
    for c, cells in same:  # make controller c identical across these cells
        ref = df[(df.controller == c) & (df.cell == cells[0])].set_index("seed")
        for k in cells[1:]:
            mask = (df.controller == c) & (df.cell == k)
            for col in COLS + ("first_loss_step", "auc_final"):
                df.loc[mask, col] = ref.loc[df.loc[mask, "seed"], col].to_numpy()
    return df.sample(frac=1, random_state=1)  # row order must not matter


@pytest.mark.parametrize("name, controllers, n_cells, size", [
    ("E6b", ["C2", "C5", "C6"], 5, 30),
    ("E7b", ["C0", "C1", "C2", "C3"], 6, 66),
    ("E8", ["C0", "C1", "C2", "C4"], 3, 24),
])
def test_family_sizes_and_holm(name, controllers, n_cells, size):
    out = week5_tests(name, fake(controllers, n_cells), np.random.default_rng(0), n_boot=200)
    assert len(out) == size
    assert (out["p_holm"] >= out["p"] - 1e-12).all()
    assert set(out["kind"]) <= {"vs_C2", "pair", "cross_cell"}


def test_cross_cell_aligns_by_seed():
    df = fake(["C2"], 2)
    out = cross_cell(df, "C2", 1, 0, ("delivered",), np.random.default_rng(0), n_boot=100)
    a = df[(df.cell == 1)].sort_values("seed")["delivered"].to_numpy(float)
    b = df[(df.cell == 0)].sort_values("seed")["delivered"].to_numpy(float)
    assert out["median_diff"].iloc[0] == pytest.approx(np.median(a - b))
    assert out["x"].iloc[0] == "C2@1" and out["y"].iloc[0] == "C2@0"


def test_identity_checks():
    df = fake(["C0", "C1", "C2", "C3"], 6, same=[("C0", (0, 1, 2, 3, 4, 5))])
    out = identity_checks("E7b", df).set_index("controller")
    assert bool(out.loc["C0", "identical"]) and not bool(out.loc["C1", "identical"])


def test_week5_descriptive_counts_marked_runs():
    df = fake(["C2", "C6"], 1)
    df.loc[df.seed == 0, "auc_series"] = "0.5000;0.5000"
    out = week5_descriptive(df, np.random.default_rng(0), n_boot=100)
    assert (out["marked_runs"] == 11).all()
    assert "known_frac_median" in out and "delivered_post_median" in out


def test_analyse_week5_missing_csvs_writes_nothing(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(analyse_week5, "RESULTS", tmp_path)
    monkeypatch.setattr(analyse_week5, "OUT", tmp_path / "analysis" / "week5")
    assert analyse_week5.main() == 1
    assert "missing: E6b, E7b, E8" in capsys.readouterr().err
    assert list(tmp_path.iterdir()) == []
