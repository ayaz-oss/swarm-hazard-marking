"""The simulator's exact output must not change (speed work must be bit-identical)."""

import json
import math
import sys
from pathlib import Path

import pytest

from swarmhazard.config import Config
from swarmhazard.seeding import make_rng

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from make_golden import GOLDEN_CASES, golden_record  # noqa: E402

GOLDEN = json.loads((ROOT / "tests" / "data" / "golden.json").read_text())

# Golden values were recorded on Windows. They reproduce bit for bit on other Windows machines
# (GitHub Actions windows-latest), but on Linux the final-state digests differ in the last
# floating-point bits (spec 2026-10-22 week-7 addendum, section 5), so they are Windows-only.
pytestmark = pytest.mark.skipif(sys.platform != "win32",
                                reason="golden values are bit-exact on Windows only (week-7 spec section 5)")


def same(a, b) -> bool:
    if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
        return True
    return a == b


def test_golden_file_covers_every_case():
    assert set(GOLDEN) == set(GOLDEN_CASES)


@pytest.mark.parametrize("name", sorted(GOLDEN_CASES))
def test_run_output_is_unchanged(name):
    result = golden_record(Config(**GOLDEN_CASES[name]), make_rng("golden", 0, 0))
    expected = GOLDEN[name]
    # Compare only keys present in the golden file, so new result keys can be added.
    diffs = {k: (result[k], v) for k, v in expected.items() if not same(result[k], v)}
    assert not diffs
