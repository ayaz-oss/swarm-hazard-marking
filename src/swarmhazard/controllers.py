"""How each controller reacts to failures.

All controllers share the same search / return behaviour (see sim.py). They
differ only here:
  C0  Ignore         - no reaction.
  C2  Mark           - push away from visible wrecks and down the repellent
                       gradient; robots also deposit repellent on wrecks (MARKING).
  C4  Oracle         - knows the true hazards and never steps inside one; when a
                       move is blocked it slides along the hazard edge. No other
                       avoidance. Upper bound on hazard avoidance, not a swarm method.
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


def hazard_tangent(world: World, pos: np.ndarray, direction: np.ndarray) -> np.ndarray:
    """Unit vector along the edge of each robot's nearest hazard, on the side closer to `direction`."""
    diff = pos[:, None, :] - world.hazard_xy[None, :, :]
    dist = np.linalg.norm(diff, axis=2)
    rows = np.arange(len(pos))
    nearest = dist.argmin(axis=1)
    radial = diff[rows, nearest] / np.maximum(dist[rows, nearest], 1e-9)[:, None]
    tangent = np.column_stack((-radial[:, 1], radial[:, 0]))
    side = np.sign((tangent * direction).sum(axis=1))
    side[side == 0] = 1.0
    return tangent * side[:, None]


def avoidance(cfg: Config, pos: np.ndarray, wreck_pos: np.ndarray, field: RepellentField,
              world: World) -> np.ndarray:
    """Vector added to each robot's intended unit heading."""
    if cfg.controller == "C0":
        return np.zeros_like(pos)
    if cfg.controller == "C2":
        return (cfg.wreck_weight * wreck_repulsion(pos, wreck_pos, cfg.sense_range)
                - cfg.repel_weight * field.gradient(pos, cfg.sense_range))
    if cfg.controller == "C4":
        return np.zeros_like(pos)  # the oracle only refuses to enter (see blocks_move)
    raise ValueError(f"No avoidance rule for controller {cfg.controller!r}")


def blocks_move(cfg: Config, world: World, new_pos: np.ndarray) -> np.ndarray:
    """Only the oracle refuses to step into a hazard."""
    if cfg.controller == "C4":
        return in_hazard(world, new_pos)
    return np.zeros(len(new_pos), dtype=bool)
