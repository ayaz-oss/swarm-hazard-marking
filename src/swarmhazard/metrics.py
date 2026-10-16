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


def field_auc(grid: np.ndarray, mask: np.ndarray) -> float:
    pos = grid[mask]
    neg = grid[~mask]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    ranks = rankdata(np.concatenate((pos, neg)))
    u = ranks[: len(pos)].sum() - len(pos) * (len(pos) + 1) / 2
    return float(u / (len(pos) * len(neg)))
