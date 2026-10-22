# Spec: journal package (after arXiv; site-fidelity model)

**Date:** 2026-10-22
**Extends:** all earlier addenda; the main model is site fidelity (week 7).
**Status:** design. The experiments below are pre-registered in `docs/hypotheses.md` only after the
user approves; no data before that.
**Not in this spec:** the physics-simulator replication (limitation #1), which gets its own plan.

All experiments use `configs/tuned_params_fidelity.yaml` (site fidelity, week-7 tuning),
100 seeds per cell, `paired_cells: true`.

## 1. A baseline from the literature: C7, risk-limit alerts (limitation #13)

Hunt, Cullen and Hauert (2021, Proc. SPIE 11758) propose "value at risk" strategies: each robot
tracks its own accumulated risk and, when it exceeds a limit, broadcasts an alert to its
neighbours. Their robots sense hazard exposure directly; ours cannot sense the hazard at all, so
C7 is an **adaptation** that uses the only evidence our robots have, wrecks. The paper must call it
"inspired by", not a reimplementation.

- Each robot keeps a risk score `r`. Each step, `r` decays by the factor (1 − `alert_decay`), and the
  robot adds 1 for each wreck it sees for the first time (the same "first sighting" rule as C2's
  marking, so both use exactly the same evidence).
- When `r ≥ alert_limit`, the robot broadcasts an alert (its own position at that step) to every
  live robot within `comm_range` (1 m), then resets `r` to 0. Alerts are not relayed.
- A robot that holds alerts is repelled from each alert position within `alert_radius` (1 m) for
  `alert_duration` steps after it received it (push weight `repel_weight` scaled by distance as
  for wrecks). There are no marks in the environment and no maps.
- C7 also avoids visible wrecks exactly as C1 does.
- Tuning (pre-registered rule, held-out experiment `tune_c7f`, 20 seeds per cell): `alert_limit`
  ∈ {1, 2, 3}, `alert_duration` ∈ {300, 1000, 3000} steps; `alert_decay` fixed at 0.001.

What C2 vs C7 isolates: persistent marks in the environment versus transient alerts passed between
neighbours, from the same evidence.

**E10** — controllers C0, C1, C2, C7; cells: 0 baseline; 1 hazard between patch and nest
(6.25, 6.25); 2 no hazard + random failures (q = 0.0000266). 1,200 runs.

## 2. Arena size and communication range (limitations #7 and #8)

E6b found no detectable difference between the shared field (C2), per-robot sighting records (C6)
and max-merged maps (C5), probably because information spread to almost every robot in our small
arena. E11 makes spreading harder.

- New config option `arena_scale` (default 1): multiplies the arena size, the nest centre, every
  patch centre and every hazard centre (radii unchanged). With `arena_scale` = 1, runs are
  bit-identical to today (golden test).
- Robot density is kept constant: `n_robots` = 20 × `arena_scale`².

**E11** — controllers C2, C5, C6; cells: 0 scale 1, comm 1 m; 1 scale 1, comm 0.5 m; 2 scale 1,
comm 0.25 m; 3 scale 2 (20 m arena, 80 robots), comm 1 m; 4 scale 2, comm 0.5 m. 1,500 runs.
Also reports `known_frac` (C6).

## 3. Two hazards (limitation #5)

**E12** — controllers C0–C4; cells: 0 one hazard (baseline, next to patch (7.5, 7.5)); 1 two hazards
(baseline plus a mirror image next to patch (2.5, 2.5), at (1.19, 3.81)); 2 two hazards with
lethality 0.1. 1,500 runs. Localisation AUC uses the union of both hazard masks; the descriptive
tables also report AUC against each hazard separately.

## 4. Analysis (to be pre-registered)

Exploratory, as in weeks 5–7: Friedman per cell, two-sided Wilcoxon vs C2 on `delivered` and
`robots_lost`, plus across-cell tests for C2 (each cell vs cell 0), Holm within each experiment.
E10 also: C7 vs C1 on `robots_lost` in every cell (does an alert beat plain avoidance?).

Total: 4,200 runs plus tuning (180 runs).
