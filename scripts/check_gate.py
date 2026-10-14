"""Go/no-go gate (spec section 8).

PASS if C2 beats C0 on items delivered with A12 > 0.64 (a medium effect)
and the oracle C4 delivers at least as much as C2 (median).

Usage: python scripts/check_gate.py results/gate.csv
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from swarmhazard.stats import a12

A12_THRESHOLD = 0.64


def main(path: str) -> int:
    df = pd.read_csv(path)
    print(df.groupby("controller")[["delivered", "robots_lost"]].agg(["median", "mean", "std"]).round(2))
    delivered = {c: g["delivered"].to_numpy() for c, g in df.groupby("controller")}

    effect = a12(delivered["C2"], delivered["C0"])
    oracle_ok = np.median(delivered["C4"]) >= np.median(delivered["C2"])
    print(f"\nA12(C2 vs C0, delivered) = {effect:.3f}  (needs > {A12_THRESHOLD})")
    print(f"median C4 >= median C2: {oracle_ok}")

    passed = effect > A12_THRESHOLD and oracle_ok
    print("GATE:", "PASS" if passed else "FAIL")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
