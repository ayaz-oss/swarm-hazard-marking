"""Virtual repellent laid on a grid over the arena.

The grid is shared (like projected light in ARK or Phormica), but a robot only
ever reads cells within its sensing range, so the information is still local.
"""

from __future__ import annotations

import numpy as np


class RepellentField:
    def __init__(self, arena_size: float, cell: float):
        self.cell = cell
        self.n = int(round(arena_size / cell))
        self.grid = np.zeros((self.n, self.n))           # grid[ix, iy]
        self.centres = (np.arange(self.n) + 0.5) * cell  # cell-centre coordinate along either axis

    def bump(self, xy, amount: float, sigma: float):
        """The Gaussian bump `deposit` would add: (x slice, y slice, values), or None if off the grid."""
        x, y = float(xy[0]), float(xy[1])
        reach = 3 * sigma
        ix0 = max(int((x - reach) / self.cell), 0)
        ix1 = min(int((x + reach) / self.cell) + 1, self.n)
        iy0 = max(int((y - reach) / self.cell), 0)
        iy1 = min(int((y + reach) / self.cell) + 1, self.n)
        if ix0 >= ix1 or iy0 >= iy1:
            return None
        dx = self.centres[ix0:ix1, None] - x
        dy = self.centres[None, iy0:iy1] - y
        return slice(ix0, ix1), slice(iy0, iy1), amount * np.exp(-(dx**2 + dy**2) / (2 * sigma**2))

    def deposit(self, xy, amount: float, sigma: float) -> None:
        """Add a Gaussian bump with peak `amount`, cut off at 3 sigma."""
        b = self.bump(xy, amount, sigma)
        if b is not None:
            sx, sy, values = b
            self.grid[sx, sy] += values

    def decay(self, rate: float) -> None:
        self.grid *= 1.0 - rate

    def value(self, pts: np.ndarray) -> np.ndarray:
        """Concentration in the cell under each point (points off the arena read the edge cell)."""
        idx = np.clip((np.asarray(pts, dtype=float) / self.cell).astype(int), 0, self.n - 1)
        return self.grid[idx[:, 0], idx[:, 1]]

    def gradient(self, pts: np.ndarray, h: float) -> np.ndarray:
        """Central-difference gradient from samples a distance h either side of each point."""
        pts = np.asarray(pts, dtype=float)
        ex = np.array([h, 0.0])
        ey = np.array([0.0, h])
        gx = (self.value(pts + ex) - self.value(pts - ex)) / (2 * h)
        gy = (self.value(pts + ey) - self.value(pts - ey)) / (2 * h)
        return np.column_stack((gx, gy))


def personal_value(maps: np.ndarray, pts: np.ndarray, cell: float) -> np.ndarray:
    """maps[i] read at pts[i] (cell under each point; off-arena points read the edge cell)."""
    n = maps.shape[1]
    idx = np.clip((np.asarray(pts, dtype=float) / cell).astype(int), 0, n - 1)
    return maps[np.arange(len(idx)), idx[:, 0], idx[:, 1]]


def personal_gradient(maps: np.ndarray, pts: np.ndarray, h: float, cell: float) -> np.ndarray:
    """Each robot's central-difference gradient of its own map (C5)."""
    pts = np.asarray(pts, dtype=float)
    ex = np.array([h, 0.0])
    ey = np.array([0.0, h])
    gx = (personal_value(maps, pts + ex, cell) - personal_value(maps, pts - ex, cell)) / (2 * h)
    gy = (personal_value(maps, pts + ey, cell) - personal_value(maps, pts - ey, cell)) / (2 * h)
    return np.column_stack((gx, gy))
