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

    Always draws one number per robot, so this stream's consumption does not
    depend on where robots are (the simulation gives it its own stream).
    """
    draws = rng.random(len(pos))
    return alive & in_hazard(world, pos) & (draws < lethality)
