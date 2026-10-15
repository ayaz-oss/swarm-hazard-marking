import numpy as np
import pytest

from swarmhazard.pheromone import RepellentField


def test_deposit_peak_and_shape():
    f = RepellentField(10.0, 0.1)
    f.deposit((5.05, 5.05), amount=2.0, sigma=0.3)  # exactly on a cell centre
    assert f.value(np.array([[5.05, 5.05]]))[0] == pytest.approx(2.0)
    assert f.value(np.array([[5.35, 5.05]]))[0] == pytest.approx(2.0 * np.exp(-0.5), rel=1e-6)
    assert f.value(np.array([[1.0, 1.0]]))[0] == 0.0


def test_decay_is_geometric():
    f = RepellentField(10.0, 0.1)
    f.deposit((5.0, 5.0), 1.0, 0.3)
    total = f.grid.sum()
    for _ in range(100):
        f.decay(0.01)
    assert f.grid.sum() == pytest.approx(total * 0.99**100)


def test_gradient_points_toward_peak():
    f = RepellentField(10.0, 0.1)
    f.deposit((5.05, 5.05), 1.0, 0.3)
    g = f.gradient(np.array([[5.55, 5.05]]), h=0.5)[0]
    assert g[0] < 0             # concentration rises toward x = 5.05
    assert abs(g[1]) < 1e-12    # symmetric in y


def test_edges_are_safe():
    f = RepellentField(10.0, 0.1)
    f.deposit((0.0, 0.0), 1.0, 0.3)
    f.deposit((10.0, 10.0), 1.0, 0.3)
    v = f.value(np.array([[-1.0, -1.0], [11.0, 11.0]]))
    assert v.shape == (2,)
    assert np.all(v > 0)
