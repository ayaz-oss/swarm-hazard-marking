import numpy as np

from swarmhazard.config import Config
from swarmhazard.controllers import avoidance, blocks_move, hazard_repulsion, wreck_repulsion
from swarmhazard.pheromone import RepellentField
from swarmhazard.seeding import make_rng
from swarmhazard.world import make_world


def setup(controller):
    cfg = Config(controller=controller)
    return cfg, make_world(cfg, make_rng("test", 0, 0)), RepellentField(cfg.arena_size, cfg.grid_cell)


def test_wreck_repulsion_pushes_away_within_range_only():
    pos = np.array([[1.0, 0.0], [3.0, 0.0]])
    push = wreck_repulsion(pos, np.array([[0.8, 0.0]]), sense_range=0.5)
    assert push[0, 0] > 0 and abs(push[0, 1]) < 1e-12
    assert np.all(push[1] == 0)


def test_wreck_repulsion_with_no_wrecks_is_zero():
    assert np.all(wreck_repulsion(np.ones((3, 2)), np.zeros((0, 2)), 0.5) == 0)


def test_hazard_repulsion_near_edge_only():
    pos = np.array([[2.3, 0.0], [5.0, 0.0]])
    push = hazard_repulsion(pos, np.array([[0.0, 0.0]]), np.array([2.0]), sense_range=0.5)
    assert push[0, 0] > 0
    assert np.all(push[1] == 0)


def test_c0_ignores_everything():
    cfg, world, field = setup("C0")
    field.deposit((5.0, 5.0), 5.0, 0.3)
    pos = np.array([[5.3, 5.0]])
    assert np.all(avoidance(cfg, pos, np.array([[5.2, 5.0]]), field, world) == 0)
    assert not blocks_move(cfg, world, np.array([[8.81, 6.19]])).any()


def test_c2_steers_away_from_repellent():
    cfg, world, field = setup("C2")
    field.deposit((5.0, 5.0), 5.0, 0.3)
    push = avoidance(cfg, np.array([[5.3, 5.0]]), np.zeros((0, 2)), field, world)
    assert push[0, 0] > 0


def test_c4_blocks_moves_into_hazards():
    cfg, world, field = setup("C4")
    assert blocks_move(cfg, world, np.array([[8.81, 6.19], [5.0, 5.0]])).tolist() == [True, False]
    push = avoidance(cfg, np.array([[8.81 - 1.2, 6.19]]), np.zeros((0, 2)), field, world)
    assert push[0, 0] < 0  # pushed west, away from the hazard centre
