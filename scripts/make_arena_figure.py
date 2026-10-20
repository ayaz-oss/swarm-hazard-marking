"""Fig. 1: arena schematic (nest, item patches, hazard positions used in the experiments).

Reads positions from the baseline Config and the experiment levels in docs/hypotheses.md.
Usage: python scripts/make_arena_figure.py   (writes results/figures/fig1_arena.{png,pdf})
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Rectangle

from swarmhazard.config import Config

ROOT = Path(__file__).resolve().parents[1]
cfg = Config()

fig, ax = plt.subplots(figsize=(4.6, 4.6))
ax.add_patch(Rectangle((0, 0), cfg.arena_size, cfg.arena_size, fill=False, lw=1.5, color="black"))
ax.add_patch(Circle(cfg.nest_center, cfg.nest_radius, color="#4c72b0", alpha=0.85))
ax.text(*cfg.nest_center, "nest", ha="center", va="center", color="white", fontsize=8)
for i, (px, py, pr, _) in enumerate(cfg.patches):
    ax.add_patch(Circle((px, py), pr, color="#55a868", alpha=0.8, label="item patch" if i == 0 else None))

hazards = [
    ((8.81, 6.19), 1.0, "baseline\n(next to patch)", "-"),
    ((6.25, 6.25), 1.0, "E2: between\npatch and nest", "--"),
    ((5.0, 9.0), 1.0, "E2: far", "--"),
    ((1.19, 3.81), 1.0, "E8: after move", ":"),
]
for (x, y), r, label, ls in hazards:
    ax.add_patch(Circle((x, y), r, fill=False, ls=ls, lw=1.4, color="#c44e52"))
    ax.text(x, y, label, ha="center", va="center", fontsize=6.5, color="#c44e52")
ax.set_xlim(-0.2, cfg.arena_size + 0.2)
ax.set_ylim(-0.2, cfg.arena_size + 0.2)
ax.set_aspect("equal")
ax.set_xlabel("x (m)")
ax.set_ylabel("y (m)")
ax.legend(loc="lower right", fontsize=7, frameon=False)
fig.tight_layout()
out = ROOT / "results" / "figures"
out.mkdir(parents=True, exist_ok=True)
for ext in ("png", "pdf"):
    fig.savefig(out / f"fig1_arena.{ext}", dpi=200)
print("wrote", out / "fig1_arena.png")
