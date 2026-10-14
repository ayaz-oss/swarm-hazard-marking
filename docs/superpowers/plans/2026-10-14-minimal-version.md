# Minimal Version (Week 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the smallest simulator that can answer the go/no-go question: at the baseline configuration, does the marking controller (C2) deliver clearly more items than the ignore controller (C0), with the oracle (C4) at least as good as C2?

**Architecture:** A vectorised numpy simulator. One frozen `Config` dataclass holds every parameter; `Simulation(cfg, rng)` owns the world (item patches, hidden hazards), the swarm (state arrays), and a repellent grid, and advances them with `step()`. Controllers differ only in how they bend a robot's heading (`avoidance`), whether they forbid moves (`blocks_move`), and whether they mark wrecks (`MARKING`). Scripts run seeds in parallel to CSV, check the gate, and animate single runs.

**Tech Stack:** Python 3.11, numpy 1.26.4, scipy 1.15.1, pandas 3.0.0, matplotlib 3.10.0, PyYAML 6.0.3, pytest 9.0.3.

**Spec:** `docs/superpowers/specs/2026-10-14-swarm-hazard-design.md` (this plan implements §2, the C0/C2/C4 rows of §3, §5–§7 as far as they apply, and §8).

## Global Constraints

- Units are metres, seconds and radians throughout.
- All randomness goes through the `numpy.random.Generator` passed into the simulation. Never call `np.random.*` module functions or Python's `random`.
- A run is fully determined by `(Config, seed)`; same inputs give an identical result dict.
- RNG seeds come from `(experiment name, cell index, seed index)` via `numpy.random.SeedSequence`. The cell index identifies the environment configuration, not the controller, so all controllers see the same starting layout for a given seed.
- Every result row records the config hash, git commit and package versions.
- No robot–robot collisions in v1.
- Controllers differ only in their reaction to wrecks and repellent; the search/return behaviour is shared.
- `results/` is git-ignored; never commit CSVs or GIFs.
- Commands are run from the repository root in Git Bash. The interpreter is `.venv/Scripts/python`.
- Every commit message ends with the trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## File Structure

| File | Responsibility |
|---|---|
| `pyproject.toml` | Package metadata and pinned dependencies |
| `configs/baseline.yaml` | Every baseline parameter with units (mirrors `Config` defaults) |
| `configs/experiments/gate.yaml` | The week-1 gate experiment |
| `src/swarmhazard/config.py` | `Config`, YAML loading, overrides, validation, hashing |
| `src/swarmhazard/seeding.py` | `make_rng(experiment, cell, seed)` |
| `src/swarmhazard/world.py` | Item patches, hazards, respawn, hazard failures |
| `src/swarmhazard/pheromone.py` | `RepellentField`: deposit, decay, local read, gradient |
| `src/swarmhazard/robots.py` | `Swarm` state arrays and behaviour-state constants |
| `src/swarmhazard/controllers.py` | Avoidance vectors and move-blocking for C0/C2/C4 |
| `src/swarmhazard/sim.py` | `Simulation.step()`, `run(cfg, rng)` |
| `src/swarmhazard/stats.py` | Vargha–Delaney A12 |
| `scripts/run_experiment.py` | Parallel seeds → `results/<name>.csv` |
| `scripts/check_gate.py` | Go/no-go verdict from the CSV |
| `scripts/animate.py` | Watch or save a single run |
| `tests/test_*.py` | One test file per module |
| `docs/learning/01-minimal-version.md` | Plain-English note for the student |
| `README.md` | How to install, test and reproduce |

---

### Task 1: Project scaffold, configuration and seeding

**Files:**
- Create: `pyproject.toml`, `README.md`, `configs/baseline.yaml`, `src/swarmhazard/__init__.py`, `src/swarmhazard/config.py`, `src/swarmhazard/seeding.py`
- Test: `tests/test_config.py`, `tests/test_seeding.py`

**Interfaces:**
- Produces: `Config` (frozen dataclass, fields below); `KNOWN_CONTROLLERS: tuple[str, ...]`; `from_dict(d: dict) -> Config`; `load_config(path, **overrides) -> Config`; `config_hash(cfg: Config) -> str` (12 hex chars); `make_rng(experiment: str, cell: int, seed: int) -> np.random.Generator`.

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "swarmhazard"
version = "0.1.0"
description = "Decentralised foraging swarm that treats robot failures as hazard information"
requires-python = ">=3.11"
license = {text = "MIT"}
dependencies = [
  "numpy==1.26.4",
  "scipy==1.15.1",
  "pandas==3.0.0",
  "matplotlib==3.10.0",
  "pyyaml==6.0.3",
]

[project.optional-dependencies]
dev = ["pytest==9.0.3"]

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Create `src/swarmhazard/__init__.py`**

```python
"""Swarm foraging with robot failures treated as information about hazards."""

__version__ = "0.1.0"
```

- [ ] **Step 3: Create the virtual environment and install**

Run:
```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"
```
Expected: ends with `Successfully installed ... swarmhazard-0.1.0`.

- [ ] **Step 4: Write the failing tests**

`tests/test_config.py`:
```python
from pathlib import Path

import pytest

from swarmhazard.config import Config, config_hash, from_dict, load_config

BASELINE = Path(__file__).resolve().parents[1] / "configs" / "baseline.yaml"


def test_baseline_yaml_matches_defaults():
    assert load_config(BASELINE) == Config()


def test_overrides_apply():
    cfg = load_config(BASELINE, controller="C2", n_robots=5)
    assert cfg.controller == "C2"
    assert cfg.n_robots == 5


def test_unknown_key_rejected():
    with pytest.raises(KeyError):
        from_dict({"n_robot": 5})


def test_unknown_controller_rejected():
    with pytest.raises(ValueError):
        Config(controller="C9")


def test_patch_overlapping_hazard_rejected():
    with pytest.raises(ValueError):
        Config(hazards=((7.5, 7.5, 1.0),))


def test_hash_stable_and_sensitive():
    assert config_hash(Config()) == config_hash(Config())
    assert config_hash(Config()) != config_hash(Config(n_robots=21))
    assert len(config_hash(Config())) == 12
```

`tests/test_seeding.py`:
```python
import numpy as np

from swarmhazard.seeding import make_rng


def test_same_inputs_same_stream():
    assert np.array_equal(make_rng("E1", 0, 3).random(5), make_rng("E1", 0, 3).random(5))


def test_any_input_change_gives_new_stream():
    base = make_rng("E1", 0, 3).random(5)
    assert not np.array_equal(base, make_rng("E1", 0, 4).random(5))
    assert not np.array_equal(base, make_rng("E1", 1, 3).random(5))
    assert not np.array_equal(base, make_rng("E2", 0, 3).random(5))
```

- [ ] **Step 5: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_config.py tests/test_seeding.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'swarmhazard.config'`

- [ ] **Step 6: Implement `config.py`, `seeding.py` and `configs/baseline.yaml`**

`src/swarmhazard/config.py`:
```python
"""Simulation parameters.

Every number the simulator uses lives in one frozen dataclass, so a run is
fully described by (Config, seed). Units: metres, seconds, radians.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, fields
from pathlib import Path

import yaml

KNOWN_CONTROLLERS = ("C0", "C2", "C4")


@dataclass(frozen=True)
class Config:
    # Arena and time
    arena_size: float = 10.0
    nest_center: tuple[float, float] = (5.0, 5.0)
    nest_radius: float = 0.75
    dt: float = 0.1
    n_steps: int = 10_000

    # Robots
    n_robots: int = 20
    speed: float = 0.1
    sense_range: float = 0.5
    pickup_radius: float = 0.05
    turn_noise: float = 0.3

    # Item patches: (x, y, radius, n_items)
    patches: tuple[tuple[float, float, float, int], ...] = (
        (2.5, 2.5, 0.75, 10),
        (7.5, 2.5, 0.75, 10),
        (2.5, 7.5, 0.75, 10),
        (7.5, 7.5, 0.75, 10),
    )

    # Hidden hazards: (x, y, radius); lethality = failure probability per step inside
    hazards: tuple[tuple[float, float, float], ...] = ((8.81, 6.19, 1.0),)
    lethality: float = 0.02

    # Controller and its weights
    controller: str = "C0"
    wreck_weight: float = 1.0
    repel_weight: float = 1.0
    oracle_weight: float = 2.0

    # Repellent field
    grid_cell: float = 0.1
    deposit_amount: float = 1.0
    deposit_sigma: float = 0.3
    decay: float = 0.0005

    def __post_init__(self):
        if self.controller not in KNOWN_CONTROLLERS:
            raise ValueError(f"Unknown controller {self.controller!r}; expected one of {KNOWN_CONTROLLERS}")
        # Items inside a hazard would make the oracle's task ill-defined.
        for px, py, pr, _ in self.patches:
            for hx, hy, hr in self.hazards:
                if math.hypot(px - hx, py - hy) < pr + hr:
                    raise ValueError(f"Patch at ({px}, {py}) overlaps hazard at ({hx}, {hy})")


def _freeze(value):
    """YAML gives lists; the frozen Config needs (nested) tuples."""
    if isinstance(value, list):
        return tuple(_freeze(v) for v in value)
    return value


def from_dict(data: dict) -> Config:
    unknown = set(data) - {f.name for f in fields(Config)}
    if unknown:
        raise KeyError(f"Unknown config keys: {sorted(unknown)}")
    return Config(**{k: _freeze(v) for k, v in data.items()})


def load_config(path, **overrides) -> Config:
    data = yaml.safe_load(Path(path).read_text()) or {}
    data.update(overrides)
    return from_dict(data)


def config_hash(cfg: Config) -> str:
    text = json.dumps(asdict(cfg), sort_keys=True)
    return hashlib.sha256(text.encode()).hexdigest()[:12]
```

`src/swarmhazard/seeding.py`:
```python
"""Reproducible random number streams.

`cell` identifies the environment configuration, NOT the controller, so every
controller sees the same starting layout for a given seed (common random numbers).
"""

from __future__ import annotations

import zlib

import numpy as np


def make_rng(experiment: str, cell: int, seed: int) -> np.random.Generator:
    # crc32 is stable across runs; Python's hash() is randomised per process.
    sequence = np.random.SeedSequence([zlib.crc32(experiment.encode()), cell, seed])
    return np.random.default_rng(sequence)
```

`configs/baseline.yaml`:
```yaml
# Baseline configuration (spec sections 2 and 4). Units: metres, seconds, radians.
# Every experiment states only how it differs from this file.
# Write decimals with a dot (0.0005, not 5e-4): YAML 1.1 reads 5e-4 as text.

# Arena and time
arena_size: 10.0          # m, side of the square arena
nest_center: [5.0, 5.0]   # m
nest_radius: 0.75         # m
dt: 0.1                   # s per step
n_steps: 10000            # 10,000 steps = ~17 simulated minutes

# Robots
n_robots: 20
speed: 0.1                # m/s
sense_range: 0.5          # m, range for items, wrecks and repellent
pickup_radius: 0.05       # m
turn_noise: 0.3           # rad, std of random heading change per step while searching

# Item patches: [x, y, radius, n_items]
patches:
  - [2.5, 2.5, 0.75, 10]
  - [7.5, 2.5, 0.75, 10]
  - [2.5, 7.5, 0.75, 10]
  - [7.5, 7.5, 0.75, 10]

# Hidden hazards: [x, y, radius]. Beside the (7.5, 7.5) patch with a 0.1 m gap,
# 1.85 m off the straight line from that patch to the nest.
hazards:
  - [8.81, 6.19, 1.0]
lethality: 0.02           # failure probability per step inside a hazard

# Controller
controller: C0
wreck_weight: 1.0         # C2: push away from visible wrecks
repel_weight: 1.0         # C2: push down the repellent gradient
oracle_weight: 2.0        # C4: push away from known hazard edges

# Repellent field (C2)
grid_cell: 0.1            # m
deposit_amount: 1.0       # peak concentration added per robot per newly seen wreck
deposit_sigma: 0.3        # m, Gaussian footprint
decay: 0.0005             # fraction lost per step (half-life about 139 s)
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_config.py tests/test_seeding.py -v`
Expected: 8 passed

- [ ] **Step 8: Write `README.md`**

```markdown
# swarmhazard

Simulation code for a study of whether a decentralised foraging robot swarm can
treat teammates' failures as information about where hidden hazards are.

Design: `docs/superpowers/specs/2026-10-14-swarm-hazard-design.md`

## Install

    python -m venv .venv
    .venv/Scripts/python -m pip install -e ".[dev]"     # Windows (Git Bash)
    # .venv/bin/python -m pip install -e ".[dev]"       # macOS / Linux

## Test

    .venv/Scripts/python -m pytest

## Reproduce the week-1 gate

    .venv/Scripts/python scripts/run_experiment.py configs/experiments/gate.yaml
    .venv/Scripts/python scripts/check_gate.py results/gate.csv

## Watch a run

    .venv/Scripts/python scripts/animate.py --controller C2 --seed 0

## Licence

MIT
```

- [ ] **Step 9: Commit**

```bash
git add pyproject.toml README.md configs/baseline.yaml src/swarmhazard/__init__.py src/swarmhazard/config.py src/swarmhazard/seeding.py tests/test_config.py tests/test_seeding.py
git commit -m "Add project scaffold, config and seeding" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: World (items and hazards)

**Files:**
- Create: `src/swarmhazard/world.py`
- Test: `tests/test_world.py`

**Interfaces:**
- Consumes: `Config` (Task 1).
- Produces: `World` dataclass with `item_pos (M,2)`, `item_patch (M,)`, `patch_xy (P,2)`, `patch_r (P,)`, `hazard_xy (H,2)`, `hazard_r (H,)`; `sample_in_disc(rng, centre, radius, n) -> (n,2)`; `make_world(cfg, rng) -> World`; `respawn_item(world, idx, rng) -> None`; `in_hazard(world, pos) -> bool (N,)`; `hazard_failures(world, pos, alive, lethality, rng) -> bool (N,)` (always draws exactly `len(pos)` uniforms).

- [ ] **Step 1: Write the failing tests**

`tests/test_world.py`:
```python
import numpy as np

from swarmhazard.config import Config
from swarmhazard.seeding import make_rng
from swarmhazard.world import hazard_failures, in_hazard, make_world, respawn_item


def world_and_rng():
    rng = make_rng("test", 0, 0)
    return make_world(Config(), rng), rng


def test_items_start_inside_their_patch():
    world, _ = world_and_rng()
    assert len(world.item_pos) == 40
    centres = world.patch_xy[world.item_patch]
    dist = np.linalg.norm(world.item_pos - centres, axis=1)
    assert np.all(dist <= world.patch_r[world.item_patch])


def test_respawn_moves_item_within_same_patch():
    world, rng = world_and_rng()
    before = world.item_pos[7].copy()
    respawn_item(world, 7, rng)
    k = world.item_patch[7]
    assert not np.array_equal(before, world.item_pos[7])
    assert np.linalg.norm(world.item_pos[7] - world.patch_xy[k]) <= world.patch_r[k]


def test_in_hazard():
    world, _ = world_and_rng()
    pos = np.array([[8.81, 6.19], [5.0, 5.0]])
    assert in_hazard(world, pos).tolist() == [True, False]


def test_no_hazards_means_never_inside():
    world = make_world(Config(hazards=()), make_rng("test", 0, 0))
    assert not in_hazard(world, np.array([[8.81, 6.19]])).any()


def test_failure_rate_inside_hazard_matches_lethality():
    world, rng = world_and_rng()
    n = 20_000
    pos = np.tile([8.81, 6.19], (n, 1))
    rate = hazard_failures(world, pos, np.ones(n, bool), 0.02, rng).mean()
    assert abs(rate - 0.02) < 0.004  # about 4 standard errors


def test_no_failures_outside_hazard_or_when_already_dead():
    world, rng = world_and_rng()
    outside = np.tile([5.0, 5.0], (1000, 1))
    assert not hazard_failures(world, outside, np.ones(1000, bool), 1.0, rng).any()
    inside = np.tile([8.81, 6.19], (1000, 1))
    assert not hazard_failures(world, inside, np.zeros(1000, bool), 1.0, rng).any()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_world.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'swarmhazard.world'`

- [ ] **Step 3: Implement `world.py`**

```python
"""The environment: item patches and hidden hazards.

Robots never read hazard positions directly; only the oracle controller (C4)
and the failure rule use them.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from swarmhazard.config import Config


@dataclass
class World:
    item_pos: np.ndarray    # (M, 2) current item positions
    item_patch: np.ndarray  # (M,) patch index of each item
    patch_xy: np.ndarray    # (P, 2)
    patch_r: np.ndarray     # (P,)
    hazard_xy: np.ndarray   # (H, 2)
    hazard_r: np.ndarray    # (H,)


def sample_in_disc(rng: np.random.Generator, centre, radius: float, n: int) -> np.ndarray:
    """n points spread uniformly over a disc (the sqrt makes it uniform by area)."""
    r = radius * np.sqrt(rng.random(n))
    theta = 2 * np.pi * rng.random(n)
    return np.asarray(centre, dtype=float) + np.column_stack((r * np.cos(theta), r * np.sin(theta)))


def make_world(cfg: Config, rng: np.random.Generator) -> World:
    patch_xy = np.array([p[:2] for p in cfg.patches], dtype=float).reshape(-1, 2)
    patch_r = np.array([p[2] for p in cfg.patches], dtype=float)
    counts = [int(p[3]) for p in cfg.patches]
    item_patch = np.repeat(np.arange(len(counts)), counts)
    if counts:
        item_pos = np.concatenate(
            [sample_in_disc(rng, patch_xy[k], patch_r[k], c) for k, c in enumerate(counts)]
        )
    else:
        item_pos = np.zeros((0, 2))
    hazard_xy = np.array([h[:2] for h in cfg.hazards], dtype=float).reshape(-1, 2)
    hazard_r = np.array([h[2] for h in cfg.hazards], dtype=float)
    return World(item_pos, item_patch, patch_xy, patch_r, hazard_xy, hazard_r)


def respawn_item(world: World, idx: int, rng: np.random.Generator) -> None:
    """A collected item reappears at a random spot in its own patch (spec section 2)."""
    k = world.item_patch[idx]
    world.item_pos[idx] = sample_in_disc(rng, world.patch_xy[k], world.patch_r[k], 1)[0]


def in_hazard(world: World, pos: np.ndarray) -> np.ndarray:
    if len(world.hazard_r) == 0:
        return np.zeros(len(pos), dtype=bool)
    dist = np.linalg.norm(pos[:, None, :] - world.hazard_xy[None, :, :], axis=2)
    return (dist < world.hazard_r[None, :]).any(axis=1)


def hazard_failures(world: World, pos: np.ndarray, alive: np.ndarray, lethality: float,
                    rng: np.random.Generator) -> np.ndarray:
    """Which robots fail this step: alive, inside a hazard, and unlucky.

    Always draws one number per robot so the random stream does not depend on
    where robots happen to be.
    """
    draws = rng.random(len(pos))
    return alive & in_hazard(world, pos) & (draws < lethality)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_world.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add src/swarmhazard/world.py tests/test_world.py
git commit -m "Add world: item patches, respawn and hidden hazards" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Repellent field

**Files:**
- Create: `src/swarmhazard/pheromone.py`
- Test: `tests/test_pheromone.py`

**Interfaces:**
- Produces: `RepellentField(arena_size: float, cell: float)` with attributes `grid (n,n)` indexed `grid[ix, iy]`, `cell`, `n`, `centres`; methods `deposit(xy, amount, sigma) -> None`, `decay(rate) -> None`, `value(pts (N,2)) -> (N,)`, `gradient(pts (N,2), h) -> (N,2)`.

- [ ] **Step 1: Write the failing tests**

`tests/test_pheromone.py`:
```python
import numpy as np
import pytest

from swarmhazard.pheromone import RepellentField


def test_deposit_peak_and_shape():
    f = RepellentField(10.0, 0.1)
    f.deposit((5.05, 5.05), amount=2.0, sigma=0.3)  # exactly on a cell centre
    assert f.value(np.array([[5.05, 5.05]]))[0] == pytest.approx(2.0)
    assert f.value(np.array([[5.35, 5.05]]))[0] == pytest.approx(2.0 * np.exp(-0.5), rel=1e-6)
    assert f.value(np.array([[1.0, 1.0]]))[0] == 0.0


def test_decay_is_geometric():
    f = RepellentField(10.0, 0.1)
    f.deposit((5.0, 5.0), 1.0, 0.3)
    total = f.grid.sum()
    for _ in range(100):
        f.decay(0.01)
    assert f.grid.sum() == pytest.approx(total * 0.99**100)


def test_gradient_points_toward_peak():
    f = RepellentField(10.0, 0.1)
    f.deposit((5.05, 5.05), 1.0, 0.3)
    g = f.gradient(np.array([[5.55, 5.05]]), h=0.5)[0]
    assert g[0] < 0             # concentration rises toward x = 5.05
    assert abs(g[1]) < 1e-12    # symmetric in y


def test_edges_are_safe():
    f = RepellentField(10.0, 0.1)
    f.deposit((0.0, 0.0), 1.0, 0.3)
    f.deposit((10.0, 10.0), 1.0, 0.3)
    v = f.value(np.array([[-1.0, -1.0], [11.0, 11.0]]))
    assert v.shape == (2,)
    assert np.all(v > 0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_pheromone.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'swarmhazard.pheromone'`

- [ ] **Step 3: Implement `pheromone.py`**

```python
"""Virtual repellent laid on a grid over the arena.

The grid is shared (like projected light in ARK or Phormica), but a robot only
ever reads cells within its sensing range, so the information is still local.
"""

from __future__ import annotations

import numpy as np


class RepellentField:
    def __init__(self, arena_size: float, cell: float):
        self.cell = cell
        self.n = int(round(arena_size / cell))
        self.grid = np.zeros((self.n, self.n))           # grid[ix, iy]
        self.centres = (np.arange(self.n) + 0.5) * cell  # cell-centre coordinate along either axis

    def deposit(self, xy, amount: float, sigma: float) -> None:
        """Add a Gaussian bump with peak `amount`, cut off at 3 sigma."""
        x, y = float(xy[0]), float(xy[1])
        reach = 3 * sigma
        ix0 = max(int((x - reach) / self.cell), 0)
        ix1 = min(int((x + reach) / self.cell) + 1, self.n)
        iy0 = max(int((y - reach) / self.cell), 0)
        iy1 = min(int((y + reach) / self.cell) + 1, self.n)
        if ix0 >= ix1 or iy0 >= iy1:
            return
        dx = self.centres[ix0:ix1, None] - x
        dy = self.centres[None, iy0:iy1] - y
        self.grid[ix0:ix1, iy0:iy1] += amount * np.exp(-(dx**2 + dy**2) / (2 * sigma**2))

    def decay(self, rate: float) -> None:
        self.grid *= 1.0 - rate

    def value(self, pts: np.ndarray) -> np.ndarray:
        """Concentration in the cell under each point (points off the arena read the edge cell)."""
        idx = np.clip((np.asarray(pts, dtype=float) / self.cell).astype(int), 0, self.n - 1)
        return self.grid[idx[:, 0], idx[:, 1]]

    def gradient(self, pts: np.ndarray, h: float) -> np.ndarray:
        """Central-difference gradient from samples a distance h either side of each point."""
        pts = np.asarray(pts, dtype=float)
        ex = np.array([h, 0.0])
        ey = np.array([0.0, h])
        gx = (self.value(pts + ex) - self.value(pts - ex)) / (2 * h)
        gy = (self.value(pts + ey) - self.value(pts - ey)) / (2 * h)
        return np.column_stack((gx, gy))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_pheromone.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/swarmhazard/pheromone.py tests/test_pheromone.py
git commit -m "Add repellent field with deposit, decay and local gradient" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Swarm state and controllers (C0, C2, C4)

**Files:**
- Create: `src/swarmhazard/robots.py`, `src/swarmhazard/controllers.py`
- Test: `tests/test_robots.py`, `tests/test_controllers.py`

**Interfaces:**
- Consumes: `Config`, `World`, `in_hazard`, `sample_in_disc` (Task 2), `RepellentField` (Task 3).
- Produces: `SEARCH = 0`, `RETURN = 1`; `Swarm` dataclass with `pos (N,2)`, `heading (N,)`, `state (N,) int8`, `alive (N,) bool`; `make_swarm(cfg, rng) -> Swarm`; `unit(theta) -> (N,2)`; `MARKING: frozenset[str]`; `wreck_repulsion(pos, wreck_pos, sense_range) -> (N,2)`; `hazard_repulsion(pos, hazard_xy, hazard_r, sense_range) -> (N,2)`; `avoidance(cfg, pos, wreck_pos, field, world) -> (N,2)`; `blocks_move(cfg, world, new_pos) -> bool (N,)`.

- [ ] **Step 1: Write the failing tests**

`tests/test_robots.py`:
```python
import numpy as np

from swarmhazard.config import Config
from swarmhazard.robots import SEARCH, make_swarm, unit
from swarmhazard.seeding import make_rng


def test_swarm_starts_alive_searching_in_nest():
    cfg = Config()
    sw = make_swarm(cfg, make_rng("test", 0, 0))
    assert sw.pos.shape == (20, 2)
    assert np.all(np.linalg.norm(sw.pos - np.array(cfg.nest_center), axis=1) < cfg.nest_radius)
    assert sw.alive.all()
    assert np.all(sw.state == SEARCH)


def test_unit_vectors():
    u = unit(np.array([0.0, np.pi / 2]))
    assert np.allclose(u, [[1, 0], [0, 1]])
```

`tests/test_controllers.py`:
```python
import numpy as np

from swarmhazard.config import Config
from swarmhazard.controllers import avoidance, blocks_move, hazard_repulsion, wreck_repulsion
from swarmhazard.pheromone import RepellentField
from swarmhazard.seeding import make_rng
from swarmhazard.world import make_world


def setup(controller):
    cfg = Config(controller=controller)
    return cfg, make_world(cfg, make_rng("test", 0, 0)), RepellentField(cfg.arena_size, cfg.grid_cell)


def test_wreck_repulsion_pushes_away_within_range_only():
    pos = np.array([[1.0, 0.0], [3.0, 0.0]])
    push = wreck_repulsion(pos, np.array([[0.8, 0.0]]), sense_range=0.5)
    assert push[0, 0] > 0 and abs(push[0, 1]) < 1e-12
    assert np.all(push[1] == 0)


def test_wreck_repulsion_with_no_wrecks_is_zero():
    assert np.all(wreck_repulsion(np.ones((3, 2)), np.zeros((0, 2)), 0.5) == 0)


def test_hazard_repulsion_near_edge_only():
    pos = np.array([[2.3, 0.0], [5.0, 0.0]])
    push = hazard_repulsion(pos, np.array([[0.0, 0.0]]), np.array([2.0]), sense_range=0.5)
    assert push[0, 0] > 0
    assert np.all(push[1] == 0)


def test_c0_ignores_everything():
    cfg, world, field = setup("C0")
    field.deposit((5.0, 5.0), 5.0, 0.3)
    pos = np.array([[5.3, 5.0]])
    assert np.all(avoidance(cfg, pos, np.array([[5.2, 5.0]]), field, world) == 0)
    assert not blocks_move(cfg, world, np.array([[8.81, 6.19]])).any()


def test_c2_steers_away_from_repellent():
    cfg, world, field = setup("C2")
    field.deposit((5.0, 5.0), 5.0, 0.3)
    push = avoidance(cfg, np.array([[5.3, 5.0]]), np.zeros((0, 2)), field, world)
    assert push[0, 0] > 0


def test_c4_blocks_moves_into_hazards():
    cfg, world, field = setup("C4")
    assert blocks_move(cfg, world, np.array([[8.81, 6.19], [5.0, 5.0]])).tolist() == [True, False]
    push = avoidance(cfg, np.array([[8.81 - 1.2, 6.19]]), np.zeros((0, 2)), field, world)
    assert push[0, 0] < 0  # pushed west, away from the hazard centre
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_robots.py tests/test_controllers.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'swarmhazard.robots'`

- [ ] **Step 3: Implement `robots.py`**

```python
"""Swarm state, stored as arrays so every robot updates in one numpy operation."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from swarmhazard.config import Config
from swarmhazard.world import sample_in_disc

SEARCH = 0  # wandering, looking for an item
RETURN = 1  # carrying an item back to the nest


@dataclass
class Swarm:
    pos: np.ndarray      # (N, 2) metres
    heading: np.ndarray  # (N,) radians
    state: np.ndarray    # (N,) SEARCH or RETURN
    alive: np.ndarray    # (N,) bool; a dead robot is a wreck at its last position


def make_swarm(cfg: Config, rng: np.random.Generator) -> Swarm:
    n = cfg.n_robots
    pos = sample_in_disc(rng, cfg.nest_center, 0.8 * cfg.nest_radius, n)
    heading = rng.uniform(-np.pi, np.pi, n)
    return Swarm(pos, heading, np.full(n, SEARCH, dtype=np.int8), np.ones(n, dtype=bool))


def unit(theta: np.ndarray) -> np.ndarray:
    return np.column_stack((np.cos(theta), np.sin(theta)))
```

- [ ] **Step 4: Implement `controllers.py`**

```python
"""How each controller reacts to failures.

All controllers share the same search / return behaviour (see sim.py). They
differ only here:
  C0  Ignore         - no reaction.
  C2  Mark           - push away from visible wrecks and down the repellent
                       gradient; robots also deposit repellent on wrecks (MARKING).
  C4  Oracle         - knows the true hazards: pushed away from their edges and
                       never allowed to step inside. Upper bound, not a swarm method.
"""

from __future__ import annotations

import numpy as np

from swarmhazard.config import Config
from swarmhazard.pheromone import RepellentField
from swarmhazard.world import World, in_hazard

MARKING = frozenset({"C2"})


def wreck_repulsion(pos: np.ndarray, wreck_pos: np.ndarray, sense_range: float) -> np.ndarray:
    """Sum of unit pushes away from each visible wreck, stronger when closer."""
    if len(wreck_pos) == 0:
        return np.zeros_like(pos)
    diff = pos[:, None, :] - wreck_pos[None, :, :]
    dist = np.linalg.norm(diff, axis=2)
    weight = np.where((dist < sense_range) & (dist > 1e-9), 1.0 - dist / sense_range, 0.0)
    direction = diff / np.maximum(dist, 1e-9)[..., None]
    return (weight[..., None] * direction).sum(axis=1)


def hazard_repulsion(pos: np.ndarray, hazard_xy: np.ndarray, hazard_r: np.ndarray,
                     sense_range: float) -> np.ndarray:
    """Push away from each hazard centre once within sense_range of its edge."""
    if len(hazard_r) == 0:
        return np.zeros_like(pos)
    diff = pos[:, None, :] - hazard_xy[None, :, :]
    dist = np.linalg.norm(diff, axis=2)
    edge = dist - hazard_r[None, :]
    weight = np.clip(1.0 - edge / sense_range, 0.0, None)
    direction = diff / np.maximum(dist, 1e-9)[..., None]
    return (weight[..., None] * direction).sum(axis=1)


def avoidance(cfg: Config, pos: np.ndarray, wreck_pos: np.ndarray, field: RepellentField,
              world: World) -> np.ndarray:
    """Vector added to each robot's intended unit heading."""
    if cfg.controller == "C0":
        return np.zeros_like(pos)
    if cfg.controller == "C2":
        return (cfg.wreck_weight * wreck_repulsion(pos, wreck_pos, cfg.sense_range)
                - cfg.repel_weight * field.gradient(pos, cfg.sense_range))
    if cfg.controller == "C4":
        return cfg.oracle_weight * hazard_repulsion(pos, world.hazard_xy, world.hazard_r, cfg.sense_range)
    raise ValueError(f"No avoidance rule for controller {cfg.controller!r}")


def blocks_move(cfg: Config, world: World, new_pos: np.ndarray) -> np.ndarray:
    """Only the oracle refuses to step into a hazard."""
    if cfg.controller == "C4":
        return in_hazard(world, new_pos)
    return np.zeros(len(new_pos), dtype=bool)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_robots.py tests/test_controllers.py -v`
Expected: 8 passed

- [ ] **Step 6: Commit**

```bash
git add src/swarmhazard/robots.py src/swarmhazard/controllers.py tests/test_robots.py tests/test_controllers.py
git commit -m "Add swarm state and C0/C2/C4 controllers" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Simulation loop

**Files:**
- Create: `src/swarmhazard/sim.py`
- Test: `tests/test_sim.py`

**Interfaces:**
- Consumes: everything from Tasks 1–4.
- Produces: `Simulation(cfg, rng)` with attributes `cfg, rng, world, swarm, field, seen (N,N) bool, nest (2,), t, delivered, first_loss_step` and methods `step() -> None`, `result() -> dict` with keys `delivered, robots_lost, first_loss_step, steps`; `run(cfg, rng) -> dict` (same keys).

Per-step order (document this in the module docstring): choose headings → move → pick up → deliver → hazard failures → (C2 only) mark new wrecks, then decay the field.

- [ ] **Step 1: Write the failing tests**

`tests/test_sim.py`:
```python
import numpy as np

from swarmhazard.config import Config
from swarmhazard.robots import RETURN, SEARCH
from swarmhazard.seeding import make_rng
from swarmhazard.sim import Simulation, run


def new_sim(**kw):
    return Simulation(Config(**kw), make_rng("test", 0, 0))


def test_same_seed_same_result():
    cfg = Config(controller="C2", lethality=0.2, n_steps=3000)
    assert run(cfg, make_rng("t", 0, 1)) == run(cfg, make_rng("t", 0, 1))


def test_robots_stay_in_arena():
    sim = new_sim(n_steps=2000)
    for _ in range(2000):
        sim.step()
    assert np.all((sim.swarm.pos >= 0) & (sim.swarm.pos <= sim.cfg.arena_size))


def test_pickup_switches_to_return_and_respawns_item():
    sim = new_sim()
    sim.swarm.pos[0] = sim.world.item_pos[0]
    before = sim.world.item_pos[0].copy()
    sim.step()
    assert sim.swarm.state[0] == RETURN
    assert not np.array_equal(before, sim.world.item_pos[0])


def test_delivery_counts_and_resumes_search():
    sim = new_sim()
    sim.swarm.state[0] = RETURN
    sim.swarm.pos[0] = sim.nest
    sim.step()
    assert sim.delivered == 1
    assert sim.swarm.state[0] == SEARCH


def test_robot_dies_in_lethal_hazard():
    sim = new_sim(lethality=1.0)
    sim.swarm.pos[0] = [8.81, 6.19]
    sim.step()
    assert not sim.swarm.alive[0]
    assert sim.first_loss_step == 0
    assert sim.result()["robots_lost"] == 1


def place_wreck_next_to_robot_0(sim):
    sim.swarm.alive[1] = False
    sim.swarm.pos[1] = [3.0, 3.0]
    sim.swarm.pos[0] = [3.2, 3.0]


def test_c2_marks_wreck_and_c0_does_not():
    c2 = new_sim(controller="C2")
    place_wreck_next_to_robot_0(c2)
    c2.step()
    assert c2.field.grid.max() > 0
    assert c2.seen[0, 1]

    c0 = new_sim(controller="C0")
    place_wreck_next_to_robot_0(c0)
    c0.step()
    assert c0.field.grid.max() == 0


def test_each_robot_marks_a_wreck_only_once():
    sim = new_sim(controller="C2")
    place_wreck_next_to_robot_0(sim)
    sim.step()
    first = sim.field.grid.max()
    sim.step()
    assert sim.field.grid.max() < first  # only decay, no second deposit


def test_oracle_never_loses_robots():
    cfg = Config(controller="C4", lethality=1.0, n_steps=5000)
    assert run(cfg, make_rng("t", 0, 2))["robots_lost"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_sim.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'swarmhazard.sim'`

- [ ] **Step 3: Implement `sim.py`**

```python
"""One simulation run.

Each step, in order:
  1. choose headings  - searchers random-walk or head for a visible item;
                        returners head for the nest; the controller bends headings
  2. move             - walls bounce robots; the oracle refuses hazard cells
  3. pick up          - a searcher within pickup_radius of an item takes it
  4. deliver          - a returner inside the nest drops its item
  5. hazard failures  - robots inside a hazard fail with probability `lethality`
  6. mark (C2 only)   - each robot that sees a wreck for the first time deposits
                        repellent on it; then the whole field decays
"""

from __future__ import annotations

import numpy as np

from swarmhazard.config import Config
from swarmhazard.controllers import MARKING, avoidance, blocks_move
from swarmhazard.pheromone import RepellentField
from swarmhazard.robots import RETURN, SEARCH, make_swarm, unit
from swarmhazard.world import hazard_failures, make_world, respawn_item


class Simulation:
    def __init__(self, cfg: Config, rng: np.random.Generator):
        self.cfg = cfg
        self.rng = rng
        self.world = make_world(cfg, rng)
        self.swarm = make_swarm(cfg, rng)
        self.field = RepellentField(cfg.arena_size, cfg.grid_cell)
        n = cfg.n_robots
        self.seen = np.zeros((n, n), dtype=bool)  # seen[i, j]: robot i has already marked wreck j
        self.nest = np.asarray(cfg.nest_center, dtype=float)
        self.t = 0
        self.delivered = 0
        self.first_loss_step = -1

    def step(self) -> None:
        sw = self.swarm
        alive = sw.alive.copy()
        searching = alive & (sw.state == SEARCH)
        returning = alive & (sw.state == RETURN)

        self._choose_headings(searching, returning)
        self._move(alive)
        self._pick_up(searching)
        self._deliver(returning)
        self._fail(alive)
        if self.cfg.controller in MARKING:
            self._mark()
            self.field.decay(self.cfg.decay)
        self.t += 1

    def _choose_headings(self, searching: np.ndarray, returning: np.ndarray) -> None:
        cfg, sw = self.cfg, self.swarm
        sw.heading[searching] += self.rng.normal(0.0, cfg.turn_noise, searching.sum())
        if len(self.world.item_pos):
            to_items = self.world.item_pos[None, :, :] - sw.pos[:, None, :]
            dist = np.linalg.norm(to_items, axis=2)
            nearest = dist.argmin(axis=1)
            rows = np.arange(len(sw.pos))
            sees_item = searching & (dist[rows, nearest] < cfg.sense_range)
            v = to_items[rows, nearest]
            sw.heading[sees_item] = np.arctan2(v[sees_item, 1], v[sees_item, 0])
        v = self.nest - sw.pos
        sw.heading[returning] = np.arctan2(v[returning, 1], v[returning, 0])

        wrecks = sw.pos[~sw.alive]
        steer = unit(sw.heading) + avoidance(cfg, sw.pos, wrecks, self.field, self.world)
        sw.heading[:] = np.where(sw.alive, np.arctan2(steer[:, 1], steer[:, 0]), sw.heading)

    def _move(self, alive: np.ndarray) -> None:
        cfg, sw = self.cfg, self.swarm
        new = sw.pos + cfg.speed * cfg.dt * unit(sw.heading)
        hit_wall = ((new < 0) | (new > cfg.arena_size)).any(axis=1)
        new = np.clip(new, 0.0, cfg.arena_size)
        blocked = blocks_move(cfg, self.world, new)
        moves = alive & ~blocked
        sw.pos[moves] = new[moves]
        bounce = alive & (hit_wall | blocked)
        sw.heading[bounce] += np.pi + self.rng.normal(0.0, 0.5, bounce.sum())

    def _pick_up(self, searching: np.ndarray) -> None:
        # A loop, not a vectorised op: two robots must not take the same item.
        if len(self.world.item_pos) == 0:
            return
        sw = self.swarm
        for i in np.flatnonzero(searching):
            d = np.linalg.norm(self.world.item_pos - sw.pos[i], axis=1)
            j = int(d.argmin())
            if d[j] < self.cfg.pickup_radius:
                sw.state[i] = RETURN
                respawn_item(self.world, j, self.rng)

    def _deliver(self, returning: np.ndarray) -> None:
        sw = self.swarm
        at_nest = returning & (np.linalg.norm(sw.pos - self.nest, axis=1) < self.cfg.nest_radius)
        sw.state[at_nest] = SEARCH
        sw.heading[at_nest] = self.rng.uniform(-np.pi, np.pi, at_nest.sum())
        self.delivered += int(at_nest.sum())

    def _fail(self, alive: np.ndarray) -> None:
        sw = self.swarm
        dies = hazard_failures(self.world, sw.pos, alive, self.cfg.lethality, self.rng)
        if dies.any():
            sw.alive[dies] = False  # a carried item is lost with the robot
            if self.first_loss_step < 0:
                self.first_loss_step = self.t

    def _mark(self) -> None:
        cfg, sw = self.cfg, self.swarm
        dead = np.flatnonzero(~sw.alive)
        if len(dead) == 0:
            return
        dist = np.linalg.norm(sw.pos[:, None, :] - sw.pos[None, dead, :], axis=2)  # (N, D)
        visible = sw.alive[:, None] & (dist < cfg.sense_range)
        new = visible & ~self.seen[:, dead]
        for col in np.flatnonzero(new.any(axis=0)):
            amount = cfg.deposit_amount * new[:, col].sum()
            self.field.deposit(sw.pos[dead[col]], amount, cfg.deposit_sigma)
        self.seen[:, dead] |= visible

    def result(self) -> dict:
        return {
            "delivered": self.delivered,
            "robots_lost": int((~self.swarm.alive).sum()),
            "first_loss_step": self.first_loss_step,
            "steps": self.t,
        }


def run(cfg: Config, rng: np.random.Generator) -> dict:
    sim = Simulation(cfg, rng)
    for _ in range(cfg.n_steps):
        sim.step()
    return sim.result()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_sim.py -v`
Expected: 8 passed

- [ ] **Step 5: Run the full suite**

Run: `.venv/Scripts/python -m pytest`
Expected: 34 passed

- [ ] **Step 6: Commit**

```bash
git add src/swarmhazard/sim.py tests/test_sim.py
git commit -m "Add simulation loop with pickup, delivery, failures and marking" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Effect size, experiment runner and gate check

**Files:**
- Create: `src/swarmhazard/stats.py`, `scripts/run_experiment.py`, `scripts/check_gate.py`, `configs/experiments/gate.yaml`
- Test: `tests/test_stats.py`

**Interfaces:**
- Consumes: `load_config`, `config_hash` (Task 1), `make_rng` (Task 1), `run` (Task 5).
- Produces: `a12(x, y) -> float`; CSV at `results/<name>.csv` (or `results/<name>_smoke.csv` when `--seeds` or `--n-steps` is given) with columns `delivered, robots_lost, first_loss_step, steps, experiment, cell, controller, seed, config_hash, wall_s, git_commit, numpy, python`; `check_gate.py` exits 0 on PASS, 1 on FAIL.

- [ ] **Step 1: Write the failing test**

`tests/test_stats.py`:
```python
import pytest

from swarmhazard.stats import a12


def test_a12_values():
    assert a12([1, 2, 3], [1, 2, 3]) == pytest.approx(0.5)
    assert a12([4, 5], [1, 2]) == 1.0
    assert a12([1, 2], [4, 5]) == 0.0
    assert a12([3, 3], [1, 3]) == pytest.approx(0.75)  # one win and one tie per draw
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_stats.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'swarmhazard.stats'`

- [ ] **Step 3: Implement `stats.py`**

```python
"""Effect sizes used throughout the paper."""

from __future__ import annotations

import numpy as np


def a12(x, y) -> float:
    """Vargha-Delaney A12: chance a random run from x beats a random run from y (ties count half).

    0.5 means no difference. Conventional thresholds: 0.56 small, 0.64 medium, 0.71 large.
    """
    x = np.asarray(x, dtype=float)[:, None]
    y = np.asarray(y, dtype=float)[None, :]
    return float((x > y).mean() + 0.5 * (x == y).mean())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_stats.py -v`
Expected: 1 passed

- [ ] **Step 5: Create `configs/experiments/gate.yaml`**

```yaml
# Week-1 go/no-go gate (spec section 8): baseline only, C0 / C2 / C4, 30 seeds.
name: gate
base: configs/baseline.yaml
controllers: [C0, C2, C4]
seeds: 30
overrides: {}
```

- [ ] **Step 6: Create `scripts/run_experiment.py`**

```python
"""Run every (controller, seed) pair of an experiment and save one CSV row per run.

Usage:
    python scripts/run_experiment.py configs/experiments/gate.yaml
    python scripts/run_experiment.py configs/experiments/gate.yaml --seeds 2 --n-steps 500   # smoke test
"""

from __future__ import annotations

import argparse
import platform
import subprocess
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from swarmhazard.config import config_hash, load_config
from swarmhazard.seeding import make_rng
from swarmhazard.sim import run

ROOT = Path(__file__).resolve().parents[1]


def git_commit() -> str:
    try:
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                             capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                               capture_output=True, text=True, check=True).stdout.strip()
        return sha + ("-dirty" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def run_one(job: dict) -> dict:
    cfg = load_config(ROOT / job["base"], **job["overrides"], controller=job["controller"])
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
    return row


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("experiment", type=Path)
    parser.add_argument("--seeds", type=int, help="override the number of seeds (smoke tests)")
    parser.add_argument("--n-steps", type=int, help="override episode length (smoke tests)")
    parser.add_argument("--workers", type=int, default=None, help="parallel processes (default: all cores)")
    args = parser.parse_args()

    spec = yaml.safe_load(args.experiment.read_text())
    overrides = dict(spec.get("overrides") or {})
    smoke = args.seeds is not None or args.n_steps is not None
    if args.n_steps is not None:
        overrides["n_steps"] = args.n_steps
    n_seeds = args.seeds if args.seeds is not None else spec["seeds"]

    jobs = [
        {"experiment": spec["name"], "base": spec["base"], "overrides": overrides,
         "controller": c, "cell": 0, "seed": s}
        for c in spec["controllers"]
        for s in range(n_seeds)
    ]
    start = time.perf_counter()
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        rows = list(pool.map(run_one, jobs))

    df = pd.DataFrame(rows)
    df["git_commit"] = git_commit()
    df["numpy"] = np.__version__
    df["python"] = platform.python_version()
    out = ROOT / "results" / f"{spec['name']}{'_smoke' if smoke else ''}.csv"
    out.parent.mkdir(exist_ok=True)
    df.to_csv(out, index=False)

    print(f"{len(df)} runs in {time.perf_counter() - start:.1f} s -> {out}")
    print(df.groupby("controller")[["delivered", "robots_lost"]].median())


if __name__ == "__main__":
    main()
```

- [ ] **Step 7: Create `scripts/check_gate.py`**

```python
"""Go/no-go gate (spec section 8).

PASS if C2 beats C0 on items delivered with A12 > 0.64 (a medium effect)
and the oracle C4 delivers at least as much as C2 (median).

Usage: python scripts/check_gate.py results/gate.csv
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from swarmhazard.stats import a12

A12_THRESHOLD = 0.64


def main(path: str) -> int:
    df = pd.read_csv(path)
    print(df.groupby("controller")[["delivered", "robots_lost"]].agg(["median", "mean", "std"]).round(2))
    delivered = {c: g["delivered"].to_numpy() for c, g in df.groupby("controller")}

    effect = a12(delivered["C2"], delivered["C0"])
    oracle_ok = np.median(delivered["C4"]) >= np.median(delivered["C2"])
    print(f"\nA12(C2 vs C0, delivered) = {effect:.3f}  (needs > {A12_THRESHOLD})")
    print(f"median C4 >= median C2: {oracle_ok}")

    passed = effect > A12_THRESHOLD and oracle_ok
    print("GATE:", "PASS" if passed else "FAIL")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
```

- [ ] **Step 8: Smoke-test the runner and gate script**

Run:
```bash
.venv/Scripts/python scripts/run_experiment.py configs/experiments/gate.yaml --seeds 2 --n-steps 500
.venv/Scripts/python scripts/check_gate.py results/gate_smoke.csv
```
Expected: first command prints `6 runs in ... s -> ...results/gate_smoke.csv` and a median table with rows C0, C2, C4. Second prints the summary table, an A12 line and `GATE: PASS` or `GATE: FAIL` (either is fine for a 500-step smoke test; only the script working matters).

- [ ] **Step 9: Commit**

```bash
git add src/swarmhazard/stats.py tests/test_stats.py scripts/run_experiment.py scripts/check_gate.py configs/experiments/gate.yaml
git commit -m "Add A12 effect size, parallel experiment runner and gate check" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Animation

**Files:**
- Create: `scripts/animate.py`

**Interfaces:**
- Consumes: `load_config` (Task 1), `make_rng` (Task 1), `Simulation` (Task 5), `RETURN` (Task 4).

- [ ] **Step 1: Create `scripts/animate.py`**

```python
"""Watch a single run.

Hazards are drawn as dashed red circles for us; the robots cannot see them.
Blue = searching, orange = carrying, black x = wreck, purple shading = repellent.

Usage:
    python scripts/animate.py --controller C2 --seed 0
    python scripts/animate.py --controller C2 --seed 0 --frames 200 --save results/c2.gif
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import FuncAnimation, PillowWriter
from matplotlib.patches import Circle

from swarmhazard.config import load_config
from swarmhazard.robots import RETURN
from swarmhazard.seeding import make_rng
from swarmhazard.sim import Simulation

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--controller", default="C2")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--steps-per-frame", type=int, default=20)
    parser.add_argument("--frames", type=int, default=500)
    parser.add_argument("--save", type=Path, help="write a GIF instead of opening a window")
    args = parser.parse_args()

    cfg = load_config(ROOT / "configs" / "baseline.yaml", controller=args.controller)
    sim = Simulation(cfg, make_rng("gate", 0, args.seed))
    size = cfg.arena_size

    fig, ax = plt.subplots(figsize=(6, 6))
    field_img = ax.imshow(sim.field.grid.T, origin="lower", extent=(0, size, 0, size),
                          cmap="Purples", vmin=0, vmax=3)
    ax.add_patch(Circle(cfg.nest_center, cfg.nest_radius, fill=False, color="tab:blue"))
    for x, y, r, _ in cfg.patches:
        ax.add_patch(Circle((x, y), r, fill=False, color="tab:green", ls=":"))
    for x, y, r in cfg.hazards:
        ax.add_patch(Circle((x, y), r, fill=False, color="tab:red", ls="--"))
    items = ax.scatter([], [], s=8, c="tab:green")
    robots = ax.scatter([], [], s=25)
    wrecks = ax.scatter([], [], s=40, marker="x", c="black")
    title = ax.set_title("")
    ax.set_xlim(0, size)
    ax.set_ylim(0, size)
    ax.set_aspect("equal")

    def update(_frame):
        for _ in range(args.steps_per_frame):
            if sim.t < cfg.n_steps:
                sim.step()
        sw = sim.swarm
        items.set_offsets(sim.world.item_pos)
        robots.set_offsets(sw.pos[sw.alive])
        robots.set_color(np.where(sw.state[sw.alive] == RETURN, "tab:orange", "tab:blue"))
        wrecks.set_offsets(sw.pos[~sw.alive] if (~sw.alive).any() else np.empty((0, 2)))
        field_img.set_data(sim.field.grid.T)
        r = sim.result()
        title.set_text(f"{cfg.controller}  t={sim.t * cfg.dt:.0f} s  "
                       f"delivered={r['delivered']}  lost={r['robots_lost']}")
        return field_img, items, robots, wrecks, title

    anim = FuncAnimation(fig, update, frames=args.frames, interval=30, blit=False)
    if args.save:
        args.save.parent.mkdir(parents=True, exist_ok=True)
        anim.save(args.save, writer=PillowWriter(fps=20))
        print(f"saved {args.save}")
    else:
        plt.show()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Render a GIF for each controller and inspect them**

Run:
```bash
.venv/Scripts/python scripts/animate.py --controller C0 --seed 0 --frames 200 --save results/c0.gif
.venv/Scripts/python scripts/animate.py --controller C2 --seed 0 --frames 200 --save results/c2.gif
.venv/Scripts/python scripts/animate.py --controller C4 --seed 0 --frames 200 --save results/c4.gif
```
Expected: three `saved results/cX.gif` lines. Open each GIF (or read individual frames) and check: robots leave the nest, carry items back, wrecks appear only inside the red circle for C0/C2, purple repellent appears around wrecks only for C2, and C4 shows no wrecks. Note any robot stuck oscillating at a hazard edge; report it rather than changing the model.

- [ ] **Step 3: Commit**

```bash
git add scripts/animate.py
git commit -m "Add single-run animation script" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Run the gate and write the learning note

**Files:**
- Create: `docs/learning/01-minimal-version.md`

- [ ] **Step 1: Time one full-length run**

Run:
```bash
.venv/Scripts/python -c "import time; from swarmhazard.config import Config; from swarmhazard.seeding import make_rng; from swarmhazard.sim import run; t=time.perf_counter(); print(run(Config(controller='C2'), make_rng('timing',0,0))); print(f'{time.perf_counter()-t:.1f} s')"
```
Expected: a result dict and a time. Record the time. If it exceeds 30 s per run, stop and report: the full study (~10k runs) would need optimisation before later plans.

- [ ] **Step 2: Run the gate experiment**

Run:
```bash
.venv/Scripts/python scripts/run_experiment.py configs/experiments/gate.yaml
.venv/Scripts/python scripts/check_gate.py results/gate.csv
```
Expected: `90 runs in ... s -> ...results/gate.csv`, then the summary and `GATE: PASS` or `GATE: FAIL`. Copy the full output of `check_gate.py` into the learning note. Do not change any parameter to make the gate pass; a FAIL is a result to report.

- [ ] **Step 3: Write `docs/learning/01-minimal-version.md`**

Use this text, replacing the bracketed result lines with the real output from Steps 1–2:

````markdown
# 01 — The minimal version

## What we built

A simulator for 20 robots in a 10 m × 10 m arena. Robots wander (a "correlated
random walk": they keep roughly their heading, with a small random turn each
step), grab any item they see within 0.5 m, carry it straight back to the nest
in the middle, and repeat. One hidden circle next to an item patch kills a robot
with 2% probability for every 0.1 s it spends inside. A dead robot stays where
it died as a "wreck" that others can see.

## The three controllers

- **C0 Ignore:** wrecks change nothing. This is a swarm that just tolerates losses.
- **C2 Mark:** the first time a robot sees a wreck, it drops a blob of virtual
  repellent on it. The repellent slowly fades (half-life about 2 minutes). Robots
  feel the slope of the repellent around them and turn away from where it is
  stronger. This is our idea: failures become information.
- **C4 Oracle:** knows exactly where the hazard is and never goes in. No real
  swarm can do this; it shows the best possible result, so we can say how much
  of that best case C2 achieves.

## Where to look in the code

| Question | File |
|---|---|
| What are all the numbers? | `configs/baseline.yaml` |
| What happens in one time step? | `src/swarmhazard/sim.py` (`Simulation.step`) |
| How do controllers differ? | `src/swarmhazard/controllers.py` (`avoidance`) |
| How does repellent spread and fade? | `src/swarmhazard/pheromone.py` |
| How do we know it's correct? | `tests/` — run `.venv/Scripts/python -m pytest` |

## Why it's reproducible

Every random number comes from one generator, seeded from
(experiment name, configuration number, seed number). Running the same command
again gives the same numbers, bit for bit. Each CSV row also records the git
commit and the exact configuration (as a hash), so any figure can be traced to
the code that made it.

## The go/no-go gate

We ran 30 seeds of each controller. The gate passes if C2 beats C0 on items
delivered with A12 > 0.64, and the oracle does at least as well as C2.
A12 is the chance that a random C2 run delivers more than a random C0 run:
0.5 means no difference, 0.64 is a "medium" effect.

One full run takes [TIME FROM STEP 1] s.

Result:

```
[FULL OUTPUT OF check_gate.py]
```

## What this means

[Two or three sentences: PASS → the effect exists at baseline and we move on to
C1, C3 and tuning. FAIL → say which condition failed and what the animations
suggest is happening; the next step is to discuss model changes before building more.]

## Questions to think about

1. Why do we give every controller the same seeds?
2. C2's wrecks pile up at the edge of the hazard. Would just steering around
   visible wrecks (C1, next week) already get most of the benefit? Why does that
   matter for the paper?
3. What would go wrong if the repellent never faded?
````

- [ ] **Step 4: Run the full test suite one last time**

Run: `.venv/Scripts/python -m pytest`
Expected: 35 passed

- [ ] **Step 5: Commit**

```bash
git add docs/learning/01-minimal-version.md
git commit -m "Record week-1 gate result and learning note" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
