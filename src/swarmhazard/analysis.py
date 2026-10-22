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
CONTROLLERS = ["C0", "C1", "C2", "C3", "C4", "C5", "C6"]
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
    """Holm step-down adjustment; NaN inputs stay NaN and do not count towards m."""
    p = np.asarray(pvals, float)
    adjusted = np.full(len(p), np.nan)
    finite = np.flatnonzero(~np.isnan(p))
    m = len(finite)
    running = 0.0
    for rank, i in enumerate(finite[np.argsort(p[finite])]):
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
            "false_sightings_mean": float(sub["false_sightings"].mean()) if "false_sightings" in sub else float("nan"),
        })
    return pd.DataFrame(rows)


# Week-5 exploratory families (docs/hypotheses.md, "Week-5 experiments"). Holm runs over every
# test of one experiment together.
WEEK5 = {
    "E6b": {"metrics": ("delivered", "robots_lost"), "pairs": [("C6", "C5")], "cross": []},
    "E7b": {"metrics": ("delivered", "robots_lost"), "pairs": [],
            "cross": [(c, k, 0, ("delivered", "robots_lost")) for c in ("C1", "C2", "C3") for k in range(1, 6)]},
    "E8": {"metrics": ("delivered_post", "lost_post"), "pairs": [],
           "cross": [("C2", 2, 1, ("delivered_pre", "lost_pre", "delivered_post", "lost_post")),
                     ("C2", 1, 0, ("delivered_post", "lost_post"))]},
    # Week-7 F counterparts: identical families to their originals.
    "E6bF": {"metrics": ("delivered", "robots_lost"), "pairs": [("C6", "C5")], "cross": []},
    "E7bF": {"metrics": ("delivered", "robots_lost"), "pairs": [],
             "cross": [(c, k, 0, ("delivered", "robots_lost")) for c in ("C1", "C2", "C3") for k in range(1, 6)]},
    "E8F": {"metrics": ("delivered_post", "lost_post"), "pairs": [],
            "cross": [("C2", 2, 1, ("delivered_pre", "lost_pre", "delivered_post", "lost_post")),
                      ("C2", 1, 0, ("delivered_post", "lost_post"))]},
}
# Runs that must be identical across paired cells (reported, not tested).
IDENTITIES = {"E7b": [("C0", (0, 1, 2, 3, 4, 5)), ("C1", (0, 5))],
              "E8": [("C0", (1, 2)), ("C1", (1, 2)), ("C4", (1, 2))],
              # E9: C0, C1, C4 don't react to false sightings, so they're identical across
              # cells that differ only in q_false (cells 0 vs 4, and 1 vs 5).
              "E9": [("C0", (0, 4)), ("C0", (1, 5)), ("C1", (0, 4)), ("C1", (1, 5)),
                     ("C4", (0, 4)), ("C4", (1, 5))],
              # Week-7 F counterparts: same paired-cell identity expectations as their originals.
              "E7bF": [("C0", (0, 1, 2, 3, 4, 5)), ("C1", (0, 5))],
              "E8F": [("C0", (1, 2)), ("C1", (1, 2)), ("C4", (1, 2))]}
# Every behavioural outcome column. false_sightings is deliberately left out: it counts noise
# events (phantoms are counted even by controllers that ignore them, e.g. C0 in E7b cell 5),
# not behaviour.
IDENTITY_COLS = ("delivered", "robots_lost", "first_loss_step", "picked_up", "items_lost", "carrying",
                 "steps", "auc_final", "delivered_pre", "lost_pre", "delivered_post", "lost_post",
                 "first_loss_post_step")


def pairwise(df, pairs, metrics, rng, n_boot=N_BOOT) -> pd.DataFrame:
    """Within each cell, x vs y for each (x, y) controller pair; two-sided, paired by seed."""
    rows = []
    for cell in sorted(df["cell"].unique()):
        for x_name, y_name in pairs:
            for metric in metrics:
                x, y = paired(df, metric, x_name, y_name, cell=cell)
                row = compare(x, y, rng, n_boot)
                row.update(kind="pair", cell=int(cell), metric=metric, x=x_name, y=y_name,
                           p=wilcoxon_p(x, y, "two-sided"), friedman_p=float("nan"))
                rows.append(row)
    return pd.DataFrame(rows)


def cross_cell(df, controller, cell_x, cell_y, metrics, rng, n_boot=N_BOOT) -> pd.DataFrame:
    """One controller in two cells of a paired-cell experiment, aligned by seed; two-sided."""
    sub = df[df["controller"] == controller]
    rows = []
    for metric in metrics:
        wide = sub.pivot(index="seed", columns="cell", values=metric)[[cell_x, cell_y]].dropna().sort_index()
        x, y = wide[cell_x].to_numpy(float), wide[cell_y].to_numpy(float)
        row = compare(x, y, rng, n_boot)
        row.update(kind="cross_cell", cell=int(cell_x), cell_y=int(cell_y), metric=metric,
                   x=f"{controller}@{cell_x}", y=f"{controller}@{cell_y}",
                   p=wilcoxon_p(x, y, "two-sided"), friedman_p=float("nan"))
        rows.append(row)
    return pd.DataFrame(rows)


def week5_tests(name, df, rng, n_boot=N_BOOT) -> pd.DataFrame:
    spec = WEEK5[name]
    parts = [exploratory(df, rng, n_boot, metrics=spec["metrics"]).assign(kind="vs_C2")]
    if spec["pairs"]:
        parts.append(pairwise(df, spec["pairs"], spec["metrics"], rng, n_boot))
    for controller, cx, cy, metrics in spec["cross"]:
        parts.append(cross_cell(df, controller, cx, cy, metrics, rng, n_boot))
    out = pd.concat(parts, ignore_index=True)
    out["p_holm"] = holm(out["p"].to_numpy())
    return out


def _marked(series) -> bool:
    return any(float(v) != 0.5 for v in str(series).split(";") if v not in ("", "nan"))


def week5_descriptive(df, rng, n_boot=N_BOOT) -> pd.DataFrame:
    """descriptive() plus marked-run counts and the week-5 columns that exist in df."""
    base = descriptive(df, rng, n_boot)
    extra_cols = [c for c in ("auc_final", "false_sightings", "delivered_pre", "lost_pre",
                              "delivered_post", "lost_post", "auc_pre", "auc_old_final",
                              "known_frac") if c in df]
    rows = []
    for (cell, controller), sub in df.groupby(["cell", "controller"]):
        row = {"cell": int(cell), "controller": controller}
        row["marked_runs"] = (int(sum(_marked(s) for s in sub["auc_series"].fillna("")))
                              if "auc_series" in sub else 0)
        idx = rng.integers(0, len(sub), size=(n_boot, len(sub)))
        for col in extra_cols:
            values = sub[col].to_numpy(float)
            row[f"{col}_n"] = int((~np.isnan(values)).sum())
            if np.isnan(values).all():
                row[f"{col}_median"] = row[f"{col}_lo"] = row[f"{col}_hi"] = float("nan")
                continue
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)  # all-NaN bootstrap resamples
                row[f"{col}_median"] = float(np.nanmedian(values))
                row[f"{col}_lo"], row[f"{col}_hi"] = _ci(np.nanmedian(values[idx], axis=1))
        rows.append(row)
    extra = pd.DataFrame(rows)
    # auc_final_median is replaced by the version with a CI
    base = base.drop(columns=[c for c in base if c in extra and c not in ("cell", "controller")])
    return base.merge(extra, on=["cell", "controller"])


def identity_checks(name, df) -> pd.DataFrame:
    rows = []
    for controller, cells in IDENTITIES.get(name, []):
        sub = df[df["controller"] == controller]
        cols = [c for c in IDENTITY_COLS if c in df]
        ref = sub[sub["cell"] == cells[0]].set_index("seed").sort_index()[cols]
        same = all(sub[sub["cell"] == k].set_index("seed").sort_index()[cols].equals(ref)
                   for k in cells[1:])
        rows.append({"experiment": name, "controller": controller,
                     "cells": " ".join(map(str, cells)), "identical": bool(same)})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Week-6 analysis (E9, docs/hypotheses.md "Week-6 experiment")
# ---------------------------------------------------------------------------

E9_CONTROLLERS = ["C0", "C1", "C2", "C3", "C4"]
E9_METRICS = ("delivered", "robots_lost")
E9_DESCRIPTIVE_COLS = ["auc_final", "false_sightings", "trip_steps_mean", "search_steps_mean",
                        "nest_steps"]


def _get_seed_series(df, controller, cell, metric):
    """Return per-seed values for one controller × cell, sorted by seed."""
    sub = df[(df["controller"] == controller) & (df["cell"] == cell)]
    return sub.sort_values("seed")[metric].to_numpy(float)


def week6_tests(df: pd.DataFrame, rng: np.random.Generator, n_boot: int = N_BOOT) -> pd.DataFrame:
    """82 pre-registered E9 tests; ONE Holm pass over all 82."""
    rows = []

    # 1. Within each cell: Friedman across C0-C4, then C0/C1/C3/C4 each vs C2 (48 tests)
    comparators = ["C0", "C1", "C3", "C4"]
    for cell in range(6):
        sub = df[df["cell"] == cell]
        for metric in E9_METRICS:
            present = [c for c in E9_CONTROLLERS if c in set(sub["controller"])]
            wide = sub.pivot(index="seed", columns="controller", values=metric)[present].dropna().sort_index()
            friedman_p = _friedman(wide)
            for c in comparators:
                if c not in wide.columns:
                    continue
                x, y = wide[c].to_numpy(float), wide["C2"].to_numpy(float)
                row = compare(x, y, rng, n_boot)
                row.update(kind="vs_C2", cell=int(cell), metric=metric, x=c, y="C2",
                           cell_y=int(cell), p=wilcoxon_p(x, y, "two-sided"),
                           friedman_p=friedman_p)
                rows.append(row)

    # 2. Fidelity vs nest per controller: cell 1 vs 0, 3 vs 2, 5 vs 4 (30 tests)
    fidelity_pairs = [(1, 0), (3, 2), (5, 4)]
    for cell_x, cell_y in fidelity_pairs:
        for c in E9_CONTROLLERS:
            for metric in E9_METRICS:
                x = _get_seed_series(df, c, cell_x, metric)
                y = _get_seed_series(df, c, cell_y, metric)
                if len(x) == 0 or len(y) == 0 or len(x) != len(y):
                    continue
                row = compare(x, y, rng, n_boot)
                row.update(kind="fidelity_vs_nest", cell=int(cell_x), cell_y=int(cell_y),
                           metric=metric, x=f"{c}@{cell_x}", y=f"{c}@{cell_y}",
                           p=wilcoxon_p(x, y, "two-sided"), friedman_p=float("nan"))
                rows.append(row)

    # 3. Interaction tests on per-seed differences (4 tests)
    # (a) C2 false-sighting gain: (cell4 - cell0) vs (cell5 - cell1), delivered
    c2_4 = _get_seed_series(df, "C2", 4, "delivered")
    c2_0 = _get_seed_series(df, "C2", 0, "delivered")
    c2_5 = _get_seed_series(df, "C2", 5, "delivered")
    c2_1 = _get_seed_series(df, "C2", 1, "delivered")
    if len(c2_4) == len(c2_0) == len(c2_5) == len(c2_1) > 0:
        x = c2_4 - c2_0  # false-sighting gain with nest
        y = c2_5 - c2_1  # false-sighting gain with fidelity
        row = compare(x, y, rng, n_boot)
        row.update(kind="interaction", cell=4, cell_y=5, metric="delivered",
                   x="C2@4-C2@0", y="C2@5-C2@1",
                   p=wilcoxon_p(x, y, "two-sided"), friedman_p=float("nan"))
        rows.append(row)

    # (b) C2 lead over C0 in random-failure control: (C2-C0 in cell2) vs (C2-C0 in cell3), delivered
    c2_c2 = _get_seed_series(df, "C2", 2, "delivered")
    c0_c2 = _get_seed_series(df, "C0", 2, "delivered")
    c2_c3 = _get_seed_series(df, "C2", 3, "delivered")
    c0_c3 = _get_seed_series(df, "C0", 3, "delivered")
    if len(c2_c2) == len(c0_c2) == len(c2_c3) == len(c0_c3) > 0:
        x = c2_c2 - c0_c2  # C2 lead in cell 2 (nest)
        y = c2_c3 - c0_c3  # C2 lead in cell 3 (fidelity)
        row = compare(x, y, rng, n_boot)
        row.update(kind="interaction", cell=2, cell_y=3, metric="delivered",
                   x="(C2-C0)@2", y="(C2-C0)@3",
                   p=wilcoxon_p(x, y, "two-sided"), friedman_p=float("nan"))
        rows.append(row)

    # (c) C2 lead over C0 at baseline: (C2-C0 in cell0) vs (C2-C0 in cell1), delivered
    c2_b0 = _get_seed_series(df, "C2", 0, "delivered")
    c0_b0 = _get_seed_series(df, "C0", 0, "delivered")
    c2_b1 = _get_seed_series(df, "C2", 1, "delivered")
    c0_b1 = _get_seed_series(df, "C0", 1, "delivered")
    if len(c2_b0) == len(c0_b0) == len(c2_b1) == len(c0_b1) > 0:
        x = c2_b0 - c0_b0  # C2 lead with nest
        y = c2_b1 - c0_b1  # C2 lead with fidelity
        row = compare(x, y, rng, n_boot)
        row.update(kind="interaction", cell=0, cell_y=1, metric="delivered",
                   x="(C2-C0)@0", y="(C2-C0)@1",
                   p=wilcoxon_p(x, y, "two-sided"), friedman_p=float("nan"))
        rows.append(row)

    # (d) C1 excess losses over C2 at baseline: (C1-C2 in cell0) vs (C1-C2 in cell1), robots_lost
    c1_b0 = _get_seed_series(df, "C1", 0, "robots_lost")
    c2_b0_l = _get_seed_series(df, "C2", 0, "robots_lost")
    c1_b1 = _get_seed_series(df, "C1", 1, "robots_lost")
    c2_b1_l = _get_seed_series(df, "C2", 1, "robots_lost")
    if len(c1_b0) == len(c2_b0_l) == len(c1_b1) == len(c2_b1_l) > 0:
        x = c1_b0 - c2_b0_l  # C1 excess losses with nest
        y = c1_b1 - c2_b1_l  # C1 excess losses with fidelity
        row = compare(x, y, rng, n_boot)
        row.update(kind="interaction", cell=0, cell_y=1, metric="robots_lost",
                   x="(C1-C2)@0", y="(C1-C2)@1",
                   p=wilcoxon_p(x, y, "two-sided"), friedman_p=float("nan"))
        rows.append(row)

    out = pd.DataFrame(rows)
    if len(out):
        out["p_holm"] = holm(out["p"].to_numpy())
    return out


def week6_descriptive(df: pd.DataFrame, rng: np.random.Generator, n_boot: int = N_BOOT) -> pd.DataFrame:
    """descriptive() plus marked-run counts and week-6 observation metrics."""
    base = descriptive(df, rng, n_boot)
    extra_cols = [c for c in E9_DESCRIPTIVE_COLS if c in df]
    rows = []
    for (cell, controller), sub in df.groupby(["cell", "controller"]):
        row = {"cell": int(cell), "controller": controller}
        row["marked_runs"] = (int(sum(_marked(s) for s in sub["auc_series"].fillna("")))
                              if "auc_series" in sub else 0)
        idx = rng.integers(0, len(sub), size=(n_boot, len(sub)))
        for col in extra_cols:
            values = sub[col].to_numpy(float)
            row[f"{col}_n"] = int((~np.isnan(values)).sum())
            if np.isnan(values).all():
                row[f"{col}_median"] = row[f"{col}_lo"] = row[f"{col}_hi"] = float("nan")
                continue
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                row[f"{col}_median"] = float(np.nanmedian(values))
                row[f"{col}_lo"], row[f"{col}_hi"] = _ci(np.nanmedian(values[idx], axis=1))
        rows.append(row)
    extra = pd.DataFrame(rows)
    base = base.drop(columns=[c for c in base if c in extra and c not in ("cell", "controller")])
    return base.merge(extra, on=["cell", "controller"])


# ---------------------------------------------------------------------------
# Week-7 analysis (F experiments; docs/hypotheses.md "Week-7 replication under site fidelity")
# ---------------------------------------------------------------------------

# Extra columns added in week-7 (repellent_in_hazard + week-6 trip/nest metrics)
W7_DESCRIPTIVE_COLS = ["repellent_in_hazard", "auc_final", "false_sightings",
                       "delivered_pre", "lost_pre", "delivered_post", "lost_post",
                       "auc_pre", "auc_old_final", "known_frac",
                       "trip_steps_mean", "search_steps_mean", "nest_steps"]
# E2F–E5F: across-cell tests for C2 only (each cell vs cell 0, delivered and robots_lost).
# These cells all have paired_cells=true so cross-cell comparisons are paired by seed.
E2F_CELLS = 4   # cells 0-3
E3F_CELLS = 5   # n_robots levels
E4F_CELLS = 4   # lethality levels
E5F_CELLS = 3   # radius levels


def _cross_cell_c2(df: pd.DataFrame, n_cells: int, rng: np.random.Generator,
                   n_boot: int = N_BOOT) -> list[pd.DataFrame]:
    """For C2, each cell vs cell 0 on delivered and robots_lost (paired by seed)."""
    parts = []
    for cell in range(1, n_cells):
        parts.append(cross_cell(df, "C2", cell, 0, ("delivered", "robots_lost"), rng, n_boot))
    return parts


def week7_e2e5_tests(name: str, df: pd.DataFrame, rng: np.random.Generator,
                     n_boot: int = N_BOOT) -> pd.DataFrame:
    """Exploratory within-cell tests (Friedman + vs C2) PLUS across-cell C2 tests in one Holm family.

    Used for E2F, E3F, E4F, E5F, which all have paired_cells=True.
    """
    n_cells = {"E2F": E2F_CELLS, "E3F": E3F_CELLS, "E4F": E4F_CELLS, "E5F": E5F_CELLS}[name]
    parts = [exploratory(df, rng, n_boot).assign(kind="vs_C2")]
    parts.extend(_cross_cell_c2(df, n_cells, rng, n_boot))
    out = pd.concat(parts, ignore_index=True)
    out["p_holm"] = holm(out["p"].to_numpy())
    return out


def week7_descriptive(df: pd.DataFrame, rng: np.random.Generator, n_boot: int = N_BOOT) -> pd.DataFrame:
    """week5_descriptive extended with week-7 columns (repellent_in_hazard, AUC over marked runs).

    Also reports auc_final_marked_median and auc_final_marked_n: AUC restricted to runs
    that have any mark (auc_series contains a value != 0.5).
    """
    base = descriptive(df, rng, n_boot)
    extra_cols = [c for c in W7_DESCRIPTIVE_COLS if c in df]
    rows = []
    for (cell, controller), sub in df.groupby(["cell", "controller"]):
        row = {"cell": int(cell), "controller": controller}
        # marked_runs: runs where auc_series has at least one value != 0.5
        row["marked_runs"] = (int(sum(_marked(s) for s in sub["auc_series"].fillna("")))
                              if "auc_series" in sub else 0)
        # AUC over marked runs only
        if "auc_final" in sub and "auc_series" in sub:
            marked_mask = np.array([_marked(s) for s in sub["auc_series"].fillna("")])
            auc_marked = sub["auc_final"].to_numpy(float)[marked_mask]
            row["auc_final_marked_n"] = int(len(auc_marked))
            if len(auc_marked) > 0:
                idx_m = rng.integers(0, len(auc_marked), size=(n_boot, len(auc_marked)))
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", RuntimeWarning)
                    row["auc_final_marked_median"] = float(np.nanmedian(auc_marked))
                    row["auc_final_marked_lo"], row["auc_final_marked_hi"] = _ci(
                        np.nanmedian(auc_marked[idx_m], axis=1))
            else:
                row["auc_final_marked_median"] = row["auc_final_marked_lo"] = row["auc_final_marked_hi"] = float("nan")
        idx = rng.integers(0, len(sub), size=(n_boot, len(sub)))
        for col in extra_cols:
            values = sub[col].to_numpy(float)
            row[f"{col}_n"] = int((~np.isnan(values)).sum())
            if np.isnan(values).all():
                row[f"{col}_median"] = row[f"{col}_lo"] = row[f"{col}_hi"] = float("nan")
                continue
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                row[f"{col}_median"] = float(np.nanmedian(values))
                row[f"{col}_lo"], row[f"{col}_hi"] = _ci(np.nanmedian(values[idx], axis=1))
        rows.append(row)
    extra = pd.DataFrame(rows)
    base = base.drop(columns=[c for c in base if c in extra and c not in ("cell", "controller")])
    return base.merge(extra, on=["cell", "controller"])


# ---------------------------------------------------------------------------
# Journal-package analysis (E10, E11, E12; docs/hypotheses.md last section)
# Pre-registered 2026-10-22.
# ---------------------------------------------------------------------------

# Extra columns for journal descriptive tables
J_DESCRIPTIVE_COLS = ["alerts_sent", "known_frac",
                      "auc_final", "auc_final_h0", "auc_final_h1",
                      "repellent_in_hazard"]

# Pre-registered Holm family sizes (docs/hypotheses.md):
# E10: 3 cells x 3 non-C2 x 2 metrics  +  2 cross-cell C2 x 2 metrics  +  3 C7-vs-C1  = 25
# E11: 5 cells x 2 non-C2 x 2 metrics  +  4 cross-cell C2 x 2 metrics  +  5x2 C6-vs-C5 = 38
# E12: 3 cells x 4 non-C2 x 2 metrics  +  2 cross-cell C2 x 2 metrics               = 28
J_FAMILY_SIZES = {"E10": 25, "E10b": 25, "E11": 38, "E12": 28}

_J_METRICS = ("delivered", "robots_lost")
_J_CONTROLLERS_ORDERED = CONTROLLERS + ["C7"]


def journal_tests(name: str, df: pd.DataFrame, rng: np.random.Generator,
                  n_boot: int = N_BOOT) -> pd.DataFrame:
    """One Holm family per journal experiment (pre-registered 2026-10-22).

    All experiments:
      1. Within each cell: each non-C2 controller vs C2 on delivered and robots_lost.
         Friedman p per cell reported alongside (NOT counted in the Holm family).
      2. C2 cross-cell: each cell (1+) vs cell 0 on delivered and robots_lost.
    E10: also C7 vs C1 on robots_lost in every cell.
    E11: also C6 vs C5 on delivered and robots_lost in every cell.
    Single Holm pass over ALL rows at the end.
    """
    rows = []
    cells = sorted(df["cell"].unique())
    ctrl_present = set(df["controller"].unique())

    # 1. Within-cell: each non-C2 vs C2
    for cell in cells:
        sub = df[df["cell"] == cell]
        for metric in _J_METRICS:
            # Friedman once per (cell, metric)
            present_ctrl = [c for c in _J_CONTROLLERS_ORDERED if c in ctrl_present]
            try:
                wide = (sub.pivot(index="seed", columns="controller", values=metric)
                        .reindex(columns=[c for c in present_ctrl if c in sub["controller"].unique()])
                        .dropna().sort_index())
            except Exception:
                wide = pd.DataFrame()
            friedman_p = _friedman(wide) if len(wide.columns) >= 2 else float("nan")
            for c in _J_CONTROLLERS_ORDERED:
                if c == "C2" or c not in ctrl_present:
                    continue
                try:
                    x, y = paired(df, metric, c, "C2", cell=cell)
                except (KeyError, ValueError):
                    continue
                row = compare(x, y, rng, n_boot)
                row.update(kind="vs_C2", cell=int(cell), metric=metric, x=c, y="C2",
                           p=wilcoxon_p(x, y, "two-sided"), friedman_p=friedman_p)
                rows.append(row)

    # 2. C2 cross-cell: each cell >= 1 vs cell 0
    sub_c2 = df[df["controller"] == "C2"]
    if not sub_c2.empty:
        for cell in [c for c in cells if c != 0]:
            for metric in _J_METRICS:
                try:
                    wide = (sub_c2.pivot(index="seed", columns="cell", values=metric)
                            [[0, cell]].dropna().sort_index())
                except (KeyError, ValueError):
                    continue
                x, y = wide[cell].to_numpy(float), wide[0].to_numpy(float)
                row = compare(x, y, rng, n_boot)
                row.update(kind="cross_cell", cell=int(cell), cell_y=0, metric=metric,
                           x=f"C2@{cell}", y="C2@0",
                           p=wilcoxon_p(x, y, "two-sided"), friedman_p=float("nan"))
                rows.append(row)

    # 3. E10 extra: C7 vs C1 on robots_lost in every cell
    if name in ("E10", "E10b") and "C7" in ctrl_present and "C1" in ctrl_present:
        for cell in cells:
            try:
                x, y = paired(df, "robots_lost", "C7", "C1", cell=cell)
            except (KeyError, ValueError):
                continue
            row = compare(x, y, rng, n_boot)
            row.update(kind="C7_vs_C1", cell=int(cell), metric="robots_lost",
                       x="C7", y="C1",
                       p=wilcoxon_p(x, y, "two-sided"), friedman_p=float("nan"))
            rows.append(row)

    # 4. E11 extra: C6 vs C5 on delivered and robots_lost in every cell
    if name == "E11" and "C6" in ctrl_present and "C5" in ctrl_present:
        for cell in cells:
            for metric in _J_METRICS:
                try:
                    x, y = paired(df, metric, "C6", "C5", cell=cell)
                except (KeyError, ValueError):
                    continue
                row = compare(x, y, rng, n_boot)
                row.update(kind="C6_vs_C5", cell=int(cell), metric=metric,
                           x="C6", y="C5",
                           p=wilcoxon_p(x, y, "two-sided"), friedman_p=float("nan"))
                rows.append(row)

    out = pd.DataFrame(rows)
    if len(out):
        out["p_holm"] = holm(out["p"].to_numpy())
    return out


def journal_descriptive(name: str, df: pd.DataFrame, rng: np.random.Generator,
                        n_boot: int = N_BOOT) -> pd.DataFrame:
    """Extends week7_descriptive with per-hazard AUC columns (E12) if present."""
    base = week7_descriptive(df, rng, n_boot)
    # Per-hazard AUC columns: auc_final_h0, auc_final_h1 (already in J_DESCRIPTIVE_COLS above)
    # week7_descriptive handles: repellent_in_hazard, known_frac, alerts_sent, auc_final, auc_series
    # Add any per-hazard AUC columns not already present
    hazard_cols = [c for c in df.columns if c.startswith("auc_final_h") and c not in base.columns]
    if not hazard_cols:
        return base
    rows = []
    for (cell, controller), sub in df.groupby(["cell", "controller"]):
        row = {"cell": int(cell), "controller": controller}
        idx = rng.integers(0, len(sub), size=(n_boot, len(sub)))
        import warnings as _w
        for col in hazard_cols:
            values = sub[col].to_numpy(float)
            row[f"{col}_n"] = int((~np.isnan(values)).sum())
            if np.isnan(values).all():
                row[f"{col}_median"] = row[f"{col}_lo"] = row[f"{col}_hi"] = float("nan")
                continue
            with _w.catch_warnings():
                _w.simplefilter("ignore", RuntimeWarning)
                row[f"{col}_median"] = float(np.nanmedian(values))
                row[f"{col}_lo"], row[f"{col}_hi"] = _ci(np.nanmedian(values[idx], axis=1))
        rows.append(row)
    extra = pd.DataFrame(rows)
    base = base.drop(columns=[c for c in base.columns if c in extra.columns
                               and c not in ("cell", "controller")])
    return base.merge(extra, on=["cell", "controller"])
