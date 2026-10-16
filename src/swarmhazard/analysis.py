"""The pre-registered analysis (docs/hypotheses.md), as functions over result tables.

Controllers in a cell share random streams seed by seed, so every comparison is
paired by seed: Wilcoxon signed-rank tests (Pratt zero handling) and a bootstrap
that resamples seeds, keeping each seed's values for all controllers together.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from scipy.stats import friedmanchisquare, wilcoxon

from swarmhazard.stats import a12

N_BOOT = 10_000
BOOT_SEED = 20261016
CONTROLLERS = ["C0", "C1", "C2", "C3", "C4"]
E2_NONE_CELL = 3
H3_BOUND = 0.36


def paired(df: pd.DataFrame, metric: str, a: str, b: str, cell: int = 0):
    """Values of `metric` for controllers a and b in one cell, aligned by seed."""
    sub = df[df["cell"] == cell]
    wide = sub.pivot(index="seed", columns="controller", values=metric)[[a, b]].dropna().sort_index()
    return wide[a].to_numpy(float), wide[b].to_numpy(float)


def wilcoxon_p(x, y, alternative: str) -> float:
    x, y = np.asarray(x, float), np.asarray(y, float)
    if np.all(x == y):
        return 1.0
    return float(wilcoxon(x, y, zero_method="pratt", alternative=alternative, method="auto").pvalue)


def holm(pvals) -> np.ndarray:
    p = np.asarray(pvals, float)
    m = len(p)
    adjusted = np.empty(m)
    running = 0.0
    for rank, i in enumerate(np.argsort(p)):
        running = max(running, (m - rank) * p[i])
        adjusted[i] = min(1.0, running)
    return adjusted


def _ci(samples) -> tuple[float, float]:
    lo, hi = np.percentile(samples, [2.5, 97.5])
    return float(lo), float(hi)


def _a12_boot(x, y, idx, chunk: int = 250) -> np.ndarray:
    out = np.empty(len(idx))
    for s in range(0, len(idx), chunk):
        xs = x[idx[s:s + chunk]][:, :, None]
        ys = y[idx[s:s + chunk]][:, None, :]
        out[s:s + chunk] = (xs > ys).mean(axis=(1, 2)) + 0.5 * (xs == ys).mean(axis=(1, 2))
    return out


def compare(x, y, rng: np.random.Generator, n_boot: int = N_BOOT) -> dict:
    """x vs y, paired by seed: medians, median paired difference, A12, seed-bootstrap CIs."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    idx = rng.integers(0, len(x), size=(n_boot, len(x)))
    d = x - y
    diff_lo, diff_hi = _ci(np.median(d[idx], axis=1))
    a_lo, a_hi = _ci(_a12_boot(x, y, idx))
    return {
        "n": int(len(x)),
        "median_x": float(np.median(x)),
        "median_y": float(np.median(y)),
        "median_diff": float(np.median(d)),
        "median_diff_lo": diff_lo,
        "median_diff_hi": diff_hi,
        "a12": a12(x, y),
        "a12_lo": a_lo,
        "a12_hi": a_hi,
    }


def confirmatory(e1: pd.DataFrame, e2: pd.DataFrame | None, rng: np.random.Generator,
                 n_boot: int = N_BOOT) -> pd.DataFrame:
    rows = []
    for hypothesis, metric, a, b in (("H1", "delivered", "C2", "C0"),
                                     ("H2", "robots_lost", "C1", "C2"),
                                     ("H4", "delivered", "C3", "C2")):
        x, y = paired(e1, metric, a, b)
        row = compare(x, y, rng, n_boot)
        row.update(hypothesis=hypothesis, metric=metric, x=a, y=b, p=wilcoxon_p(x, y, "greater"))
        rows.append(row)
    for row, p in zip(rows, holm([r["p"] for r in rows])):
        row["p_holm"] = float(p)
        row["supported"] = bool(p < 0.05)
    if e2 is not None:
        x, y = paired(e2, "delivered", "C2", "C0", cell=E2_NONE_CELL)
        row = compare(x, y, rng, n_boot)
        row.update(hypothesis="H3", metric="delivered", x="C2", y="C0", p=float("nan"),
                   p_holm=float("nan"), supported=bool(row["a12_lo"] > H3_BOUND))
        rows.append(row)
    return pd.DataFrame(rows)


def _friedman(wide: pd.DataFrame) -> float:
    if wide.shape[1] < 3:
        return float("nan")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        p = friedmanchisquare(*[wide[c].to_numpy(float) for c in wide.columns]).pvalue
    return float(p)


def exploratory(df: pd.DataFrame, rng: np.random.Generator, n_boot: int = N_BOOT,
                metrics=("delivered", "robots_lost")) -> pd.DataFrame:
    """Per cell and metric: Friedman across controllers, then two-sided Wilcoxon vs C2;
    Holm across every pairwise test in the experiment."""
    rows = []
    for cell, sub in df.groupby("cell"):
        present = [c for c in CONTROLLERS if c in set(sub["controller"])]
        if "C2" not in present:
            continue
        for metric in metrics:
            wide = sub.pivot(index="seed", columns="controller", values=metric)[present].dropna().sort_index()
            friedman_p = _friedman(wide)
            for c in present:
                if c == "C2":
                    continue
                x, y = wide[c].to_numpy(float), wide["C2"].to_numpy(float)
                row = compare(x, y, rng, n_boot)
                row.update(cell=int(cell), metric=metric, x=c, y="C2",
                           p=wilcoxon_p(x, y, "two-sided"), friedman_p=friedman_p)
                rows.append(row)
    out = pd.DataFrame(rows)
    if len(out):
        out["p_holm"] = holm(out["p"].to_numpy())
    return out


def descriptive(df: pd.DataFrame, rng: np.random.Generator, n_boot: int = N_BOOT) -> pd.DataFrame:
    """Per cell and controller: medians with seed-bootstrap CIs and secondary metrics."""
    rows = []
    for (cell, controller), sub in df.groupby(["cell", "controller"]):
        delivered = sub["delivered"].to_numpy(float)
        lost = sub["robots_lost"].to_numpy(float)
        idx = rng.integers(0, len(sub), size=(n_boot, len(sub)))
        d_lo, d_hi = _ci(np.median(delivered[idx], axis=1))
        l_lo, l_hi = _ci(np.median(lost[idx], axis=1))
        total_lost = lost.sum()
        rows.append({
            "cell": int(cell), "controller": controller, "n": int(len(sub)),
            "delivered_median": float(np.median(delivered)), "delivered_lo": d_lo, "delivered_hi": d_hi,
            "lost_median": float(np.median(lost)), "lost_lo": l_lo, "lost_hi": l_hi,
            "items_per_robot_lost": float(delivered.sum() / total_lost) if total_lost > 0 else float("nan"),
            "auc_final_median": float(sub["auc_final"].median()) if "auc_final" in sub else float("nan"),
            "hazard_area": float(sub["hazard_area"].iloc[0]) if "hazard_area" in sub else float("nan"),
        })
    return pd.DataFrame(rows)
