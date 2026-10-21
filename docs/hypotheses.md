# Pre-registered hypotheses and analysis plan

Committed before any main experiment (E1–E7) runs. Changing anything here after
main results exist must be reported in the paper as a deviation.

## Primary metric

Items delivered to the nest per run (10,000 steps, ~17 simulated minutes).

Secondary metrics (reported descriptively, plus the confirmatory tests below):
- **Robots lost** per run.
- **Items per robot lost**, per controller and cell: total items delivered divided by
  total robots lost across all seeds. Reported as "not applicable" when no robot was lost
  (always the case for C4).
- **Localisation AUC**: `auc_final`, the AUC of the repellent field at the end of the run
  (marking controllers C2 and C3 only). The full `auc_series` is used only for
  figures over time. `auc_mean` is not used for inference, because it includes early
  samples taken before any robot is lost.

## Hypotheses (spec section 4)

A12(X, Y) is the probability that a run of X scores higher than a run of Y on the named
metric (ties count half), computed with `swarmhazard.stats.a12`.

| ID | Claim | Experiment | Confirmatory test |
|---|---|---|---|
| H1 | C2 delivers more items than C0 | E1 | one-sided Wilcoxon signed-rank on per-seed differences C2 − C0 in items delivered (alternative: greater); effect size A12(C2, C0) |
| H2 | C2 loses fewer robots than C1 | E1 | one-sided Wilcoxon signed-rank on per-seed differences C1 − C2 in robots lost (alternative: greater); effect size A12(C1, C2) |
| H3 | In the random-failure control, C2's item cost relative to C0 is small | E2 (no-hazard level) | non-inferiority: supported if the lower bound of the bootstrap 95% CI of A12(C2, C0) on items delivered is above 0.36 |
| H4 | C3 delivers more items than C2 when the hazard is next to a patch | E1 | one-sided Wilcoxon signed-rank on per-seed differences C3 − C2 in items delivered (alternative: greater); effect size A12(C3, C2) |

**Deviation from spec section 4 (H3):** the spec states H3 as |A12 − 0.5| < 0.14. It is
operationalised as a one-sided bound, because the hypothesis is about a cost: C2 doing
better than C0 in the control does not count against it.

The random-failure mechanism used by E2's no-hazard level is specified below (Random-failure control).

## Statistics

- 100 seeds per cell. Every controller runs every seed of a cell with the same random
  streams (seeded by experiment, cell and seed only), so results are **paired by seed**.
- **Paired tests.** Confirmatory tests use the Wilcoxon signed-rank test on per-seed
  differences: `scipy.stats.wilcoxon(x, y, zero_method="pratt", alternative=..., method="auto")`
  with scipy 1.15.1, where x and y are aligned by seed.
- **Confirmatory family:** H1, H2 and H4, tested on E1 with Holm correction across these
  three tests at α = 0.05. A hypothesis is supported if its Holm-adjusted p-value is below
  0.05. Effect sizes are reported with bootstrap 95% CIs but no A12 threshold is required
  for support.
- H3 is decided only by its CI rule above (not part of the Holm family).
- **Bootstrap:** percentile method, 10,000 resamples, 95% two-sided intervals. The
  resampling unit is the seed: seed indices are drawn with replacement and each drawn
  seed contributes its paired values for every controller. The bootstrap generator is
  `numpy.random.default_rng(20261016)`. Applies to medians, median paired differences
  and A12.
- Reported for each comparison: medians, the median per-seed difference, A12, and their
  bootstrap CIs.
- **Exploratory** (labelled as such): per experiment, Friedman test across controllers
  (the paired counterpart of Kruskal–Wallis), then two-sided Wilcoxon signed-rank tests
  against C2 with Holm correction within that experiment.
- `first_loss_step = -1` means no robot was lost; treat it as missing, never as a number.

## Tuning protocol (spec section 3)

- Tuned at the baseline configuration only, on experiments `tune_c2` and `tune_c3`, whose
  random streams are independent of the gate and of E1–E7.
- C2 grid: repel_weight {0.5, 1, 2, 4} × deposit_sigma {0.2, 0.3, 0.5} × decay {0.0002, 0.0005, 0.002}; 20 seeds per cell.
- C3 grid: risk_k {0.25, 0.5, 1, 2, 4} on top of the chosen C2 values; 20 seeds per cell.
- Selection rule: highest median items delivered; ties → lowest mean robots lost.
- Deviation from spec section 3: the spec lists deposit amount as a tuned parameter. It is fixed at 1 because the repellent push is proportional to deposit_amount × repel_weight, so tuning repel_weight covers it; deposit_sigma (the footprint width), which the spec does not list, is tuned instead. wreck_weight is fixed at 1 because C1 shares it.
- The chosen values are committed to `configs/tuned_params.yaml` before any main experiment runs.
- Every main experiment (E1–E7) loads `configs/tuned_params.yaml` through `overrides_file`.

## Decisions recorded before the main experiments (2026-10-16)

1. **Proceed despite the narrow go/no-go failure.** The week-2 re-check of the
   pre-registered gate (spec section 8; default parameters, 30 seeds) gave
   A12(C2, C0) = 0.629 on items delivered (bootstrap 95% CI 0.49–0.77), just below the
   0.64 threshold, while robots lost showed a large effect (A12(C2, C0) = 0.134, CI
   0.05–0.24). The drop from week 1 (0.673) was checked and is not caused by a code
   defect: the random-stream change gave a fresh sample of starting layouts, and a shift
   of 0.044 is within the sampling error of A12 at 30 seeds (about 0.07). The spec's
   rule (revise the model if the gate fails) is therefore not applied; this is a
   deviation from spec section 8 and will be reported as one. The primary metric is
   unchanged.
2. **Paired analysis.** Confirmatory tests switch from the unpaired Mann–Whitney U to
   the paired Wilcoxon signed-rank test, because the design pairs controllers by seed
   (per-seed items delivered for C0 and C2 at the gate correlate with Spearman ρ = 0.77).
   On the gate data the paired test (as specified above) gives p = 0.0009 against
   p = 0.043 unpaired.
3. **Keep the tuned values.** Performance was flat across the tuning grid: the spread of
   cell means (SD 1.09 items) matches what seed noise alone would give (SE 1.13), and the
   marginal means show no trend in repel_weight or decay. The pre-registered selection
   (repel_weight 0.5, deposit_sigma 0.3, decay 0.0002; risk_k 0.5) is kept, and the paper
   will state that C2's performance was insensitive to these parameters over the grid.

## Experiment levels (spec section 4; addendum `docs/superpowers/specs/2026-10-16-week-3-addendum.md`)

| Exp | Cells, in order |
|---|---|
| E1 | baseline |
| E2 | 0 next to patch (8.81, 6.19); 1 between patch and nest (6.25, 6.25); 2 far from everything (5.0, 9.0); 3 no hazard, random failures |
| E3 | n_robots 5, 10, 20, 40, 80 |
| E4 | lethality 0.005, 0.02, 0.1, 1.0 |
| E5 | radius 0.5 m at (8.4546, 6.5454); 1 m at (8.81, 6.19); 2 m at (9.5153, 5.4847) — the 2 m hazard extends past the east wall; results are read against the in-arena hazard area |
| E6 | n_robots 5, 10, 20, 40, 80 |
| E7 | (q_miss, q_false) = (0, 0); (0.2, 0); (0, 0.00001); (0.2, 0.00001) |

## Random-failure control (E2 cell 3)

No hazards. Every step, each live robot fails independently with probability
q = 0.0000266, wherever it is, leaving a wreck there. q matches C0's mean losses at
baseline in the week-2 go/no-go re-check (4.67 of 20 robots per 10,000-step run):
q = 1 − (1 − 4.67/20)^(1/10000) ≈ 2.66 × 10⁻⁵. Random failures use their own random
stream, so all other randomness is identical to runs without them.

## Week-4 experiments (exploratory; `docs/superpowers/specs/2026-10-19-week-4-addendum.md`)

No confirmatory hypotheses. Analysed with the exploratory tables above (Friedman per
cell, two-sided Wilcoxon vs C2, Holm within each experiment) and descriptive tables.

| Exp | Controllers | Cells, in order |
|---|---|---|
| E6 | C2, C5 | n_robots 5, 10, 20, 40, 80 |
| E7 | C0, C1, C2, C3 | (q_miss, q_false) = (0, 0); (0.2, 0); (0, 0.00001); (0.2, 0.00001) |

- **C5:** each robot keeps its own repellent map, marks it itself, and every 10 steps
  (1 s) takes the cell-wise maximum with the maps of live robots within 1 m
  (synchronous, one hop per exchange). Uses C2's tuned parameters; not tuned itself.
  Localisation AUC uses the mean of the live robots' maps.
- **Known confound in E6:** C2's shared field sums deposits (a wreck seen by k robots peaks near k × deposit_amount), whereas C5 merges maps by element-wise maximum (peaks near deposit_amount), and both use the same untuned repel_weight. C2 therefore pushes harder at well-observed wrecks. E6 compares the two mechanisms as specified, so any C2–C5 difference reflects both where the information is held and how strongly it repels. Localisation AUC is rank-based and unaffected by this scale difference.
- **Misses:** each step, each robot misses each wreck in range with probability q_miss
  (no repulsion and no marking from it that step).
- **False sightings:** each step, each live robot sees a non-existent wreck at its own
  position with probability q_false; marking controllers deposit there.
- C0 is added to E7 as a reference; the base spec listed C1–C3.
- E6 and E7 run from a frozen worktree (`scripts/run_batch.py`). Their simulator code
  differs from E1's; they are accepted only if every golden case recorded at E1's commit
  is unchanged at theirs (C0–C4 behaviour bit-identical).

**Clarification added 2026-10-19, after the E6/E7 batch started (no data examined):** the 'Known confound in E6' bullet above understates C5's deposits. In C5 each robot also adds a full bump when it first sees a wreck itself (its `seen` record is its own), even if it already received that wreck through an exchange, so C5's map values can exceed deposit_amount; C5's exchange itself takes the element-wise maximum. The confound therefore concerns how deposits from several observers combine (sum in the shared field vs max-merge plus own bumps), not a fixed k-to-1 ratio. Rank-based AUC is unaffected by a uniform rescaling, but summing and max-merging can change the relative ranks between wrecks seen by different numbers of robots, so AUC is not strictly unaffected. C5's AUC uses the mean of the live robots' maps, a swarm-level quantity no single robot holds. E7 cells use different random layouts (the seed stream depends on the cell), so comparisons across noise levels are unpaired and not covered by the pre-registered tests; they will be reported descriptively.

## Reproducibility claim

Exact re-runs are claimed on the same machine and software environment (recorded per row).
Across machines, results are expected to agree statistically, not bit for bit.

## Week-5 experiments (exploratory; added 2026-10-20, before any E6b, E7b or E8 data exist; `docs/superpowers/specs/2026-10-20-week-5-addendum.md`)

No confirmatory hypotheses. Nothing above this section is changed. 100 seeds per cell;
parameters from the baseline plus `configs/tuned_params.yaml` (a cell's own value wins).

| Exp | Controllers | Cells, in order | Paired cells |
|---|---|---|---|
| E6b | C2, C5, C6 | n_robots 5, 10, 20, 40, 80 | no |
| E7b | C0, C1, C2, C3 | 0 no noise; 1 q_miss 0.5; 2 q_miss 0.8; 3 q_miss 0.5, miss_run 100; 4 q_miss 0.8, miss_run 100; 5 q_false 0.0001 | yes |
| E8 | C0, C1, C2, C4 | hazard moves at step 5000 to: 0 (8.81, 6.19), i.e. stays (static), decay 0.0002; 1 (1.19, 3.81), decay 0.0002; 2 (1.19, 3.81), decay 0.002 | yes |

- **C6:** as C2, but each robot holds its own set of sighting records (position, observer,
  step), created exactly when C2 would deposit, and every 10 steps (1 s) adds the records
  of live robots within 1 m (set union, synchronous, one hop per exchange). Its map is the
  sum of C2's decayed bumps over the records it knows, so with full propagation it equals
  C2's shared field. C2's tuned parameters; not tuned itself. AUC uses the mean of the live
  robots' maps. C2 vs C6 changes only where the information is held; C5 vs C6 changes only
  how observations combine (max-merge vs sum). C5 remains untuned.
- **Paired cells:** every cell uses cell 0's random streams (`make_rng(name, 0, seed)`), so
  seeds are paired across cells as well as across controllers.
- **Correlated misses (`miss_run` > 0):** each (robot, wreck) pair is blind a fraction
  q_miss of the time, in spells of `miss_run` steps on average (two-state chain; spec
  addendum section 2). `miss_run` = 0 means independent misses as in E7.
- **Hazard move (E8):** at the start of step 5000 the hazard is replaced; wrecks stay where
  they are. The oracle C4 knows the new position at once (and steers out if the hazard
  appears on top of it). Results are split at the move: `delivered_pre`, `lost_pre`,
  `delivered_post`, `lost_post`; `auc_final` is against the new hazard, `auc_pre` and
  `auc_old_final` against the old one.

**Analysis (all exploratory).** Paired two-sided Wilcoxon signed-rank tests (Pratt zeros) and
seed-bootstrap CIs as in the Statistics section, with **Holm correction over every test
within each experiment**, where the tests are the Wilcoxon comparisons in items 1–4
(Friedman p-values are reported alongside, not counted in the Holm family):

1. Within each cell: Friedman across the experiment's controllers, then each controller vs
   C2. Metrics: E6b and E7b `delivered` and `robots_lost`; E8 `delivered_post` and
   `lost_post`.
2. E6b also: C6 vs C5 in every cell, on `delivered` and `robots_lost`.
3. E7b also (across cells, paired by seed): for each of C1, C2 and C3, each of cells 1–5 vs
   cell 0, on `delivered` and `robots_lost`.
4. E8 also (across cells, paired by seed), C2 only: cell 2 vs cell 1 on `delivered_pre`,
   `lost_pre`, `delivered_post` and `lost_post`; cell 1 vs cell 0 on `delivered_post` and
   `lost_post`.

Family sizes: E6b 30 tests, E7b 66, E8 24. Localisation AUC (`auc_final`; in E8 also
`auc_pre` and `auc_old_final`), the number of runs with any mark, `known_frac` (C6) and
`false_sightings` are reported descriptively (medians with bootstrap CIs). Built-in identity
checks are reported, not tested: in E7b every C0 run is identical across cells and C1 is
identical in cells 0 and 5; in E8, C0, C1 and C4 are identical in cells 1 and 2. E6b, E7b and
E8 are accepted only if every golden case recorded at E1's commit is unchanged at their
commit (C0–C5 bit-identical with the new features off).

## Week-6 experiment (exploratory; added 2026-10-21, before any E9 data exist; `docs/superpowers/specs/2026-10-21-week-6-addendum.md`)

No confirmatory hypotheses. Nothing above this section is changed. 100 seeds per cell;
parameters from the baseline plus `configs/tuned_params.yaml` (a cell's own value wins).

| Exp | Controllers | Cells, in order | Paired cells |
|---|---|---|---|
| E9 | C0, C1, C2, C3, C4 | 0 baseline, search_start nest; 1 baseline, last_pickup; 2 hazards [] + random_fail_rate 0.0000266, nest; 3 same, last_pickup; 4 baseline + q_false 0.0001, nest; 5 same, last_pickup | yes |

- **Site fidelity (`search_start: last_pickup`):** after a delivery, a robot with a recorded
  pickup position heads straight to it (state OUTBOUND; wreck and repellent avoidance as in
  RETURN; no pickups) and switches to SEARCH within `sense_range` of it. `search_start: nest`
  is the behaviour of E1–E8 and must be bit-identical to it (golden test unchanged).
- **New observation metrics (descriptive only):** `trip_steps_mean`, `search_steps_mean`,
  `nest_steps` (robot-steps within 1.5 m of the nest centre).

**Candidate mechanism, stated before the data:** the week-5 false-sighting gain and C2's lead
in the random-failure control come from search restarting at the nest. Expected under this
candidate: (a) C2's false-sighting gain is smaller with fidelity; (b) C2's lead over C0 in
the random-failure control is smaller with fidelity; (c) `nest_steps` is lower with fidelity.

**Analysis (all exploratory).** Paired two-sided Wilcoxon signed-rank tests (Pratt zeros) and
seed-bootstrap CIs as in the Statistics section, with **Holm correction over all tests in
items 1–3 together** (Friedman p-values are reported alongside, not in the Holm family):

1. Within each cell: Friedman across C0–C4, then C0, C1, C3 and C4 each vs C2, on `delivered`
   and `robots_lost` (6 cells × 4 × 2 = 48 tests).
2. Fidelity vs nest, per controller (paired by seed): cell 1 vs 0, 3 vs 2 and 5 vs 4 for each
   of C0–C4, on `delivered` and `robots_lost` (3 × 5 × 2 = 30 tests).
3. Interaction tests, on per-seed differences (paired by seed):
   (a) C2's false-sighting gain: (cell 4 − cell 0) vs (cell 5 − cell 1), `delivered`;
   (b) C2's lead in the random-failure control: (C2 − C0 in cell 2) vs (C2 − C0 in cell 3), `delivered`;
   (c) C2's lead over C0 at baseline: (C2 − C0 in cell 0) vs (C2 − C0 in cell 1), `delivered`;
   (d) C1's excess losses over C2 at baseline: (C1 − C2 in cell 0) vs (C1 − C2 in cell 1), `robots_lost` (4 tests).

Family size: 82 tests. Reported descriptively (medians with bootstrap CIs): `delivered`,
`robots_lost`, `auc_final` (C2, C3), runs with any mark, `false_sightings`,
`trip_steps_mean`, `search_steps_mean`, `nest_steps`. Identity checks (reported, not tested):
C0, C1 and C4 are identical in cells 0 and 4, and in cells 1 and 5 (none of them reacts to
false sightings). E9 is accepted only if every golden case recorded at E1's commit is
unchanged at its commit.
