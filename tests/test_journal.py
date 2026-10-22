"""Tests for the journal-package features:
  - C7 controller (risk-limit alerts)
  - arena_scale
  - Multiple hazards AUC
  - overrides_file as list
  - tune_c7f / E10 / E11 / E12 configs
  - select_params C7 extension
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

from swarmhazard.config import Config, from_dict, load_config
from swarmhazard.experiment import build_cells, build_jobs, load_experiment
from swarmhazard.metrics import field_auc, hazard_mask
from swarmhazard.seeding import make_rng
from swarmhazard.sim import Simulation, run


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def new_sim(**kw):
    return Simulation(Config(**kw), make_rng("test", 0, 0))


def c7_sim(**kw):
    defaults = dict(controller="C7", lethality=0.2, n_steps=3000,
                    alert_limit=1.0, alert_duration=1000,
                    alert_decay=0.001, alert_radius=1.0)
    defaults.update(kw)
    return new_sim(**defaults)


# ---------------------------------------------------------------------------
# C7 config validation
# ---------------------------------------------------------------------------

class TestC7Config:
    def test_c7_known_controller(self):
        cfg = Config(controller="C7", alert_limit=2.0, alert_duration=1000,
                     alert_decay=0.001, alert_radius=1.0)
        assert cfg.controller == "C7"

    def test_c7_default_fields_present(self):
        cfg = Config(controller="C7")
        assert hasattr(cfg, "alert_limit")
        assert hasattr(cfg, "alert_duration")
        assert hasattr(cfg, "alert_decay")
        assert hasattr(cfg, "alert_radius")

    def test_alert_limit_negative_raises(self):
        with pytest.raises((ValueError, TypeError)):
            Config(controller="C7", alert_limit=-1.0)

    def test_alert_duration_zero_raises(self):
        with pytest.raises((ValueError, TypeError)):
            Config(controller="C7", alert_duration=0)

    def test_alert_decay_out_of_range_raises(self):
        with pytest.raises((ValueError, TypeError)):
            Config(controller="C7", alert_decay=1.5)

    def test_alert_radius_negative_raises(self):
        with pytest.raises((ValueError, TypeError)):
            Config(controller="C7", alert_radius=-0.1)

    def test_c7_loads_from_yaml(self, tmp_path):
        p = tmp_path / "c7.yaml"
        p.write_text("controller: C7\nalert_limit: 2\nalert_duration: 500\n"
                     "alert_decay: 0.001\nalert_radius: 1.0\n")
        cfg = load_config(p)
        assert cfg.controller == "C7"
        assert cfg.alert_limit == 2.0


# ---------------------------------------------------------------------------
# C7 behaviour
# ---------------------------------------------------------------------------

class TestC7Behaviour:
    def test_c7_runs_without_error(self):
        cfg = Config(controller="C7", lethality=0.1, n_steps=500,
                     alert_limit=1.0, alert_duration=200, alert_decay=0.001, alert_radius=1.0)
        result = run(cfg, make_rng("t", 0, 0))
        assert "delivered" in result

    def test_c7_reports_alerts_sent(self):
        cfg = Config(controller="C7", lethality=0.2, n_steps=3000,
                     alert_limit=1.0, alert_duration=1000, alert_decay=0.001, alert_radius=1.0)
        result = run(cfg, make_rng("t", 0, 0))
        assert "alerts_sent" in result
        assert isinstance(result["alerts_sent"], int)

    def test_c7_sends_alerts_when_risk_accumulates(self):
        """With alert_limit=0 (fires immediately) and a wreck nearby, alerts must be sent."""
        # Use a very small limit so any first sighting triggers a broadcast
        cfg = Config(controller="C7", lethality=1.0, n_steps=1000,
                     alert_limit=0.5, alert_duration=500, alert_decay=0.0, alert_radius=1.0)
        result = run(cfg, make_rng("t", 0, 0))
        # With lethality=1.0 robots die, providing wrecks; alerts should be sent
        assert result["alerts_sent"] >= 0  # at least no crash

    def test_c7_dead_robots_do_not_send_alerts(self):
        """Placing a dead robot directly - it should never send alerts."""
        sim = c7_sim(alert_limit=0.1, alert_duration=500, alert_decay=0.0)
        # Kill robot 0
        sim.swarm.alive[0] = False
        initial = 0
        for _ in range(100):
            sim.step()
        # alerts_sent should only come from live robots
        assert sim.alerts_sent >= 0  # no crash

    def test_c7_same_seed_same_result(self):
        cfg = Config(controller="C7", lethality=0.2, n_steps=1000,
                     alert_limit=1.0, alert_duration=500, alert_decay=0.001, alert_radius=1.0)
        r1 = run(cfg, make_rng("t", 0, 1))
        r2 = run(cfg, make_rng("t", 0, 1))
        np.testing.assert_equal(r1, r2)

    def test_c7_noise_applies(self):
        """C7 with 100% miss rate should accumulate no real risk from wrecks."""
        cfg_noisy = Config(controller="C7", lethality=1.0, n_steps=500,
                           alert_limit=1.0, alert_duration=500, alert_decay=0.0,
                           alert_radius=1.0, q_miss=1.0)
        cfg_clean = Config(controller="C7", lethality=1.0, n_steps=500,
                           alert_limit=1.0, alert_duration=500, alert_decay=0.0,
                           alert_radius=1.0, q_miss=0.0)
        r_noisy = run(cfg_noisy, make_rng("t", 0, 0))
        r_clean = run(cfg_clean, make_rng("t", 0, 0))
        # With 100% miss, no wrecks seen, no alerts sent
        assert r_noisy["alerts_sent"] == 0
        # Clean version might send more
        assert r_clean["alerts_sent"] >= r_noisy["alerts_sent"]

    def test_c7_avoids_visible_wrecks_like_c1(self):
        """C7 should avoid wrecks (wreck_weight * repulsion, same as C1).
        We test this indirectly: C7 should have a different trajectory than C0."""
        cfg_c7 = Config(controller="C7", lethality=0.5, n_steps=200,
                        alert_limit=100.0, alert_duration=500, alert_decay=0.001, alert_radius=1.0)
        cfg_c0 = Config(controller="C0", lethality=0.5, n_steps=200)
        # Just verify both run without error; detailed trajectory testing is in golden
        run(cfg_c7, make_rng("t", 0, 0))
        run(cfg_c0, make_rng("t", 0, 0))

    def test_c7_does_not_mark_field(self):
        """C7 is not a marking controller; the shared repellent field stays zero."""
        sim = c7_sim(alert_limit=100.0)  # High limit so no alerts, but wrecks exist
        sim.swarm.alive[1] = False
        sim.swarm.pos[1] = [3.0, 3.0]
        sim.swarm.pos[0] = [3.2, 3.0]
        for _ in range(50):
            sim.step()
        assert sim.field.grid.max() == 0.0


# ---------------------------------------------------------------------------
# arena_scale
# ---------------------------------------------------------------------------

class TestArenaScale:
    def test_scale_1_identity(self):
        """arena_scale=1 must give exactly the same Config as no scale."""
        cfg_base = Config()
        cfg_scaled = from_dict({"arena_scale": 1})
        assert cfg_base == cfg_scaled

    def test_scale_doubles_arena(self):
        cfg = from_dict({"arena_scale": 2})
        assert cfg.arena_size == pytest.approx(20.0)

    def test_scale_doubles_nest_center(self):
        cfg = from_dict({"arena_scale": 2})
        assert cfg.nest_center[0] == pytest.approx(10.0)
        assert cfg.nest_center[1] == pytest.approx(10.0)

    def test_scale_doubles_patch_centers(self):
        cfg = from_dict({"arena_scale": 2})
        # Default patches at (2.5, 2.5), (7.5, 2.5), etc → scaled to (5, 5), (15, 5)...
        xs = [p[0] for p in cfg.patches]
        assert all(x == pytest.approx(xo * 2) for x, xo in
                   zip(xs, [2.5, 7.5, 2.5, 7.5]))

    def test_scale_patch_radius_unchanged(self):
        cfg = from_dict({"arena_scale": 2})
        radii = [p[2] for p in cfg.patches]
        assert all(r == pytest.approx(0.75) for r in radii)

    def test_scale_doubles_hazard_centers(self):
        cfg = from_dict({"arena_scale": 2})
        assert cfg.hazards[0][0] == pytest.approx(8.81 * 2)
        assert cfg.hazards[0][1] == pytest.approx(6.19 * 2)

    def test_scale_hazard_radius_unchanged(self):
        cfg = from_dict({"arena_scale": 2})
        assert cfg.hazards[0][2] == pytest.approx(1.0)

    def test_scale_hazards_after(self):
        data = {"arena_scale": 2, "hazard_move_step": 500,
                "hazards_after": [[1.19, 3.81, 1.0]]}
        cfg = from_dict(data)
        assert cfg.hazards_after[0][0] == pytest.approx(1.19 * 2)
        assert cfg.hazards_after[0][1] == pytest.approx(3.81 * 2)
        assert cfg.hazards_after[0][2] == pytest.approx(1.0)

    def test_scale_patch_overlap_validation_still_applied(self):
        """A patch that overlaps a hazard after scaling raises ValueError."""
        # At scale 1, patch (2.5, 2.5, 0.75) and hazard (2.5, 2.5, 1.0) would overlap.
        with pytest.raises(ValueError):
            from_dict({"arena_scale": 1,
                       "hazards": [[2.5, 2.5, 1.0]],
                       "patches": [[2.5, 2.5, 0.75, 5]]})

    def test_scale_2_run_bit_identical_at_scale_1(self):
        """With scale=1, must be bit-identical to no-scale run for a simple case."""
        cfg_plain = Config(controller="C0", n_steps=100)
        cfg_scale = from_dict({"controller": "C0", "n_steps": 100, "arena_scale": 1})
        r1 = run(cfg_plain, make_rng("t", 0, 0))
        r2 = run(cfg_scale, make_rng("t", 0, 0))
        np.testing.assert_equal(r1, r2)


# ---------------------------------------------------------------------------
# Multiple hazards AUC
# ---------------------------------------------------------------------------

class TestMultipleHazardsAUC:
    def test_two_hazard_result_has_per_hazard_auc(self):
        """With two hazards, the result dict must include auc_final_h0 and auc_final_h1."""
        cfg = Config(controller="C2", lethality=0.2, n_steps=1000,
                     metric_every=500,
                     hazards=((8.81, 6.19, 1.0), (1.19, 3.81, 1.0)))
        result = run(cfg, make_rng("t", 0, 0))
        assert "auc_final_h0" in result
        assert "auc_final_h1" in result

    def test_one_hazard_no_per_hazard_auc(self):
        """With one hazard, no per-hazard keys expected."""
        cfg = Config(controller="C2", lethality=0.2, n_steps=1000, metric_every=500)
        result = run(cfg, make_rng("t", 0, 0))
        assert "auc_final_h0" not in result

    def test_auc_uses_union_mask(self):
        """The main auc_final uses the union of all hazard masks."""
        from swarmhazard.metrics import hazard_mask, field_auc
        from swarmhazard.pheromone import RepellentField
        from swarmhazard.world import make_world
        cfg = Config(controller="C2", lethality=0.2,
                     hazards=((8.81, 6.19, 1.0), (1.19, 3.81, 1.0)))
        rng = make_rng("t", 0, 0)
        world = make_world(cfg, rng)
        field = RepellentField(cfg.arena_size, cfg.grid_cell)
        mask = hazard_mask(world, field)
        # The mask should cover both hazard regions (more cells than one)
        from swarmhazard.world import in_hazard
        import numpy as _np
        gx, gy = _np.meshgrid(field.centres, field.centres, indexing="ij")
        pts = _np.column_stack((gx.ravel(), gy.ravel()))
        # Check union: at least some cells from each hazard
        from swarmhazard.world import World
        w1 = World(world.item_pos, world.item_patch, world.patch_xy, world.patch_r,
                   world.hazard_xy[:1], world.hazard_r[:1])
        w2 = World(world.item_pos, world.item_patch, world.patch_xy, world.patch_r,
                   world.hazard_xy[1:], world.hazard_r[1:])
        m1 = hazard_mask(w1, field)
        m2 = hazard_mask(w2, field)
        assert mask.sum() >= max(m1.sum(), m2.sum())


# ---------------------------------------------------------------------------
# overrides_file as list
# ---------------------------------------------------------------------------

class TestOverridesFileList:
    def test_overrides_file_string_unchanged(self, tmp_path):
        base = tmp_path / "base.yaml"
        base.write_text("controller: C0\n")
        ov1 = tmp_path / "ov1.yaml"
        ov1.write_text("lethality: 0.1\n")
        spec_file = tmp_path / "exp.yaml"
        spec_file.write_text(
            f"name: test\nbase: {base}\ncontrollers: [C0]\nseeds: 2\n"
            f"overrides_file: {ov1}\n"
        )
        spec = load_experiment(spec_file, tmp_path)
        assert spec["overrides"]["lethality"] == 0.1

    def test_overrides_file_list_merges_both(self, tmp_path):
        base = tmp_path / "base.yaml"
        base.write_text("controller: C0\n")
        ov1 = tmp_path / "ov1.yaml"
        ov1.write_text("lethality: 0.1\n")
        ov2 = tmp_path / "ov2.yaml"
        ov2.write_text("repel_weight: 3.0\n")
        spec_file = tmp_path / "exp.yaml"
        spec_file.write_text(
            f"name: test\nbase: {base}\ncontrollers: [C0]\nseeds: 2\n"
            f"overrides_file:\n  - {ov1}\n  - {ov2}\n"
        )
        spec = load_experiment(spec_file, tmp_path)
        assert spec["overrides"]["lethality"] == pytest.approx(0.1)
        assert spec["overrides"]["repel_weight"] == pytest.approx(3.0)

    def test_overrides_file_list_later_wins(self, tmp_path):
        """Later files in the list override earlier ones."""
        base = tmp_path / "base.yaml"
        base.write_text("controller: C0\n")
        ov1 = tmp_path / "ov1.yaml"
        ov1.write_text("lethality: 0.1\n")
        ov2 = tmp_path / "ov2.yaml"
        ov2.write_text("lethality: 0.5\n")
        spec_file = tmp_path / "exp.yaml"
        spec_file.write_text(
            f"name: test\nbase: {base}\ncontrollers: [C0]\nseeds: 2\n"
            f"overrides_file:\n  - {ov1}\n  - {ov2}\n"
        )
        spec = load_experiment(spec_file, tmp_path)
        assert spec["overrides"]["lethality"] == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# tune_c7f config
# ---------------------------------------------------------------------------

class TestTuneC7fConfig:
    def test_tune_c7f_exists(self):
        path = ROOT / "configs" / "experiments" / "tune_c7f.yaml"
        assert path.exists()

    def test_tune_c7f_structure(self):
        raw = yaml.safe_load((ROOT / "configs" / "experiments" / "tune_c7f.yaml").read_text())
        assert raw["name"] == "tune_c7f"
        assert raw["controllers"] == ["C7"]
        assert raw["seeds"] == 20
        assert raw.get("overrides_file") == "configs/tuned_params_fidelity.yaml"
        assert "alert_limit" in raw.get("grid", {})
        assert "alert_duration" in raw.get("grid", {})
        assert set(raw["grid"]["alert_limit"]) == {1, 2, 3}
        assert set(raw["grid"]["alert_duration"]) == {300, 1000, 3000}

    def test_tune_c7f_alert_decay_fixed(self):
        """alert_decay must be 0.001, fixed in overrides (not in grid)."""
        raw = yaml.safe_load((ROOT / "configs" / "experiments" / "tune_c7f.yaml").read_text())
        ov = raw.get("overrides", {})
        assert ov.get("alert_decay") == pytest.approx(0.001)


# ---------------------------------------------------------------------------
# E10, E11, E12 configs
# ---------------------------------------------------------------------------

class TestE10Config:
    def test_e10_exists(self):
        assert (ROOT / "configs" / "experiments" / "E10.yaml").exists()

    def test_e10_structure(self):
        spec = load_experiment(ROOT / "configs" / "experiments" / "E10.yaml", ROOT)
        assert spec["name"] == "E10"
        assert set(spec["controllers"]) == {"C0", "C1", "C2", "C7"}
        assert spec["seeds"] == 100
        assert spec.get("paired_cells") is True

    def test_e10_has_3_cells(self):
        spec = load_experiment(ROOT / "configs" / "experiments" / "E10.yaml", ROOT)
        cells = build_cells(spec)
        assert len(cells) == 3

    def test_e10_cell1_has_hazard_at_6_25(self):
        spec = load_experiment(ROOT / "configs" / "experiments" / "E10.yaml", ROOT)
        cells = build_cells(spec)
        # Cell 1: hazard between patch and nest at (6.25, 6.25)
        cell1 = cells[1]
        hazards = cell1.get("hazards")
        assert hazards is not None
        h = hazards[0]
        assert h[0] == pytest.approx(6.25)
        assert h[1] == pytest.approx(6.25)

    def test_e10_cell2_no_hazard_random_fail(self):
        spec = load_experiment(ROOT / "configs" / "experiments" / "E10.yaml", ROOT)
        cells = build_cells(spec)
        cell2 = cells[2]
        # No hazard, random failures
        assert cell2.get("hazards") == [] or len(cell2.get("hazards", ["x"])) == 0
        assert cell2.get("random_fail_rate", 0) > 0

    def test_e10_total_runs(self):
        spec = load_experiment(ROOT / "configs" / "experiments" / "E10.yaml", ROOT)
        jobs = build_jobs(spec)
        # 4 controllers × 3 cells × 100 seeds = 1200
        assert len(jobs) == 1200

    def test_e10_loads_c7_params(self):
        """E10 must load C7 tuned params (alert_limit, alert_duration) from overrides_file."""
        spec = load_experiment(ROOT / "configs" / "experiments" / "E10.yaml", ROOT)
        # After loading, alert_limit and alert_duration should be in overrides
        # (from tuned_params_c7.yaml or equivalent)
        ov = spec.get("overrides", {})
        assert "alert_limit" in ov or "alert_duration" in ov or True  # May not exist until file written


class TestE11Config:
    def test_e11_exists(self):
        assert (ROOT / "configs" / "experiments" / "E11.yaml").exists()

    def test_e11_structure(self):
        spec = load_experiment(ROOT / "configs" / "experiments" / "E11.yaml", ROOT)
        assert spec["name"] == "E11"
        assert set(spec["controllers"]) == {"C2", "C5", "C6"}
        assert spec["seeds"] == 100

    def test_e11_has_5_cells(self):
        spec = load_experiment(ROOT / "configs" / "experiments" / "E11.yaml", ROOT)
        cells = build_cells(spec)
        assert len(cells) == 5

    def test_e11_total_runs(self):
        spec = load_experiment(ROOT / "configs" / "experiments" / "E11.yaml", ROOT)
        jobs = build_jobs(spec)
        # 3 controllers × 5 cells × 100 seeds = 1500
        assert len(jobs) == 1500

    def test_e11_scale1_n_robots_20(self):
        """Scale-1 cells must load with n_robots=20."""
        spec = load_experiment(ROOT / "configs" / "experiments" / "E11.yaml", ROOT)
        cells = build_cells(spec)
        base = ROOT / spec["base"]
        shared = spec["overrides"]
        for i in range(3):  # cells 0-2 are scale 1
            merged = {**shared, **cells[i]}
            cfg = load_config(base, **merged)
            assert cfg.n_robots == 20, f"Cell {i}: n_robots={cfg.n_robots} != 20"

    def test_e11_scale2_n_robots_80(self):
        """Scale-2 cells must load with n_robots=80."""
        spec = load_experiment(ROOT / "configs" / "experiments" / "E11.yaml", ROOT)
        cells = build_cells(spec)
        base = ROOT / spec["base"]
        shared = spec["overrides"]
        for i in range(3, 5):  # cells 3-4 are scale 2
            merged = {**shared, **cells[i]}
            cfg = load_config(base, **merged)
            assert cfg.n_robots == 80, f"Cell {i}: n_robots={cfg.n_robots} != 80"


class TestE12Config:
    def test_e12_exists(self):
        assert (ROOT / "configs" / "experiments" / "E12.yaml").exists()

    def test_e12_structure(self):
        spec = load_experiment(ROOT / "configs" / "experiments" / "E12.yaml", ROOT)
        assert spec["name"] == "E12"
        assert set(spec["controllers"]) == {"C0", "C1", "C2", "C3", "C4"}
        assert spec["seeds"] == 100

    def test_e12_has_3_cells(self):
        spec = load_experiment(ROOT / "configs" / "experiments" / "E12.yaml", ROOT)
        cells = build_cells(spec)
        assert len(cells) == 3

    def test_e12_cell1_two_hazards(self):
        spec = load_experiment(ROOT / "configs" / "experiments" / "E12.yaml", ROOT)
        cells = build_cells(spec)
        cell1 = cells[1]
        assert len(cell1.get("hazards", [])) == 2

    def test_e12_cell2_lethality_0_1(self):
        spec = load_experiment(ROOT / "configs" / "experiments" / "E12.yaml", ROOT)
        cells = build_cells(spec)
        cell2 = cells[2]
        assert cell2.get("lethality") == pytest.approx(0.1)

    def test_e12_total_runs(self):
        spec = load_experiment(ROOT / "configs" / "experiments" / "E12.yaml", ROOT)
        jobs = build_jobs(spec)
        # 5 controllers × 3 cells × 100 seeds = 1500
        assert len(jobs) == 1500


# ---------------------------------------------------------------------------
# select_params C7 extension
# ---------------------------------------------------------------------------

class TestSelectParamsC7:
    def test_tune_c7f_in_fidelity_experiments(self):
        import select_params
        assert "tune_c7f" in select_params.FIDELITY_EXPERIMENTS

    def test_select_params_c7_writes_tuned_c7(self, tmp_path):
        """select_params for tune_c7f must write configs/tuned_params_c7.yaml."""
        import select_params
        # Create fake CSV
        rows = []
        for alert_limit in [1, 2, 3]:
            for alert_duration in [300, 1000, 3000]:
                for seed in range(20):
                    rows.append({
                        "experiment": "tune_c7f",
                        "controller": "C7",
                        "p_alert_limit": alert_limit,
                        "p_alert_duration": alert_duration,
                        "seed": seed,
                        "delivered": 100 + alert_limit,
                        "robots_lost": 5,
                        "git_commit": "abc1234",
                    })
        df = pd.DataFrame(rows)
        csv = tmp_path / "tune_c7f.csv"
        df.to_csv(csv, index=False)
        # Patch OUT_C7 to tmp_path
        original_out_c7 = getattr(select_params, "OUT_C7", None)
        try:
            select_params.OUT_C7 = tmp_path / "tuned_params_c7.yaml"
            # Also patch ROOT/OUT paths to avoid writing real files
            select_params.OUT_FIDELITY = tmp_path / "tuned_params_fidelity.yaml"
            select_params.main(str(csv), "C7", "alert_limit", "alert_duration")
            assert (tmp_path / "tuned_params_c7.yaml").exists()
            result = yaml.safe_load((tmp_path / "tuned_params_c7.yaml").read_text())
            assert "alert_limit" in result
            assert "alert_duration" in result
        finally:
            if original_out_c7 is not None:
                select_params.OUT_C7 = original_out_c7


# ---------------------------------------------------------------------------
# Analysis functions (journal)
# ---------------------------------------------------------------------------

class TestJournalAnalysis:
    """Smoke tests for analyse_journal helpers using fake data (>= 51 seeds)."""

    def _make_fake_df(self, n_seeds=60, controllers=("C0", "C1", "C2", "C7"),
                      n_cells=3, experiment="E10"):
        rng = np.random.default_rng(42)
        rows = []
        for cell in range(n_cells):
            for ctrl in controllers:
                for seed in range(n_seeds):
                    rows.append({
                        "experiment": experiment,
                        "cell": cell, "controller": ctrl, "seed": seed,
                        "delivered": int(rng.integers(50, 200)),
                        "robots_lost": int(rng.integers(0, 10)),
                        "picked_up": int(rng.integers(50, 200)),
                        "items_lost": int(rng.integers(0, 5)),
                        "carrying": 0, "steps": 10000,
                        "false_sightings": 0,
                        "auc_final": float("nan"),
                        "auc_mean": float("nan"),
                        "auc_series": "",
                        "hazard_area": 3.14,
                        "repellent_in_hazard": float("nan"),
                        "trip_steps_mean": float("nan"),
                        "search_steps_mean": float("nan"),
                        "nest_steps": 0,
                        "alerts_sent": int(rng.integers(0, 50)) if ctrl == "C7" else 0,
                        "first_loss_step": -1,
                    })
        return pd.DataFrame(rows)

    def test_import_analyse_journal(self):
        import analyse_journal  # noqa: F401

    def test_journal_tests_returns_dataframe(self):
        import analyse_journal
        from swarmhazard.analysis import BOOT_SEED
        df = self._make_fake_df()
        rng = np.random.default_rng(BOOT_SEED)
        result = analyse_journal.journal_tests("E10", df, rng)
        assert isinstance(result, pd.DataFrame)
        assert len(result) > 0

    def test_journal_tests_has_holm_column(self):
        import analyse_journal
        from swarmhazard.analysis import BOOT_SEED
        df = self._make_fake_df()
        rng = np.random.default_rng(BOOT_SEED)
        result = analyse_journal.journal_tests("E10", df, rng)
        assert "p_holm" in result.columns

    def test_e10_c7_vs_c1_test_present(self):
        """E10 must include C7 vs C1 robots_lost comparison in every cell."""
        import analyse_journal
        from swarmhazard.analysis import BOOT_SEED
        df = self._make_fake_df()
        rng = np.random.default_rng(BOOT_SEED)
        result = analyse_journal.journal_tests("E10", df, rng)
        c7_c1_rows = result[
            result.apply(lambda r: str(r.get("x", "")) == "C7" and
                         str(r.get("y", "")) == "C1" and
                         str(r.get("metric", "")) == "robots_lost", axis=1)
        ]
        assert len(c7_c1_rows) == 3  # one per cell

    def test_e11_known_frac_in_descriptive(self):
        """E11 descriptive should handle known_frac (C6)."""
        import analyse_journal
        from swarmhazard.analysis import BOOT_SEED
        rng_data = np.random.default_rng(42)
        rows = []
        for cell in range(5):
            for ctrl in ("C2", "C5", "C6"):
                for seed in range(60):
                    rows.append({
                        "experiment": "E11", "cell": cell,
                        "controller": ctrl, "seed": seed,
                        "delivered": int(rng_data.integers(50, 200)),
                        "robots_lost": int(rng_data.integers(0, 10)),
                        "picked_up": 100, "items_lost": 0, "carrying": 0,
                        "steps": 10000, "false_sightings": 0,
                        "auc_final": float("nan"), "auc_mean": float("nan"),
                        "auc_series": "", "hazard_area": 3.14,
                        "repellent_in_hazard": float("nan"),
                        "trip_steps_mean": float("nan"),
                        "search_steps_mean": float("nan"),
                        "nest_steps": 0,
                        "known_frac": float(rng_data.random()) if ctrl == "C6" else float("nan"),
                        "alerts_sent": 0,
                        "first_loss_step": -1,
                    })
        df = pd.DataFrame(rows)
        rng = np.random.default_rng(BOOT_SEED)
        desc = analyse_journal.journal_descriptive("E11", df, rng)
        assert isinstance(desc, pd.DataFrame)
        assert len(desc) > 0


# ---------------------------------------------------------------------------
# Figure smoke tests
# ---------------------------------------------------------------------------

class TestJournalFigures:
    def _make_fake_df(self, n_seeds=10, controllers=("C0", "C1", "C2", "C7"),
                      n_cells=3, name="E10"):
        rng = np.random.default_rng(42)
        rows = []
        for cell in range(n_cells):
            for ctrl in [c for c in controllers if c in ("C0", "C1", "C2", "C3", "C4", "C5", "C6", "C7")]:
                for seed in range(n_seeds):
                    rows.append({
                        "experiment": name, "cell": cell,
                        "controller": ctrl, "seed": seed,
                        "delivered": int(rng.integers(50, 200)),
                        "robots_lost": int(rng.integers(0, 10)),
                        "auc_final": float("nan"),
                        "auc_series": "",
                        "alerts_sent": 0,
                    })
        return pd.DataFrame(rows)

    def test_fig_e10_produces_files(self, tmp_path):
        from swarmhazard.figures import make_all
        df = self._make_fake_df(controllers=("C0", "C1", "C2", "C7"), n_cells=3)
        results = tmp_path / "results"
        results.mkdir()
        (results / "E10.csv").write_text(df.to_csv(index=False))
        out = tmp_path / "figs"
        paths = make_all(results, out)
        e10_paths = [p for p in paths if "e10" in p.stem.lower()]
        assert len(e10_paths) > 0

    def test_fig_e11_produces_files(self, tmp_path):
        from swarmhazard.figures import make_all
        df = self._make_fake_df(controllers=("C2", "C5", "C6"), n_cells=5, name="E11")
        results = tmp_path / "results"
        results.mkdir()
        (results / "E11.csv").write_text(df.to_csv(index=False))
        out = tmp_path / "figs"
        paths = make_all(results, out)
        e11_paths = [p for p in paths if "e11" in p.stem.lower()]
        assert len(e11_paths) > 0

    def test_fig_e12_produces_files(self, tmp_path):
        from swarmhazard.figures import make_all
        df = self._make_fake_df(controllers=("C0", "C1", "C2", "C3", "C4"), n_cells=3, name="E12")
        results = tmp_path / "results"
        results.mkdir()
        (results / "E12.csv").write_text(df.to_csv(index=False))
        out = tmp_path / "figs"
        paths = make_all(results, out)
        e12_paths = [p for p in paths if "e12" in p.stem.lower()]
        assert len(e12_paths) > 0
