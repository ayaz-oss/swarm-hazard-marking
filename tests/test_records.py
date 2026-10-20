import numpy as np
import pytest

from swarmhazard.config import Config
from swarmhazard.pheromone import RepellentField
from swarmhazard.records import SightingRecords
from swarmhazard.seeding import make_rng
from swarmhazard.sim import Simulation

DECAY = 0.002


def build(n_robots=3):
    field = RepellentField(10.0, 0.1)
    return field, SightingRecords(n_robots, field, 1.0, 0.3)


def reference_field(events, now):
    """C2's arithmetic: each event deposits at its step, then the field decays once per step."""
    field = RepellentField(10.0, 0.1)
    for t in range(now):
        for xy, step in events:
            if step == t:
                field.deposit(xy, 1.0, 0.3)
        field.decay(DECAY)
    return field


EVENTS = [((3.0, 3.0), 2), ((3.0, 3.0), 5), ((3.4, 3.1), 5), ((0.05, 9.97), 7)]


def add_all(rec, observer=0):
    for k, (xy, step) in enumerate(EVENTS):
        rec.add(("p", xy), np.array(xy), observer, step)


def test_full_knowledge_map_equals_c2_field():
    field, rec = build()
    add_all(rec)
    alive = np.array([True, False, False])  # only robot 0 (who knows everything) counts
    ref = reference_field(EVENTS, 10)
    assert np.allclose(rec.mean_map(alive, 10, DECAY), ref.grid, rtol=1e-12, atol=1e-15)


def test_full_knowledge_gradient_equals_c2_gradient():
    field, rec = build()
    add_all(rec)
    pts = np.array([[3.1, 3.0], [3.3, 2.9], [0.2, 9.8]])
    rec.know[:] = True
    ref = reference_field(EVENTS, 10)
    assert np.allclose(rec.gradient(pts, 0.5, 10, DECAY), ref.gradient(pts, 0.5), rtol=1e-12, atol=1e-15)


def test_unknown_records_do_not_steer():
    field, rec = build()
    add_all(rec, observer=0)
    pts = np.array([[3.1, 3.0]] * 3)
    g = rec.gradient(pts, 0.5, 10, DECAY)
    assert np.any(g[0] != 0) and np.all(g[1:] == 0)


def test_no_records_no_gradient():
    field, rec = build()
    assert np.all(rec.gradient(np.ones((3, 2)), 0.5, 0, DECAY) == 0)
    assert np.isnan(rec.known_frac(np.ones(3, dtype=bool)))


def test_share_is_synchronous_one_hop_and_skips_the_dead():
    field, rec = build(4)
    rec.add(("w", 9), np.array([5.0, 5.0]), 0, 0)
    pos = np.array([[1.0, 1.0], [1.8, 1.0], [2.6, 1.0], [1.0, 1.5]])
    alive = np.array([True, True, True, False])
    rec.share(alive, pos, 1.0)
    assert rec.know[:, 0].tolist() == [True, True, False, False]
    rec.share(alive, pos, 1.0)
    assert rec.know[:, 0].tolist() == [True, True, True, False]
    assert rec.known_frac(alive) == 1.0


def test_c6_with_instant_full_sharing_behaves_like_c2():
    # share every step with everyone: each robot knows every record by the next read, so C6 is C2
    # (the sums differ only in rounding order).
    kw = dict(lethality=1.0, hazards=((9.0, 5.0, 1.0),), n_steps=1500, repel_weight=0.5, decay=0.0002)
    a = Simulation(Config(controller="C2", **kw), make_rng("t", 0, 3))
    b = Simulation(Config(controller="C6", share_every=1, comm_range=100.0, **kw), make_rng("t", 0, 3))
    for _ in range(1500):
        a.step()
        b.step()
    assert np.allclose(a.swarm.pos, b.swarm.pos, atol=1e-6)
    assert a.result()["robots_lost"] == b.result()["robots_lost"] > 0
    assert np.allclose(a.field.grid, b.records.mean_map(b.swarm.alive, b.t, b.cfg.decay), atol=1e-9)
    assert b.result()["known_frac"] == 1.0


def test_c6_without_contact_knows_only_its_own_records():
    sim = Simulation(Config(controller="C6", lethality=1.0, hazards=((9.0, 5.0, 1.0),), comm_range=0.0,
                            n_steps=3000), make_rng("t", 0, 3))
    for _ in range(3000):
        sim.step()
    r = sim.result()
    assert r["robots_lost"] > 0 and 0.0 < r["known_frac"] < 1.0  # (seed 3: seed 0 has no sighting at all)
    assert len(sim.auc_series) == 6
