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

KNOWN_CONTROLLERS = ("C0", "C1", "C2", "C3", "C4", "C5")


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
    random_fail_rate: float = 0.0  # per robot per step, anywhere (E2 random-failure control)
    # Detection noise (E7): miss probability per robot-wreck-step; false sighting per robot-step
    q_miss: float = 0.0
    q_false: float = 0.0

    # Controller and its weights
    controller: str = "C0"
    wreck_weight: float = 1.0
    repel_weight: float = 1.0
    risk_k: float = 1.0
    share_every: int = 10     # C5: steps between map exchanges (1 s)
    comm_range: float = 1.0   # C5: m, robots this close exchange maps

    # Repellent field
    grid_cell: float = 0.1
    deposit_amount: float = 1.0
    deposit_sigma: float = 0.3
    decay: float = 0.0005

    # Metrics
    metric_every: int = 500

    def __post_init__(self):
        if self.controller not in KNOWN_CONTROLLERS:
            raise ValueError(f"Unknown controller {self.controller!r}; expected one of {KNOWN_CONTROLLERS}")
        # Items inside a hazard would make the oracle's task ill-defined.
        for px, py, pr, _ in self.patches:
            for hx, hy, hr in self.hazards:
                if math.hypot(px - hx, py - hy) < pr + hr:
                    raise ValueError(f"Patch at ({px}, {py}) overlaps hazard at ({hx}, {hy})")
        for name in ("random_fail_rate", "q_miss", "q_false"):
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in [0, 1], got {value}")
        if self.share_every < 1:
            raise ValueError(f"share_every must be >= 1, got {self.share_every}")
        if self.comm_range < 0:
            raise ValueError(f"comm_range must be >= 0, got {self.comm_range}")


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
