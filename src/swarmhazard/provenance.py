"""Where a result came from: code version, machine and package versions (spec section 6).

Exact re-runs are only claimed on the same machine and environment: chaotic
dynamics can amplify last-bit floating-point differences between CPUs.
"""

from __future__ import annotations

import platform
import subprocess
from importlib.metadata import version
from pathlib import Path

PACKAGES = {"numpy": "numpy", "scipy": "scipy", "pandas": "pandas",
            "matplotlib": "matplotlib", "pyyaml": "PyYAML"}


def git_commit(root: Path) -> str:
    try:
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=root,
                             capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=root,
                               capture_output=True, text=True, check=True).stdout.strip()
        return sha + ("-dirty" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def provenance(root: Path) -> dict:
    info = {
        "git_commit": git_commit(root),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
    }
    info.update({f"v_{key}": version(dist) for key, dist in PACKAGES.items()})
    return info
