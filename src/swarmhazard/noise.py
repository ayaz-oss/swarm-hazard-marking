"""Correlated detection misses (week-5 addendum section 2).

Each (robot, wreck) pair is a two-state chain: blind or seeing. Blind spells last `run`
steps on average and the pair is blind a fraction q of the time. One uniform draw per pair
per step, the same number of draws as independent misses.
"""

from __future__ import annotations

import numpy as np


def next_blind(blind: np.ndarray | None, draws: np.ndarray, q: float, run: float) -> np.ndarray:
    if blind is None:  # first step: start in the stationary distribution
        return draws < q
    stay = 1.0 - 1.0 / run
    enter = q / (run * (1.0 - q))
    return np.where(blind, draws < stay, draws < enter)
