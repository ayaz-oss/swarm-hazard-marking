# Spec addendum: week 3 (main experiments E1–E5)

**Date:** 2026-10-16
**Extends:** `docs/superpowers/specs/2026-10-14-swarm-hazard-design.md` (the base spec stays authoritative where this addendum is silent)
**Pre-registration:** `docs/hypotheses.md` (authoritative for statistics)

## 1. Random-failure control (base spec §2, E2 no-hazard level)

- No hazards. Every step, each live robot fails independently with probability
  `random_fail_rate` = 0.0000266, wherever it is, and becomes a wreck there.
- The rate matches C0's mean losses at baseline in the week-2 go/no-go re-check
  (4.67 of 20 robots per 10,000-step run): q = 1 − (1 − 4.67/20)^(1/10000) ≈ 2.66 × 10⁻⁵.
- Random failures draw from a fifth random stream (`rng.spawn(5)`; the first four children
  are unchanged), one draw per robot per step, so runs with rate 0 are bit-identical to
  week-2 runs.
- `random_fail_rate` defaults to 0 and must lie in [0, 1].

## 2. Experiment levels

All main experiments: controllers C0–C4, 100 seeds per cell, parameters from
`configs/tuned_params.yaml` via `overrides_file`, everything else from the baseline.

| Exp | Cells (in order) |
|---|---|
| E1 | baseline only |
| E2 | 0 next to patch (8.81, 6.19); 1 between patch and nest (6.25, 6.25); 2 far from everything (5.0, 9.0); 3 no hazard, random failures — all radius 1 m |
| E3 | n_robots 5, 10, 20, 40, 80 |
| E4 | lethality 0.005, 0.02, 0.1, 1.0 |
| E5 | radius 0.5 m at (8.4546, 6.5454); 1 m at (8.81, 6.19); 2 m at (9.5153, 5.4847) |

E5 rule: the hazard edge sits 0.1 m from the (7.5, 7.5) patch edge, in the baseline
direction (1, −1)/√2. The 2 m hazard extends past the east wall; each run reports the
hazard area inside the arena (`hazard_area`, m²) and E5 results are read against it.

The between-patch-and-nest hazard leaves only 0.02 m clear of both the patch and the nest
edges (geometry forces this for a 1 m radius).

## 3. Speed

- A golden test fixes the exact output of four short runs (C0, C2, C3, C4). Every speed
  change must keep it passing bit for bit; a change that breaks it is dropped.
- Changes: a cheaper vector-length helper with identical arithmetic, and a pick-up step
  that computes distances once and only re-checks robots after an item has moved.
- The runner defaults to 4 worker processes (measured fastest on the development laptop).

## 4. Analysis and figures

- `swarmhazard.analysis` implements `docs/hypotheses.md`: paired Wilcoxon signed-rank
  (Pratt zero handling), Holm across H1/H2/H4, H3 by its bootstrap rule, exploratory
  Friedman + two-sided Wilcoxon vs C2 with Holm within each experiment, seed-resampling
  percentile bootstrap (10,000 resamples, generator seed 20261016).
- `scripts/analyse.py` writes CSV tables to `results/analysis/`; `scripts/make_figures.py`
  writes PNG and PDF figures to `results/figures/`. Both only read result CSVs.
- Figures: E1 box plots (items delivered, robots lost); E2 by placement; E3–E5 sweeps
  (median with interquartile band); localisation AUC over time for C2/C3 in E1.
  Colour-blind-safe Okabe–Ito palette, one colour per controller across all figures.

## 5. Runs

E1 first, then E2–E5, sequentially, 4 workers, laptop kept awake; ~8,500 runs. Each
experiment is smoke-tested (1 seed, 200 steps) before the full batch. Results are
analysed only after all five finish.

## 6. Out of scope (week 4)

C5 (per-robot maps), E6, E7 (detection noise), the moving-hazard option.
