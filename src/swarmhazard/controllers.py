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
