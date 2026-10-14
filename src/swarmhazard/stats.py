"""Effect sizes used throughout the paper."""

from __future__ import annotations

import numpy as np


def a12(x, y) -> float:
    """Vargha-Delaney A12: chance a random run from x beats a random run from y (ties count half).

    0.5 means no difference. Conventional thresholds: 0.56 small, 0.64 medium, 0.71 large.
    """
    x = np.asarray(x, dtype=float)[:, None]
    y = np.asarray(y, dtype=float)[None, :]
    return float((x > y).mean() + 0.5 * (x == y).mean())
