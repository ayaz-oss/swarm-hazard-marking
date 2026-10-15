"""Reproducible random number streams.

`cell` identifies the environment configuration, NOT the controller, so every
controller sees the same starting layout for a given seed (common random numbers).
"""

from __future__ import annotations

import zlib

import numpy as np


def make_rng(experiment: str, cell: int, seed: int) -> np.random.Generator:
    # crc32 is stable across runs; Python's hash() is randomised per process.
    sequence = np.random.SeedSequence([zlib.crc32(experiment.encode()), cell, seed])
    return np.random.default_rng(sequence)
