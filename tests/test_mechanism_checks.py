import math
import sys
from pathlib import Path

import numpy as np
import pytest

from swarmhazard.config import Config
from swarmhazard.seeding import make_rng
from swarmhazard.sim import run

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from mechanism_checks import (auc_curve, first_auc_step, median_step,  # noqa: E402
                              predicted_death_fraction, trace_run, visits_from_trace)


def test_visits_split_on_exit_and_end_on_death():
    inside = np.array([[0, 1], [1, 1], [1, 0], [0, 1], [1, 1], [1, 0]], dtype=bool)
    died = np.zeros_like(inside)
    died[4, 1] = True
    assert visits_from_trace(inside, died) == [(0, 1, 2, False), (0, 4, 2, False),
                                                (1, 0, 2, False), (1, 3, 2, True)]


def test_visit_open_at_end_of_trace_counts_as_survived():
    inside = np.array([[0], [1], [1]], dtype=bool)
    assert visits_from_trace(inside, np.zeros_like(inside)) == [(0, 1, 2, False)]


def test_predicted_death_fraction():
    assert predicted_death_fraction([1, 1], 0.5) == pytest.approx(0.5)
    assert predicted_death_fraction([100], 1.0) == 1.0
    assert predicted_death_fraction([10], 0.0) == 0.0


def test_first_auc_step_reports_the_sample_step():
    assert first_auc_step([0.5, 0.5, 0.71], every=10) == 30
    assert first_auc_step([0.5, 0.5], every=10) == -1


def test_median_step_treats_never_as_later_than_any_step():
    assert median_step([10, 20, 30]) == 20
    assert median_step([10, -1, -1]) == -1  # most runs never got there
    assert median_step([10, 30, -1]) == 30


def test_auc_curve_columns():
    curve = auc_curve([[0.5, 0.8], [0.5, 0.5], [0.6, 0.9]], first_marks=[5, 15, 3],
                      first_losses=[4, -1, 2], every=10)
    assert list(curve["step"]) == [10, 20]
    assert list(curve["median_auc"]) == [0.5, 0.8]
    assert list(curve["frac_marked"]) == pytest.approx([2 / 3, 1.0])
    assert list(curve["frac_lost"]) == pytest.approx([2 / 3, 2 / 3])


def test_trace_run_only_observes():
    cfg = Config(controller="C2", lethality=0.2, n_steps=1500, metric_every=10)
    result, inside, died, first_mark, auc = trace_run(cfg, make_rng("t", 0, 3))
    assert result == run(cfg, make_rng("t", 0, 3))
    assert inside.shape == died.shape == (1500, cfg.n_robots)
    assert (inside | ~died).all()  # with no background failures, every death happens inside
    assert died.sum() == result["robots_lost"]
    if result["first_loss_step"] >= 0:
        assert died[result["first_loss_step"]].any() and not died[:result["first_loss_step"]].any()
    assert first_mark == -1 or first_mark >= result["first_loss_step"] >= 0
    assert len(auc) == 150 and not math.isnan(auc[0])
