from pathlib import Path

import numpy as np
import pandas as pd

from swarmhazard.experiment import build_cells, load_experiment
from swarmhazard.figures import LEVELS, make_all

ROOT = Path(__file__).resolve().parents[1]


def fake(name, n_cells, seeds=5):
    rng = np.random.default_rng(0)
    rows = []
    for cell in range(n_cells):
        for c in ["C0", "C1", "C2", "C3", "C4", "C5"]:
            for s in range(seeds):
                rows.append({"experiment": name, "cell": cell, "hazard_area": [0.75, 3.18, 8.23][cell % 3], "controller": c, "seed": s,
                             "delivered": rng.integers(30, 50), "robots_lost": rng.integers(0, 6),
                             "auc_series": "0.5000;0.7000;0.8000" if c in ("C2", "C3") else ""})
    return pd.DataFrame(rows)


def test_levels_match_experiment_files():
    for name, levels in LEVELS.items():
        cells = build_cells(load_experiment(ROOT / "configs" / "experiments" / f"{name}.yaml", ROOT))
        assert len(cells) == len(levels)


def test_make_all_writes_figures(tmp_path):
    for name in ["E1", "E2", "E3", "E4", "E5", "E6", "E7"]:
        n_cells = 1 if name == "E1" else len(LEVELS[name])
        fake(name, n_cells).to_csv(tmp_path / f"{name}.csv", index=False)
    written = make_all(tmp_path, tmp_path / "figures")
    assert len(written) >= 5
    assert all(p.exists() and p.stat().st_size > 0 for p in written)
