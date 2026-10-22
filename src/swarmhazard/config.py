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

KNOWN_CONTROLLERS = ("C0", "C1", "C2", "C3", "C4", "C5", "C6", "C7")


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

    # Site fidelity (E9): "nest" = default (restart search at the nest after delivery);
    # "last_pickup" = head straight back to the last pickup position (OUTBOUND state).
    search_start: str = "nest"

    # Controller and its weights
    controller: str = "C0"
    wreck_weight: float = 1.0
    repel_weight: float = 1.0
    risk_k: float = 1.0
    share_every: int = 10     # C5/C6: steps between exchanges (1 s)
    comm_range: float = 1.0   # C5/C6: m, robots this close exchange

    # C7: risk-limit alerts (section 1)
    alert_limit: float = 2.0       # risk score threshold for broadcasting an alert
    alert_duration: int = 1000     # steps a received alert remains active
    alert_decay: float = 0.001     # per-step multiplicative decay of risk score
    alert_radius: float = 1.0      # radius (m) within which alerts repel

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
        if self.search_start not in ("nest", "last_pickup"):
            raise ValueError(f"search_start must be 'nest' or 'last_pickup', got {self.search_start!r}")
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
        if self.alert_limit < 0:
            raise ValueError(f"alert_limit must be >= 0, got {self.alert_limit}")
        if self.alert_duration < 1:
            raise ValueError(f"alert_duration must be >= 1, got {self.alert_duration}")
        if not 0.0 <= self.alert_decay <= 1.0:
            raise ValueError(f"alert_decay must be in [0, 1], got {self.alert_decay}")
        if self.alert_radius < 0:
            raise ValueError(f"alert_radius must be >= 0, got {self.alert_radius}")
        if self.metric_every < 1:
            raise ValueError(f"metric_every must be >= 1, got {self.metric_every}")


def _freeze(value):
    """YAML gives lists; the frozen Config needs (nested) tuples."""
    if isinstance(value, list):
        return tuple(_freeze(v) for v in value)
    return value


def _apply_scale(data: dict) -> dict:
    """Consume arena_scale from data and scale the relevant spatial fields in-place.

    Scales: arena_size, nest_center, every patch centre (not radius), every hazard
    centre (not radius), and hazards_after centres (not radii).
    With arena_scale=1 the dict is returned unchanged (bit-identical behaviour).
    """
    scale = float(data.pop("arena_scale", 1.0))
    if scale == 1.0:
        return data
    data = dict(data)  # shallow copy so we do not mutate the caller's dict

    if "arena_size" in data:
        data["arena_size"] = float(data["arena_size"]) * scale
    else:
        data["arena_size"] = Config.__dataclass_fields__["arena_size"].default * scale  # type: ignore[attr-defined]

    if "nest_center" in data:
        nc = data["nest_center"]
        data["nest_center"] = [nc[0] * scale, nc[1] * scale]
    else:
        nc = Config.__dataclass_fields__["nest_center"].default  # type: ignore[attr-defined]
        data["nest_center"] = [nc[0] * scale, nc[1] * scale]

    def scale_patches(patches):
        return [[p[0] * scale, p[1] * scale, p[2], p[3]] for p in patches]

    def scale_hazards(hazards):
        return [[h[0] * scale, h[1] * scale, h[2]] for h in hazards]

    if "patches" in data:
        data["patches"] = scale_patches(data["patches"])
    else:
        data["patches"] = scale_patches(
            [list(p) for p in Config.__dataclass_fields__["patches"].default])  # type: ignore[attr-defined]

    if "hazards" in data:
        data["hazards"] = scale_hazards(data["hazards"])
    else:
        data["hazards"] = scale_hazards(
            [list(h) for h in Config.__dataclass_fields__["hazards"].default])  # type: ignore[attr-defined]

    if "hazards_after" in data and data["hazards_after"]:
        data["hazards_after"] = scale_hazards(data["hazards_after"])

    return data


def from_dict(data: dict) -> Config:
    data = dict(data)  # do not mutate caller's dict
    data = _apply_scale(data)
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
