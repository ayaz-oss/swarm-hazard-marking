import numpy as np

from swarmhazard.config import Config
from swarmhazard.seeding import make_rng
from swarmhazard.world import hazard_failures, in_hazard, make_world, respawn_item


def world_and_rng():
    rng = make_rng("test", 0, 0)
    return make_world(Config(), rng), rng


def test_items_start_inside_their_patch():
    world, _ = world_and_rng()
    assert len(world.item_pos) == 40
    centres = world.patch_xy[world.item_patch]
    dist = np.linalg.norm(world.item_pos - centres, axis=1)
    assert np.all(dist <= world.patch_r[world.item_patch])


def test_respawn_moves_item_within_same_patch():
    world, rng = world_and_rng()
    before = world.item_pos[7].copy()
    respawn_item(world, 7, rng)
    k = world.item_patch[7]
    assert not np.array_equal(before, world.item_pos[7])
    assert np.linalg.norm(world.item_pos[7] - world.patch_xy[k]) <= world.patch_r[k]


def test_in_hazard():
    world, _ = world_and_rng()
    pos = np.array([[8.81, 6.19], [5.0, 5.0]])
    assert in_hazard(world, pos).tolist() == [True, False]


def test_no_hazards_means_never_inside():
    world = make_world(Config(hazards=()), make_rng("test", 0, 0))
    assert not in_hazard(world, np.array([[8.81, 6.19]])).any()


def test_failure_rate_inside_hazard_matches_lethality():
    world, rng = world_and_rng()
    n = 20_000
    pos = np.tile([8.81, 6.19], (n, 1))
    rate = hazard_failures(world, pos, np.ones(n, bool), 0.02, rng).mean()
    assert abs(rate - 0.02) < 0.004  # about 4 standard errors


def test_no_failures_outside_hazard_or_when_already_dead():
    world, rng = world_and_rng()
    outside = np.tile([5.0, 5.0], (1000, 1))
    assert not hazard_failures(world, outside, np.ones(1000, bool), 1.0, rng).any()
    inside = np.tile([8.81, 6.19], (1000, 1))
    assert not hazard_failures(world, inside, np.zeros(1000, bool), 1.0, rng).any()
