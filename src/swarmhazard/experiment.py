"""Experiment files: which configurations, controllers and seeds to run.

A cell is one configuration (a set of parameter overrides). Every controller
runs every seed in every cell, and the RNG depends on (name, cell, seed) only,
so controllers are compared on identical conditions. With the opt-in key
`paired_cells: true` the RNG depends on (name, 0, seed) instead, so every cell
reuses cell 0's streams and cells differ only in their parameters.
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
    ov_file = spec.get("overrides_file")
    if ov_file:
        # Support either a single path string or a list of paths (later entries win).
        ov_files = [ov_file] if isinstance(ov_file, str) else list(ov_file)
        for f in ov_files:
            shared.update(yaml.safe_load((root / f).read_text()) or {})
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
    jobs = [
        {"experiment": spec["name"], "base": spec["base"], "overrides": {**shared, **cell},
         "params": cell, "controller": controller, "cell": index, "seed": seed}
        for index, cell in enumerate(build_cells(spec))
        for controller in spec["controllers"]
        for seed in range(n_seeds)
    ]
    if spec.get("paired_cells"):
        # Every cell reuses cell 0's random streams, so cells differ only in their parameters
        # and comparisons across cells are paired by seed (week-5 addendum section 2).
        for job in jobs:
            job["rng_cell"] = 0
    return jobs


def run_one(job: dict, root: Path) -> dict:
    cfg = load_config(root / job["base"], **job["overrides"], controller=job["controller"])
    rng_cell = job.get("rng_cell", job["cell"])
    rng = make_rng(job["experiment"], rng_cell, job["seed"])
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
    if "rng_cell" in job:
        row["rng_cell"] = rng_cell
    row.update({f"p_{name}": value for name, value in job["params"].items()})
    return row
