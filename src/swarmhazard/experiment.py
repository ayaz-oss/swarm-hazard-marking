"""Experiment files: which configurations, controllers and seeds to run.

A cell is one configuration (a set of parameter overrides). Every controller
runs every seed in every cell, and the RNG depends on (name, cell, seed) only,
so controllers are compared on identical conditions.
"""

from __future__ import annotations

import time
from itertools import product
from pathlib import Path

import yaml

from swarmhazard.config import config_hash, load_config
from swarmhazard.seeding import make_rng
from swarmhazard.sim import run


def load_experiment(path: Path, root: Path) -> dict:
    spec = yaml.safe_load(Path(path).read_text())
    shared = {}
    if spec.get("overrides_file"):
        shared.update(yaml.safe_load((root / spec["overrides_file"]).read_text()) or {})
    shared.update(spec.get("overrides") or {})
    spec["overrides"] = shared
    return spec


def build_cells(spec: dict) -> list[dict]:
    if spec.get("grid"):
        names = list(spec["grid"])
        return [dict(zip(names, values)) for values in product(*(spec["grid"][n] for n in names))]
    return [dict(cell) for cell in (spec.get("cells") or [{}])]


def build_jobs(spec: dict, seeds: int | None = None, n_steps: int | None = None) -> list[dict]:
    shared = dict(spec.get("overrides") or {})
    if n_steps is not None:
        shared["n_steps"] = n_steps
    n_seeds = seeds if seeds is not None else spec["seeds"]
    return [
        {"experiment": spec["name"], "base": spec["base"], "overrides": {**shared, **cell},
         "params": cell, "controller": controller, "cell": index, "seed": seed}
        for index, cell in enumerate(build_cells(spec))
        for controller in spec["controllers"]
        for seed in range(n_seeds)
    ]


def run_one(job: dict, root: Path) -> dict:
    cfg = load_config(root / job["base"], **job["overrides"], controller=job["controller"])
    rng = make_rng(job["experiment"], job["cell"], job["seed"])
    start = time.perf_counter()
    row = run(cfg, rng)
    row.update(
        experiment=job["experiment"],
        cell=job["cell"],
        controller=job["controller"],
        seed=job["seed"],
        config_hash=config_hash(cfg),
        wall_s=round(time.perf_counter() - start, 3),
    )
    row.update({f"p_{name}": value for name, value in job["params"].items()})
    return row
