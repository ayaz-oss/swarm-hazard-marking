"""Pick the best tuning cell and merge its parameters into configs/tuned_params.yaml
(or configs/tuned_params_fidelity.yaml for the fidelity tuning experiments).

Rule (docs/hypotheses.md): highest median items delivered; ties -> lowest mean robots lost.

Usage (nest restart):
    python scripts/select_params.py results/tune_c2.csv C2 repel_weight deposit_sigma decay
    python scripts/select_params.py results/tune_c3.csv C3 risk_k

Usage (site fidelity):
    python scripts/select_params.py results/tune_c2f.csv C2 repel_weight deposit_sigma decay
    python scripts/select_params.py results/tune_c3f.csv C3 risk_k
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import yaml

from swarmhazard.tuning import select_best

ROOT = Path(__file__).resolve().parents[1]
OUT_NEST = ROOT / "configs" / "tuned_params.yaml"
OUT_FIDELITY = ROOT / "configs" / "tuned_params_fidelity.yaml"

FIDELITY_EXPERIMENTS = {"tune_c2f", "tune_c3f"}
NEST_EXPERIMENTS = {"tune_c2", "tune_c3"}


def main(csv: str, controller: str, *params: str) -> None:
    df = pd.read_csv(csv)
    experiments = set(df["experiment"])
    is_fidelity = bool(experiments & FIDELITY_EXPERIMENTS)
    is_nest = bool(experiments & NEST_EXPERIMENTS)
    if is_fidelity and is_nest:
        sys.exit(f"Refusing: {sorted(experiments)} mixes fidelity and nest tuning experiments.")
    if not (is_fidelity or is_nest):
        sys.exit(f"Refusing: {sorted(experiments)} is not a recognised tuning experiment "
                 f"({sorted(NEST_EXPERIMENTS | FIDELITY_EXPERIMENTS)}).")
    if not experiments <= (FIDELITY_EXPERIMENTS if is_fidelity else NEST_EXPERIMENTS):
        sys.exit(f"Refusing: {sorted(experiments)} contains unrecognised experiments.")

    OUT = OUT_FIDELITY if is_fidelity else OUT_NEST
    cols = [f"p_{p}" for p in params]
    table = (df[df["controller"] == controller].groupby(cols)
             .agg(delivered=("delivered", "median"), lost=("robots_lost", "mean"), runs=("seed", "size"))
             .sort_values(["delivered", "lost"], ascending=[False, True]))
    print(table.head(10).to_string())

    best = select_best(df, list(params), controller)
    if is_fidelity:
        # For fidelity, always rewrite the whole file (so it is self-contained and has search_start).
        # The file always contains search_start: last_pickup regardless of which parameters were just
        # selected, so tune_c3f's run (which only selects risk_k) preserves all C2 values.
        current = yaml.safe_load(OUT.read_text()) if OUT.exists() else {}
        current = current or {}
        # Strip comment-only header values (yaml.safe_load returns plain dict)
        current.update(best)
        current["search_start"] = "last_pickup"
        header = (f"# Tuned parameters for site-fidelity experiments (week-7 spec). "
                  f"Written by scripts/select_params.py.\n"
                  f"# Last update: {controller} from {Path(csv).name}, code {df['git_commit'].iloc[0]}.\n"
                  f"# Rule: highest median items delivered; ties -> lowest mean robots lost.\n"
                  f"# Contains search_start: last_pickup for all fidelity experiments.\n")
        OUT.write_text(header + yaml.safe_dump(current, sort_keys=True))
    else:
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
