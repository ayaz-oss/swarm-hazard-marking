"""Watch a single run.

Hazards are drawn as dashed red circles for us; the robots cannot see them.
Blue = searching, orange = carrying, black x = wreck, purple shading = repellent.

Usage:
    python scripts/animate.py --controller C2 --seed 0
    python scripts/animate.py --controller C2 --seed 0 --frames 200 --save results/c2.gif
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import FuncAnimation, PillowWriter
from matplotlib.patches import Circle

from swarmhazard.config import load_config
from swarmhazard.robots import RETURN
from swarmhazard.seeding import make_rng
from swarmhazard.sim import Simulation

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--controller", default="C2")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--steps-per-frame", type=int, default=20)
    parser.add_argument("--frames", type=int, default=500)
    parser.add_argument("--save", type=Path, help="write a GIF instead of opening a window")
    args = parser.parse_args()

    cfg = load_config(ROOT / "configs" / "baseline.yaml", controller=args.controller)
    sim = Simulation(cfg, make_rng("gate", 0, args.seed))
    size = cfg.arena_size

    fig, ax = plt.subplots(figsize=(6, 6))
    field_img = ax.imshow(sim.field.grid.T, origin="lower", extent=(0, size, 0, size),
                          cmap="Purples", vmin=0, vmax=3)
    ax.add_patch(Circle(cfg.nest_center, cfg.nest_radius, fill=False, color="tab:blue"))
    for x, y, r, _ in cfg.patches:
        ax.add_patch(Circle((x, y), r, fill=False, color="tab:green", ls=":"))
    for x, y, r in cfg.hazards:
        ax.add_patch(Circle((x, y), r, fill=False, color="tab:red", ls="--"))
    items = ax.scatter([], [], s=8, c="tab:green")
    robots = ax.scatter([], [], s=25)
    wrecks = ax.scatter([], [], s=40, marker="x", c="black")
    title = ax.set_title("")
    ax.set_xlim(0, size)
    ax.set_ylim(0, size)
    ax.set_aspect("equal")

    def update(_frame):
        for _ in range(args.steps_per_frame):
            if sim.t < cfg.n_steps:
                sim.step()
        sw = sim.swarm
        items.set_offsets(sim.world.item_pos)
        robots.set_offsets(sw.pos[sw.alive])
        robots.set_color(np.where(sw.state[sw.alive] == RETURN, "tab:orange", "tab:blue"))
        wrecks.set_offsets(sw.pos[~sw.alive] if (~sw.alive).any() else np.empty((0, 2)))
        field_img.set_data(sim.field.grid.T)
        r = sim.result()
        title.set_text(f"{cfg.controller}  t={sim.t * cfg.dt:.0f} s  "
                       f"delivered={r['delivered']}  lost={r['robots_lost']}")
        return field_img, items, robots, wrecks, title

    anim = FuncAnimation(fig, update, frames=args.frames, interval=30, blit=False)
    if args.save:
        args.save.parent.mkdir(parents=True, exist_ok=True)
        anim.save(args.save, writer=PillowWriter(fps=20))
        print(f"saved {args.save}")
    else:
        plt.show()


if __name__ == "__main__":
    main()
