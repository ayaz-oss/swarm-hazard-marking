"""Draw every figure from results/E*.csv into results/figures/.

Usage: python scripts/make_figures.py
"""

from __future__ import annotations

from pathlib import Path

from swarmhazard.figures import make_all

ROOT = Path(__file__).resolve().parents[1]

if __name__ == "__main__":
    for path in make_all(ROOT / "results", ROOT / "results" / "figures"):
        print(path)
