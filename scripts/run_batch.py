"""Run main experiments from a frozen copy of one commit, so later edits cannot touch them.

Checks out HEAD into .batch/<sha>/ (a git worktree), runs the golden test there, then
runs each experiment from that copy with its src/ first on the import path, writing
results to this checkout's results/. Keeps Windows from idle-sleeping meanwhile and
removes the worktree when everything succeeded.

Usage: python scripts/run_batch.py E6 E7 [--workers 4]
"""

from __future__ import annotations

import argparse
import ctypes
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def git(*args: str, cwd: Path = ROOT) -> str:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


def batch_env(worktree: Path, base: dict | None = None) -> dict:
    env = dict(os.environ if base is None else base)
    src = str(worktree / "src")
    env["PYTHONPATH"] = src + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    return env


def keep_awake(on: bool) -> None:
    if sys.platform != "win32":
        return
    es_continuous, es_system_required = 0x80000000, 0x00000001
    ctypes.windll.kernel32.SetThreadExecutionState(es_continuous | (es_system_required if on else 0))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("experiments", nargs="+", help="experiment names, e.g. E6 E7")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    if git("status", "--porcelain"):
        print("Refusing: commit your changes first.", file=sys.stderr)
        return 1
    sha = git("rev-parse", "--short", "HEAD")
    worktree = ROOT / ".batch" / sha
    if not worktree.exists():
        git("worktree", "add", "--detach", str(worktree), sha)
    env = batch_env(worktree)
    results = ROOT / "results"
    results.mkdir(exist_ok=True)

    golden = subprocess.run([sys.executable, "-m", "pytest", "-q", "tests/test_golden.py"],
                            cwd=worktree, env=env)
    if golden.returncode != 0:
        print(f"Refusing: golden test failed at {sha}.", file=sys.stderr)
        return 1

    keep_awake(True)
    try:
        for name in args.experiments:
            start = time.time()
            with open(results / f"{name}.log", "w") as log:
                rc = subprocess.run(
                    [sys.executable, str(worktree / "scripts" / "run_experiment.py"),
                     f"configs/experiments/{name}.yaml", "--workers", str(args.workers),
                     "--results-dir", str(results)],
                    cwd=worktree, env=env, stdout=log, stderr=subprocess.STDOUT).returncode
            print(f"{name}: exit {rc}, {time.time() - start:.0f} s (code {sha})", flush=True)
            if rc != 0:
                return rc
    finally:
        keep_awake(False)
    git("worktree", "remove", str(worktree))
    return 0


if __name__ == "__main__":
    sys.exit(main())
