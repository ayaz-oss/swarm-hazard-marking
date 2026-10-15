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
