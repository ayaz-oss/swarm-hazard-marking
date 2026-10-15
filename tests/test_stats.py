import pytest

from swarmhazard.stats import a12


def test_a12_values():
    assert a12([1, 2, 3], [1, 2, 3]) == pytest.approx(0.5)
    assert a12([4, 5], [1, 2]) == 1.0
    assert a12([1, 2], [4, 5]) == 0.0
    assert a12([3, 3], [1, 3]) == pytest.approx(0.75)  # one win and one tie per draw
