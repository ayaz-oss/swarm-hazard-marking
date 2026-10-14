import numpy as np

from swarmhazard.seeding import make_rng


def test_same_inputs_same_stream():
    assert np.array_equal(make_rng("E1", 0, 3).random(5), make_rng("E1", 0, 3).random(5))


def test_any_input_change_gives_new_stream():
    base = make_rng("E1", 0, 3).random(5)
    assert not np.array_equal(base, make_rng("E1", 0, 4).random(5))
    assert not np.array_equal(base, make_rng("E1", 1, 3).random(5))
    assert not np.array_equal(base, make_rng("E2", 0, 3).random(5))
