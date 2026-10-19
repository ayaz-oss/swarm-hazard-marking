# Spec addendum: week 4 (C5, E6, E7, frozen batches)

**Date:** 2026-10-19
**Extends:** `docs/superpowers/specs/2026-10-14-swarm-hazard-design.md` and `docs/superpowers/specs/2026-10-16-week-3-addendum.md`
**Pre-registration:** `docs/hypotheses.md` (E6 and E7 are exploratory; their definitions are added there before they run)

## 1. C5: per-robot maps (base spec §3)

- Each robot holds its own repellent grid (same 0.1 m cells as the shared field, float64).
- Marking: the first time a robot detects a given wreck it adds the usual Gaussian bump
  (`deposit_amount`, `deposit_sigma`) to **its own** map only.
- Every map decays by `decay` per step, exactly like the shared field.
- Steering: wreck repulsion as C1/C2 (`wreck_weight`), minus `repel_weight` × the gradient
  of the robot's **own** map, sampled ±`sense_range` around it.
- Sharing: every `share_every` = 10 steps (1 s), each live robot replaces its map with the
  cell-wise maximum of its own map and the maps of live robots within `comm_range` = 1 m.
  The exchange is synchronous (everyone merges what neighbours held before the exchange),
  so information travels one hop per exchange.
- Parameters: C5 uses C2's tuned `repel_weight`, `deposit_sigma` and `decay`; it is not tuned.
- Localisation AUC: computed on the mean of the live robots' maps (all maps if none live).

## 2. Detection noise (base spec §2, E7)

- Misses: each step, for every (robot, wreck) pair, the robot fails to detect that wreck
  with probability `q_miss`. A missed wreck neither repels the robot nor gets marked by it
  that step (it can be detected on a later step).
- False sightings: each step, each live robot "sees" a non-existent wreck at its own
  position with probability `q_false`. Marking controllers (C2, C3 into the shared field;
  C5 into the robot's own map) deposit a bump there. C0, C1 and C4 are unaffected (a
  phantom at the robot's own position has no direction to repel from). Each run reports
  `false_sightings`.
- Noise draws come from a sixth random stream (`rng.spawn(6)`), a fixed number of draws per
  step, so runs with `q_miss = q_false = 0` are bit-identical to week-3 runs.

## 3. Experiments

| Exp | Controllers | Cells (in order) | Seeds |
|---|---|---|---|
| E6 | C2, C5 | n_robots 5, 10, 20, 40, 80 | 100 |
| E7 | C0, C1, C2, C3 | (q_miss, q_false) = (0, 0); (0.2, 0); (0, 0.00001); (0.2, 0.00001) | 100 |

All other parameters from the baseline plus `configs/tuned_params.yaml`. C0 is added to E7 as
a noise-free reference (beyond the base spec's C1–C3). 2,600 runs in total.

## 4. Frozen batches

- `scripts/run_batch.py E6 E7` refuses a dirty tree, checks out HEAD into the git-ignored
  `.batch/<sha>/` worktree, runs the golden test there (and refuses if it fails), then runs
  each experiment from the worktree with its `src/` first on `PYTHONPATH`, writing to this
  checkout's `results/`. It keeps Windows from idle-sleeping while it runs and removes the
  worktree on success.
- Every result row records `package_root` (where `swarmhazard` was imported from).

## 5. Analysis provenance across code versions

`scripts/analyse.py` requires E1–E7. An experiment whose simulator code differs from E1's
is accepted only if every golden case recorded at E1's commit is present and identical in
`tests/data/golden.json` at the experiment's commit (the batch runner has verified the
golden test passes at that commit). This pins C0–C4 behaviour bit for bit across versions.

## 6. Deferred tests and guards

Tests: double hit counted once; random-failing carrier counted in `items_lost`; first loss
from random failure; wall-clipped hazard area; exact experiment levels; non-vacuous C3
tests; smoke tests for `descriptive` and `exploratory`. Guards: seed identity in the
completeness check; `risk_k ≥ 0`, `metric_every ≥ 1`, `share_every ≥ 1`,
`comm_range ≥ 0`, `q_miss`, `q_false` in [0, 1].
