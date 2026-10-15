"""The parameter-selection rule, fixed in docs/hypotheses.md before tuning ran.

Highest median items delivered; ties broken by the lowest mean robots lost.
"""

from __future__ import annotations

import pandas as pd


def select_best(df: pd.DataFrame, params: list[str], controller: str) -> dict[str, float]:
    cols = [f"p_{p}" for p in params]
    summary = (df[df["controller"] == controller]
               .groupby(cols)
               .agg(delivered=("delivered", "median"), lost=("robots_lost", "mean"))
               .reset_index()
               .sort_values(["delivered", "lost"], ascending=[False, True]))
    best = summary.iloc[0]
    return {p: float(best[f"p_{p}"]) for p in params}
