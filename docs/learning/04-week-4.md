# 04 — Week 4: C5, detection noise, and the E6 and E7 experiments

Everything about E6 and E7 in this note is **exploratory**. They were
pre-registered as exploratory in `docs/hypotheses.md`: there are no
confirmatory hypotheses, no p-value here is a confirmatory result, and the
explanations I give are candidates, not things we have verified.

## 1. What was added and why

Three things were added this week.

**Frozen batches.** E6 and E7 needed new simulator code (noise and C5), but E1–E5
had been run with the old code. To keep each experiment tied to the exact code
that produced it, `scripts/run_batch.py` runs a batch from a frozen copy
("worktree") of the repository at one commit. E6 and E7 both ran from commit
5d8ca9e. The analysis script prints a provenance line for each experiment:

```
E2: code 45b4ce5 (simulator identical to fe78c66)
E3: code 4cf295a (simulator identical to fe78c66)
E4: code 4cf295a (simulator identical to fe78c66)
E5: code 4cf295a (simulator identical to fe78c66)
E6: code 5d8ca9e (simulator changed; every golden case from fe78c66 reproduced bit-identically)
E7: code 5d8ca9e (simulator changed; every golden case from fe78c66 reproduced bit-identically)
```

"Bit-identical" here means: every golden test case recorded at E1's commit
gives exactly the same output at 5d8ca9e, and a separate differential check on
six extra configurations also matched. That check was done on one machine only,
so it supports "the old controllers behave the same in the new code", not a
claim across computers.

**Detection noise.** Two new settings, `q_miss` and `q_false`:

- `q_miss`: each step, each robot independently misses each wreck in range with
  probability `q_miss`. A missed wreck gives no repulsion and no marking that step.
- `q_false`: each step, each live robot "sees" a wreck that does not exist, at
  its own position, with probability `q_false`. Controllers that mark leave a
  repellent deposit there.

Because misses are independent from step to step, a wreck that stays in range
for k steps is missed the whole time with probability 0.2^k (for q_miss = 0.2).
So the miss noise is **weak by construction**: mostly a short delay in noticing
a wreck, plus roughly 20% weaker average repulsion from wrecks. It does not make
robots blind to a wreck for long. With q_false = 1e-5 we expected about 2
phantom sightings per 20-robot run; the realised mean is reported below.

**Controller C5.** See the next section.

## 2. How C5 differs from C2

Both are repellent-marking controllers. They differ in where the information
lives:

- **C2:** one shared repellent field. Every robot that sees a wreck adds to the
  same field, so deposits from several observers are **summed**.
- **C5:** each robot keeps its **own** repellent map and marks it itself. Every
  10 steps (1 s), a robot takes the cell-wise **maximum** of its map with the maps
  of live robots within 1 m (synchronous, one hop per exchange). A robot also adds
  its own bump the first time it sees a wreck itself, even if it already learned
  of that wreck through an exchange.

C5 uses C2's tuned parameters but was not tuned itself.

**The confound (a fact about the design).** E6 does not isolate "shared field
versus private maps". The two controllers also combine observations differently
(sum in C2; max-merge plus own bumps in C5), and C5 is untuned. So any C2–C5
difference would reflect the mechanisms as a whole, not the information medium
alone. Also, C5's localisation AUC is the mean of the live robots' maps, which is
a swarm-level quantity that no single robot actually holds. AUC is rank-based, so
a uniform rescaling would not change it, but summing and max-merging can change
the ranking between wrecks seen by different numbers of robots, so AUC is not
strictly immune to the confound either.

## 3. E6 results (exploratory): C2 versus C5 by swarm size

100 seeds per cell, paired by seed. Medians with bootstrap 95% CIs (from
`E6_descriptive.csv`); the AUC is the median final localisation AUC.

| Robots | Delivered C2 | Delivered C5 | Lost C2 | Lost C5 | AUC C2 | AUC C5 |
|---|---|---|---|---|---|---|
| 5 | 12 [12, 13] | 12 [12, 13] | 1 | 1 | 0.5000 | 0.5000 |
| 10 | 23 [22, 24.5] | 23 [22, 24.5] | 1 [1, 2] | 1 [1, 2] | 0.7223 | 0.7218 |
| 20 | 45 [43.5, 46] | 44.5 [43, 46] | 2 | 2 | 0.7672 | 0.7633 |
| 40 | 88 [85.5, 89.5] | 87 [86, 89] | 2 [2, 3] | 3 [2, 3] | 0.8522 | 0.8525 |
| 80 | 165 [162.5, 167] | 166.5 [163, 168] | 3 | 3 | 0.8715 | 0.8713 |

Paired comparison C5 versus C2 (exploratory table, Holm-adjusted over the 10
tests in E6):

- Median paired difference in items delivered is 0 at N = 5, 10, 20 and 40 and 0.5
  at N = 80; the median paired difference in robots lost is 0 at every size.
- The A12 values (chance a C5 run beats a C2 run, 0.5 = no difference) for
  delivered items are 0.497, 0.488, 0.477, 0.463 and 0.522 for N = 5 to 80; all
  the CIs include 0.5 except N = 40 (0.463 [0.428, 0.498]), whose upper end only
  just reaches 0.5.
- The one raw p-value below 0.05 is N = 40 delivered (p = 0.033), which becomes
  Holm p = 0.33. Nothing survives correction.

Plain reading: in this set-up, C5 and C2 are very close at every swarm size. The
figure (`e6_sweep.png`) shows the two lines on top of each other for delivered
items and for robots lost. The only visible gap is at N = 40 for robots lost
(medians 3 against 2), but the CIs overlap and the paired median difference is 0.
Possible candidate explanations for the similarity (not tested): both mechanisms
may spread the same information well enough over these distances, or the
difference between them may be smaller than what 100 seeds can detect. I cannot
tell these apart from this data, and the confound above means "no difference" is
not a clean verdict on shared versus private maps either.

At N = 5 the AUC is exactly 0.5 for both controllers (and also for C2 in E3 at
N = 5). I have not checked why; a candidate is that with 5 robots there is too
little information to rank cells, but that is a guess to verify.

## 4. E7 results (exploratory): detection noise

Four cells: no noise; 20% missed (q_miss = 0.2); false sightings (q_false = 1e-5);
both. Controllers C0, C1, C2, C3 (C0 added as a reference), 100 seeds each.

**How many false sightings happened.** From the `false_sightings_mean` column:
0 in the two cells without false sightings; in the false-sightings cell the means
are 1.81 (C0), 1.92 (C1), 1.93 (C2), 1.93 (C3); in the "both" cell 1.77, 1.83,
1.82, 1.82. So about two per run, as intended. (C0 and C1 do not react to false
sightings by design, so for them the number only says how many occurred.)

**Medians with bootstrap 95% CIs by noise level (descriptive only).** The cells use
different random layouts, so comparisons *across* noise levels are unpaired and are
not covered by any pre-registered test. I report them as medians only and draw no
tested conclusion from them.

| Controller | Metric | No noise | 20% missed | False sightings | Both |
|---|---|---|---|---|---|
| C0 | delivered | 43 [42, 45] | 43 [40.5, 44] | 43 [41.5, 44] | 43 [41.5, 45] |
| C1 | delivered | 45 [44, 46] | 45 [43, 45] | 43 [42, 45] | 45 [43.5, 46] |
| C2 | delivered | 45 [44.5, 46.5] | 45 [43, 47] | 45 [43.5, 46] | 46 [44, 48] |
| C3 | delivered | 45 [44, 47] | 45 [43.5, 47] | 45 [43.5, 46] | 46 [45, 48] |
| C0 | lost | 4 | 4.5 | 4 | 4 |
| C1 | lost | 3 | 3 | 3 | 3 |
| C2 | lost | 2 | 2 | 2 | 2 |
| C3 | lost | 2 | 2 | 2 | 2 |

Final localisation AUC (median) for C2: 0.7545, 0.7618, 0.7655, 0.7392; for C3:
0.7545, 0.7621, 0.7640, 0.7404. The AUC is the medians only here; the spreads
(interquartile ranges, e.g. C2: 0.722–0.846 with no noise, 0.705–0.788 with both)
overlap heavily.

Calibration: C1 is unaffected by false sightings by design, yet its median
delivered is 45 with no noise and 43 in the false-sightings cell. That 2-item
difference is therefore ordinary between-cell variation from different layouts.
Differences of that size across cells should not be read as an effect of noise.
By that yardstick, none of the across-cell changes in the table above is clearly
larger than layout variation. In particular, the "both" cell having the highest
C2 and C3 medians (46) is probably not a benefit of noise; this is a candidate
reading, not something tested.

**Within-cell controller comparisons (exploratory, paired by seed, Holm-adjusted
over the 24 tests in E7).** These are valid comparisons because all controllers in
a cell share seeds.

- C0 versus C2, delivered: C2 is higher in every cell. Median paired differences
  (C0 minus C2) are -1.5, -2, -2 and -3; A12 = 0.397, 0.382, 0.393, 0.351; Holm p
  from 4.8e-06 to 8.9e-04.
- C0 versus C2, robots lost: C0 loses more in every cell (A12 0.84 to 0.93).
- C1 versus C2, robots lost: C1 loses more in every cell (median difference 1,
  A12 0.736 to 0.769, all Holm p below 1.4e-08 in the table).
- C1 versus C2, delivered: only the "both" cell survives correction (median
  difference -2, A12 0.408, Holm p = 0.0067); the other three cells do not.
- C3 versus C2: no difference in any cell (all Holm p equal 1.0, A12 between 0.494
  and 0.506).

In other words, the ordering seen without noise (C2 and C3 lose fewer robots than
C1, which loses fewer than C0) is still there in all three noisy cells. With noise this
weak, that is not surprising and does not show the controllers are robust to
stronger noise.

## 5. Replication checks

These compare medians across different batches that should share a configuration
but use different seeds; they are sanity checks, not tests.

- **E7 cell 0 against E1** (same configuration, C0–C3). Delivered medians: C0 43
  vs 42, C1 45 vs 43, C2 45 vs 45, C3 45 vs 45. Lost medians: C0 4 vs 5, C1 3 vs 3,
  C2 2 vs 2, C3 2 vs 2. Close, with differences of 1 to 2 items and 1 robot, which
  match the layout-to-layout spread seen above. The C2 final AUC is the one
  that differs by more: E7 cell 0 median 0.7545 against E1 0.7956. The
  interquartile ranges overlap (E1 0.723–0.859; E7 0.722–0.846), so this looks
  like seed-to-seed variation, but I have not tested it.
- **E6 N = 20, C2 against E3 N = 20, C2.** Delivered 45 vs 44, lost 2 vs 2, AUC
  0.7672 vs 0.7558. Same picture: close.

## 6. What this means for the paper

Suggested wording only, for discussion with your mentor:

- The week-3 confirmatory results are unchanged. `confirmatory.csv`, regenerated
  this week, has identical values: H1 A12 = 0.6609, H2 A12 = 0.7894, H3 lower CI
  bound = 0.5186, H4 Holm p = 0.1562.
- E6 and E7 are exploratory and should be labelled that way. They were defined
  before the analysis and the E6/E7 batch, and they changed no parameter after the
  results were seen. One clarification to the E6 confound was added on 2026-10-19
  after the batch started but before any data were examined; that dated note in
  `hypotheses.md` should be cited.
- E6: in this set-up, private maps with local exchange (C5) performed about like
  the shared field (C2) at every size. Say this together with the confound
  (different combination rules; C5 untuned; swarm-level AUC), and do not word it as
  "shared and private maps are equivalent".
- E7: with this weak noise, the controller ordering was preserved. Say plainly
  that the noise is weak by construction, and do not claim robustness to
  detection noise in general. Cross-noise-level differences are unpaired and
  descriptive only.
- Reproducibility: bit-identity was checked on one machine only.

## 7. Things to check with your mentor

1. Is it acceptable to describe E6 as a comparison of mechanisms, given that the
   combination rule and tuning differ, or should a follow-up change only one factor
   (for example, tuning C5, or giving it the same summing rule)?
2. Should E7 be repeated with stronger noise (for example, a higher `q_miss` or
   correlated misses) before the paper says anything about robustness? Would a
   paired design across noise levels (same layouts in every cell) be better?
3. Why is AUC exactly 0.5 at N = 5, and does that make AUC uninformative at small
   swarm sizes?
4. The E7 cell-0 AUC for C2 (0.7545) sits below E1's (0.7956). Is seed-to-seed
   variation a sufficient explanation, or is it worth a check?
5. The N = 40 delivered result (raw p = 0.033, Holm p = 0.33) is a typical
   multiple-testing near-miss. Confirm that it should be reported as not
   significant and not followed up as a finding.
6. Whether the paper needs the bit-identity caveat (same machine only) in the
   methods section, and in what words.
