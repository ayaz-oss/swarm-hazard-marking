"""How each controller reacts to failures.

All controllers share the same search / return behaviour (see sim.py). They
differ only here:
  C0  Ignore         - no reaction.
  C1  Avoid wrecks   - push away from visible wrecks only; no memory, no marking.
  C2  Mark           - push away from visible wrecks and down the repellent
                       gradient; robots also deposit repellent on wrecks (MARKING).
  C3  Mark + risk    - as C2, but the push is divided by (1 + risk_k * items in
                       view), so robots accept some risk near a rich patch.
  C4  Oracle         - knows the true hazards and never steps inside one; when a
                       move is blocked it slides along the hazard edge. No other
                       avoidance. Upper bound on hazard avoidance, not a swarm method.
"""

from __future__ import annotations

import numpy as np

from swarmhazard.config import Config
from swarmhazard.geometry import norm
from swarmhazard.pheromone import RepellentField
from swarmhazard.world import World, in_hazard

MARKING = frozenset({"C2", "C3"})


def wreck_repulsion(pos: np.ndarray, wreck_pos: np.ndarray, sense_range: float,
                    detected: np.ndarray | None = None) -> np.ndarray:
    """Sum of pushes away from each visible wreck, stronger when closer.

    `detected[i, j]` False means robot i missed wreck j this step (E7 noise).
    """
    if len(wreck_pos) == 0:
        return np.zeros_like(pos)
    diff = pos[:, None, :] - wreck_pos[None, :, :]
    dist = norm(diff)
    visible = (dist < sense_range) & (dist > 1e-9)
    if detected is not None:
        visible &= detected
    weight = np.where(visible, 1.0 - dist / sense_range, 0.0)
    direction = diff / np.maximum(dist, 1e-9)[..., None]
    return (weight[..., None] * direction).sum(axis=1)


def items_in_view(pos: np.ndarray, item_pos: np.ndarray, sense_range: float) -> np.ndarray:
    if len(item_pos) == 0:
        return np.zeros(len(pos), dtype=int)
    dist = norm(pos[:, None, :] - item_pos[None, :, :])
    return (dist < sense_range).sum(axis=1)


def hazard_tangent(world: World, pos: np.ndarray, direction: np.ndarray) -> np.ndarray:
    """Unit vector along the edge of each robot's nearest hazard, on the side closer to `direction`."""
    diff = pos[:, None, :] - world.hazard_xy[None, :, :]
    dist = norm(diff)
    rows = np.arange(len(pos))
    nearest = dist.argmin(axis=1)
    radial = diff[rows, nearest] / np.maximum(dist[rows, nearest], 1e-9)[:, None]
    tangent = np.column_stack((-radial[:, 1], radial[:, 0]))
    side = np.sign((tangent * direction).sum(axis=1))
    side[side == 0] = 1.0
    return tangent * side[:, None]


def avoidance(cfg: Config, pos: np.ndarray, wreck_pos: np.ndarray, field: RepellentField,
              world: World, detected: np.ndarray | None = None,
              maps: np.ndarray | None = None) -> np.ndarray:
    """Vector added to each robot's intended unit heading."""
    if cfg.controller == "C0":
        return np.zeros_like(pos)
    if cfg.controller == "C1":
        return cfg.wreck_weight * wreck_repulsion(pos, wreck_pos, cfg.sense_range, detected)
    if cfg.controller in ("C2", "C3"):
        push = (cfg.wreck_weight * wreck_repulsion(pos, wreck_pos, cfg.sense_range, detected)
                - cfg.repel_weight * field.gradient(pos, cfg.sense_range))
        if cfg.controller == "C3":
            push = push / (1.0 + cfg.risk_k * items_in_view(pos, world.item_pos, cfg.sense_range))[:, None]
        return push
    if cfg.controller == "C4":
        return np.zeros_like(pos)  # the oracle only refuses to enter (see blocks_move)
    raise ValueError(f"No avoidance rule for controller {cfg.controller!r}")


def blocks_move(cfg: Config, world: World, new_pos: np.ndarray) -> np.ndarray:
    """Only the oracle refuses to step into a hazard."""
    if cfg.controller == "C4":
        return in_hazard(world, new_pos)
    return np.zeros(len(new_pos), dtype=bool)
