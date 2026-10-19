"""Small geometry helpers shared by the simulator."""

from __future__ import annotations

import numpy as np


def norm(v: np.ndarray) -> np.ndarray:
    """Euclidean length along the last axis.

    Same arithmetic as np.linalg.norm(v, axis=-1) for real arrays
    (sqrt of the summed squares), without its per-call overhead, so results
    are bit-identical (tests/test_golden.py checks this).
    """
    return np.sqrt(np.add.reduce(v * v, axis=-1))
