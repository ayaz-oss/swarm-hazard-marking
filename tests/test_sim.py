import math

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


@pytest.mark.parametrize("controller, marks",
                         [("C0", False), ("C1", False), ("C2", True), ("C3", True), ("C4", False)])
def test_which_controllers_mark_wrecks(controller, marks):
    sim = new_sim(controller=controller)
    place_wreck_next_to_robot_0(sim)
    sim.step()
    assert (sim.field.grid.max() > 0) == marks


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


def test_oracle_returner_gets_round_a_hazard_in_its_way():
    sim = new_sim(controller="C4", lethality=1.0)
    sim.swarm.pos[0] = [9.9, 6.19]   # east of the hazard; the nest is due west
    sim.swarm.state[0] = RETURN
    for _ in range(2000):
        sim.step()
        if sim.swarm.state[0] == SEARCH:
            break
    assert sim.swarm.alive[0]
    assert sim.swarm.state[0] == SEARCH  # it delivered


def test_every_picked_up_item_is_delivered_lost_or_still_carried():
    r = run(Config(controller="C0", lethality=0.2, n_steps=3000), make_rng("t", 0, 4))
    assert r["picked_up"] > 0
    assert r["delivered"] > 0
    assert r["picked_up"] == r["delivered"] + r["items_lost"] + r["carrying"]


def test_robot_that_dies_carrying_an_item_counts_it_as_lost():
    sim = new_sim(lethality=1.0)
    sim.swarm.state[0] = RETURN
    sim.picked_up = 1            # robot 0 is carrying one item
    sim.swarm.pos[0] = [8.81, 6.19]
    sim.step()
    r = sim.result()
    assert not sim.swarm.alive[0]
    assert r["items_lost"] == 1 and r["carrying"] == 0
    assert r["picked_up"] == r["delivered"] + r["items_lost"] + r["carrying"]


def test_auc_recorded_only_for_marking_controllers():
    c0 = run(Config(controller="C0", n_steps=500), make_rng("t", 0, 3))
    assert math.isnan(c0["auc_final"]) and c0["auc_series"] == ""

    sim = new_sim(controller="C2", lethality=0.0, metric_every=1)
    sim.swarm.alive[1] = False
    sim.swarm.pos[1] = [8.81, 6.19]   # a wreck at the hazard centre
    sim.swarm.pos[0] = [9.01, 6.19]   # an observer beside it
    sim.step()
    assert sim.result()["auc_final"] > 0.9


def test_random_failures_occur_at_the_configured_rate():
    sim = Simulation(Config(hazards=(), random_fail_rate=0.01, n_robots=2000), make_rng("t", 0, 0))
    sim.step()
    lost_fraction = 1.0 - sim.swarm.alive.mean()
    assert abs(lost_fraction - 0.01) < 0.0067  # about 3 standard errors


@pytest.mark.parametrize("rate", [-0.1, 1.5])
def test_random_fail_rate_must_be_a_probability(rate):
    with pytest.raises(ValueError):
        Config(random_fail_rate=rate)


def test_hazard_area_is_reported():
    r = run(Config(n_steps=1), make_rng("t", 0, 0))
    assert abs(r["hazard_area"] - math.pi) < 0.05
    assert run(Config(n_steps=1, hazards=()), make_rng("t", 0, 0))["hazard_area"] == 0.0


def test_missed_wrecks_are_not_marked():
    sim = new_sim(controller="C2", q_miss=1.0)
    place_wreck_next_to_robot_0(sim)
    sim.step()
    assert sim.field.grid.max() == 0
    assert not sim.seen[0, 1]


@pytest.mark.parametrize("controller, deposits", [("C1", False), ("C2", True)])
def test_false_sightings_mark_only_for_marking_controllers(controller, deposits):
    sim = new_sim(controller=controller, q_false=1.0)
    sim.step()
    r = sim.result()
    assert r["false_sightings"] == sim.cfg.n_robots
    assert (sim.field.grid.max() > 0) == deposits


def test_c5_marks_only_the_observers_own_map():
    sim = new_sim(controller="C5")
    place_wreck_next_to_robot_0(sim)
    sim.step()
    assert sim.maps[0].max() > 0
    assert sim.maps[2:].max() == 0
    assert sim.field.grid.max() == 0


def test_c5_maps_spread_one_hop_per_exchange():
    sim = new_sim(controller="C5", share_every=1)
    sim.maps[0, 30, 30] = 5.0
    sim.swarm.pos[0] = [3.0, 3.0]
    sim.swarm.pos[2] = [3.5, 3.0]   # 0.5 m from robot 0
    sim.swarm.pos[4] = [4.3, 3.0]   # 0.8 m from robot 2, 1.3 m from robot 0
    sim.step()
    assert sim.maps[2, 30, 30] > 0
    assert sim.maps[4, 30, 30] == 0   # needs a second exchange
    sim.step()
    assert sim.maps[4, 30, 30] > 0


def test_c5_localisation_uses_the_live_robots_mean_map():
    sim = new_sim(controller="C5", lethality=0.0, metric_every=1)
    sim.swarm.alive[1] = False
    sim.swarm.pos[1] = [8.81, 6.19]
    sim.swarm.pos[0] = [9.01, 6.19]
    sim.step()
    assert sim.result()["auc_final"] > 0.5


def test_hazard_and_random_failure_together_count_each_robot_once():
    sim = new_sim(lethality=1.0, random_fail_rate=1.0)
    sim.swarm.pos[:] = [8.81, 6.19]
    sim.step()
    r = sim.result()
    assert r["robots_lost"] == sim.cfg.n_robots
    assert r["first_loss_step"] == 0


def test_random_failure_of_a_carrier_loses_its_item():
    sim = new_sim(hazards=(), random_fail_rate=1.0)
    sim.swarm.state[0] = RETURN
    sim.swarm.pos[0] = [1.0, 1.0]   # away from the nest, so it cannot deliver first
    sim.picked_up = 1
    sim.step()
    r = sim.result()
    assert r["items_lost"] == 1 and r["carrying"] == 0
    assert r["first_loss_step"] == 0


def test_hazard_area_is_clipped_by_the_wall():
    r = run(Config(n_steps=1, hazards=((9.5153, 5.4847, 2.0),)), make_rng("t", 0, 0))
    assert 7.9 < r["hazard_area"] < 8.5      # about 8.23 m², well below pi * 2**2 = 12.57


def test_c5_auc_ignores_dead_robots_maps():
    sim = new_sim(controller="C5", lethality=0.0, metric_every=1)
    sim.swarm.alive[1] = False
    sim.swarm.pos[1] = [8.81, 6.19]
    sim.swarm.pos[0] = [9.01, 6.19]
    sim.maps[1, 10, 10] = 1000.0        # a huge value far from the hazard, in a dead robot's map
    sim.step()
    assert sim.result()["auc_final"] > 0.5   # would collapse if dead maps were averaged in


def test_c5_dead_robots_neither_send_nor_receive_maps():
    sim = new_sim(controller="C5", share_every=1)
    sim.swarm.alive[3] = False
    sim.swarm.pos[3] = [3.7, 3.0]
    sim.maps[3, 30, 30] = 5.0           # dead robot holds information
    sim.swarm.pos[0] = [3.0, 3.0]       # live neighbour 0.2 m away
    sim.maps[0, 70, 70] = 5.0           # live robot holds other information
    sim.step()
    assert sim.maps[0, 30, 30] == 0     # nothing received from the dead robot
    assert sim.maps[3, 70, 70] == 0     # nothing sent to the dead robot


def test_c5_maps_decay_and_false_sightings_go_into_own_map():
    sim = new_sim(controller="C5", q_false=1.0)
    sim.step()
    assert sim.result()["false_sightings"] == sim.cfg.n_robots
    assert all(sim.maps[i].max() > 0 for i in range(sim.cfg.n_robots))
    assert sim.field.grid.max() == 0
    sim2 = new_sim(controller="C5")
    sim2.maps[0, 50, 50] = 1.0
    sim2.step()
    assert sim2.maps[0, 50, 50] == pytest.approx(1.0 - sim2.cfg.decay)
