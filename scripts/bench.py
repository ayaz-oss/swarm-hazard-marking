"""Time single full-length runs (one process).

Usage: python scripts/bench.py
"""

from __future__ import annotations

import time

from swarmhazard.config import Config
from swarmhazard.seeding import make_rng
from swarmhazard.sim import run

if __name__ == "__main__":
    for controller in ("C0", "C2"):
        start = time.perf_counter()
        run(Config(controller=controller), make_rng("bench", 0, 0))
        print(f"{controller}: {time.perf_counter() - start:.2f} s per 10,000-step run")
