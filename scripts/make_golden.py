"""Write tests/data/golden.json: the exact output of short runs.

Run ONCE, on the code as it is before any speed change, and commit the file.
tests/test_golden.py then checks that later changes leave these runs bit-identical.

Each record is the result dict plus a SHA-256 digest of the full final state
(positions, headings, states, alive flags, item positions, repellent grid and
the seen matrix), so small trajectory changes are caught, not only counters.

Usage: python scripts/make_golden.py          (first run: writes the whole file)
       python scripts/make_golden.py --add    (re-verifies every existing case bit
                                               for bit, aborts writing nothing on any
                                               difference, then adds only missing cases)
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
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
    "C5": {"controller": "C5", "lethality": 0.2, "n_steps": 3000, "metric_every": 500},
    "C2_noisy": {"controller": "C2", "lethality": 0.2, "n_steps": 3000, "metric_every": 500,
                 "q_miss": 0.2, "q_false": 0.0001},
    "C2_noisy_deadly": {"controller": "C2", "lethality": 1.0, "hazards": ((9.0, 5.0, 1.0),),
                        "n_steps": 6000, "metric_every": 500, "q_miss": 0.5, "q_false": 0.0001},
    "C6": {"controller": "C6", "lethality": 0.2, "n_steps": 3000, "metric_every": 500},
    "C6_deadly": {"controller": "C6", "lethality": 1.0, "hazards": ((9.0, 5.0, 1.0),),
                  "n_steps": 4000, "metric_every": 500, "q_false": 0.0001},
    "C2_corrmiss_deadly": {"controller": "C2", "lethality": 1.0, "hazards": ((9.0, 5.0, 1.0),),
                           "n_steps": 4000, "metric_every": 500, "q_miss": 0.8, "miss_run": 100.0},
    "C2_move": {"controller": "C2", "lethality": 0.2, "n_steps": 4000, "metric_every": 500, "decay": 0.002,
                "hazard_move_step": 2000, "hazards_after": ((1.19, 3.81, 1.0),)},
    "C4_move": {"controller": "C4", "lethality": 0.2, "n_steps": 3000,
                "hazard_move_step": 500, "hazards_after": ((5.0, 5.0, 1.0),)},
    # Week-6: site fidelity (search_start = last_pickup)
    "C0_fidelity": {"controller": "C0", "lethality": 0.2, "n_steps": 3000,
                    "search_start": "last_pickup"},
    "C2_fidelity": {"controller": "C2", "lethality": 0.2, "n_steps": 3000, "metric_every": 500,
                    "search_start": "last_pickup"},
    "C4_fidelity": {"controller": "C4", "lethality": 0.2, "n_steps": 3000,
                    "search_start": "last_pickup"},
    # Journal-package: C7 and arena_scale
    "C7": {"controller": "C7", "lethality": 0.2, "n_steps": 3000,
           "alert_limit": 2.0, "alert_duration": 1000, "alert_decay": 0.001, "alert_radius": 1.0},
    "C7_fidelity": {"controller": "C7", "lethality": 0.2, "n_steps": 3000,
                    "alert_limit": 2.0, "alert_duration": 1000, "alert_decay": 0.001, "alert_radius": 1.0,
                    "search_start": "last_pickup"},
    # arena_scale=2: all spatial fields doubled; using C0 to keep it fast
    "C0_scale2": {"controller": "C0", "lethality": 0.2, "n_steps": 1000,
                  "arena_size": 20.0, "n_robots": 80,
                  "nest_center": (10.0, 10.0),
                  "patches": ((5.0, 5.0, 0.75, 10), (15.0, 5.0, 0.75, 10),
                               (5.0, 15.0, 0.75, 10), (15.0, 15.0, 0.75, 10)),
                  "hazards": ((17.62, 12.38, 1.0),)},
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


def _same(a, b) -> bool:
    if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
        return True
    return a == b


def main() -> int:
    add = "--add" in sys.argv[1:]
    existing = json.loads(OUT.read_text()) if OUT.exists() else {}
    if existing and not add:
        print("golden.json exists; use --add to add new cases (existing ones are never rewritten)")
        return 1
    for name, expected in existing.items():
        record = golden_record(Config(**GOLDEN_CASES[name]), make_rng("golden", 0, 0))
        diffs = [k for k, v in expected.items() if not _same(record[k], v)]
        if diffs:
            print(f"ABORT: existing case {name} changed in {diffs}; nothing written")
            return 1
    for name, kw in GOLDEN_CASES.items():
        if name not in existing:
            existing[name] = golden_record(Config(**kw), make_rng("golden", 0, 0))
            r = existing[name]
            print("added", name, {k: r[k] for k in ("delivered", "robots_lost", "picked_up", "auc_final")})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(existing, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
