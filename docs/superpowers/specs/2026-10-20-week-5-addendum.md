# Spec addendum: week 5 (C6, paired noise cells, a moving hazard, mechanism checks)

**Date:** 2026-10-20
**Extends:** `docs/superpowers/specs/2026-10-14-swarm-hazard-design.md`, `2026-10-16-week-3-addendum.md` and `2026-10-19-week-4-addendum.md`
**Pre-registration:** `docs/hypotheses.md`, section "Week-5 experiments" (E6b, E7b and E8 are exploratory; their definitions are added there before any of their data exist)

Week 5 answers four objections a reviewer is likely to raise against the week-3/4 results:

| Objection | Answer this week |
|---|---|
| (a) E6 changes two things at once: C2 sums deposits, C5 max-merges, and C5 is untuned | **E6b** with a new controller C6 that differs from C2 in one factor only (where the information is held) |
| (b) E7's misses are weak by construction (independent per step) and its cells use different layouts | **E7b**: much stronger and correlated misses, more false sightings, and cells paired by seed (same layouts in every cell) |
| (c) The value of the field's decay is untested (a static hazard never makes old marks wrong) | **E8**: the hazard moves once, half-way through; two decay levels for C2 |
| (d) Two explanations in the week-3 note are untested: E4 saturation, and the AUC staying at 0.5 until ~300 s | **Mechanism checks**: small descriptive runs, no new pre-registration needed |

Every new feature defaults OFF. With the defaults, C0–C5 behave bit-identically to E1's
commit (fe78c66): every existing golden case must pass unchanged, and new features get new
golden cases through `scripts/make_golden.py --add`.

## 1. C6: shared sighting records (base spec §3; for E6b)

**Why C6.** E6 compared C2 (one shared field, deposits summed) with C5 (private maps,
max-merged, untuned). Any difference would mix three factors. C6 keeps C2's arithmetic
exactly and changes only where the information is held: each robot holds its own copy of
the information and passes it on only to robots near it.

- A **sighting record** is (position, observer, step). A record is created exactly when C2
  would deposit: the first time a robot detects a given wreck (the same `seen` rule as C2),
  and for each false sighting (at the robot's own position).
- Each robot knows a set of records. It knows a record it created from that step on.
- **Sharing:** every `share_every` = 10 steps (1 s), each live robot adds to its set every
  record known by live robots within `comm_range` = 1 m (set union; synchronous, so
  information travels one hop per exchange; same timing and neighbourhood rule as C5).
  Dead robots neither send nor receive.
- **Robot i's map** is the sum, over the records it knows, of C2's Gaussian bump
  (`deposit_amount`, `deposit_sigma`, the same 0.1 m grid cells and 3σ cut-off) times
  (1 − `decay`)^(age in steps). This is exactly the sum C2's shared field holds, restricted
  to the records robot i knows. **If every robot knew every record, every robot's map
  would equal C2's shared field** (up to floating-point rounding, because the sum is
  formed in a different order). A test checks this.
- Steering: wreck repulsion as C1/C2 (`wreck_weight`), minus `repel_weight` × the gradient
  of the robot's own map, read with the same central difference (±`sense_range`) as C2.
- Parameters: C2's tuned `repel_weight`, `deposit_sigma` and `decay`. C6 needs no tuning
  of its own: with full propagation it *is* C2, so C2's tuned values are its natural
  reference. `share_every` and `comm_range` are C5's values.
- Localisation AUC: the mean of the live robots' maps (as C5; all maps if none live).
- New result key for C6 runs: `known_frac`, the mean over live robots of the fraction of
  all records they know at the end of the run (1.0 = full propagation, i.e. C2's field).
- Implementation: a robot's map is never stored as a grid. The simulator keeps the record
  list and a boolean knowledge matrix (robots × records); the steering reads each robot's
  map only at its four gradient sample points. Records at the same position share one bump.

**What E6b can and cannot say.** C2 vs C6 isolates the information medium (shared field vs
private copies passed between neighbours) with everything else equal. C5 vs C6 isolates the
combination rule (max-merge plus own bumps vs summed records), with the medium equal. C5 is
still untuned; E6b does not tune it. C6's AUC, like C5's, is a swarm-level quantity no
single robot holds.

## 2. Paired cells and stronger detection noise (base spec §2; for E7b)

**Paired cells (opt-in).** An experiment file may set `paired_cells: true`. Then every cell
seeds its random streams as cell 0 does (`make_rng(name, 0, seed)`), so cells differ only in
their parameters: same item layouts, start positions, motion noise, respawns, hazard draws
and noise draws. Comparisons *across* cells are then paired by seed. Each row records
`rng_cell`. Without the key nothing changes (the job dicts are identical to before).

Consequences that serve as built-in checks: C0 ignores wrecks, so in E7b every C0 run is
identical across all cells; C1 ignores false sightings, so C1 is identical in cells 0 and 5.
In E8, C0, C1 and C4 do not use the field, so they are identical in cells 1 and 2.

**Correlated misses (opt-in).** New parameter `miss_run` (mean length, in steps, of a blind
spell). `miss_run = 0` (default) keeps the existing independent misses exactly. With
`miss_run > 0`, each (robot, wreck) pair is a two-state chain, updated every step from one
uniform draw per pair:

- blind → blind with probability 1 − 1/`miss_run`;
- seeing → blind with probability `q_miss` / (`miss_run` × (1 − `q_miss`)).

So a pair is blind a fraction `q_miss` of the time (the stationary probability), in spells
lasting `miss_run` steps on average. The chain starts in its stationary distribution (the
first step's draws decide blind with probability `q_miss`). It uses exactly as many noise
draws per step as independent mode. Valid only if `q_miss` < 1, `miss_run` ≥ 1 and the
entry probability is ≤ 1 (`miss_run` ≥ `q_miss`/(1 − `q_miss`)).

Why `miss_run` = 100 steps (10 s): a robot moving at 0.1 m/s takes about 10 s to cross the
1 m-wide sensing disc around a wreck, so a blind spell typically lasts a whole pass. With
independent misses (week 4), even `q_miss` = 0.8 would miss a wreck for a whole 100-step pass
with probability 0.8^100 ≈ 2 × 10⁻¹⁰, i.e. only a delay.

**More false sightings.** `q_false` = 0.0001 gives about 20 phantom sightings per 20-robot run
(10× week 4).

## 3. A moving hazard (base spec "future work"; for E8)

- New parameters `hazard_move_step` (default −1 = never) and `hazards_after` (default
  empty). At the start of step `hazard_move_step`, the hazards are replaced by
  `hazards_after`. The failure rule and the oracle use the new hazards from that step on;
  the localisation mask is recomputed. Wrecks stay where they died, so their wreck repulsion
  and any marks around them are now stale.
- Patches may not overlap `hazards_after` (same check as `hazards`). `hazards_after`
  without a move step is an error.
- **Oracle escape.** When the hazard appears on top of a C4 robot, C4 would otherwise be
  stuck (it refuses every move into a hazard). Rule: a C4 robot that is inside a hazard
  steers straight away from the nearest hazard centre, and only moves *into* a hazard from
  outside are blocked. When no C4 robot is inside a hazard (always, before week 5) nothing
  changes; the golden cases confirm this.
- New result keys, present only when a move is configured: `delivered_pre`, `lost_pre`
  (counts at the moment of the move), `delivered_post`, `lost_post` (the rest of the run),
  `first_loss_post_step` (first loss at or after the move, −1 if none), `auc_pre` (map
  against the old hazard at the move) and `auc_old_final` (map against the old hazard at
  the end; how much stale information remains). `auc_final` is against the new hazard.
  The AUC keys are NaN for controllers without a map.
- **New position:** (1.19, 3.81), radius 1 m: the baseline hazard (8.81, 6.19) reflected
  through the nest centre (5, 5). It sits beside the (2.5, 2.5) patch with the same 0.1 m
  gap, at the same distance from the nest and the same distance from the walls, so the
  hazard before and after the move is equally hard.
- **Decay levels for C2:** the tuned 0.0002 per step (half-life ≈ 3,466 steps ≈ 347 s) and
  0.002 (half-life ≈ 347 steps ≈ 35 s), a value on the week-2 tuning grid, where C2's
  baseline performance did not differ detectably from the tuned value.
- A static cell "moves" the hazard to where it already is, so it has the same pre/post
  columns with nothing physically changed.

## 4. Experiments

| Exp | Controllers | Cells (in order) | Seeds | Paired cells | Runs |
|---|---|---|---|---|---|
| E6b | C2, C5, C6 | n_robots 5, 10, 20, 40, 80 | 100 | no | 1,500 |
| E7b | C0, C1, C2, C3 | 0 no noise; 1 q_miss 0.5; 2 q_miss 0.8; 3 q_miss 0.5, miss_run 100; 4 q_miss 0.8, miss_run 100; 5 q_false 0.0001 | 100 | yes | 2,400 |
| E8 | C0, C1, C2, C4 | move at step 5000 to: 0 the same place (static), decay 0.0002; 1 (1.19, 3.81), decay 0.0002; 2 (1.19, 3.81), decay 0.002 | 100 | yes | 1,200 |

All other parameters from the baseline plus `configs/tuned_params.yaml` (a cell's `decay`
overrides the tuned value). 5,100 runs. Batches run from a frozen worktree with
`scripts/run_batch.py ... --workers 4`, results in this checkout's `results/`.

Why these controllers: E7b keeps E7's set (C0 as a reference). E8 drops C3 (H4: no detectable
difference from C2) and adds C4, which knows the new position at once (the best case after
a move). E6b keeps C5 so all three mechanisms share seeds.

## 5. Analysis (`scripts/analyse_week5.py`)

Statistics as in `docs/hypotheses.md` (paired Wilcoxon signed-rank, Pratt zeros, two-sided;
seed bootstrap with 10,000 resamples and generator seed 20261016; Holm). All exploratory.

- **Within cells**, per experiment: Friedman across controllers, then each controller vs C2.
  Metrics: E6b and E7b `delivered`, `robots_lost`; E8 `delivered_post`, `lost_post`.
- **Extra pre-specified comparisons:**
  - E6b: C6 vs C5 in every cell (`delivered`, `robots_lost`).
  - E7b (paired cells): for each of C1, C2, C3, every noisy cell (1–5) vs cell 0
    (`delivered`, `robots_lost`).
  - E8 (paired cells), C2 only: cell 2 vs cell 1 (`delivered_pre`, `lost_pre`,
    `delivered_post`, `lost_post`) and cell 1 vs cell 0 (`delivered_post`, `lost_post`).
- **Holm within each experiment**, over every test in that experiment (within-cell and
  extra together).
- Descriptive tables per cell and controller (medians with bootstrap CIs; AUC medians and
  the number of runs with any mark; E8 pre/post columns, `auc_pre`, `auc_old_final`;
  E6b `known_frac` for C6).
- Provenance and completeness: as `scripts/analyse.py` (every golden case recorded at
  E1's commit fe78c66 unchanged at the batch commit; frozen package root; full seed sets;
  tuned parameters and baseline lines unchanged). For paired-cell experiments, the
  built-in identities in §2 are checked and reported.

## 6. Mechanism checks (descriptive; no pre-registration needed)

`scripts/mechanism_checks.py` steps the simulator and only observes it (no simulator
change). Both checks re-run existing main-experiment streams, so their outcomes can be
compared row by row with the existing CSVs as a check that observing changed nothing.

1. **E4 saturation.** C0 with E4's streams (`make_rng("E4", cell, seed)`), seeds 0–19, at the
   four E4 lethalities, plus lethality 0 (cell 1's streams) for natural hazard visits. A
   *visit* is a maximal run of consecutive steps a live robot spends inside the hazard. Per
   visit: length and whether it ended in death. Reported: the distribution of natural
   visit lengths; the death fraction per visit predicted from it, mean of 1 − (1 − p)^L; the
   observed death fraction per visit at each p; entries per run. Saturation is supported if
   the predicted and observed per-visit death fractions are close to 1 at p ≥ 0.1, so that
   losses are bounded by how many robots enter.
2. **AUC delay.** C2 with E1's streams, seeds 0–29, AUC sampled every 10 steps (sampling
   does not affect behaviour). Per run: first loss step, first step with any repellent on
   the field (first mark) and first step the AUC leaves 0.5. Reported: medians of these, the
   fraction of runs marked over time, and the median AUC curve at 10-step resolution next to
   the 500-step one. Candidate explanation to check: the median AUC stays at 0.5 until more
   than half of the runs have a mark, and marks need a second robot to come within 0.5 m
   of a wreck, which can take long after the first loss.

Outputs go to `results/mechanism/` (git-ignored); the write-up is section 1 of
`docs/learning/05-week-5.md`.

## 7. Out of scope

Tuning C5 or C6; several moves or a continuously moving hazard; noise in the AUC metric;
physics simulators.
