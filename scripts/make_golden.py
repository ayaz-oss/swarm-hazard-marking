"""Write tests/data/golden.json: the exact output of four short runs.

Run ONCE, on the code as it is before any speed change, and commit the file.
tests/test_golden.py then checks that later changes leave these runs bit-identical.

Usage: python scripts/make_golden.py
"""

from __future__ import annotations

import json
from pathlib import Path

from swarmhazard.config import Config
from swarmhazard.seeding import make_rng
from swarmhazard.sim import run

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tests" / "data" / "golden.json"

# Short runs with a deadly hazard so that deaths, marking and avoidance all happen.
GOLDEN_CASES = {
    "C0": {"controller": "C0", "lethality": 0.2, "n_steps": 3000},
    "C2": {"controller": "C2", "lethality": 0.2, "n_steps": 3000, "metric_every": 500},
    "C3": {"controller": "C3", "lethality": 0.2, "n_steps": 3000, "metric_every": 500},
    "C4": {"controller": "C4", "lethality": 0.2, "n_steps": 3000},
}


def main() -> None:
    golden = {name: run(Config(**kw), make_rng("golden", 0, 0)) for name, kw in GOLDEN_CASES.items()}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(golden, indent=2, sort_keys=True))
    print(f"wrote {OUT}")
    for name, r in golden.items():
        print(name, {k: r[k] for k in ("delivered", "robots_lost", "picked_up")})


if __name__ == "__main__":
    main()
