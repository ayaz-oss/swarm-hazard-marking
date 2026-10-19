import os
import sys
from pathlib import Path

from swarmhazard.provenance import provenance

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from run_batch import batch_env  # noqa: E402


def test_batch_env_puts_worktree_code_first(tmp_path):
    env = batch_env(tmp_path, {"PYTHONPATH": "elsewhere"})
    parts = env["PYTHONPATH"].split(os.pathsep)
    assert parts[0] == str(tmp_path / "src")
    assert parts[-1] == "elsewhere"
    assert batch_env(tmp_path, {})["PYTHONPATH"] == str(tmp_path / "src")


def test_provenance_records_where_the_package_came_from():
    assert Path(provenance(ROOT)["package_root"]) == (ROOT / "src").resolve()
