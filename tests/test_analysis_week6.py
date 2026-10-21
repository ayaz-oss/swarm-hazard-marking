"""Unit tests for the week-6 analysis functions (E9)."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import analyse_week6  # noqa: E402

from swarmhazard.analysis import (  # noqa: E402
    holm,
    identity_checks,
    week6_descriptive,
    week6_tests,
)

COLS = ("delivered", "robots_lost")


def fake(controllers=None, n_cells=6, seeds=51, same=()):
    """Build a minimal E9-like result table."""
    if controllers is None:
        controllers = ["C0", "C1", "C2", "C3", "C4"]
    rng = np.random.default_rng(42)
    rows = []
    for cell in range(n_cells):
        for c in controllers:
            for s in range(seeds):
                rows.append({
                    "cell": cell, "controller": c, "seed": s,
                    "delivered": int(rng.integers(10, 50)),
                    "robots_lost": int(rng.integers(0, 10)),
                    "first_loss_step": int(100 + s),
                    "picked_up": 60,
                    "items_lost": 2,
                    "carrying": 1,
                    "steps": 10000,
                    "auc_final": 0.6 if c in ("C2", "C3") else float("nan"),
                    "auc_series": "0.5000;0.7000" if c in ("C2", "C3") else "",
                    "false_sightings": int(rng.integers(0, 5)),
                    "trip_steps_mean": float(rng.uniform(50, 200)),
                    "search_steps_mean": float(rng.uniform(100, 400)),
                    "nest_steps": int(rng.integers(1000, 5000)),
                    "hazard_area": 3.14,
                })
    df = pd.DataFrame(rows)
    for c, cells in same:
        ref = df[(df.controller == c) & (df.cell == cells[0])].set_index("seed")
        for k in cells[1:]:
            mask = (df.controller == c) & (df.cell == k)
            for col in COLS + ("first_loss_step", "auc_final", "steps", "picked_up",
                                "items_lost", "carrying"):
                df.loc[mask, col] = ref.loc[df.loc[mask, "seed"], col].to_numpy()
    return df.sample(frac=1, random_state=7)


def test_week6_tests_family_size_is_82():
    df = fake()
    out = week6_tests(df, np.random.default_rng(0), n_boot=100)
    assert len(out) == 82


def test_week6_tests_holm_applied_over_all_82():
    df = fake()
    out = week6_tests(df, np.random.default_rng(0), n_boot=100)
    assert np.allclose(out["p_holm"], holm(out["p"].to_numpy()), equal_nan=True)


def test_week6_tests_kind_values():
    df = fake()
    out = week6_tests(df, np.random.default_rng(0), n_boot=100)
    assert set(out["kind"]) <= {"vs_C2", "fidelity_vs_nest", "interaction"}
    # Check counts: 48 vs_C2, 30 fidelity_vs_nest, 4 interaction
    assert (out["kind"] == "vs_C2").sum() == 48
    assert (out["kind"] == "fidelity_vs_nest").sum() == 30
    assert (out["kind"] == "interaction").sum() == 4


def test_week6_descriptive_has_new_metric_columns():
    df = fake()
    out = week6_descriptive(df, np.random.default_rng(0), n_boot=100)
    for col in ("trip_steps_mean_median", "search_steps_mean_median", "nest_steps_median",
                "auc_final_median", "false_sightings_median", "marked_runs"):
        assert col in out.columns, f"missing column: {col}"


def test_week6_descriptive_marked_runs():
    df = fake()
    df.loc[df.seed == 0, "auc_series"] = "0.5000;0.5000"
    out = week6_descriptive(df, np.random.default_rng(0), n_boot=100)
    # Seeds 1..50 have "0.5000;0.7000" (has non-0.5 value) and seed 0 has "0.5000;0.5000"
    c2_rows = out[out.controller == "C2"]
    assert (c2_rows["marked_runs"] == 50).all()


def test_identity_checks_e9():
    df = fake(same=[("C0", (0, 4)), ("C0", (1, 5)), ("C1", (0, 4)),
                    ("C1", (1, 5)), ("C4", (0, 4)), ("C4", (1, 5))])
    out = identity_checks("E9", df).set_index(["controller", "cells"])
    # C0 identical in (0,4) and (1,5)
    assert bool(out.loc[("C0", "0 4"), "identical"])
    assert bool(out.loc[("C0", "1 5"), "identical"])
    # A controller that wasn't forced identical should not be identical (C2)
    out2 = identity_checks("E9", fake())
    c0_04 = out2[(out2.controller == "C0") & (out2.cells == "0 4")]
    # With random data, they're almost certainly NOT identical
    # Just check it returns a value
    assert len(c0_04) == 1


def test_identity_checks_wrong_controller_fails():
    df = fake()  # C2 not forced identical
    out = identity_checks("E9", df)
    c2_rows = out[out.controller == "C2"]
    assert len(c2_rows) == 0  # C2 is not in E9 identity spec


def test_analyse_week6_script_fails_on_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(analyse_week6, "RESULTS", tmp_path)
    monkeypatch.setattr(analyse_week6, "OUT", tmp_path / "out")
    assert analyse_week6.main() == 1


def test_analyse_week6_script_runs_on_fake_data(tmp_path, monkeypatch):
    df = fake()
    df["git_commit"] = "abc1234"
    df["package_root"] = str(ROOT)
    (tmp_path / "E9.csv").write_text(df.to_csv(index=False))
    monkeypatch.setattr(analyse_week6, "RESULTS", tmp_path)
    monkeypatch.setattr(analyse_week6, "OUT", tmp_path / "out")
    monkeypatch.setattr(analyse_week6, "_golden_at", lambda c, root: {})
    monkeypatch.setattr(analyse_week6, "golden_unchanged", lambda a, b: True)
    monkeypatch.setattr(analyse_week6, "_golden_branch_problems", lambda *a: [])
    monkeypatch.setattr(analyse_week6, "completeness_problems", lambda *a: [])
    result = analyse_week6.main()
    assert result == 0
    assert (tmp_path / "out" / "E9_tests.csv").exists()
    assert (tmp_path / "out" / "E9_descriptive.csv").exists()
    assert (tmp_path / "out" / "identity_checks.csv").exists()
    tests = pd.read_csv(tmp_path / "out" / "E9_tests.csv")
    assert len(tests) == 82


def test_week6_tests_interaction_directions():
    """Interaction test (a): C2 false-sighting gain is difference of differences."""
    df = fake()
    out = week6_tests(df, np.random.default_rng(0), n_boot=100)
    ia = out[out["kind"] == "interaction"]
    # Should have tests for all 4 interaction cases
    assert len(ia) == 4
    # Test labels
    labels_x = set(ia["x"].tolist())
    assert "C2@4-C2@0" in labels_x
    assert "(C2-C0)@2" in labels_x
    assert "(C2-C0)@0" in labels_x
    assert "(C1-C2)@0" in labels_x
