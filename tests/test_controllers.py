import numpy as np

from swarmhazard.config import Config
from swarmhazard.controllers import avoidance, blocks_move, hazard_tangent, items_in_view, wreck_repulsion
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


def test_c4_blocks_moves_into_hazards_without_a_safety_band():
    cfg, world, field = setup("C4")
    assert blocks_move(cfg, world, np.array([[8.81, 6.19], [5.0, 5.0]])).tolist() == [True, False]
    near_edge = np.array([[8.81 - 1.2, 6.19]])
    assert np.all(avoidance(cfg, near_edge, np.zeros((0, 2)), field, world) == 0)


def test_hazard_tangent_is_perpendicular_and_follows_direction():
    _, world, _ = setup("C4")
    east_edge = np.array([[8.81 + 1.0, 6.19]])
    t = hazard_tangent(world, east_edge, np.array([[-1.0, 0.1]]))
    assert np.allclose(t, [[0.0, 1.0]])


def test_c1_avoids_wrecks_but_ignores_repellent():
    cfg, world, field = setup("C1")
    field.deposit((5.0, 5.0), 5.0, 0.3)
    assert np.all(avoidance(cfg, np.array([[5.3, 5.0]]), np.zeros((0, 2)), field, world) == 0)
    push = avoidance(cfg, np.array([[1.0, 0.0]]), np.array([[0.8, 0.0]]), field, world)
    assert push[0, 0] > 0


def test_c3_matches_c2_when_no_items_in_view():
    c2, world, field = setup("C2")
    c3 = Config(controller="C3", risk_k=2.0)
    field.deposit((5.0, 5.0), 5.0, 0.3)
    pos = np.array([[5.3, 5.0]])  # beside the nest: no item within 0.5 m
    wrecks = np.array([[5.5, 5.0]])
    assert np.linalg.norm(avoidance(c2, pos, wrecks, field, world)) > 0
    assert np.allclose(avoidance(c3, pos, wrecks, field, world), avoidance(c2, pos, wrecks, field, world))


def test_c3_pushes_less_when_items_in_view():
    c2, world, field = setup("C2")
    c3 = Config(controller="C3", risk_k=2.0)
    pos = world.item_pos[:1].copy()
    field.deposit(pos[0] + np.array([-0.3, 0.0]), 5.0, 0.3)
    n = items_in_view(pos, world.item_pos, c3.sense_range)[0]
    assert n >= 1
    expected = avoidance(c2, pos, np.zeros((0, 2)), field, world) / (1 + 2.0 * n)
    assert np.linalg.norm(expected) > 0
    assert np.allclose(avoidance(c3, pos, np.zeros((0, 2)), field, world), expected)


def test_undetected_wrecks_do_not_repel():
    pos = np.array([[1.0, 0.0]])
    wrecks = np.array([[0.8, 0.0]])
    assert wreck_repulsion(pos, wrecks, 0.5, detected=np.array([[True]]))[0, 0] > 0
    assert np.all(wreck_repulsion(pos, wrecks, 0.5, detected=np.array([[False]])) == 0)


def test_c5_steers_down_its_own_map_only():
    cfg, world, field = setup("C5")
    maps = np.zeros((2, field.n, field.n))
    sx, sy, values = field.bump((5.0, 5.0), 5.0, 0.3)
    maps[0, sx, sy] += values
    pos = np.array([[5.3, 5.0], [5.3, 5.0]])
    push = avoidance(cfg, pos, np.zeros((0, 2)), field, world, maps=maps)
    assert push[0, 0] > 0
    assert np.all(push[1] == 0)


def test_c3_scales_the_wreck_term_too():
    c2, world, _ = setup("C2")
    c3 = Config(controller="C3", risk_k=2.0)
    field = RepellentField(c2.arena_size, c2.grid_cell)  # empty: only the wreck term acts
    pos = world.item_pos[:1].copy()
    wrecks = pos + np.array([[0.2, 0.0]])
    n = items_in_view(pos, world.item_pos, c3.sense_range)[0]
    c2_push = avoidance(c2, pos, wrecks, field, world)
    assert np.linalg.norm(c2_push) > 0
    assert np.allclose(avoidance(c3, pos, wrecks, field, world), c2_push / (1 + 2.0 * n))
