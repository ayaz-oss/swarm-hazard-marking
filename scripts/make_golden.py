"""Write tests/data/golden.json: the exact output of short runs.

Run ONCE, on the code as it is before any speed change, and commit the file.
tests/test_golden.py then checks that later changes leave these runs bit-identical.

Each record is the result dict plus a SHA-256 digest of the full final state
(positions, headings, states, alive flags, item positions, repellent grid and
the seen matrix), so small trajectory changes are caught, not only counters.

Usage: python scripts/make_golden.py
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from swarmhazard.config import Config
from swarmhazard.seeding import make_rng
from swarmhazard.sim import Simulation

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tests" / "data" / "golden.json"

# Short runs with a deadly hazard so that deaths, marking and avoidance all happen.
GOLDEN_CASES = {
    "C0": {"controller": "C0", "lethality": 0.2, "n_steps": 3000},
    "C1": {"controller": "C1", "lethality": 0.2, "n_steps": 3000},
    "C2": {"controller": "C2", "lethality": 0.2, "n_steps": 3000, "metric_every": 500},
    "C2_deadly": {
        "controller": "C2",
        "lethality": 1.0,
        "n_steps": 4000,
        "metric_every": 500,
        "hazards": ((9.0, 5.0, 1.0),),
    },
    "C3": {"controller": "C3", "lethality": 0.2, "n_steps": 6000, "metric_every": 500, "risk_k": 4.0},
    "C4": {"controller": "C4", "lethality": 0.2, "n_steps": 3000},
}


def state_digest(sim: Simulation) -> str:
    h = hashlib.sha256()
    arrays = (
        sim.swarm.pos,
        sim.swarm.heading,
        sim.swarm.state,
        sim.swarm.alive,
        sim.world.item_pos,
        sim.field.grid,
        sim.seen,
    )
    for a in arrays:
        h.update(np.ascontiguousarray(a).tobytes())
    return h.hexdigest()


def golden_record(cfg: Config, rng: np.random.Generator) -> dict:
    sim = Simulation(cfg, rng)
    for _ in range(cfg.n_steps):
        sim.step()
    record = sim.result()
    record["state_digest"] = state_digest(sim)
    return record


def main() -> None:
    golden = {name: golden_record(Config(**kw), make_rng("golden", 0, 0)) for name, kw in GOLDEN_CASES.items()}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(golden, indent=2, sort_keys=True))
    print(f"wrote {OUT}")
    for name, r in golden.items():
        print(name, {k: r[k] for k in ("delivered", "robots_lost", "picked_up", "state_digest")})


if __name__ == "__main__":
    main()
