"""C6: sighting records shared between neighbours (week-5 addendum section 1).

A record is (position, observer, step), created exactly when C2 would deposit. A robot's
map is the sum of C2's bumps over the records it knows, each decayed by (1 - decay)^age, so
a robot that knows every record has exactly C2's shared field (up to rounding order). Maps
are never stored as grids; a robot's map is read only where the robot samples it.
"""

from __future__ import annotations

import numpy as np

from swarmhazard.geometry import norm
from swarmhazard.pheromone import RepellentField


class SightingRecords:
    def __init__(self, n_robots: int, field: RepellentField, amount: float, sigma: float):
        self.field, self.amount, self.sigma = field, amount, sigma
        self.xy = np.zeros((0, 2))                      # one row per bump position
        self.window = np.zeros((0, 4), dtype=int)       # ix0, ix1, iy0, iy1 of C2's 3-sigma cut-off
        self.rec_pos = np.zeros(0, dtype=int)           # record -> position row
        self.rec_step = np.zeros(0, dtype=int)          # step at which the record was made
        self.know = np.zeros((n_robots, 0), dtype=bool)  # know[i, r]: robot i knows record r
        self._index: dict = {}

    def add(self, key, xy, observer: int, step: int) -> None:
        p = self._index.get(key)
        if p is None:
            sx, sy, _ = self.field.bump(xy, self.amount, self.sigma)
            p = self._index[key] = len(self.xy)
            self.xy = np.vstack((self.xy, np.asarray(xy, dtype=float)[None, :]))
            self.window = np.vstack((self.window, [[sx.start, sx.stop, sy.start, sy.stop]]))
        self.rec_pos = np.append(self.rec_pos, p)
        self.rec_step = np.append(self.rec_step, step)
        column = np.zeros((len(self.know), 1), dtype=bool)
        column[observer] = True
        self.know = np.hstack((self.know, column))

    def _record_weights(self, now: int, decay: float) -> np.ndarray:
        return (1.0 - decay) ** (now - self.rec_step).astype(float)

    def _position_weights(self, know: np.ndarray, now: int, decay: float) -> np.ndarray:
        """(robots, positions): summed decayed amounts of the records each robot knows."""
        onehot = np.zeros((len(self.rec_pos), len(self.xy)))
        onehot[np.arange(len(self.rec_pos)), self.rec_pos] = 1.0
        return (know * self._record_weights(now, decay)[None, :]) @ onehot

    def _bumps_at(self, pts: np.ndarray) -> np.ndarray:
        """(points, positions): C2's unit bump of each position, read in the cell under each point."""
        f = self.field
        idx = np.clip((np.asarray(pts, dtype=float) / f.cell).astype(int), 0, f.n - 1)
        ix, iy = idx[:, 0:1], idx[:, 1:2]
        w = self.window
        inside = (ix >= w[:, 0]) & (ix < w[:, 1]) & (iy >= w[:, 2]) & (iy < w[:, 3])
        dx = f.centres[idx[:, 0]][:, None] - self.xy[None, :, 0]
        dy = f.centres[idx[:, 1]][:, None] - self.xy[None, :, 1]
        return np.where(inside, self.amount * np.exp(-(dx**2 + dy**2) / (2 * self.sigma**2)), 0.0)

    def gradient(self, pts: np.ndarray, h: float, now: int, decay: float) -> np.ndarray:
        """Robot i's central-difference gradient of its own map at pts[i] (same rule as C2)."""
        pts = np.asarray(pts, dtype=float)
        if len(self.rec_pos) == 0:
            return np.zeros_like(pts)
        weights = self._position_weights(self.know, now, decay)

        def value(p):
            return (weights * self._bumps_at(p)).sum(axis=1)

        ex, ey = np.array([h, 0.0]), np.array([0.0, h])
        gx = (value(pts + ex) - value(pts - ex)) / (2 * h)
        gy = (value(pts + ey) - value(pts - ey)) / (2 * h)
        return np.column_stack((gx, gy))

    def share(self, alive: np.ndarray, pos: np.ndarray, comm_range: float) -> None:
        """Synchronous one-hop exchange: each live robot adds what live neighbours knew before."""
        live = np.flatnonzero(alive)
        if len(live) < 2 or self.know.shape[1] == 0:
            return
        close = norm(pos[live][:, None, :] - pos[live][None, :, :]) < comm_range
        close |= np.eye(len(live), dtype=bool)
        self.know[live] = (close.astype(np.int64) @ self.know[live].astype(np.int64)) > 0

    def mean_map(self, alive: np.ndarray, now: int, decay: float) -> np.ndarray:
        """Mean of the live robots' maps (all robots if none live), as a grid."""
        grid = np.zeros((self.field.n, self.field.n))
        if len(self.rec_pos) == 0:
            return grid
        rows = self.know[alive] if alive.any() else self.know
        amounts = self._position_weights(rows, now, decay).mean(axis=0)
        for p in np.flatnonzero(amounts > 0):
            sx, sy, values = self.field.bump(self.xy[p], self.amount * amounts[p], self.sigma)
            grid[sx, sy] += values
        return grid

    def known_frac(self, alive: np.ndarray) -> float:
        if self.know.shape[1] == 0 or not alive.any():
            return float("nan")
        return float(self.know[alive].mean())
