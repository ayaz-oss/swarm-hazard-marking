"""Two small descriptive checks (week-5 addendum section 6). They only observe the simulator.

saturation: C0 with E4's random streams, seeds 0-19, at E4's four lethalities plus lethality 0
  (natural hazard visits, cell 1's streams). A visit is a maximal run of steps a live robot is
  inside the hazard at the failure check.
auc-delay:  C2 with E1's random streams, seeds 0-29, AUC every 10 steps (sampling does not change
  behaviour). First loss, first mark and first step the AUC leaves 0.5.

Both re-run existing main-experiment runs; outcomes are compared with E1.csv / E4.csv in
--reference-dir when present, as a check that observing changed nothing.

Step convention: first_loss_step and first_mark_step are step indices (the value of sim.t while
that step ran), as in the main result files. An AUC sample at step s is taken after steps
0..s-1, so a run counts as marked (or as having lost a robot) at sample s when its first
mark (first loss) step is < s.

Usage: python scripts/mechanism_checks.py [--reference-dir DIR] [--workers 4]
"""

from __future__ import annotations

import argparse
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

from swarmhazard.config import load_config
from swarmhazard.experiment import build_jobs, load_experiment
from swarmhazard.seeding import make_rng
from swarmhazard.sim import Simulation
from swarmhazard.world import in_hazard

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "mechanism"
SAT_SEEDS = 20
AUC_SEEDS = 30
AUC_EVERY = 10
MAIN_EVERY = 500  # the main experiments' AUC sampling interval


# ---------------------------------------------------------------- pure helpers

def visits_from_trace(inside: np.ndarray, died: np.ndarray) -> list[tuple[int, int, int, bool]]:
    """Maximal runs of True per robot column: (robot, start step, length, ended in death).

    A visit still open at the end of the trace counts as survived.
    """
    out = []
    for i in range(inside.shape[1]):
        col = np.concatenate(([0], inside[:, i].astype(np.int8), [0]))
        d = np.diff(col)
        for s, e in zip(np.flatnonzero(d == 1), np.flatnonzero(d == -1)):  # e is exclusive
            out.append((i, int(s), int(e - s), bool(died[e - 1, i])))
    return out


def predicted_death_fraction(lengths, p: float) -> float:
    """Mean chance that a visit of each length ends in death at per-step lethality p."""
    return float(np.mean(1.0 - (1.0 - p) ** np.asarray(lengths, float)))


def first_auc_step(series, every: int) -> int:
    """Step of the first AUC sample that is not 0.5 (-1 if none)."""
    for k, a in enumerate(series):
        if abs(a - 0.5) > 1e-12:
            return (k + 1) * every
    return -1


def median_step(steps) -> int | float:
    """Median of step values where -1 means 'never' (later than any step); -1 if the median is never."""
    v = np.asarray(steps, float)
    m = float(np.median(np.where(v < 0, np.inf, v)))
    return -1 if not np.isfinite(m) else (int(m) if m == int(m) else m)


def auc_curve(series_list, first_marks, first_losses, every: int) -> pd.DataFrame:
    a = np.asarray(series_list, float)
    steps = (np.arange(a.shape[1]) + 1) * every
    marks = np.asarray(first_marks)[:, None]
    losses = np.asarray(first_losses)[:, None]
    return pd.DataFrame({
        "step": steps,
        "median_auc": np.median(a, axis=0),
        "frac_marked": ((marks >= 0) & (marks < steps)).mean(axis=0),
        "frac_lost": ((losses >= 0) & (losses < steps)).mean(axis=0),
    })


# ---------------------------------------------------------------- simulation

def trace_run(cfg, rng):
    """Step a run while observing it. Returns (result, inside, died, first_mark_step, auc_series)."""
    sim = Simulation(cfg, rng)
    shape = (cfg.n_steps, cfg.n_robots)
    inside = np.zeros(shape, dtype=bool)
    died = np.zeros(shape, dtype=bool)
    first_mark = -1
    for t in range(cfg.n_steps):
        alive_before = sim.swarm.alive.copy()
        sim.step()
        inside[t] = alive_before & in_hazard(sim.world, sim.swarm.pos)
        died[t] = alive_before & ~sim.swarm.alive
        if first_mark < 0 and sim.field.grid.max() > 0:
            first_mark = t
    return sim.result(), inside, died, first_mark, list(sim.auc_series)


def _work(task):
    kind, job, overrides = task
    cfg = load_config(ROOT / job["base"], **{**job["overrides"], **overrides}, controller=job["controller"])
    result, inside, died, first_mark, auc = trace_run(cfg, make_rng(job["experiment"], job["cell"], job["seed"]))
    keep = {k: result[k] for k in ("delivered", "robots_lost", "first_loss_step")}
    if kind == "sat":
        return keep, visits_from_trace(inside, died), int(inside.any(axis=0).sum())
    return keep, auc, first_mark


def _reference(ref_dir: Path | None, name: str) -> pd.DataFrame | None:
    if ref_dir is None or not (ref_dir / f"{name}.csv").exists():
        return None
    return pd.read_csv(ref_dir / f"{name}.csv").set_index(["cell", "controller", "seed"])


def _iqr(x):
    return (float(np.percentile(x, 25)), float(np.percentile(x, 75))) if len(x) else (np.nan, np.nan)


def saturation(pool, ref: pd.DataFrame | None):
    spec = load_experiment(ROOT / "configs/experiments/E4.yaml", ROOT)
    jobs = [j for j in build_jobs(spec, seeds=SAT_SEEDS) if j["controller"] == "C0"]
    tasks = [("sat", j, {}) for j in jobs]
    tasks += [("sat", j, {"lethality": 0.0}) for j in jobs if j["cell"] == 1]
    out = list(pool.map(_work, tasks))
    visit_rows, run_rows = [], []
    for (kind, job, over), (res, visits, entered) in zip(tasks, out):
        p = over.get("lethality", job["params"]["lethality"])
        row = {"lethality": p, "cell": job["cell"], "seed": job["seed"], "robots_entered": entered, **res,
               "visits": len(visits)}
        if ref is not None and not over:
            r = ref.loc[(job["cell"], "C0", job["seed"])]
            for k in ("delivered", "robots_lost", "first_loss_step"):
                row[f"match_{k}"] = bool(r[k] == res[k])
        run_rows.append(row)
        visit_rows += [{"lethality": p, "seed": job["seed"], "robot": i, "start": s, "length": n, "died": d}
                       for i, s, n, d in visits]
    visits = pd.DataFrame(visit_rows)
    runs = pd.DataFrame(run_rows)
    natural = visits.loc[visits["lethality"] == 0.0, "length"].to_numpy()
    summary = []
    for p, v in visits.groupby("lethality"):
        r = runs[runs["lethality"] == p]
        q1, q3 = _iqr(v["length"])
        flags = [c for c in r if c.startswith("match_")]
        summary.append({
            "lethality": p, "runs": len(r), "visits_per_run": len(v) / len(r),
            "robots_entering_per_run": r["robots_entered"].mean(),
            "visit_len_median": float(np.median(v["length"])), "visit_len_q1": q1, "visit_len_q3": q3,
            "observed_death_frac": v["died"].mean(),
            "predicted_death_frac": predicted_death_fraction(natural, p),
            "mean_robots_lost": r["robots_lost"].mean(),
            "e4_rows_compared": int(r[flags].notna().all(axis=1).sum()) if flags and p > 0 else 0,
            "e4_all_match": bool(r[flags].astype(bool).all().all()) if flags and p > 0 else None,
        })
    return visits, pd.DataFrame(summary), runs


def auc_delay(pool, ref: pd.DataFrame | None):
    spec = load_experiment(ROOT / "configs/experiments/E1.yaml", ROOT)
    jobs = [j for j in build_jobs(spec, seeds=AUC_SEEDS) if j["controller"] == "C2"]
    tasks = [("auc", j, {"metric_every": AUC_EVERY}) for j in jobs]
    out = list(pool.map(_work, tasks))
    rows, series = [], []
    ratio = MAIN_EVERY // AUC_EVERY
    for (_, job, _), (res, auc, first_mark) in zip(tasks, out):
        row = {"seed": job["seed"], "first_loss_step": res["first_loss_step"], "first_mark_step": first_mark,
               "first_auc_step": first_auc_step(auc, AUC_EVERY), "delivered": res["delivered"],
               "robots_lost": res["robots_lost"]}
        if ref is not None:
            r = ref.loc[(job["cell"], "C2", job["seed"])]
            for k in ("delivered", "robots_lost", "first_loss_step"):
                row[f"match_{k}"] = bool(r[k] == res[k])
            main = [float(x) for x in str(r["auc_series"]).split(";")]
            mine = [round(a, 4) for a in auc[ratio - 1::ratio]]
            row["match_auc_500"] = bool(np.allclose(main, mine, atol=1e-4, rtol=0))
        rows.append(row)
        series.append(auc)
    runs = pd.DataFrame(rows)
    curve = auc_curve(series, runs["first_mark_step"], runs["first_loss_step"], AUC_EVERY)
    return runs, curve


def _fmt(step, dt=0.1):
    return "never (median)" if step == -1 else f"step {step} ({step * dt:g} s)"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reference-dir", type=Path, default=None)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args(argv)
    OUT.mkdir(parents=True, exist_ok=True)
    e4, e1 = _reference(args.reference_dir, "E4"), _reference(args.reference_dir, "E1")
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        visits, summary, sat_runs = saturation(pool, e4)
        runs, curve = auc_delay(pool, e1)
    visits.to_csv(OUT / "saturation_visits.csv", index=False)
    summary.to_csv(OUT / "saturation_summary.csv", index=False)
    sat_runs.to_csv(OUT / "saturation_runs.csv", index=False)
    runs.to_csv(OUT / "auc_delay_runs.csv", index=False)
    curve.to_csv(OUT / "auc_delay_curve.csv", index=False)

    print("Saturation (C0, E4 streams, seeds 0-19):")
    print(summary.to_string(index=False))
    print("\nAUC delay (C2, E1 streams, seeds 0-29, AUC every 10 steps):")
    for col in ("first_loss_step", "first_mark_step", "first_auc_step"):
        print(f"  median {col}: {_fmt(median_step(runs[col]))}")
    above = curve[curve["median_auc"] > 0.5]
    print(f"  first 10-step sample with median AUC > 0.5: {_fmt(int(above['step'].iloc[0]) if len(above) else -1)}")
    coarse = above[above["step"] % MAIN_EVERY == 0]
    print(f"  first 500-step sample with median AUC > 0.5: {_fmt(int(coarse['step'].iloc[0]) if len(coarse) else -1)}")
    half = curve[curve["frac_marked"] > 0.5]
    print(f"  first sample with more than half the runs marked: {_fmt(int(half['step'].iloc[0]) if len(half) else -1)}")

    ok = True
    for name, df in (("E4", sat_runs), ("E1", runs)):
        flags = [c for c in df if c.startswith("match_")]
        if not flags:
            print(f"{name}: no reference file, not compared")
            continue
        checked = df[flags].dropna()
        good = bool(checked.astype(bool).all().all())
        ok &= good
        print(f"{name}: {len(checked)} rows compared on {', '.join(flags)}: {'all match' if good else 'MISMATCH'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
