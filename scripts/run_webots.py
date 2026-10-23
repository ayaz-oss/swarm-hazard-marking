"""Launch Webots headless runs for the swarm-hazard physics replication.

Usage
-----
python scripts/run_webots.py [options]

Options
  --experiment  YAML file (default: configs/experiments/W1.yaml)
  --controller  override controller (e.g. C2); repeatable or comma-separated
  --seeds       comma-separated seeds (default: from YAML)
  --n-seeds     how many seeds to run (default: from YAML; ignored if --seeds given)
  --n-steps     steps per run (default: from YAML n_steps field)
  --parallel    parallel Webots instances (default: 2)
  --out         output CSV path (default: from YAML or results/W1.csv)
  --smoke       shorthand: 1 seed, 2000 steps, controllers C0 C1 C2 C4
  --calib       shorthand: C0 only, no-hazard override, seeds 0-4, 3000 steps

Example
  python scripts/run_webots.py --smoke --controller C2

Webots flags used
  --batch --mode=fast --no-rendering --minimize --stdout --stderr
  These suppress the GUI and run as fast as the physics allows.

Each run spawns one Webots process.  The supervisor writes one CSV row to the
shared output file (append mode, thread-safe because each Webots process owns
its own supervisor).  A temp copy of foraging.wbt is written per run (with the
correct controllerArgs for controller and seed), then deleted after the run.
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import yaml

# ── resolve project root ──────────────────────────────────────────────────────
_HERE = Path(os.path.dirname(os.path.abspath(__file__)))  # scripts/
_ROOT = _HERE.parent                                        # worktree root

WEBOTS_EXE = (
    Path(os.environ.get("WEBOTS_HOME",
                        r"C:\Users\toaya\AppData\Local\Programs\Webots"))
    / "msys64" / "mingw64" / "bin" / "webots.exe"
)
WORLD_TEMPLATE = _ROOT / "webots" / "worlds" / "foraging.wbt"


# ── helpers ───────────────────────────────────────────────────────────────────

def _read_world_template() -> str:
    return WORLD_TEMPLATE.read_text(encoding="utf-8")


def _make_run_world(controller: str, seed: int, n_steps: int,
                    out_csv: str, tmp_dir: Path,  # noqa: ARG001
                    lethality_override: float | None = None) -> Path:
    """Write a per-run WBT file with supervisor controllerArgs set.

    IMPORTANT: the temp WBT is written into the SAME ``webots/worlds/``
    directory as the template.  Webots resolves both EXTERNPROTO paths and
    controller directories relative to the WBT file, so placing it elsewhere
    breaks controller lookup.  ``tmp_dir`` is kept as a parameter for
    compatibility but is ignored.

    Temp files are named ``foraging_{controller}_{seed}.wbt``.  They are
    cleaned up after each run.  Add ``webots/worlds/foraging_*.wbt`` to
    ``.gitignore`` to keep them out of version control.
    """
    text = _read_world_template()

    # Replace the default controllerArgs block for the supervisor.
    # The pattern matches the block inside the SUPERVISOR Robot node.
    lethality_line = f'    "{lethality_override}"\n' if lethality_override is not None else ""
    new_args = (
        f'  controllerArgs [\n'
        f'    "{controller}"\n'
        f'    "{seed}"\n'
        f'    "{out_csv.replace(chr(92), "/")}"\n'
        f'    "{n_steps}"\n'
        f'{lethality_line}'
        f'  ]'
    )
    # Replace the controllerArgs block (the default has "C2" and "0").
    text = re.sub(
        r'controllerArgs \[\s*\n\s*"[^"]*"\s*\n\s*"[^"]*"\s*\n\s*\]',
        new_args.strip(),
        text,
    )
    # Write temp WBT alongside the template so relative paths remain valid.
    worlds_dir = WORLD_TEMPLATE.parent
    tmp_wbt = worlds_dir / f"foraging_{controller}_{seed}.wbt"
    tmp_wbt.write_text(text, encoding="utf-8")
    return tmp_wbt


def _run_one(controller: str, seed: int, n_steps: int,
             out_csv: str, tmp_dir: Path, timeout: int = 600,
             lethality_override: float | None = None) -> dict:
    """Launch one Webots run and return timing info."""
    wbt = _make_run_world(controller, seed, n_steps, out_csv, tmp_dir,
                          lethality_override=lethality_override)
    cmd = [
        str(WEBOTS_EXE),
        "--batch",
        "--mode=fast",
        "--no-rendering",
        "--minimize",
        "--stdout",
        "--stderr",
        str(wbt),
    ]
    t0 = time.perf_counter()
    try:
        result = subprocess.run(
            cmd,
            timeout=timeout,
            capture_output=True,
            text=True,
        )
        wall = time.perf_counter() - t0
        stdout = result.stdout
        stderr = result.stderr
        rc = result.returncode
    except subprocess.TimeoutExpired as e:
        wall = time.perf_counter() - t0
        stdout = ""
        stderr = f"TIMEOUT after {timeout}s"
        rc = -1
    finally:
        try:
            wbt.unlink()
        except OSError:
            pass

    ok = rc in (0, 1)  # Webots exits 1 on simulationQuit(0) in some versions
    return {
        "controller": controller,
        "seed": seed,
        "wall_s": round(wall, 2),
        "rc": rc,
        "ok": ok,
        "stdout": stdout[-500:] if stdout else "",
        "stderr": stderr[-500:] if stderr else "",
    }


# ── main ──────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Run Webots swarm-hazard physics replication.")
    p.add_argument("--experiment", default=str(_ROOT / "configs" / "experiments" / "W1.yaml"))
    p.add_argument("--controller", action="append", help="Repeat or comma-separate")
    p.add_argument("--seeds", help="Comma-separated seed list")
    p.add_argument("--n-seeds", type=int)
    p.add_argument("--n-steps", type=int)
    p.add_argument("--parallel", type=int, default=2)
    p.add_argument("--out", help="Output CSV path")
    p.add_argument("--smoke", action="store_true",
                   help="One seed (0), 2000 steps, controllers C0 C2")
    p.add_argument("--calib", action="store_true",
                   help="C0, no hazard, seeds 0-4, 3000 steps (calibration run)")
    p.add_argument("--no-hazard", dest="no_hazard", action="store_true",
                   help="Set lethality=0 (pass argv[5]=0.0 to supervisor)")
    p.add_argument("--timeout", type=int, default=600,
                   help="Per-run timeout in seconds (default: 600)")
    p.add_argument("--verbose", action="store_true")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    # Load experiment spec
    spec = yaml.safe_load(Path(args.experiment).read_text()) or {}
    webots_spec = spec.get("webots", {})

    # Determine controllers
    if args.smoke:
        controllers = ["C0", "C2"]
    elif args.calib:
        controllers = ["C0"]
    elif args.controller:
        controllers = []
        for c in args.controller:
            controllers.extend(c.split(","))
    else:
        controllers = spec.get("controllers", ["C0", "C2"])

    # Determine seeds
    if args.smoke:
        seeds = [0]
    elif args.calib:
        seeds = list(range(5))
    elif args.seeds:
        seeds = [int(s) for s in args.seeds.split(",")]
    elif args.n_seeds is not None:
        seeds = list(range(args.n_seeds))
    else:
        seeds = list(range(spec.get("seeds", 5)))

    # n_steps
    if args.smoke:
        n_steps = 2000
    elif args.calib:
        n_steps = 3000
    elif args.n_steps:
        n_steps = args.n_steps
    else:
        n_steps = spec.get("n_steps", 10000)

    # Output CSV
    out_csv = args.out or webots_spec.get("result_file", str(_ROOT / "results" / "W1.csv"))
    out_csv = str(_ROOT / out_csv) if not os.path.isabs(out_csv) else out_csv
    Path(out_csv).parent.mkdir(parents=True, exist_ok=True)

    parallel = args.parallel or webots_spec.get("n_parallel", 2)

    # Lethality override (--no-hazard or --calib always sets 0.0)
    lethality_override: float | None = None
    if getattr(args, "no_hazard", False) or args.calib:
        lethality_override = 0.0

    # Build job list
    jobs = [
        {"controller": ctrl, "seed": seed}
        for ctrl in controllers
        for seed in seeds
    ]

    print(f"[run_webots] {len(jobs)} runs: controllers={controllers}, "
          f"seeds={seeds[:5]}{'...' if len(seeds) > 5 else ''}, "
          f"n_steps={n_steps}, parallel={parallel}")
    print(f"[run_webots] output -> {out_csv}")
    print(f"[run_webots] Webots: {WEBOTS_EXE}")

    if not WEBOTS_EXE.exists():
        print(f"ERROR: Webots not found at {WEBOTS_EXE}", file=sys.stderr)
        sys.exit(1)

    tmp_dir = Path(tempfile.mkdtemp(prefix="swarmhazard_wbt_"))
    t_total = time.perf_counter()

    times = []
    n_ok = 0
    n_fail = 0

    try:
        with ThreadPoolExecutor(max_workers=parallel) as pool:
            futures = {
                pool.submit(
                    _run_one,
                    j["controller"], j["seed"], n_steps, out_csv, tmp_dir, args.timeout,
                    lethality_override,
                ): j
                for j in jobs
            }
            for fut in as_completed(futures):
                j = futures[fut]
                try:
                    r = fut.result()
                except Exception as exc:
                    print(f"  EXCEPTION {j}: {exc}", file=sys.stderr)
                    n_fail += 1
                    continue

                times.append(r["wall_s"])
                if r["ok"]:
                    n_ok += 1
                    status = "OK"
                else:
                    n_fail += 1
                    status = f"FAIL(rc={r['rc']})"

                print(f"  [{status}] {r['controller']} seed={r['seed']} "
                      f"{r['wall_s']:.1f}s")
                if args.verbose or not r["ok"]:
                    if r["stdout"]:
                        print(f"    stdout: {r['stdout']}")
                    if r["stderr"]:
                        print(f"    stderr: {r['stderr']}")
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass

    total_wall = time.perf_counter() - t_total

    if times:
        mean_t = sum(times) / len(times)
        print(f"\n[run_webots] done: {n_ok}/{n_ok+n_fail} OK in "
              f"{total_wall:.0f}s total")
        print(f"  Mean per run: {mean_t:.1f}s")
        print(f"  Extrapolated to 10,000 steps "
              f"({10000/n_steps:.1f}×): {mean_t * 10000/n_steps:.1f}s/run")
        print(f"  Extrapolated to 400 runs: "
              f"{mean_t * 10000/n_steps * 400 / 3600:.1f}h")
    else:
        print("[run_webots] No runs completed.")


if __name__ == "__main__":
    main()
