"""All paper figures, drawn from result CSVs only.

One colour per controller everywhere (Okabe–Ito, colour-blind safe). Sweeps show the
median with an interquartile band; inference lives in the analysis tables, not here. E5 is
plotted against the in-arena hazard area (pre-registered), with the nominal radius in the tick labels.
"""

from __future__ import annotations

import warnings
from pathlib import Path

with warnings.catch_warnings():
    # matplotlib uses pyparsing camelCase names that newer pyparsing deprecates;
    # a third-party import-time notice, silenced here only while matplotlib loads.
    warnings.simplefilter("ignore", DeprecationWarning)
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

CONTROLLERS = ["C0", "C1", "C2", "C3", "C4", "C5", "C6"]
PALETTE = {"C0": "#999999", "C1": "#E69F00", "C2": "#0072B2", "C3": "#009E73", "C4": "#CC79A7",
           "C5": "#D55E00", "C6": "#56B4E9"}
NAMES = {"C0": "C0 ignore", "C1": "C1 avoid wrecks", "C2": "C2 mark",
         "C3": "C3 mark + risk", "C4": "C4 oracle", "C5": "C5 own maps", "C6": "C6 shared records"}
METRICS = {"delivered": "Items delivered", "robots_lost": "Robots lost"}
POST_METRICS = {"delivered_post": "Items delivered after the move", "lost_post": "Robots lost after the move"}
LEVELS = {
    "E2": ["next to patch", "between patch\nand nest", "far", "no hazard\n(random failures)"],
    "E3": [5, 10, 20, 40, 80],
    "E4": [0.005, 0.02, 0.1, 1.0],
    "E5": [0.5, 1.0, 2.0],
    "E6": [5, 10, 20, 40, 80],
    "E7": ["no noise", "20% missed", "false\nsightings", "both"],
    "E6b": [5, 10, 20, 40, 80],
    "E7b": ["no noise", "50% missed", "80% missed", "50% missed\n(10 s spells)",
            "80% missed\n(10 s spells)", "false sightings\n(x10)"],
    "E8": ["static", "moved,\ntuned decay", "moved,\nfast decay"],
}
XLABEL = {"E3": "Swarm size (robots)", "E4": "Lethality per step inside the hazard",
          "E5": "Hazard area inside the arena (m²)", "E6": "Swarm size (robots)",
          "E6b": "Swarm size (robots)"}
LOGX = {"E3": True, "E4": True, "E5": False, "E6": True, "E6b": True}
METRIC_EVERY_S = 50.0  # metric_every (500 steps) x dt (0.1 s)


def _save(fig, out_dir: Path, stem: str) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = [out_dir / f"{stem}.png", out_dir / f"{stem}.pdf"]
    fig.savefig(paths[0], dpi=200, bbox_inches="tight")
    fig.savefig(paths[1], bbox_inches="tight")
    plt.close(fig)
    return paths


def _boxes(ax, df: pd.DataFrame, metric: str) -> None:
    present = [c for c in CONTROLLERS if c in set(df["controller"])]
    data = [df.loc[df["controller"] == c, metric].to_numpy(float) for c in present]
    bp = ax.boxplot(data, widths=0.6, patch_artist=True, showfliers=False)
    for patch, c in zip(bp["boxes"], present):
        patch.set_facecolor(PALETTE[c])
        patch.set_alpha(0.35)
    for k, (c, values) in enumerate(zip(present, data), start=1):
        jitter = np.linspace(-0.15, 0.15, len(values)) if len(values) > 1 else np.zeros(len(values))
        ax.scatter(k + jitter, values, s=5, color=PALETTE[c], alpha=0.6, linewidths=0)
    ax.set_xticks(range(1, len(present) + 1), present)
    ax.set_ylabel({**METRICS, **POST_METRICS}[metric])


def fig_e1(df: pd.DataFrame, out_dir: Path) -> list[Path]:
    fig, axes = plt.subplots(1, 2, figsize=(8, 3.2))
    for ax, metric in zip(axes, METRICS):
        _boxes(ax, df, metric)
    fig.suptitle("E1: baseline (100 seeds per controller)")
    return _save(fig, out_dir, "e1_baseline")


CELL_TITLES = {"E2": ("E2: hazard placement", "e2_placement"),
               "E7": ("E7: detection noise", "e7_noise"),
               "E7b": ("E7b: strong and correlated detection noise (cells paired by seed)", "e7b_noise"),
               "E8": ("E8: after the hazard moves (step 5000)", "e8_move")}


def fig_cells(df: pd.DataFrame, name: str, out_dir: Path,
              metrics: dict = METRICS) -> list[Path]:
    levels = LEVELS[name]
    fig, axes = plt.subplots(2, len(levels), figsize=(3 * len(levels), 5.6), sharey="row")
    for col, label in enumerate(levels):
        sub = df[df["cell"] == col]
        for row, metric in enumerate(metrics):
            _boxes(axes[row, col], sub, metric)
            if col > 0:
                axes[row, col].set_ylabel("")
        axes[0, col].set_title(label)
    title, stem = CELL_TITLES[name]
    fig.suptitle(title)
    return _save(fig, out_dir, stem)


def fig_sweep(df: pd.DataFrame, name: str, out_dir: Path) -> list[Path]:
    x = np.asarray(LEVELS[name], float)
    xticks = xlabels = None
    if name == "E5":
        # Pre-registered: read E5 against the hazard area inside the arena, not the nominal radius.
        area = df.groupby("cell")["hazard_area"].first().reindex(range(len(x)))
        x = area.to_numpy(float)
        xticks = x
        xlabels = [f"{a:.2f}\n(r {r:g} m)" for a, r in zip(x, LEVELS[name])]
    fig, axes = plt.subplots(1, 2, figsize=(8, 3.2))
    for ax, metric in zip(axes, METRICS):
        for c in CONTROLLERS:
            sub = df[df["controller"] == c]
            if sub.empty:
                continue
            q = sub.groupby("cell")[metric].quantile([0.25, 0.5, 0.75]).unstack()
            q = q.reindex(range(len(x)))
            ax.plot(x, q[0.5], marker="o", color=PALETTE[c], label=NAMES[c])
            ax.fill_between(x, q[0.25], q[0.75], color=PALETTE[c], alpha=0.15, linewidth=0)
        if LOGX[name]:
            ax.set_xscale("log")
        ax.set_xlabel(XLABEL[name])
        if xticks is not None:
            ax.set_xticks(xticks, xlabels, fontsize=8)
        ax.set_ylabel(METRICS[metric])
    axes[1].legend(frameon=False, fontsize=8)
    fig.suptitle(f"{name}: median with interquartile band")
    return _save(fig, out_dir, f"{name.lower()}_sweep")


def fig_auc(df: pd.DataFrame, out_dir: Path) -> list[Path]:
    fig, ax = plt.subplots(figsize=(4.5, 3.2))
    for c in ("C2", "C3"):
        series = [s for s in df.loc[df["controller"] == c, "auc_series"].dropna() if str(s)]
        if not series:
            continue
        values = np.array([[float(v) for v in str(s).split(";")] for s in series])
        t = METRIC_EVERY_S * np.arange(1, values.shape[1] + 1)
        ax.plot(t, np.median(values, axis=0), color=PALETTE[c], label=NAMES[c])
        ax.fill_between(t, np.percentile(values, 25, axis=0), np.percentile(values, 75, axis=0),
                        color=PALETTE[c], alpha=0.15, linewidth=0)
    ax.axhline(0.5, color="#666666", linewidth=0.8, linestyle=":")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Localisation AUC")
    ax.legend(frameon=False, fontsize=8)
    ax.set_title("E1: how well the repellent map outlines the hazard")
    return _save(fig, out_dir, "e1_auc_over_time")


def fig_e8_auc(df: pd.DataFrame, out_dir: Path) -> list[Path]:
    fig, ax = plt.subplots(figsize=(5.5, 3.4))
    styles = {1: ("-", "moved, tuned decay"), 2: ("--", "moved, fast decay")}
    for cell, (linestyle, label) in styles.items():
        mask = (df["controller"] == "C2") & (df["cell"] == cell)
        series = [s for s in df.loc[mask, "auc_series"].dropna() if str(s)]
        if not series:
            continue
        values = np.array([[float(v) for v in str(s).split(";")] for s in series])
        t = METRIC_EVERY_S * np.arange(1, values.shape[1] + 1)
        ax.plot(t, np.median(values, axis=0), color=PALETTE["C2"], linestyle=linestyle, label=f"{NAMES['C2']}, {label}")
        ax.fill_between(t, np.percentile(values, 25, axis=0), np.percentile(values, 75, axis=0),
                        color=PALETTE["C2"], alpha=0.12, linewidth=0)
    ax.axvline(500.0, color="#666666", linewidth=0.9, linestyle="--")
    ax.annotate("hazard moves", (500.0, 1.0), xycoords=("data", "axes fraction"), xytext=(4, -4),
                textcoords="offset points", ha="left", va="top", fontsize=8, color="#444444")
    ax.axhline(0.5, color="#666666", linewidth=0.8, linestyle=":")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Localisation AUC (current hazard)")
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    ax.set_title("E8: the map must relearn the moved hazard")
    return _save(fig, out_dir, "e8_auc_over_time")


def make_all(results_dir: Path, out_dir: Path) -> list[Path]:
    with warnings.catch_warnings():
        # Same third-party pyparsing deprecation notices, raised lazily while drawing text.
        warnings.filterwarnings("ignore", category=DeprecationWarning, module=r"(matplotlib|pyparsing)(\.|$)")
        return _make_all(results_dir, out_dir)


def _make_all(results_dir: Path, out_dir: Path) -> list[Path]:
    written: list[Path] = []
    path = results_dir / "E1.csv"
    if path.exists():
        e1 = pd.read_csv(path)
        written += fig_e1(e1, out_dir)
        written += fig_auc(e1, out_dir)
    for name in ("E2", "E7", "E7b"):
        path = results_dir / f"{name}.csv"
        if path.exists():
            written += fig_cells(pd.read_csv(path), name, out_dir)
    for name in ("E3", "E4", "E5", "E6", "E6b"):
        path = results_dir / f"{name}.csv"
        if path.exists():
            written += fig_sweep(pd.read_csv(path), name, out_dir)
    path = results_dir / "E8.csv"
    if path.exists():
        e8 = pd.read_csv(path)
        written += fig_cells(e8, "E8", out_dir, metrics=POST_METRICS)
        written += fig_e8_auc(e8, out_dir)
    return written
