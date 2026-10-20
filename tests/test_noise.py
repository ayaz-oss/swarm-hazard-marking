import numpy as np
import pytest

from swarmhazard.config import Config
from swarmhazard.noise import next_blind
from swarmhazard.seeding import make_rng
from swarmhazard.sim import Simulation


def chain(q, run, steps=20000, pairs=50):
    rng = np.random.default_rng(1)
    blind = None
    trace = np.empty((steps, pairs), dtype=bool)
    for t in range(steps):
        blind = next_blind(blind, rng.random(pairs), q, run)
        trace[t] = blind
    return trace


def mean_spell(trace):
    spells = []
    for col in trace.T:
        edges = np.flatnonzero(np.diff(np.concatenate(([0], col.astype(int), [0]))))
        spells += list(edges[1::2] - edges[::2])
    return np.mean(spells)


@pytest.mark.parametrize("q, run", [(0.5, 100.0), (0.8, 100.0), (0.3, 10.0)])
def test_blind_fraction_and_spell_length(q, run):
    trace = chain(q, run)
    assert trace.mean() == pytest.approx(q, abs=0.03)
    assert mean_spell(trace) == pytest.approx(run, rel=0.1)


def test_first_step_starts_in_stationary_state():
    draws = np.array([0.1, 0.49, 0.51, 0.9])
    assert next_blind(None, draws, 0.5, 100.0).tolist() == [True, True, False, False]


def test_correlated_misses_leave_c0_unchanged():
    base = dict(controller="C0", lethality=0.2, n_steps=500)
    a = Simulation(Config(**base), make_rng("t", 0, 0))
    b = Simulation(Config(**base, q_miss=0.8, miss_run=100.0), make_rng("t", 0, 0))
    for _ in range(500):
        a.step()
        b.step()
    assert np.array_equal(a.swarm.pos, b.swarm.pos)


def test_correlated_misses_hide_wrecks_for_long_spells():
    sim = Simulation(Config(controller="C1", q_miss=0.8, miss_run=100.0), make_rng("t", 0, 0))
    seen = []
    for _ in range(300):
        sim.step()
        seen.append(sim._detected[0, 1])
    # 300 steps of one pair: with spells of ~100 steps there are long constant stretches.
    changes = np.count_nonzero(np.diff(np.array(seen, dtype=int)))
    assert changes < 30
