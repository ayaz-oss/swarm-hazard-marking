"""Figure for the Webots physics replication (W1): items delivered and robots lost per controller,
box plots with every seed as a dot. Usage: python scripts/make_webots_figure.py [W1_CSV]"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
df = pd.read_csv(sys.argv[1] if len(sys.argv) > 1 else ROOT / "results" / "W1.csv")
ctrls = ["C0", "C1", "C2", "C4"]
colours = {"C0": "#999999", "C1": "#E69F00", "C2": "#0072B2", "C4": "#CC79A7"}
fig, axes = plt.subplots(1, 2, figsize=(8, 3.4))
rng = np.random.default_rng(0)
for ax, metric, label in zip(axes, ["delivered", "robots_lost"], ["Items delivered", "Robots lost"]):
    data = [df.loc[df.controller == c, metric].to_numpy() for c in ctrls]
    bp = ax.boxplot(data, tick_labels=ctrls, showfliers=False, patch_artist=True, widths=0.55)
    for patch, c in zip(bp["boxes"], ctrls):
        patch.set_facecolor(colours[c]); patch.set_alpha(0.35)
    for i, (c, v) in enumerate(zip(ctrls, data), start=1):
        ax.scatter(i + rng.uniform(-0.18, 0.18, len(v)), v, s=6, color=colours[c], alpha=0.7, zorder=3)
    ax.set_ylabel(label)
fig.suptitle("W1: Webots physics replication (site fidelity, 100 seeds per controller)", fontsize=10)
fig.tight_layout()
out = ROOT / "results" / "figures"
for ext in ("png", "pdf"):
    fig.savefig(out / f"w1_webots.{ext}", dpi=200)
print("wrote", out / "w1_webots.png")
