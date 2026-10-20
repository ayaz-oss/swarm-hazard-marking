from pathlib import Path

import numpy as np
import yaml

from swarmhazard.config import load_config
from swarmhazard.experiment import build_cells, build_jobs, load_experiment, run_one
from swarmhazard.provenance import provenance

ROOT = Path(__file__).resolve().parents[1]


def spec(**kw):
    s = {"name": "x", "base": "configs/baseline.yaml", "controllers": ["C0", "C2"],
         "seeds": 3, "overrides": {}}
    s.update(kw)
    return s


def test_grid_expands_to_product():
    cells = build_cells(spec(grid={"a": [1, 2], "b": [3, 4, 5]}))
    assert len(cells) == 6
    assert cells[0] == {"a": 1, "b": 3}


def test_controllers_share_cell_index_and_overrides():
    jobs = build_jobs(spec(cells=[{"decay": 0.001}, {"decay": 0.002}]))
    assert len(jobs) == 2 * 2 * 3
    for cell in (0, 1):
        for seed in range(3):
            pair = [j for j in jobs if j["cell"] == cell and j["seed"] == seed]
            assert {j["controller"] for j in pair} == {"C0", "C2"}
            assert pair[0]["overrides"] == pair[1]["overrides"]


def test_overrides_file_merged_and_explicit_overrides_win(tmp_path):
    (tmp_path / "tuned.yaml").write_text("repel_weight: 2.0\ndecay: 0.001\n")
    exp = tmp_path / "e.yaml"
    exp.write_text("name: e\nbase: b.yaml\ncontrollers: [C2]\nseeds: 1\n"
                   "overrides_file: tuned.yaml\noverrides:\n  decay: 0.002\n")
    s = load_experiment(exp, tmp_path)
    assert s["overrides"] == {"repel_weight": 2.0, "decay": 0.002}


def test_run_one_returns_a_labelled_row():
    job = build_jobs(spec(controllers=["C2"], seeds=1, grid={"repel_weight": [2.0]}), n_steps=20)[0]
    row = run_one(job, ROOT)
    assert row["steps"] == 20
    assert row["p_repel_weight"] == 2.0
    assert row["controller"] == "C2" and row["cell"] == 0 and row["seed"] == 0


def test_provenance_records_versions():
    p = provenance(ROOT)
    assert p["v_numpy"] == np.__version__
    assert {"git_commit", "python", "platform", "v_scipy", "v_pandas", "v_matplotlib", "v_pyyaml"} <= set(p)


MAIN = ["E1", "E2", "E3", "E4", "E5"]


def test_main_experiments_are_valid_and_use_tuned_parameters():
    tuned = yaml.safe_load((ROOT / "configs" / "tuned_params.yaml").read_text())
    for name in MAIN:
        s = load_experiment(ROOT / "configs" / "experiments" / f"{name}.yaml", ROOT)
        assert s["name"] == name
        assert s["controllers"] == ["C0", "C1", "C2", "C3", "C4"]
        assert s["seeds"] == 100
        for key, value in tuned.items():
            assert s["overrides"][key] == value
        jobs = build_jobs(s)
        for cell in sorted({j["cell"] for j in jobs}):
            job = next(j for j in jobs if j["cell"] == cell)
            load_config(ROOT / job["base"], **job["overrides"], controller=job["controller"])
    e2 = build_cells(load_experiment(ROOT / "configs" / "experiments" / "E2.yaml", ROOT))
    assert len(e2) == 4
    assert e2[3]["hazards"] == [] and e2[3]["random_fail_rate"] > 0


def test_main_experiment_levels_are_exactly_as_preregistered():
    def cells(name):
        return build_cells(load_experiment(ROOT / "configs" / "experiments" / f"{name}.yaml", ROOT))
    assert cells("E1") == [{}]
    assert cells("E2") == [{}, {"hazards": [[6.25, 6.25, 1.0]]}, {"hazards": [[5.0, 9.0, 1.0]]},
                           {"hazards": [], "random_fail_rate": 0.0000266}]
    assert cells("E3") == [{"n_robots": n} for n in (5, 10, 20, 40, 80)]
    assert cells("E4") == [{"lethality": p} for p in (0.005, 0.02, 0.1, 1.0)]
    assert cells("E5") == [{"hazards": [[8.4546, 6.5454, 0.5]]}, {}, {"hazards": [[9.5153, 5.4847, 2.0]]}]


def test_week4_experiments():
    e6 = load_experiment(ROOT / "configs" / "experiments" / "E6.yaml", ROOT)
    assert e6["controllers"] == ["C2", "C5"] and e6["seeds"] == 100
    assert build_cells(e6) == [{"n_robots": n} for n in (5, 10, 20, 40, 80)]
    e7 = load_experiment(ROOT / "configs" / "experiments" / "E7.yaml", ROOT)
    assert e7["controllers"] == ["C0", "C1", "C2", "C3"] and e7["seeds"] == 100
    assert build_cells(e7) == [{}, {"q_miss": 0.2}, {"q_false": 0.00001}, {"q_miss": 0.2, "q_false": 0.00001}]
    tuned = yaml.safe_load((ROOT / "configs" / "tuned_params.yaml").read_text())
    for spec in (e6, e7):
        for key, value in tuned.items():
            assert spec["overrides"][key] == value
        for job in build_jobs(spec, seeds=1):
            load_config(ROOT / job["base"], **job["overrides"], controller=job["controller"])


def test_unpaired_jobs_are_unchanged():
    assert all("rng_cell" not in j for j in build_jobs(spec(cells=[{}, {"q_miss": 0.5}])))


def test_paired_cells_use_cell_zero_streams():
    jobs = build_jobs(spec(cells=[{}, {"q_miss": 0.5}], paired_cells=True))
    assert {j["rng_cell"] for j in jobs} == {0}
    assert {j["cell"] for j in jobs} == {0, 1}


def test_paired_cells_differ_only_in_parameters():
    # C0 ignores wrecks, so with paired streams a miss-noise cell must reproduce cell 0 exactly.
    s = spec(controllers=["C0"], seeds=1, cells=[{"lethality": 0.2}, {"lethality": 0.2, "q_miss": 0.5}],
             paired_cells=True)
    a, b = (run_one(j, ROOT) for j in build_jobs(s, n_steps=400))
    for key in ("delivered", "robots_lost", "first_loss_step", "picked_up"):
        assert a[key] == b[key]
    assert a["rng_cell"] == b["rng_cell"] == 0 and (a["cell"], b["cell"]) == (0, 1)


def test_week5_experiments_are_exactly_as_preregistered():
    def load(name):
        return load_experiment(ROOT / "configs" / "experiments" / f"{name}.yaml", ROOT)
    e6b, e7b, e8 = load("E6b"), load("E7b"), load("E8")
    assert e6b["controllers"] == ["C2", "C5", "C6"] and not e6b.get("paired_cells")
    assert build_cells(e6b) == [{"n_robots": n} for n in (5, 10, 20, 40, 80)]
    assert e7b["controllers"] == ["C0", "C1", "C2", "C3"] and e7b["paired_cells"] is True
    assert build_cells(e7b) == [{}, {"q_miss": 0.5}, {"q_miss": 0.8}, {"q_miss": 0.5, "miss_run": 100.0},
                                {"q_miss": 0.8, "miss_run": 100.0}, {"q_false": 0.0001}]
    assert e8["controllers"] == ["C0", "C1", "C2", "C4"] and e8["paired_cells"] is True
    assert e8["overrides"]["hazard_move_step"] == 5000
    assert build_cells(e8) == [{"hazards_after": [[8.81, 6.19, 1.0]], "decay": 0.0002},
                               {"hazards_after": [[1.19, 3.81, 1.0]], "decay": 0.0002},
                               {"hazards_after": [[1.19, 3.81, 1.0]], "decay": 0.002}]
    tuned = yaml.safe_load((ROOT / "configs" / "tuned_params.yaml").read_text())
    for s in (e6b, e7b, e8):
        assert s["seeds"] == 100
        for key, value in tuned.items():
            if key != "decay" or s is not e8:
                assert s["overrides"][key] == value
        for job in build_jobs(s, seeds=1):
            load_config(ROOT / job["base"], **job["overrides"], controller=job["controller"])
