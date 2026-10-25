"""Pre-registered analysis of the Webots replication W1 (docs/hypotheses.md, "Webots physics
replication"): H1W (C2 delivers more than C0) and H2W (C2 loses fewer robots than C1), one-sided
paired Wilcoxon (Pratt), Holm across the two; A12 and seed-bootstrap CIs. Descriptive: medians with
CIs per controller, C4 vs C2, C2's AUC and repellent_in_hazard, push_steps, trip/search times, and
a side-by-side comparison with E1F (unpaired across simulators).

Usage: python scripts/analyse_webots.py [W1_CSV] [E1F_CSV]
Writes results/analysis/webots/{confirmatory_W.csv, W1_descriptive.csv, W1_vs_E1F.csv}.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from swarmhazard.analysis import BOOT_SEED, N_BOOT, compare, holm, paired, wilcoxon_p  # noqa: E402

CONTROLLERS = ["C0", "C1", "C2", "C4"]
HYPOTHESES = (("H1W", "delivered", "C2", "C0"), ("H2W", "robots_lost", "C1", "C2"))


def completeness_problems(df: pd.DataFrame, seeds: int = 100) -> list[str]:
    problems = []
    if df.duplicated(["controller", "seed"]).any():
        problems.append("duplicate (controller, seed) rows")
    for c in CONTROLLERS:
        got = set(df.loc[df["controller"] == c, "seed"])
        missing = sorted(set(range(seeds)) - got)
        if missing:
            problems.append(f"{c}: {len(missing)} seeds missing")
    if "steps" in df and (df["steps"] != 10000).any():
        problems.append("some runs did not complete 10,000 steps")
    return problems


def confirmatory_w(df: pd.DataFrame, rng: np.random.Generator, n_boot: int = N_BOOT) -> pd.DataFrame:
    df = df.assign(cell=0)
    rows = []
    for hyp, metric, a, b in HYPOTHESES:
        x, y = paired(df, metric, a, b)
        row = compare(x, y, rng, n_boot)
        row.update(hypothesis=hyp, metric=metric, x=a, y=b, p=wilcoxon_p(x, y, "greater"))
        rows.append(row)
    for row, p in zip(rows, holm([r["p"] for r in rows])):
        row["p_holm"] = float(p)
        row["supported"] = bool(p < 0.05)
    return pd.DataFrame(rows)


def _median_ci(values, rng, n_boot):
    v = np.asarray(values, float)
    v = v[~np.isnan(v)]
    if len(v) == 0:
        return np.nan, np.nan, np.nan, 0
    idx = rng.integers(0, len(v), size=(n_boot, len(v)))
    lo, hi = np.percentile(np.median(v[idx], axis=1), [2.5, 97.5])
    return float(np.median(v)), float(lo), float(hi), int(len(v))


def descriptive_w(df: pd.DataFrame, rng: np.random.Generator, n_boot: int = N_BOOT) -> pd.DataFrame:
    cols = ["delivered", "robots_lost", "auc_final", "repellent_in_hazard", "push_steps",
            "trip_steps_mean", "search_steps_mean", "nest_steps"]
    rows = []
    for c in CONTROLLERS:
        sub = df[df["controller"] == c]
        row = {"controller": c, "n": len(sub)}
        for col in cols:
            if col in sub:
                m, lo, hi, n = _median_ci(sub[col], rng, n_boot)
                row.update({f"{col}_median": m, f"{col}_lo": lo, f"{col}_hi": hi, f"{col}_n": n})
        if "auc_final" in sub:
            row["marked_runs"] = int((sub["auc_final"].notna() & (sub["auc_final"] != 0.5)).sum())
        rows.append(row)
    return pd.DataFrame(rows)


def c4_vs_c2(df: pd.DataFrame, rng: np.random.Generator, n_boot: int = N_BOOT) -> pd.DataFrame:
    df = df.assign(cell=0)
    rows = []
    for metric in ("delivered", "robots_lost"):
        x, y = paired(df, metric, "C4", "C2")
        row = compare(x, y, rng, n_boot)
        row.update(metric=metric, x="C4", y="C2", note="descriptive")
        rows.append(row)
    return pd.DataFrame(rows)


def vs_e1f(w1: pd.DataFrame, e1f: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for c in CONTROLLERS:
        a, b = w1[w1["controller"] == c], e1f[e1f["controller"] == c]
        rows.append({"controller": c,
                     "webots_delivered_median": float(a["delivered"].median()),
                     "e1f_delivered_median": float(b["delivered"].median()),
                     "webots_lost_median": float(a["robots_lost"].median()),
                     "e1f_lost_median": float(b["robots_lost"].median())})
    return pd.DataFrame(rows)


def main(argv: list[str]) -> int:
    w1_path = Path(argv[1]) if len(argv) > 1 else ROOT / "results" / "W1.csv"
    e1f_path = Path(argv[2]) if len(argv) > 2 else ROOT.parent / "Research Project" / "results" / "E1F.csv"
    w1 = pd.read_csv(w1_path)
    problems = completeness_problems(w1)
    for p in problems:
        print("PROBLEM:", p)
    if problems:
        return 1
    rng = np.random.default_rng(BOOT_SEED)
    out = ROOT / "results" / "analysis" / "webots"
    out.mkdir(parents=True, exist_ok=True)
    conf = confirmatory_w(w1, rng)
    conf.to_csv(out / "confirmatory_W.csv", index=False)
    pd.concat([descriptive_w(w1, rng)]).to_csv(out / "W1_descriptive.csv", index=False)
    c4_vs_c2(w1, rng).to_csv(out / "W1_C4_vs_C2.csv", index=False)
    if e1f_path.exists():
        vs_e1f(w1, pd.read_csv(e1f_path)).to_csv(out / "W1_vs_E1F.csv", index=False)
    pd.set_option("display.width", 200)
    print(conf[["hypothesis", "x", "y", "median_x", "median_y", "median_diff", "median_diff_lo",
                "median_diff_hi", "a12", "a12_lo", "a12_hi", "p", "p_holm", "supported"]].round(4)
          .to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
