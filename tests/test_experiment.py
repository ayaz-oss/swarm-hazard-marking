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
