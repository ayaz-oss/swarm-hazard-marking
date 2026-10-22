"""How well the swarm's repellent map picks out the true hazard (spec section 4).

ROC AUC = probability that a randomly chosen hazard cell carries more
repellent than a randomly chosen safe cell (ties count half). 0.5 means the
map carries no information; 1.0 means it separates hazard from safe perfectly.
"""

from __future__ import annotations

import numpy as np
from scipy.stats import rankdata

from swarmhazard.pheromone import RepellentField
from swarmhazard.world import World, in_hazard


def hazard_mask(world: World, field: RepellentField) -> np.ndarray:
    gx, gy = np.meshgrid(field.centres, field.centres, indexing="ij")
    pts = np.column_stack((gx.ravel(), gy.ravel()))
    return in_hazard(world, pts).reshape(field.n, field.n)


def per_hazard_masks(world: World, field: RepellentField) -> list[np.ndarray]:
    """One mask per hazard (individual circles, not the union)."""
    from swarmhazard.world import World as _World
    gx, gy = np.meshgrid(field.centres, field.centres, indexing="ij")
    pts = np.column_stack((gx.ravel(), gy.ravel()))
    masks = []
    for i in range(len(world.hazard_r)):
        w_single = _World(
            world.item_pos, world.item_patch,
            world.patch_xy, world.patch_r,
            world.hazard_xy[i:i+1], world.hazard_r[i:i+1],
        )
        masks.append(in_hazard(w_single, pts).reshape(field.n, field.n))
    return masks


def repellent_in_hazard_share(grid: np.ndarray, mask: np.ndarray, is_marking: bool) -> float:
    """Share of the repellent field's total mass that lies inside the true hazard mask.

    NaN when the controller does not mark (is_marking is False), or when the field
    is empty (total mass is zero). Does not change behaviour or random streams.
    """
    if not is_marking:
        return float("nan")
    total = float(grid.sum())
    if total == 0.0:
        return float("nan")
    return float(grid[mask].sum() / total)


def field_auc(grid: np.ndarray, mask: np.ndarray) -> float:
    pos = grid[mask]
    neg = grid[~mask]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    ranks = rankdata(np.concatenate((pos, neg)))
    u = ranks[: len(pos)].sum() - len(pos) * (len(pos) + 1) / 2
    return float(u / (len(pos) * len(neg)))
