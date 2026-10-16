"""The simulator's exact output must not change (speed work must be bit-identical)."""

import json
import math
import sys
from pathlib import Path

import pytest

from swarmhazard.config import Config
from swarmhazard.seeding import make_rng
from swarmhazard.sim import run

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from make_golden import GOLDEN_CASES  # noqa: E402

GOLDEN = json.loads((ROOT / "tests" / "data" / "golden.json").read_text())


def same(a, b) -> bool:
    if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
        return True
    return a == b


@pytest.mark.parametrize("name", sorted(GOLDEN_CASES))
def test_run_output_is_unchanged(name):
    result = run(Config(**GOLDEN_CASES[name]), make_rng("golden", 0, 0))
    expected = GOLDEN[name]
    # Compare only keys present in the golden file, so new result keys can be added.
    diffs = {k: (result[k], v) for k, v in expected.items() if not same(result[k], v)}
    assert not diffs
