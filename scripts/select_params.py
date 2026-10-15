"""Pick the best tuning cell and merge its parameters into configs/tuned_params.yaml.

Rule (docs/hypotheses.md): highest median items delivered; ties -> lowest mean robots lost.

Usage:
    python scripts/select_params.py results/tune_c2.csv C2 repel_weight deposit_sigma decay
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import yaml

from swarmhazard.tuning import select_best

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "configs" / "tuned_params.yaml"


def main(csv: str, controller: str, *params: str) -> None:
    df = pd.read_csv(csv)
    cols = [f"p_{p}" for p in params]
    table = (df[df["controller"] == controller].groupby(cols)
             .agg(delivered=("delivered", "median"), lost=("robots_lost", "mean"), runs=("seed", "size"))
             .sort_values(["delivered", "lost"], ascending=[False, True]))
    print(table.head(10).to_string())

    best = select_best(df, list(params), controller)
    current = yaml.safe_load(OUT.read_text()) if OUT.exists() else {}
    current = current or {}
    current.update(best)
    header = (f"# Tuned parameters (spec section 3). Written by scripts/select_params.py.\n"
              f"# Last update: {controller} from {Path(csv).name}, code {df['git_commit'].iloc[0]}.\n"
              f"# Rule: highest median items delivered; ties -> lowest mean robots lost.\n")
    OUT.write_text(header + yaml.safe_dump(current, sort_keys=True))
    print(f"\nchosen: {best} -> {OUT}")


if __name__ == "__main__":
    main(*sys.argv[1:])
