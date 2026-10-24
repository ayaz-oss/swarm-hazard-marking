"""Run the test_motion supervisor for 100 steps and print all output.

Creates a temp copy of foraging.wbt with the supervisor controller changed to
'test_motion', launches Webots, captures stdout/stderr, prints everything.

Usage:  python scripts/run_motion_test.py
"""
from __future__ import annotations
import os
import re
import subprocess
import sys
import time
from pathlib import Path

_HERE = Path(os.path.dirname(os.path.abspath(__file__)))
_ROOT = _HERE.parent

WEBOTS_EXE = (
    Path(os.environ.get("WEBOTS_HOME",
                        r"C:\Users\toaya\AppData\Local\Programs\Webots"))
    / "msys64" / "mingw64" / "bin" / "webots.exe"
)
WORLD_TEMPLATE = _ROOT / "webots" / "worlds" / "foraging.wbt"
TMP_WBT = _ROOT / "webots" / "worlds" / "foraging_motion_test.wbt"


def main() -> None:
    text = WORLD_TEMPLATE.read_text(encoding="utf-8")

    # Replace supervisor controller name and args (minimal args: just 100 steps)
    text = re.sub(
        r'(DEF SUPERVISOR Robot \{[^}]*?controller\s*")supervisor(")',
        r'\1test_motion\2',
        text,
        flags=re.DOTALL,
    )
    # Strip controllerArgs entirely (test_motion doesn't need them)
    text = re.sub(
        r'controllerArgs \[\s*\n(?:.*\n)*?\s*\]',
        'controllerArgs []',
        text,
    )

    TMP_WBT.write_text(text, encoding="utf-8")
    print(f"[run_motion_test] temp world: {TMP_WBT}")
    print(f"[run_motion_test] Webots: {WEBOTS_EXE}")

    cmd = [
        str(WEBOTS_EXE),
        "--batch",
        "--mode=fast",
        "--no-rendering",
        "--minimize",
        "--stdout",
        "--stderr",
        str(TMP_WBT),
    ]

    t0 = time.perf_counter()
    try:
        result = subprocess.run(cmd, timeout=300, capture_output=True, text=True)
        wall = time.perf_counter() - t0
        print(f"[run_motion_test] done in {wall:.1f}s, rc={result.returncode}")
        print("=== STDOUT ===")
        print(result.stdout)
        if result.stderr:
            print("=== STDERR (tail) ===")
            print(result.stderr[-2000:])
    except subprocess.TimeoutExpired:
        print("TIMEOUT")
    finally:
        try:
            TMP_WBT.unlink()
        except OSError:
            pass


if __name__ == "__main__":
    main()
