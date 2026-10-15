import numpy as np
import pytest

from swarmhazard.config import Config
from swarmhazard.robots import RETURN, SEARCH
from swarmhazard.seeding import make_rng
from swarmhazard.sim import Simulation, run


def new_sim(**kw):
    return Simulation(Config(**kw), make_rng("test", 0, 0))


def test_same_seed_same_result():
    cfg = Config(controller="C2", lethality=0.2, n_steps=3000)
    assert run(cfg, make_rng("t", 0, 1)) == run(cfg, make_rng("t", 0, 1))


def test_robots_stay_in_arena():
    sim = new_sim(n_steps=2000)
    for _ in range(2000):
        sim.step()
    assert np.all((sim.swarm.pos >= 0) & (sim.swarm.pos <= sim.cfg.arena_size))


def test_pickup_switches_to_return_and_respawns_item():
    sim = new_sim()
    sim.swarm.pos[0] = sim.world.item_pos[0]
    before = sim.world.item_pos[0].copy()
    sim.step()
    assert sim.swarm.state[0] == RETURN
    assert not np.array_equal(before, sim.world.item_pos[0])


def test_delivery_counts_and_resumes_search():
    sim = new_sim()
    sim.swarm.state[0] = RETURN
    sim.swarm.pos[0] = sim.nest
    sim.step()
    assert sim.delivered == 1
    assert sim.swarm.state[0] == SEARCH


def test_robot_dies_in_lethal_hazard():
    sim = new_sim(lethality=1.0)
    sim.swarm.pos[0] = [8.81, 6.19]
    sim.step()
    assert not sim.swarm.alive[0]
    assert sim.first_loss_step == 0
    assert sim.result()["robots_lost"] == 1


def place_wreck_next_to_robot_0(sim):
    sim.swarm.alive[1] = False
    sim.swarm.pos[1] = [3.0, 3.0]
    sim.swarm.pos[0] = [3.2, 3.0]


def test_c2_marks_wreck_and_c0_does_not():
    c2 = new_sim(controller="C2")
    place_wreck_next_to_robot_0(c2)
    c2.step()
    assert c2.field.grid.max() > 0
    assert c2.seen[0, 1]

    c0 = new_sim(controller="C0")
    place_wreck_next_to_robot_0(c0)
    c0.step()
    assert c0.field.grid.max() == 0


def test_each_robot_marks_a_wreck_only_once():
    sim = new_sim(controller="C2")
    place_wreck_next_to_robot_0(sim)
    sim.step()
    first = sim.field.grid.max()
    sim.step()
    assert sim.field.grid.max() < first  # only decay, no second deposit


def test_oracle_never_loses_robots():
    cfg = Config(controller="C4", lethality=1.0, n_steps=5000)
    assert run(cfg, make_rng("t", 0, 2))["robots_lost"] == 0


def test_dead_robots_are_inert():
    sim = new_sim(controller="C2")
    sim.swarm.alive[0] = False
    sim.swarm.alive[1] = False
    sim.swarm.pos[0] = sim.world.item_pos[0]
    sim.swarm.state[0] = SEARCH
    sim.swarm.pos[1] = sim.nest
    sim.swarm.state[1] = RETURN
    pos_before = sim.swarm.pos[[0, 1]].copy()
    state_before = sim.swarm.state[[0, 1]].copy()
    heading_before = sim.swarm.heading[[0, 1]].copy()
    item_before = sim.world.item_pos[0].copy()
    for _ in range(5):
        sim.step()
    assert np.array_equal(sim.swarm.pos[[0, 1]], pos_before)
    assert np.array_equal(sim.swarm.state[[0, 1]], state_before)
    assert np.array_equal(sim.swarm.heading[[0, 1]], heading_before)
    assert np.array_equal(sim.world.item_pos[0], item_before)
    assert sim.delivered == 0


def test_two_observers_deposit_twice():
    def wreck_sim(observers):
        sim = new_sim(controller="C2")
        sim.swarm.alive[2] = False
        sim.swarm.pos[2] = [3.0, 3.0]
        for robot, xy in observers:
            sim.swarm.pos[robot] = xy
        return sim

    a = wreck_sim([(0, [3.2, 3.0])])
    b = wreck_sim([(0, [3.2, 3.0]), (1, [3.0, 3.2])])
    a.step()
    b.step()
    assert b.field.grid.max() == pytest.approx(2 * a.field.grid.max(), rel=1e-6)
    assert b.seen[0, 2]
    assert b.seen[1, 2]


def test_one_robot_dying_does_not_change_others_randomness():
    # Under C0 robots do not interact for the first 200 steps (no item is
    # reachable yet), so killing robot 0 must leave every other path unchanged.
    a = new_sim()
    b = new_sim()
    b.swarm.alive[0] = False
    for _ in range(200):
        a.step()
        b.step()
    assert np.array_equal(a.swarm.pos[1:], b.swarm.pos[1:])
