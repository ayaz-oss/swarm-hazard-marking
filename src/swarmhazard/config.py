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

KNOWN_CONTROLLERS = ("C0", "C1", "C2", "C3", "C4", "C5", "C6")


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
    # Hazard move (E8): at the start of step hazard_move_step the hazards become hazards_after
    hazard_move_step: int = -1  # -1 = never
    hazards_after: tuple[tuple[float, float, float], ...] = ()
    random_fail_rate: float = 0.0  # per robot per step, anywhere (E2 random-failure control)
    # Detection noise (E7): miss probability per robot-wreck-step; false sighting per robot-step
    q_miss: float = 0.0
    q_false: float = 0.0
    miss_run: float = 0.0  # E7b: mean blind-spell length in steps for correlated misses; 0 = independent

    # Controller and its weights
    controller: str = "C0"
    wreck_weight: float = 1.0
    repel_weight: float = 1.0
    risk_k: float = 1.0
    share_every: int = 10     # C5/C6: steps between exchanges (1 s)
    comm_range: float = 1.0   # C5/C6: m, robots this close exchange

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
            for hx, hy, hr in self.hazards + self.hazards_after:
                if math.hypot(px - hx, py - hy) < pr + hr:
                    raise ValueError(f"Patch at ({px}, {py}) overlaps hazard at ({hx}, {hy})")
        if self.hazard_move_step < -1:
            raise ValueError(f"hazard_move_step must be >= -1, got {self.hazard_move_step}")
        if self.hazards_after and self.hazard_move_step < 0:
            raise ValueError("hazards_after needs hazard_move_step >= 0")
        for name in ("random_fail_rate", "q_miss", "q_false"):
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in [0, 1], got {value}")
        if self.miss_run < 0:
            raise ValueError(f"miss_run must be >= 0, got {self.miss_run}")
        if self.miss_run > 0:
            if self.miss_run < 1 or self.q_miss >= 1:
                raise ValueError("correlated misses need miss_run >= 1 and q_miss < 1")
            # Tolerance: 0.8 / (4 * 0.2) evaluates to 1 + 2e-16 in floating point.
            if self.q_miss / (self.miss_run * (1 - self.q_miss)) > 1 + 1e-12:
                raise ValueError(f"miss_run must be >= q_miss / (1 - q_miss), got {self.miss_run}")
        if self.share_every < 1:
            raise ValueError(f"share_every must be >= 1, got {self.share_every}")
        if self.comm_range < 0:
            raise ValueError(f"comm_range must be >= 0, got {self.comm_range}")
        if self.risk_k < 0:
            raise ValueError(f"risk_k must be >= 0, got {self.risk_k}")
        if self.metric_every < 1:
            raise ValueError(f"metric_every must be >= 1, got {self.metric_every}")


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
