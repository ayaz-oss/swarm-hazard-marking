"""Tests for week-7 components:
- tune_c2f/tune_c3f configs and select_params.py fidelity extension
- E1F-E8F experiment files (levels, controllers, seeds, overrides_file, paired_cells)
- repellent_in_hazard metric
- week7_descriptive and week7_e2e5_tests analysis functions
- week-7 figure smoke test (via LEVELS and make_all)
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import analyse_week7  # noqa: E402

from swarmhazard.analysis import (  # noqa: E402
    BOOT_SEED,
    holm,
    identity_checks,
    week5_tests,
    week7_descriptive,
    week7_e2e5_tests,
)
from swarmhazard.config import Config, load_config  # noqa: E402
from swarmhazard.experiment import build_cells, build_jobs, load_experiment  # noqa: E402
from swarmhazard.figures import LEVELS, make_all  # noqa: E402
from swarmhazard.metrics import repellent_in_hazard_share  # noqa: E402
from swarmhazard.seeding import make_rng  # noqa: E402
from swarmhazard.sim import Simulation  # noqa: E402

FIDELITY_OVERRIDES = ROOT / "configs" / "tuned_params_fidelity.yaml"
FIDELITY_EXPS = ["E1F", "E2F", "E3F", "E4F", "E5F", "E6bF", "E7bF", "E8F"]


# ---------------------------------------------------------------------------
# Tuning config tests
# ---------------------------------------------------------------------------

def test_tune_c2f_structure():
    spec = load_experiment(ROOT / "configs" / "experiments" / "tune_c2f.yaml", ROOT)
    assert spec["name"] == "tune_c2f"
    assert spec["controllers"] == ["C2"]
    assert spec["seeds"] == 20
    assert spec["overrides"].get("search_start") == "last_pickup"
    assert "repel_weight" in spec.get("grid", {})
    assert "deposit_sigma" in spec.get("grid", {})
    assert "decay" in spec.get("grid", {})
    # Same grid as tune_c2
    c2 = load_experiment(ROOT / "configs" / "experiments" / "tune_c2.yaml", ROOT)
    raw = yaml.safe_load((ROOT / "configs" / "experiments" / "tune_c2f.yaml").read_text())
    assert raw["grid"] == yaml.safe_load(
        (ROOT / "configs" / "experiments" / "tune_c2.yaml").read_text()
    )["grid"]


def test_tune_c3f_structure():
    raw = yaml.safe_load((ROOT / "configs" / "experiments" / "tune_c3f.yaml").read_text())
    assert raw["name"] == "tune_c3f"
    assert raw["controllers"] == ["C3"]
    assert raw["seeds"] == 20
    # Must load fidelity overrides (to pick up C2 values from tune_c2f output)
    assert raw.get("overrides_file") == "configs/tuned_params_fidelity.yaml"
    # Same grid as tune_c3
    assert raw["grid"] == yaml.safe_load(
        (ROOT / "configs" / "experiments" / "tune_c3.yaml").read_text()
    )["grid"]


# ---------------------------------------------------------------------------
# select_params.py fidelity extension
# ---------------------------------------------------------------------------

def test_select_params_writes_fidelity_file(tmp_path, monkeypatch):
    import select_params as sp
    monkeypatch.setattr(sp, "ROOT", ROOT)
    fidelity_out = tmp_path / "tuned_params_fidelity.yaml"
    monkeypatch.setattr(sp, "OUT_FIDELITY", fidelity_out)
    monkeypatch.setattr(sp, "OUT_NEST", tmp_path / "tuned_params.yaml")

    # Build a minimal tune_c2f CSV
    rows = []
    for rw in [0.5, 1.0]:
        for ds in [0.2, 0.3]:
            for dc in [0.0002]:
                for seed in range(2):
                    rows.append({"experiment": "tune_c2f", "controller": "C2", "seed": seed,
                                 "p_repel_weight": rw, "p_deposit_sigma": ds, "p_decay": dc,
                                 "delivered": 10 + rw, "robots_lost": 1.0,
                                 "git_commit": "abc1234"})
    csv_path = tmp_path / "tune_c2f.csv"
    pd.DataFrame(rows).to_csv(csv_path, index=False)
    sp.main(str(csv_path), "C2", "repel_weight", "deposit_sigma", "decay")
    assert fidelity_out.exists()
    result = yaml.safe_load(fidelity_out.read_text())
    assert result["search_start"] == "last_pickup"
    assert "repel_weight" in result
    assert "deposit_sigma" in result
    assert "decay" in result
    # Nest params file must NOT be written
    assert not (tmp_path / "tuned_params.yaml").exists()


def test_select_params_rejects_mixed_experiments(tmp_path, monkeypatch):
    import select_params as sp
    monkeypatch.setattr(sp, "ROOT", ROOT)
    rows = [{"experiment": "tune_c2f", "controller": "C2", "seed": 0,
             "p_repel_weight": 0.5, "p_deposit_sigma": 0.3, "p_decay": 0.0002,
             "delivered": 10, "robots_lost": 1.0, "git_commit": "abc"},
            {"experiment": "tune_c2", "controller": "C2", "seed": 0,
             "p_repel_weight": 0.5, "p_deposit_sigma": 0.3, "p_decay": 0.0002,
             "delivered": 10, "robots_lost": 1.0, "git_commit": "abc"}]
    csv_path = tmp_path / "mixed.csv"
    pd.DataFrame(rows).to_csv(csv_path, index=False)
    with pytest.raises(SystemExit):
        sp.main(str(csv_path), "C2", "repel_weight", "deposit_sigma", "decay")


def test_select_params_c3f_preserves_c2f_values(tmp_path, monkeypatch):
    """Running select_params for C3 (tune_c3f) must preserve existing fidelity params."""
    import select_params as sp
    monkeypatch.setattr(sp, "ROOT", ROOT)
    fidelity_out = tmp_path / "tuned_params_fidelity.yaml"
    monkeypatch.setattr(sp, "OUT_FIDELITY", fidelity_out)
    # Pre-populate with C2 values
    fidelity_out.write_text("decay: 0.0002\ndeposit_sigma: 0.3\nrepel_weight: 0.5\n"
                            "search_start: last_pickup\n")
    # tune_c3f CSV
    rows = [{"experiment": "tune_c3f", "controller": "C3", "seed": s,
             "p_risk_k": k, "delivered": 10 + k, "robots_lost": 1.0, "git_commit": "abc"}
            for k in [0.5, 1.0, 2.0] for s in range(2)]
    csv_path = tmp_path / "tune_c3f.csv"
    pd.DataFrame(rows).to_csv(csv_path, index=False)
    sp.main(str(csv_path), "C3", "risk_k")
    result = yaml.safe_load(fidelity_out.read_text())
    assert result["search_start"] == "last_pickup"
    assert result["repel_weight"] == 0.5
    assert result["decay"] == 0.0002
    assert "risk_k" in result


# ---------------------------------------------------------------------------
# Fidelity overrides file (placeholder)
# ---------------------------------------------------------------------------

def test_fidelity_params_file_exists_and_has_search_start():
    assert FIDELITY_OVERRIDES.exists()
    data = yaml.safe_load(FIDELITY_OVERRIDES.read_text())
    assert data.get("search_start") == "last_pickup"
    # Must have the same core tuning keys as tuned_params.yaml
    tuned = yaml.safe_load((ROOT / "configs" / "tuned_params.yaml").read_text())
    for key in tuned:
        assert key in data, f"fidelity params missing key: {key}"


# ---------------------------------------------------------------------------
# F experiment files
# ---------------------------------------------------------------------------

def _load(name: str):
    return load_experiment(ROOT / "configs" / "experiments" / f"{name}.yaml", ROOT)


def test_all_f_experiments_point_at_fidelity_overrides():
    for name in FIDELITY_EXPS:
        raw = yaml.safe_load((ROOT / "configs" / "experiments" / f"{name}.yaml").read_text())
        assert raw.get("overrides_file") == "configs/tuned_params_fidelity.yaml", \
            f"{name} must use configs/tuned_params_fidelity.yaml"


def test_f_experiments_have_correct_seeds():
    for name in FIDELITY_EXPS:
        spec = _load(name)
        assert spec["seeds"] == 100, f"{name}: expected 100 seeds"


def test_f_experiment_controllers_match_counterparts():
    pairs = [("E1F", "E1"), ("E2F", "E2"), ("E3F", "E3"), ("E4F", "E4"),
             ("E5F", "E5"), ("E6bF", "E6b"), ("E7bF", "E7b"), ("E8F", "E8")]
    for fname, cname in pairs:
        f = _load(fname)
        c = _load(cname)
        assert f["controllers"] == c["controllers"], \
            f"{fname} controllers {f['controllers']} != {cname} {c['controllers']}"


def test_f_experiment_cells_match_counterparts():
    pairs = [("E1F", "E1"), ("E2F", "E2"), ("E3F", "E3"), ("E4F", "E4"),
             ("E5F", "E5"), ("E6bF", "E6b"), ("E7bF", "E7b"), ("E8F", "E8")]
    for fname, cname in pairs:
        f = build_cells(_load(fname))
        c = build_cells(_load(cname))
        assert len(f) == len(c), f"{fname} has {len(f)} cells, {cname} has {len(c)}"


def test_multi_cell_f_experiments_have_paired_cells():
    """Every multi-cell F experiment must have paired_cells=True (week-7 spec section 3)."""
    single_cell = {"E1F"}  # only E1F has a single cell (baseline)
    for name in FIDELITY_EXPS:
        spec = _load(name)
        if name not in single_cell:
            assert spec.get("paired_cells") is True, \
                f"{name} should have paired_cells: true"


def test_f_experiment_loads_search_start():
    """Every F experiment must ultimately carry search_start=last_pickup in its overrides."""
    for name in FIDELITY_EXPS:
        spec = _load(name)
        assert spec["overrides"].get("search_start") == "last_pickup", \
            f"{name}: overrides.search_start must be 'last_pickup'"


def test_e8f_has_hazard_move_step():
    spec = _load("E8F")
    assert spec["overrides"].get("hazard_move_step") == 5000


def test_e2f_cell3_is_random_failure_control():
    cells = build_cells(_load("E2F"))
    assert cells[3]["hazards"] == []
    assert cells[3]["random_fail_rate"] > 0


def test_f_configs_are_loadable():
    """Every job from every F experiment must produce a valid Config."""
    for name in FIDELITY_EXPS:
        spec = _load(name)
        for job in build_jobs(spec, seeds=1):
            load_config(ROOT / job["base"], **job["overrides"], controller=job["controller"])


# ---------------------------------------------------------------------------
# repellent_in_hazard metric
# ---------------------------------------------------------------------------

def test_repellent_in_hazard_share_nan_for_non_marking():
    grid = np.ones((10, 10))
    mask = np.zeros((10, 10), dtype=bool)
    mask[:3, :3] = True
    assert np.isnan(repellent_in_hazard_share(grid, mask, is_marking=False))


def test_repellent_in_hazard_share_nan_for_empty_field():
    grid = np.zeros((10, 10))
    mask = np.ones((10, 10), dtype=bool)
    assert np.isnan(repellent_in_hazard_share(grid, mask, is_marking=True))


def test_repellent_in_hazard_share_fraction():
    grid = np.zeros((10, 10))
    grid[:3, :3] = 1.0  # 9 cells in hazard, 0 outside
    mask = np.zeros((10, 10), dtype=bool)
    mask[:3, :3] = True
    val = repellent_in_hazard_share(grid, mask, is_marking=True)
    assert val == pytest.approx(1.0)
    # Now put half outside
    grid[5, 5] = 9.0  # equal mass outside
    val = repellent_in_hazard_share(grid, mask, is_marking=True)
    assert val == pytest.approx(0.5)


def test_repellent_in_hazard_in_sim_result_nan_for_c0():
    cfg = Config(controller="C0", n_steps=200, lethality=0.2)
    rng = make_rng("test_w7_c0", 0, 0)
    sim = Simulation(cfg, rng)
    for _ in range(cfg.n_steps):
        sim.step()
    result = sim.result()
    assert "repellent_in_hazard" in result
    assert np.isnan(result["repellent_in_hazard"])


def test_repellent_in_hazard_in_sim_result_float_for_c2():
    cfg = Config(controller="C2", n_steps=500, lethality=0.5)
    rng = make_rng("test_w7_c2", 0, 0)
    sim = Simulation(cfg, rng)
    for _ in range(cfg.n_steps):
        sim.step()
    result = sim.result()
    assert "repellent_in_hazard" in result
    # May be NaN (no marks) or a float in [0,1]
    val = result["repellent_in_hazard"]
    assert np.isnan(val) or (0.0 <= val <= 1.0)


def test_repellent_in_hazard_does_not_change_golden():
    """The new metric must not affect existing golden values (just adds a new key)."""
    from make_golden import GOLDEN_CASES, golden_record
    import json
    GOLDEN = json.loads((ROOT / "tests" / "data" / "golden.json").read_text())
    # Pick a fast case
    cfg = Config(**GOLDEN_CASES["C2"])
    result = golden_record(cfg, make_rng("golden", 0, 0))
    expected = GOLDEN["C2"]
    diffs = {k: (result[k], v) for k, v in expected.items()
             if not (isinstance(result[k], float) and isinstance(v, float) and
                     np.isnan(result[k]) and np.isnan(v)) and result[k] != v}
    assert not diffs, f"golden changed: {diffs}"


# ---------------------------------------------------------------------------
# week7 analysis functions
# ---------------------------------------------------------------------------

COLS = ("delivered", "robots_lost")


def fake_df(controllers, n_cells, seeds=51, with_e8_cols=False, with_fidelity_cols=False):
    rng = np.random.default_rng(42)
    rows = []
    for cell in range(n_cells):
        for c in controllers:
            for s in range(seeds):
                row = {
                    "cell": cell, "controller": c, "seed": s,
                    "delivered": int(rng.integers(10, 50)),
                    "robots_lost": int(rng.integers(0, 10)),
                    "first_loss_step": 100 + s,
                    "picked_up": 60, "items_lost": 2, "carrying": 1, "steps": 10000,
                    "auc_final": 0.65 if c in ("C2", "C3") else float("nan"),
                    "auc_series": "0.5000;0.6500" if c in ("C2", "C3") else "",
                    "false_sightings": 0,
                    "repellent_in_hazard": 0.7 if c in ("C2", "C3", "C5", "C6") else float("nan"),
                    "trip_steps_mean": float(rng.uniform(50, 200)),
                    "search_steps_mean": float(rng.uniform(100, 400)),
                    "nest_steps": int(rng.integers(1000, 5000)),
                    "hazard_area": 3.14,
                }
                if with_e8_cols:
                    row.update({"delivered_pre": int(rng.integers(5, 30)),
                                "lost_pre": int(rng.integers(0, 5)),
                                "delivered_post": int(rng.integers(5, 25)),
                                "lost_post": int(rng.integers(0, 4)),
                                "auc_pre": 0.6, "auc_old_final": 0.55,
                                "first_loss_post_step": -1})
                rows.append(row)
    return pd.DataFrame(rows).sample(frac=1, random_state=7)


def test_week7_descriptive_has_repellent_in_hazard():
    df = fake_df(["C0", "C2"], 1)
    out = week7_descriptive(df, np.random.default_rng(0), n_boot=100)
    assert "repellent_in_hazard_median" in out.columns
    # C0: all NaN, so n=0
    c0 = out[out.controller == "C0"]
    assert int(c0["repellent_in_hazard_n"].iloc[0]) == 0
    # C2: non-NaN
    c2 = out[out.controller == "C2"]
    assert int(c2["repellent_in_hazard_n"].iloc[0]) == 51


def test_week7_descriptive_has_auc_marked():
    df = fake_df(["C2"], 1)
    out = week7_descriptive(df, np.random.default_rng(0), n_boot=100)
    assert "auc_final_marked_median" in out.columns
    assert "auc_final_marked_n" in out.columns
    # All C2 runs have auc_series with 0.6500 != 0.5 → all 51 are marked
    assert int(out["auc_final_marked_n"].iloc[0]) == 51


def test_week7_descriptive_auc_marked_count_zero_when_no_marks():
    df = fake_df(["C0"], 1)
    out = week7_descriptive(df, np.random.default_rng(0), n_boot=100)
    if "auc_final_marked_n" in out.columns:
        assert int(out["auc_final_marked_n"].iloc[0]) == 0


@pytest.mark.parametrize("name,n_cells,n_ctrl", [
    ("E2F", 4, 5),
    ("E3F", 5, 5),
    ("E4F", 4, 5),
    ("E5F", 3, 5),
])
def test_week7_e2e5_tests_family_and_holm(name, n_cells, n_ctrl):
    """Tests are all within-cell Wilcoxon vs C2 + cross-cell C2 tests; one Holm pass."""
    controllers = ["C0", "C1", "C2", "C3", "C4"][:n_ctrl]
    df = fake_df(controllers, n_cells)
    out = week7_e2e5_tests(name, df, np.random.default_rng(0), n_boot=100)
    assert len(out) > 0
    # Holm must equal holm(p)
    assert np.allclose(out["p_holm"], holm(out["p"].to_numpy()), equal_nan=True)
    # Must have both vs_C2 and cross_cell kinds
    assert "vs_C2" in set(out["kind"])
    assert "cross_cell" in set(out["kind"])
    # cross_cell tests: C2 vs cell 0 for each non-zero cell, 2 metrics each
    n_cross = (n_cells - 1) * 2
    assert (out["kind"] == "cross_cell").sum() == n_cross


def test_week7_e2f_e5f_within_cell_family_size():
    """E2F should have (n_ctrl-1)*n_cells within-cell tests + (n_cells-1)*2 cross-cell tests."""
    df = fake_df(["C0", "C1", "C2", "C3", "C4"], 4)
    out = week7_e2e5_tests("E2F", df, np.random.default_rng(0), n_boot=100)
    n_within = 4 * 4   # 4 controllers vs C2 * 2 metrics * 4 cells - wait: exploratory gives
    # (n_ctrl-1)*n_cells*n_metrics = 4*4*2? No: exploratory iterates cells, then controllers != C2
    # For E2F: 5 controllers, 4 cells, 2 metrics → 4*4*2 = 32 within-cell + 3*2 = 6 cross-cell = 38
    n_cross = 3 * 2
    n_within = 4 * 4 * 2  # 4 cells, 4 comparators, 2 metrics
    assert len(out) == n_within + n_cross


@pytest.mark.parametrize("name,controllers,n_cells,size", [
    ("E6bF", ["C2", "C5", "C6"], 5, 30),
    ("E7bF", ["C0", "C1", "C2", "C3"], 6, 66),
    ("E8F", ["C0", "C1", "C2", "C4"], 3, 24),
])
def test_week5_tests_work_for_f_experiments(name, controllers, n_cells, size):
    df = fake_df(controllers, n_cells, with_e8_cols=(name == "E8F"))
    out = week5_tests(name, df, np.random.default_rng(0), n_boot=100)
    assert len(out) == size
    assert np.allclose(out["p_holm"], holm(out["p"].to_numpy()), equal_nan=True)


# ---------------------------------------------------------------------------
# analyse_week7 script tests
# ---------------------------------------------------------------------------

def _patch_git(monkeypatch):
    monkeypatch.setattr(analyse_week7, "_golden_at", lambda c, root: {})
    monkeypatch.setattr(analyse_week7, "golden_unchanged", lambda a, b: True)
    monkeypatch.setattr(analyse_week7, "_golden_branch_problems", lambda *a: [])
    monkeypatch.setattr(analyse_week7, "completeness_problems", lambda name, df: [])


def test_analyse_week7_missing_csvs(tmp_path, monkeypatch):
    monkeypatch.setattr(analyse_week7, "RESULTS", tmp_path)
    monkeypatch.setattr(analyse_week7, "OUT", tmp_path / "out")
    assert analyse_week7.main() == 1


def test_analyse_week7_writes_confirmatory_and_exploratory(tmp_path, monkeypatch):
    _patch_git(monkeypatch)
    monkeypatch.setattr(analyse_week7, "RESULTS", tmp_path)
    monkeypatch.setattr(analyse_week7, "OUT", tmp_path / "week7")
    rng = np.random.default_rng(0)

    def make_csv(name, controllers, n_cells, seeds=51, e8=False):
        df = fake_df(controllers, n_cells, seeds=seeds, with_e8_cols=e8)
        df["git_commit"] = "abc1234"
        df["package_root"] = f"/x/.batch/abc1234/src"
        df["experiment"] = name
        df.to_csv(tmp_path / f"{name}.csv", index=False)

    make_csv("E1F", ["C0", "C1", "C2", "C3", "C4"], 1)
    make_csv("E2F", ["C0", "C1", "C2", "C3", "C4"], 4)
    make_csv("E3F", ["C0", "C1", "C2", "C3", "C4"], 5)
    make_csv("E4F", ["C0", "C1", "C2", "C3", "C4"], 4)
    make_csv("E5F", ["C0", "C1", "C2", "C3", "C4"], 3)
    make_csv("E6bF", ["C2", "C5", "C6"], 5)
    make_csv("E7bF", ["C0", "C1", "C2", "C3"], 6)
    make_csv("E8F", ["C0", "C1", "C2", "C4"], 3, e8=True)

    rc = analyse_week7.main()
    assert rc == 0
    out = tmp_path / "week7"
    assert (out / "confirmatory_F.csv").exists()
    conf = pd.read_csv(out / "confirmatory_F.csv")
    assert set(conf["hypothesis"]) == {"H1F", "H2F", "H3F", "H4F"}
    # Exploratory/tests files exist
    for name in ("E2F", "E3F", "E4F", "E5F"):
        assert (out / f"{name}_exploratory.csv").exists()
    for name in ("E6bF", "E7bF", "E8F"):
        assert (out / f"{name}_tests.csv").exists()
    for name in analyse_week7.F_NAMES:
        assert (out / f"{name}_descriptive.csv").exists()
    assert (out / "model_comparison.csv").exists()


# ---------------------------------------------------------------------------
# Figure smoke test
# ---------------------------------------------------------------------------

def test_levels_include_f_experiments():
    for name in ["E2F", "E3F", "E4F", "E5F", "E6bF", "E7bF", "E8F"]:
        assert name in LEVELS, f"{name} not in figures.LEVELS"
        # Check cell count matches experiment
        spec = _load(name)
        cells = build_cells(spec)
        assert len(cells) == len(LEVELS[name]), \
            f"{name}: LEVELS has {len(LEVELS[name])} entries but spec has {len(cells)} cells"


def test_make_all_writes_f_figures(tmp_path):
    def fake_csv(name, n_cells, seeds=5, e8=False):
        df = fake_df(["C0", "C1", "C2", "C3", "C4", "C5", "C6"], n_cells, seeds=seeds,
                     with_e8_cols=e8)
        df.to_csv(tmp_path / f"{name}.csv", index=False)

    fake_csv("E1F", 1)
    fake_csv("E2F", 4)
    fake_csv("E3F", 5)
    fake_csv("E4F", 4)
    fake_csv("E5F", 3)
    fake_csv("E6bF", 5)
    fake_csv("E7bF", 6)
    fake_csv("E8F", 3, e8=True)

    written = make_all(tmp_path, tmp_path / "figures")
    names = {p.name for p in written}
    for stem in ("e1F_baseline", "e2F_placement", "e3f_sweep", "e4f_sweep", "e5f_sweep",
                 "e6bf_sweep", "e7bF_noise", "e8F_move"):
        assert f"{stem}.png" in names, f"missing figure: {stem}.png (got {sorted(names)})"
    assert all(p.exists() and p.stat().st_size > 0 for p in written if "F" in p.name or "f" in p.name)
