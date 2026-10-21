# Spec addendum: week 6 (search restart at the nest, site fidelity, E9)

**Date:** 2026-10-21
**Extends:** the base spec and the 2026-10-16, 2026-10-19 and 2026-10-20 addenda
**Pre-registration:** `docs/hypotheses.md`, section "Week-6 experiment" (exploratory; added before any E9 data exist)

## 1. Why

Week 5 found that ten times more false sightings *raised* C2's deliveries (E7b cell 5: +7
items). Week 6's first check (`scripts/diag_e2_random_wrecks.py`) found the same pattern in
E2's random-failure control: 34% of C2's random wrecks fell within 1.5 m of the nest, and
C2's lead over C0 correlated with them (Spearman ρ = 0.39). Note 05 put this down to
"crowding near the nest", but robots never collide in this model. Reading the code
(`Simulation._deliver`) gives a simpler candidate. After each delivery, a robot gets a
uniformly random heading and restarts its correlated random walk *at the nest*. A random
walk drifts away slowly, so robots spend about 38% of their time within 1.5 m of the nest,
and anything that pushes them outward (here, repellent marks near the nest) shortens their
search. If that is the mechanism, the effect belongs to our foraging model and not to
marking. It may also inflate C2's apparent advantage wherever marks lie near the nest.

E9 tests this by switching on **site fidelity**, the standard alternative in central-place
foraging. After a delivery, the robot heads straight back to where it last picked up an
item, then resumes its random-walk search there.

## 2. Site fidelity (`search_start`)

- New config field `search_start`: `"nest"` (default; today's behaviour) or `"last_pickup"`.
- Each robot records the position where it last picked up an item (`last_pickup`; none at
  the start of a run).
- With `"last_pickup"`, a robot that delivers and has a recorded pickup enters a new state,
  **OUTBOUND**. Each step its heading points at `last_pickup` (no turning noise), and the
  controller's usual wreck and repellent avoidance is added exactly as in RETURN. It leaves
  OUTBOUND for SEARCH when it is within `sense_range` (0.5 m) of `last_pickup`. A robot in
  OUTBOUND does not pick up items. A robot with no recorded pickup goes straight to SEARCH,
  as today.
- The draws from the motion stream stay the same in number and order in both modes (the
  fresh heading is still drawn at every delivery and simply not used when the robot goes
  OUTBOUND). With `"nest"`, runs are bit-identical to week 5, and the golden test must pass
  unchanged.
- A robot that dies while OUTBOUND carries nothing, so `items_lost` is unchanged in meaning.

## 3. New observation metrics (all modes; observation only)

- `trip_steps_mean`: the mean number of steps from pickup to delivery, over the run's deliveries.
- `search_steps_mean`: the mean number of steps from a delivery (or the start of the run) to
  the robot's next pickup. With site fidelity this includes the OUTBOUND leg.
- `nest_steps`: robot-steps spent by live robots within 1.5 m of the nest centre.

These are recorded for every run from week 6 on. They do not change behaviour or the random
streams.

## 4. E9

| Exp | Controllers | Cells, in order | Paired cells |
|---|---|---|---|
| E9 | C0, C1, C2, C3, C4 | 0 baseline, nest; 1 baseline, fidelity; 2 no hazard + random failures, nest; 3 no hazard + random failures, fidelity; 4 baseline + q_false 0.0001, nest; 5 baseline + q_false 0.0001, fidelity | yes |

"Baseline" is E1's configuration (one 1 m hazard next to a patch, lethality 0.02). The
random-failure cells use E2 cell 3's rate (q = 0.0000266, no hazard). 100 seeds per cell;
3,000 runs.

## 5. What would count as support for the candidate mechanism (stated before the data)

If restarting search at the nest drives the week-5 effects, then with site fidelity:

- (a) the false-sighting gain for C2, (cell 4 − cell 0) per seed, is larger than
  (cell 5 − cell 1);
- (b) C2's lead over C0 in the random-failure control, (C2 − C0) per seed, is larger in cell 2
  than in cell 3;
- (c) robots spend less time near the nest (`nest_steps`) in cells 1, 3 and 5 than in 0, 2 and 4.

Robustness of the main findings: if C2 still delivers more than C0 and loses fewer robots
than C1 in cell 1, the H1/H2 pattern does not depend on the search-restart rule.

## 6. Out of scope

Robot–robot collisions; site fidelity in the other experiments; tuning under site fidelity
(C2 keeps its tuned parameters).
