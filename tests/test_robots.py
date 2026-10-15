import numpy as np

from swarmhazard.config import Config
from swarmhazard.robots import SEARCH, make_swarm, unit
from swarmhazard.seeding import make_rng


def test_swarm_starts_alive_searching_in_nest():
    cfg = Config()
    sw = make_swarm(cfg, make_rng("test", 0, 0))
    assert sw.pos.shape == (20, 2)
    assert np.all(np.linalg.norm(sw.pos - np.array(cfg.nest_center), axis=1) < cfg.nest_radius)
    assert sw.alive.all()
    assert np.all(sw.state == SEARCH)


def test_unit_vectors():
    u = unit(np.array([0.0, np.pi / 2]))
    assert np.allclose(u, [[1, 0], [0, 1]])
