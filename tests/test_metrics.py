import numpy as np
import pytest

from swarmhazard.config import Config
from swarmhazard.metrics import field_auc, hazard_mask
from swarmhazard.pheromone import RepellentField
from swarmhazard.seeding import make_rng
from swarmhazard.world import make_world


def test_field_auc_values():
    mask = np.array([[True, False], [False, False]])
    assert field_auc(mask.astype(float), mask) == 1.0
    assert field_auc((~mask).astype(float), mask) == 0.0
    assert field_auc(np.zeros((2, 2)), mask) == 0.5
    assert field_auc(np.array([[2.0, 1.0], [3.0, 0.0]]), mask) == pytest.approx(2 / 3)


def test_hazard_mask_area_matches_circle():
    cfg = Config()
    field = RepellentField(cfg.arena_size, cfg.grid_cell)
    mask = hazard_mask(make_world(cfg, make_rng("t", 0, 0)), field)
    assert mask.shape == field.grid.shape
    assert abs(mask.sum() * cfg.grid_cell**2 - np.pi * 1.0**2) < 0.05
