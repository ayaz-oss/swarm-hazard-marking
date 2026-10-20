# 05 — Week 5: mechanism checks, and E6b, E7b and E8

Section 1 is two small **descriptive** checks of explanations that note 03 left
as untested candidates (its "things to check" items 8 and 9). They are not
hypothesis tests: there are no p-values, the seed counts are small (20 per
lethality for the first check, 30 for the second), and they were set up as
descriptive checks in the week-5 addendum (section 6), not pre-registered. All
numbers below are copied from the CSV files in `results/mechanism/`, written by
`scripts/mechanism_checks.py`.

## 1. Mechanism checks

### How the checks work, and why I trust that they changed nothing

The script does not change the simulator. It re-runs runs we already had, with
the same configuration and the same random streams, and only watches them step
by step:

- **Saturation:** C0 with E4's random streams, seeds 0–19, at E4's four
  lethalities (0.005, 0.02, 0.1, 1.0 per step), plus a fifth set at lethality 0
  on the same layouts as the 0.02 cell, to see how robots move through the hazard
  when nothing kills them ("natural" visits).
- **AUC delay:** C2 with E1's random streams, seeds 0–29, with the localisation
  AUC sampled every 10 steps (1 s) instead of every 500 steps (50 s). Sampling
  the AUC does not change what the robots do.

Because these are the same runs, their results should be identical to the rows
in `E4.csv` and `E1.csv`. They were: all 80 E4 rows (4 lethalities × 20 seeds)
matched on items delivered, robots lost and first-loss step, and all 30 E1 rows
matched on those three plus the 500-step AUC series. So watching the runs did
not change them. (This was checked on one machine only, like the golden test.)

A **visit** is a stretch of consecutive steps that a live robot spends inside
the hazard at the moment the simulator checks for failures. A visit ends when the
robot leaves or dies.

### 1a. E4 saturation (C0, 20 seeds per lethality)

Note 03's candidate: above lethality 0.1, almost every robot that enters the
hazard dies, so losses are limited by how many robots enter rather than by the
lethality.

First, natural visits (lethality 0). A run had 14.35 visits on average, made by
5.1 different robots. The median visit lasted 86 steps (8.6 s), with an
interquartile range of 29 to 235 steps. So note 03's guess of "on the order of
100 or more steps" is about right for a typical visit, but a quarter of visits
last 29 steps or fewer (perhaps robots clipping the edge; not checked).

From these natural lengths I predicted the chance that a visit ends in death at
each lethality p, as the mean of 1 − (1 − p)^L over the visit lengths L, and
compared it with what happened:

| Lethality | Visits per run | Robots entering per run | Median visit length [IQR], steps | Death fraction per visit: predicted | observed | Mean robots lost | Lost per robot that entered |
|---|---|---|---|---|---|---|---|
| 0 | 14.35 | 5.1 | 86 [29, 235] | 0 | 0 | 0 | 0 |
| 0.005 | 9.8 | 5.75 | 45.5 [21.5, 102] | 0.408 | 0.378 | 3.7 | 0.643 |
| 0.02 | 5.8 | 4.7 | 22 [9, 42] | 0.699 | 0.724 | 4.2 | 0.894 |
| 0.1 | 6.95 | 6.35 | 6 [3, 13] | 0.911 | 0.906 | 6.3 | 0.992 |
| 1.0 | 5.55 | 5.55 | 1 [1, 1] | 1.000 | 1.000 | 5.55 | 1.000 |

(Visit lengths at p > 0 are cut short by deaths, which is why they shrink.)

What this shows, descriptively:

- At p = 0.1, 0.906 of visits ended in death, and 0.992 of the robots that
  entered the hazard were lost (6.3 lost against 6.35 entering per run). At
  p = 1.0 every visit ended in death on its first step, and robots lost equals
  robots entering (5.55). So at p ≥ 0.1, in these runs, losses were essentially
  the number of robots that went in. This is what the saturation candidate
  predicts.
- At p = 0.005 it is different: robots entered more than once (9.8 visits by
  5.75 robots) and only 0.643 of entering robots were lost, so there the
  lethality still matters.
- The predicted death fractions from the natural visit lengths are close to the
  observed ones at every lethality (within about 0.03). So the simple picture
  "a robot's chance of dying is set by how long it stays inside" fits these runs.

What it does not show:

- E4's cells were not paired: each lethality has its own layouts and random
  streams. The number of robots entering per run varies from 4.7 to 6.35 between
  cells, and that is a candidate explanation for why C0's mean losses were a bit
  lower at 1.0 than at 0.1 (here 5.55 against 6.3; note 03 saw the same small
  dip). I have not checked that; it would need the same layouts at every
  lethality.
- The predictions use natural visit lengths from one cell's layouts (the 0.02
  cell's) for every lethality.
- Only C0 was checked, with 20 seeds per lethality. It says nothing directly
  about why C2 and C3 are flat across lethality.

### 1b. Why the median AUC stays at 0.5 for so long (C2, 30 seeds)

The puzzle from note 03: in E1, the median C2 localisation AUC is exactly 0.5
until about 300 s, although the median first loss (over all 100 seeds) is at
step 1605, about 160 s. The candidate: the median is 0.5 while fewer than half
the runs have any mark at all, and a mark needs a live robot to come within
0.5 m (the sensing range) of a wreck, which can happen long after the loss.

Per run, I recorded the first-loss step, the first step with any repellent on
the field (first mark), and the first 10-step AUC sample that is not 0.5.

Medians over the 30 runs:

- first loss: step 2092 (209.2 s). These 30 seeds lose their first robot later
  than the full 100 seeds did, so their timings are not the same as note 03's.
- first mark: step 3908.5 (about 391 s).
- AUC first leaves 0.5: step 3915 (391.5 s).

Two things stand out:

1. **Once a run has a mark, its AUC leaves 0.5 straight away.** In all 29 runs
   with a mark, the AUC moved away from 0.5 at the next 10-step sample (1 to 10
   steps after the first mark; median 6). So there is no extra delay *inside* a
   run between marking and the map showing something. Note 03's candidate
   ("a delay before the map separates the hazard from its surroundings") is not
   what these runs show.
2. **The delay is between the first loss and the first mark.** Per run, the first
   mark came a median of 1137 steps (about 114 s) after the first loss
   (interquartile range 717 to 2375 steps; range 0 to 6682). Every run lost at
   least one robot, but one run (seed 9) never marked anything in 10,000 steps.

The median curve over time, next to the fraction of runs that had a mark and the
fraction that had lost a robot (from `auc_delay_curve.csv`):

| Step (time) | Median AUC | Fraction of runs marked | Fraction of runs with a loss |
|---|---|---|---|
| 2000 (200 s) | 0.5 | 0.167 | 0.5 |
| 3000 (300 s) | 0.5 | 0.333 | 0.7 |
| 3500 (350 s) | 0.5 | 0.4 | 0.8 |
| 3700 (370 s) | 0.5 | 0.467 | 0.8 |
| 3710 (371 s) | 0.598 | 0.5 | 0.833 |
| 4000 (400 s) | 0.598 | 0.5 | 0.867 |
| 4120 (412 s) | 0.699 | 0.533 | 0.9 |
| 4500 (450 s) | 0.713 | 0.633 | 0.9 |
| 5000 (500 s) | 0.745 | 0.8 | 0.933 |

The median AUC stays at exactly 0.5 until step 3700, when 14 of the 30 runs are
marked. At step 3710 the 15th run gets its mark: with 30 runs, the median is the
average of the 15th and 16th values, so it rises to 0.598 as soon as half the
runs are marked. At step 4120 the 16th run is marked and the median jumps again,
to 0.699. With the usual 500-step sampling, the first sample above 0.5 for these
seeds is step 4000 (400 s), so the jump looks like a single step.

What this shows, descriptively: in these 30 runs, the step shape of the median
AUC curve comes from the median switching from unmarked runs (AUC exactly 0.5) to
marked runs, which happens when half the runs have a mark. The flat start and the first
jump are a property of taking the median over runs, not a slow improvement of the
map inside each run. The later rise (median AUC from 0.598 to 0.745 by step 5000)
may mix more runs being marked with maps improving within runs; this check did not
separate the two.
Half of the runs had lost a robot by step 2000, but half had a mark only by step
3710.

What it does not show: *why* the first mark comes so long after the first loss.
In the code, a robot only marks a wreck it sees within 0.5 m, so some other robot
has to come close to the wreck first. That this explains the 114 s median gap is
still a candidate; I did not measure when robots first came within 0.5 m of each
wreck. One run (seed 20) marked in the same step as its first loss, which fits
the idea (a robot was presumably nearby), but one run is not evidence.

### What this changes for the paper

Suggested wording only, for discussion with your mentor:

- **E4 discussion.** Instead of "a likely explanation, which we did not test", the
  paper can say that a descriptive check (C0, 20 seeds per lethality, not a test)
  found that at lethality 0.1 and 1.0 nearly every robot that entered the hazard
  was lost (0.992 and 1.000 per robot that entered), so losses were bounded by
  how many robots entered. Add that E4's cells use different layouts.
- **AUC-over-time figure.** The caption should say (in a 30-seed descriptive check) that the median AUC is exactly
  0.5 while fewer than half of the runs have any mark, so the flat start and the
  jump are a feature of the median over runs, not of the maps' quality. It may be
  worth showing the fraction of runs marked next to the curve.
- Nothing confirmatory changes. No simulator code changed; the re-runs matched
  the stored results row by row.

### Things to check with your mentor

1. Can these descriptive checks be cited in the paper, given the small seed counts
   (20 and 30) and that they were not pre-registered as tests?
2. For the AUC figure: show the fraction of runs marked alongside it, plot the
   AUC over marked runs only, or both? (This links to note 04's question about
   reporting AUC only over runs with a mark.)
3. Is it worth measuring directly how long it takes, after a loss, for another
   robot to come within 0.5 m of the wreck, to test the candidate for the
   loss-to-mark gap?
4. E4's cells are not paired, and the number of robots entering differs between
   cells. Is a caveat enough, or should the saturation check be repeated on the
   same layouts at every lethality?
5. The predicted death fractions use natural visit lengths from only one cell's
   layouts. Is that acceptable for a descriptive comparison?

## 2. E6b, E7b and E8: what was run

Everything from here on is **exploratory**. E6b, E7b and E8 were pre-registered as
exploratory experiments in the last section of `docs/hypotheses.md` ("Week-5
experiments"). That section was added at 85625f8 and finalised (a wording
clarification) at 37bf380, both before any E6b, E7b or E8 data existed, and it was
approved on 2026-10-20. There are no confirmatory hypotheses, so no
p-value below is a confirmatory result, and the explanations I give are candidates
unless the numbers show them directly.

Each experiment answers one of the reviewer objections in the week-5 addendum
(`docs/superpowers/specs/2026-10-20-week-5-addendum.md`):

- (a) E6 changed two things at once (C5 max-merges where C2 sums, and C5 is untuned).
  **E6b** adds C6, which differs from C2 in one factor only.
- (b) E7's misses were weak by construction and its cells used different layouts.
  **E7b** uses much stronger and correlated misses, ten times more false sightings,
  and the same layouts in every cell.
- (c) A static hazard never makes old marks wrong, so the value of decay was never
  tested. In **E8** the hazard moves once, half-way through, with two decay levels for C2.

### Provenance and run counts

All three batches ran from a frozen copy of the repository at commit 37bf380, with 4
workers (from `results/week5_batch.out`):

| Experiment | Controllers | Cells | Runs | Batch time |
|---|---|---|---|---|
| E6b | C2, C5, C6 | 5 (5, 10, 20, 40, 80 robots) | 1,500 | 1,963 s |
| E7b | C0, C1, C2, C3 | 6 noise cells, paired | 2,400 | 1,644 s |
| E8 | C0, C1, C2, C4 | 3 cells (static; moved with tuned decay; moved with fast decay), paired | 1,200 | 940 s |

That is 5,100 runs of 10,000 steps, 100 seeds per cell, and every row in the three
CSVs carries commit 37bf380. The provenance check in the analysis
(`results/analysis/week5/analyse_week5.log`) says "code 37bf380 (every golden case
from fe78c66 reproduced bit-identically)" for each of E6b, E7b and E8, which means
the old controllers C0–C5 behave exactly as at E1's commit when the new features are
off. As in week 4, this was checked on one machine only.

**Identity checks.** "Paired cells" means every cell reuses cell 0's random streams,
so cells differ only in their parameters. Some controllers ignore the thing that
changes between cells, so their runs must come out identical row for row. All five
checks in `identity_checks.csv` came out True:

- E7b: C0 (ignores wrecks) is identical in all six cells; C1 (ignores false
  sightings) is identical in cells 0 and 5.
- E8: C0, C1 and C4 (none of them uses the field) are identical in cells 1 and 2.

What this confirms: the cells really do share layouts, start positions and noise
draws, so cross-cell differences for C2 and C3 come from the changed parameter and not
from different layouts. That was the second half of objection (b). (I also checked
that in E8 every controller's pre-move counts are identical in cells 0 and 1, which
should be true because nothing differs before step 5000; they are. C2's differ
between cells 1 and 2, as they should, because the decay differs from the start.)

## 3. E6b (objection a): C2 versus C6 versus C5 by swarm size

**What was asked.** Does it matter *where* the information is held? C6 makes exactly
the same deposits as C2, but each robot keeps its own copy of the sighting records and
passes them only to robots within 1 m, every 1 s. If every robot knew every record, its
map would equal C2's shared field. So C2 vs C6 changes only the information medium,
and C6 vs C5 changes only the combination rule (sum vs max-merge).

**What was run.** C2, C5 and C6 at 5, 10, 20, 40 and 80 robots, 100 seeds per cell.
Within a cell the controllers share seeds (paired); the cells are not paired with each
other.

Medians with bootstrap 95% CIs (`E6b_descriptive.csv`):

| Robots | Delivered C2 | Delivered C5 | Delivered C6 | Lost C2 | Lost C5 | Lost C6 |
|---|---|---|---|---|---|---|
| 5 | 12 [11, 13] | 12 [11, 13] | 12 [11, 13] | 1 [1, 1] | 1 [1, 1] | 1 [1, 1] |
| 10 | 23 [22, 24] | 23 [22, 24] | 23 [22, 24] | 1 [1, 1] | 1 [1, 1] | 1 [1, 1] |
| 20 | 45 [44, 47] | 45 [44, 46.5] | 45 [44, 47] | 2 [2, 2] | 2 [2, 2] | 2 [2, 2] |
| 40 | 85.5 [84, 87] | 85 [83, 86.5] | 85 [83, 86.5] | 3 [2, 3] | 2.5 [2, 3] | 2 [2, 3] |
| 80 | 168 [165, 170] | 165.5 [162.5, 169] | 166.5 [163.5, 169] | 3 [3, 3] | 3 [3, 3] | 3 [3, 3] |

Median final localisation AUC (same file): C2 / C5 / C6 = 0.5 / 0.5 / 0.5 at N = 5;
0.7192 / 0.7192 / 0.7192 at 10; 0.7618 / 0.7614 / 0.7614 at 20; 0.8408 / 0.8381 /
0.8365 at 40; 0.8834 / 0.8766 / 0.8762 at 80. Runs with any mark (C2 / C5 / C6):
22 / 22 / 22 at N = 5, 61 / 59 / 59 at 10, 94 / 94 / 94 at 20, and 100 for all three
at 40 and 80. So, as in week 4, the N = 5 median AUC of exactly 0.5 is because most
runs never mark anything.

**How far the information spread in C6** (`known_frac`: at the end of a run, the mean
over live robots of the fraction of all records they know; 1.0 means every robot knows
everything, i.e. C6's maps equal C2's field). Only runs with at least one record
have a value (`known_frac_n`): 22 runs at N = 5, 61 at 10, 94 at 20, 100 at 40 and 80.
Medians [CI]: 0.75 [0.5, 1.0] at N = 5, 1.0 [0.857, 1.0] at 10, 1.0 at 20 and 40,
0.9968 [0.9957, 1.0] at 80. The means, which I computed from `E6b.csv` because they are
not in the table, are lower: 0.708, 0.749, 0.918, 0.941 and 0.958. The share of runs
with records in which every live robot knew every record (exactly 1.0) was 45%, 52%,
72%, 63% and 49% for N = 5 to 80. So from N = 10 up, about half or more of the runs
reached full spread (which is why the median is 1.0, or 0.997 at N = 80), and most of
the rest came close, but in some runs the spread was clearly incomplete (the means are
pulled down by them, most at N = 10).

**Tested comparisons** (`E6b_tests.csv`; paired Wilcoxon, Holm over all 30 tests in
E6b). Nothing survives Holm. The smallest Holm p is 0.4292, for robots lost at N = 10,
C5 vs C2 and C6 vs C2 (raw p = 0.0143 for both; medians 1 vs 1; A12 = 0.512 [0.502,
0.525], paired median difference 0 [0, 0]). Every other test has Holm p = 1.
For delivered items, A12 of C6 vs C2 ranges from 0.493 to 0.504 over the five sizes,
and its paired median differences are 0 except at N = 80 (−0.5 [−2, 2]). For C6 vs C5
every paired median difference is 0 and every A12 lies between 0.481 and 0.516.

The figure (`e6b_sweep.png`) shows the three delivered lines on top of each other. The
only visible gap is robots lost at N = 40 (medians 3, 2.5, 2), but the paired median
differences there are 0 [0, 0] and the Holm p is 1.

**Plain reading.** In this set-up, C6 (private copies passed between neighbours)
showed no detectable difference from C2 (one shared field) at any swarm size, and no
detectable difference from C5 either (100 seeds per size). This is not a finding of
equivalence; it only says that 100 seeds did not detect a difference.

**Candidate explanation** (not tested). Because C6's information spread fully or
nearly fully in many runs, C6 was often close to *being* C2, so finding no detectable
difference between C6 and C2 is what this candidate explanation predicts. It does not
show that the medium is irrelevant, and it does not tell us what happens when the
information does *not* spread.

**What it means for the E6 confound.** Week 4 could not say whether C5 ≈ C2 was
because the medium does not matter or because the combination rule hid a difference.
E6b separates the two factors, and neither one showed a detectable effect here: C2 vs
C6 (medium only) and C6 vs C5 (combination rule only) are both null after Holm.

**What it does not show:**

- C5 is still untuned. C6 needs no tuning (with full spread it is C2), but C5 might
  behave differently with its own tuned parameters.
- One arena size (10 m) and one communication range (1 m). In a larger arena, or
  with a shorter range, the information might not spread, and then the medium could
  matter. E6b cannot say.
- C5's and C6's AUC is the mean of the live robots' maps, a swarm-level quantity no
  single robot holds.

## 4. E7b (objection b): stronger and correlated misses, paired layouts

**What was asked.** Week 4's misses were independent each step, so a wreck was almost
never missed for a whole pass; they only delayed noticing it. Do the week-4
patterns survive much harsher noise?

**What was run.** C0, C1, C2, C3, 100 seeds, six cells that all use cell 0's random
streams (so the layouts are the same in every cell):

- 0: no noise
- 1: q_miss 0.5 (independent misses)
- 2: q_miss 0.8 (independent)
- 3: q_miss 0.5 in blind spells of 100 steps (10 s) on average (`miss_run` 100)
- 4: q_miss 0.8 in 10 s spells
- 5: false sightings ×10 (q_false = 0.0001)

A 10 s blind spell is about the time a robot takes to cross the 1 m sensing disc
around a wreck, so in cells 3 and 4 a robot can miss a wreck for a whole pass.

Medians with bootstrap 95% CIs (`E7b_descriptive.csv`):

| Controller | Metric | 0 none | 1 miss 0.5 | 2 miss 0.8 | 3 miss 0.5, spells | 4 miss 0.8, spells | 5 false ×10 |
|---|---|---|---|---|---|---|---|
| C0 | delivered | 42.5 [40, 44.5] | 42.5 [40, 44.5] | 42.5 [40, 44.5] | 42.5 [40, 44.5] | 42.5 [40, 44.5] | 42.5 [40, 44.5] |
| C1 | delivered | 44 [42.5, 45] | 44 [43, 45] | 44.5 [43, 45.5] | 43.5 [42, 45] | 44 [42, 45] | 44 [42.5, 45] |
| C2 | delivered | 45 [44, 46] | 45 [44, 46] | 44 [43, 45] | 45 [44, 46] | 45 [44, 46] | 51.5 [49, 55] |
| C3 | delivered | 44.5 [44, 46] | 45 [43, 45.5] | 44 [43, 45] | 45 [44, 46] | 44 [43, 46] | 51 [49, 54] |
| C0 | lost | 4 [4, 5] | 4 [4, 5] | 4 [4, 5] | 4 [4, 5] | 4 [4, 5] | 4 [4, 5] |
| C1 | lost | 3 [3, 3] | 3 [3, 4] | 4 [3, 4] | 4 [3, 4] | 4 [4, 4] | 3 [3, 3] |
| C2 | lost | 2 [2, 2] | 2 [2, 2] | 2 [2, 2] | 2 [2, 2] | 2 [2, 2.5] | 2 [2, 3] |
| C3 | lost | 2 [2, 2] | 2 [2, 2] | 2 [2, 2] | 2 [2, 2] | 2 [2, 3] | 2 [2, 2] |

(C0 is the same in every column because its runs are identical across cells.)

Median final AUC for C2, cells 0–5: 0.7645, 0.7851, 0.7957, 0.7613, 0.7521, 0.6179;
for C3: 0.7696, 0.7851, 0.7957, 0.7633, 0.7521, 0.6302. C2 runs with any mark: 95,
95, 95, 94, 91, 100. False sightings per run in cell 5 (mean): C0 17.5, C1 18.13, C2
18.63, C3 18.60, close to the 20 the addendum expected (0 in every other cell).

### Within each cell (controllers compared with C2, paired by seed)

From `E7b_tests.csv`, Holm over all 66 tests in E7b:

- **Robots lost, C0 vs C2:** C0 loses more in every cell (paired median difference 2
  in each; A12 from 0.8715 to 0.9187; Holm p at most 2.039e-14).
- **Robots lost, C1 vs C2:** C1 loses more in every cell (paired median difference 1
  or 2; A12 from 0.697 in cell 5 to 0.8527 in cell 2; Holm p at most 1.773e-05).
- **Delivered, C0 vs C2:** C2 delivers more in every cell (A12 of C0 vs C2 from 0.1974
  to 0.3994; Holm p at most 5.552e-05).
- **Delivered, C1 vs C2:** survives Holm in cells 3 (A12 0.4273, Holm p = 0.005678), 4
  (A12 0.4185, Holm p = 0.0005802) and 5 (A12 0.2281, Holm p = 1.095e-08), not in
  cells 0, 1, 2 (Holm p = 1, 0.8721, 1).
- **C3 vs C2:** no detectable difference in any cell on either metric (every Holm p
  is 1; A12 between 0.4789 and 0.5034).

So the week-4 pattern holds in every cell, including the harsh ones: C2 lost fewer
robots than C0 and C1, and C3 showed no detectable difference from C2.

### Across cells (each noisy cell vs cell 0, same layouts)

These tests are new: because the cells are paired, I can now ask whether noise changes
a controller's results, which week 4 could not. Each line is "cell k vs cell 0" for
one controller; the paired median difference is cell k minus cell 0.

**C1, robots lost** (median 3 with no noise):

| Cell | Median | Paired median difference [CI] | A12 [CI] | Holm p |
|---|---|---|---|---|
| 1 miss 0.5 | 3 | 0 [0, 0] | 0.5364 [0.4842, 0.5897] | 1 |
| 2 miss 0.8 | 4 | 0.5 [0, 1] | 0.619 [0.5726, 0.6682] | 4.172e-05 |
| 3 miss 0.5, spells | 4 | 0 [0, 1] | 0.6122 [0.5627, 0.6631] | 0.0002346 |
| 4 miss 0.8, spells | 4 | 1 [0, 1] | 0.6948 [0.6443, 0.7457] | 1.489e-08 |
| 5 false ×10 | 3 | identical runs | 0.5 | 1 |

So C1 loses more robots when misses are strong (cell 2) or correlated (cells 3 and 4),
most in cell 4. C1's deliveries show no detectable change in any cell (smallest Holm
p = 0.1303, cell 4).

**C2 and C3:**

- **Delivered:** no detectable change in cells 1–4 for either controller (every Holm
  p is 1). Cell 5 is different; see section 5.
- **Robots lost, cell 4** (q_miss 0.8 in spells): both shift upwards. C2: medians 2
  vs 2, paired median difference 0 [0, 0], A12 = 0.5969 [0.5575, 0.6395], Holm p =
  0.0002902. C3: medians 2 vs 2, paired median difference 0 [0, 0], A12 = 0.6003
  [0.5595, 0.6442], Holm p = 0.0001878.
- **Robots lost, cell 3** (q_miss 0.5 in spells): raw p-values are small (C2 0.0044,
  C3 0.0027) but neither survives Holm (C2 Holm p = 0.1532, A12 0.5395; C3 Holm p =
  0.09894, A12 0.543).
- **Robots lost, cell 5:** C2 A12 = 0.626, Holm p = 0.05005 (just above 0.05); C3
  A12 = 0.6094, Holm p = 0.1943. Neither survives.
- Cells 1 and 2 (independent misses): no detectable change for C2 or C3 (Holm p = 1).

I want to be careful about the size of the cell-4 effect. The medians are equal and the
paired median difference is 0, so on most seeds C2 lost the same number of robots as
without noise. The A12 of about 0.60 says that when the two differ, the noisy run more
often lost more. That is a small shift, smaller than C1's (A12 0.6948, paired median
difference 1; a descriptive comparison, not tested).

**Plain reading.** In these runs, strong or correlated misses made C1 lose more robots
(tested), while C2 and C3 delivered no detectably different numbers of items and lost
slightly more robots only in the harshest miss cell (4). Within every cell, C2 still
lost fewer robots than C1 and C0.

**Candidate explanation** (not tested): C1 can only avoid a wreck while it sees it, so
every missed step is a step without avoidance, and a 10 s blind spell can last a whole
pass. C2 only needs to see a wreck once to mark it; after that the repellent steers
robots away whether or not the wreck is seen. So misses mostly delay C2's marking, and
a long blind spell delays it more, which would fit the small shift in cell 4. The AUC
numbers do not contradict this (descriptive only): C2's median AUC stayed between
0.7521 and 0.7957 in cells 1–4, against 0.7645 with no noise, and 91–95 runs were
marked in each of those cells.

**What it does not show:** robustness to detection noise in general. These are five
specific noise settings in one arena with one hazard. I also did not measure *when* the
first mark happened in each cell, so "misses delay marking" is still only a candidate.

## 5. E7b cell 5: false sightings raised deliveries

**The surprise.** With ten times more false sightings, C2 and C3 delivered far *more*
items, not fewer:

- C2: median 51.5 [49, 55] against 45 [44, 46] without noise; paired median difference
  7 [4.5, 10]; A12 = 0.7565 [0.6907, 0.8196]; Holm p = 2.997e-08.
- C3: median 51 [49, 54] against 44.5 [44, 46]; paired median difference 7.5 [5, 9];
  A12 = 0.7478 [0.6812, 0.8107]; Holm p = 2.574e-08.
- Within cell 5, C2 delivered far more than C0 (paired median difference C0 minus C2
  −10 [−14, −6], A12 0.1974) and C1 (−6 [−10, −5], A12 0.2281).

A phantom sighting puts a repellent deposit where a robot is, so I expected it to push
robots away from harmless places and cost deliveries. The opposite happened, and it is
the biggest change across cells in E7b. In the box plot (`e7b_noise.png`) the C2 and C3 boxes
in the last panel sit clearly above all the others.

### A small diagnostic (not pre-registered)

To see where this comes from, I ran a small **descriptive** diagnostic
(`scripts/diag_false_sightings.py`, output `results/mechanism/false_sightings_diag.csv`).
It was not pre-registered and has no tests. It runs C2 only, seeds 0–19 (20 seeds),
with E7b's paired random streams, in five variants:

- a: no noise (this is E7b cell 0)
- b: q_false = 0.0001 (this is E7b cell 5)
- c: as b, but `repel_weight` = 0, so the field is laid down but does not steer
- d: as b, but with no hazard
- e: no noise and no hazard

Variants a and b reproduced C2's E7b rows for seeds 0–19 row for row (delivered, robots
lost and false sightings all identical), so the diagnostic is the same simulation.

Medians over the 20 seeds:

| Variant | Delivered | Robots lost | False sightings | Share of final repellent within 1.5 m of the nest | Robot-steps within 1.5 m of the nest |
|---|---|---|---|---|---|
| a no noise | 43 | 2 | 0 | 0 | 75,669 |
| b false sightings | 54 | 3 | 17.5 | 0.277 | 55,269.5 |
| c false sightings, no steering | 42.5 | 4 | 17 | 0.215 | 74,406.5 |
| d false sightings, no hazard | 58.5 | 0 | 18.5 | 0.269 | 63,072 |
| e no noise, no hazard | 50 | 0 | 0 | (no field) | 78,633.5 |

Paired by seed (my own calculation from the same file): b delivered more than a on 18
of 20 seeds (median difference 12); d more than e on 17 of 20 (median difference 9); c
against a, 6 higher, 4 tied, 10 lower (median difference −0.5).

What the numbers show directly, for these 20 seeds:

- About 28% of the final repellent in b lies within 1.5 m of the nest, although that
  disc is only about 7% of the 10 m × 10 m arena (π × 1.5² ≈ 7.07 m²). In a, none of
  it does: no real mark lies within 1.5 m of the nest. So phantom repellent is
  concentrated near the nest, at about four times that disc's share of the area.
- Robots spend a lot of time near the nest: in a, 75,669 robot-steps out of at most
  200,000 (20 robots × 10,000 steps), about 38%, in that 7% disc. With false
  sightings (b) this falls to 55,269.5 (lower on 18 of 20 seeds).
- Without steering (c, `repel_weight` = 0) there was no gain (42.5 against 43), and
  the time near the nest barely changed.
- Without the hazard (d vs e) a similar gain appeared (median paired difference 9,
  against 12 for b vs a).

**Candidate explanation.** A phantom happens where a robot is, and robots are mostly
near the nest, so most phantom repellent sits around the nest. That repellent pushes
robots out of the crowded nest area faster after they deliver, and that seems to help
foraging. The first part (where the repellent is, and that robots spend less time near
the nest) is shown above; that this is *why* deliveries rise is a candidate, because I
did not measure crowding or trip times.

**What I want to be honest about:**

- If the candidate explanation is right, this would be a property of our foraging
  model (robots lingering and possibly crowding near the nest), not evidence that
  detection noise is good. A version of the model where robots leave the nest
  efficiently might not show it.
- It may matter for the E2 random-failure control. There, robots fail at random places,
  and wrecks near the nest would also be marked by C2, which might push robots out of
  the nest area in the same way. This is a question for my mentor, not a claim: I have
  not checked where E2's random wrecks were.
- C2's localisation AUC drops in this cell (median 0.6179 against 0.7645 with no
  noise). That is consistent with the map now holding marks away from the hazard
  (in the diagnostic, about 28% of C2's final field lay within 1.5 m of the nest,
  20 seeds), but I did not show that this is the cause. Higher deliveries came with a
  worse map.
- The diagnostic has 20 seeds and only C2, and was designed after seeing the E7b
  result. It describes; it does not test.

## 6. E8 (objection c): the hazard moves

**What was asked.** With a static hazard old marks are never wrong, so decay never had
to do anything. What happens when the hazard moves, and does faster decay help the map
catch up?

**What was run.** C0, C1, C2, C4, 100 seeds, three paired cells. At the start of step
5000 (500 s) the hazard is replaced:

- 0: "moved" to where it already was (static), tuned decay 0.0002 per step
- 1: moved to (1.19, 3.81), the old position reflected through the nest, tuned decay
- 2: moved to (1.19, 3.81), fast decay 0.002 (half-life about 35 s instead of 347 s)

Wrecks stay where they died, so after the move their repellent marks sit on cells that
are now safe. C4 (the oracle) knows the new position at once.

Before the move, all cells are alike, as they should be with paired streams. C2's
pre-move medians are 21 delivered / 1 lost in cells 0 and 1 (identical runs) and 22 / 1
in cell 2; the fast vs tuned decay tests on the pre-move columns show no detectable
difference (Holm p = 0.7446 for both).

Medians after the move with bootstrap CIs (`E8_descriptive.csv`):

| Controller | Delivered after: static | moved, tuned | moved, fast | Lost after: static | moved, tuned | moved, fast |
|---|---|---|---|---|---|---|
| C0 | 21 [20, 23] | 20 [18.5, 21] | 20 [18.5, 21] | 2 [1, 2] | 3 [2, 3] | 3 [2, 3] |
| C1 | 22 [21, 23] | 21 [20, 21] | 21 [20, 21] | 1 [1, 1] | 2 [2, 2.5] | 2 [2, 2.5] |
| C2 | 23 [22, 24] | 21.5 [20, 23] | 21 [20, 22.5] | 0 [0, 0.5] | 2 [1, 2] | 2 [2, 2] |
| C4 | 26 [25, 26] | 25 [25, 26.5] | 25 [25, 26.5] | 0 [0, 0] | 0 [0, 0] | 0 [0, 0] |

### Tested comparisons (`E8_tests.csv`, Holm over all 24 tests in E8)

- **C2, moved vs static** (cell 1 vs cell 0, tuned decay): C2 lost more robots after a
  move than when the hazard stayed: medians 2 vs 0, paired median difference 1 [1, 1],
  A12 = 0.8563 [0.8123, 0.8976], Holm p = 4.854e-14. It also delivered fewer: 21.5 vs
  23, paired median difference −1 [−2, −0.5], A12 = 0.3881, Holm p = 1.239e-06. (From
  `E8.csv`: 60 of 100 static runs lost no robot after step 5000, against 4 of 100 moved
  runs.)
- **C4 after the move** loses almost no robots: median 0 in every cell; in cell 1, 86
  runs lost none and 14 lost one (from `E8.csv`). Against C2 in cell 1: paired median
  difference −1 [−2, −1], A12 = 0.0501, Holm p = 4.117e-17. It also delivered more (25
  vs 21.5, A12 0.7453, Holm p = 1.525e-09).
- **C2 still loses fewer than C0 after a move:** cell 1, 2 vs 3, A12 (C0 vs C2) =
  0.7178, Holm p = 3.864e-08; cell 2, A12 = 0.6812, Holm p = 8.298e-07. Against C1:
  cell 1 A12 = 0.632, Holm p = 0.0001313; cell 2 A12 = 0.5895, Holm p = 0.01709 (medians
  2 vs 2 in both). C1 vs C2 on delivered items after the move does not survive Holm in
  any cell (Holm p = 0.0513, 0.06049, 0.2636).
- **Fast vs tuned decay** (cell 2 vs cell 1, C2): no detectable difference on any of
  the four metrics. Delivered before: Holm p = 0.7446; lost before: 0.7446; delivered
  after: 0.7446 (medians 21 vs 21.5, A12 0.4921); lost after: 0.2262 (raw p = 0.045,
  medians 2 vs 2, A12 0.5476).

**Plain reading.** In these runs, a moved hazard cost C2 robots and deliveries compared
with a static one, but C2 still lost fewer robots than C0 (and than C1) after the move.
C4, which knows the new position, lost almost none, so there is room to do better.
Faster decay (0.002) did not show any detectable difference from the tuned 0.0002.

### The map relearns: AUC over time

The localisation AUC is measured against the old hazard before 500 s and against the
new hazard after it (`e8_auc_over_time.png`, C2, moved cells). From the AUC series in
`E8.csv`, the median AUC in cell 1 (tuned decay) is 0.7291 at 500 s, then **0.4814**
at every sample from 550 s to 700 s, then 0.6939 at 750 s, rising to **0.7222** at
1000 s. Fast decay (cell 2) follows almost the same curve: 0.7304 at 500 s, 0.4814
from 550 to 700 s, 0.6833 at 750 s, 0.7196 at 1000 s. For comparison, the static cell
ends at 0.7676.

Candidate explanation for the dip just below 0.5 (I did not measure when the new
marks appeared): right after the move, the only marks are around the old wrecks, which
are now on safe cells, so against the new hazard the marked cells rank as *less*
likely to be hazard than the unmarked ones (73 of 100 runs are below 0.5 at 550 s in
cell 1; that number is measured). The AUC would then recover once robots die at the
new position and those wrecks get marked.

The final map against the *old* hazard (`auc_old_final`, how much stale information
is left) is 0.7441 [0.7165, 0.7635] with tuned decay and 0.7530 [0.7307, 0.7755] with
fast decay, so the old hazard is still "visible" in the map at 1000 s in both.

**Why the two decay curves overlap: a candidate explanation from reading the code,
not tested.** The AUC is rank-based: it only asks whether
hazard cells score higher than other cells. Decay multiplies every deposit by the same
factor each step, so it shrinks the whole field without changing the order of cells
made by deposits of the same age. Faster decay mostly makes old and new deposits differ
more in strength, and that hardly changes the ranking here. What fast decay does change
is how *strongly* the field pushes robots, because steering uses the gradient, not the
ranking. With fast decay the old marks should push less after 35 s or so; but that did
not turn into a detectable difference in losses or deliveries. (None of this
paragraph was measured.)

**Caveats.**

- "Marked runs" in E8 counts a run as marked if any AUC sample differs from 0.5. After
  the move, a stale map read against the new hazard also differs from 0.5, so it counts
  as marked even if nothing near the new hazard is marked. The C2 counts (96, 99, 99 in
  cells 0, 1, 2) should be read with that in mind.
- The AUC-over-time figure measures against the old hazard before 500 s and the new
  one after, and its caption must say so. Its y-axis says "current hazard", but that
  is easy to miss.
- One move, one new position, two decay levels. E8 cannot say that decay never
  matters: a different decay value, a hazard that moves more often, or a longer run
  after the move might show a difference.

## 7. What this changes for the paper

Suggested wording only, for discussion with my mentor. Everything here is exploratory
and should be labelled that way, citing the dated week-5 section of `hypotheses.md`
(added at 85625f8, finalised at 37bf380, both before any data existed). The confirmatory results from week 3 are
not touched.

- **E6 / E6b.** "In a follow-up that changes one factor at a time, C6 (private record
  copies shared with neighbours, otherwise identical to C2) showed no detectable
  difference from C2 or from C5 at any swarm size after Holm correction (100 seeds per
  size). A likely reason (not tested) is that the records spread to nearly every
  robot in most runs (median fraction known 0.997–1.0, means 0.75–0.96 for N ≥ 10) in
  our 10 m arena with 1 m communication." Keep: C5 untuned; one arena size and range; never "equivalent".
- **E7 / E7b.** "With stronger and correlated misses on the same layouts, C2 still lost
  fewer robots than C0 and C1 in every cell, and C3 showed no detectable difference from
  C2. C1's losses rose with strong or correlated misses; in the miss cells (1–4) C2's
  deliveries showed no detectable change and its losses shifted slightly (A12 0.60) only with 80% misses in
  10 s spells." Do not claim robustness in general.
- **False sightings.** Report the cell-5 rise plainly, with the AUC drop, and describe
  the diagnostic as a small, non-pre-registered, descriptive check whose candidate
  candidate explanation, if right, would make it a property of the foraging model
  (robots lingering and possibly crowding near the nest), not a benefit of noise.
- **E8.** "When the hazard moved half-way through, C2 lost more robots than when it
  stayed (median 2 vs 0 after the move), but still fewer than C0. The map partly
  relearned the new position (median AUC against the new hazard from just below 0.5
  straight after the move to 0.722 at the end, below the static cell's 0.768), while
  the old position was still visible in the map (median AUC against the old hazard at
  the end 0.744). A tenfold faster decay showed no detectable difference on any of the four tested
  metrics." Add the "marked runs" caveat and fix the figure caption.

## 8. Things to check with your mentor

1. The E7b cell-5 result is the largest cross-cell change in E7b, and its diagnostic was
   designed after seeing it. How should it go in the paper: as a reported surprise with
   a candidate explanation, or should the diagnostic be repeated with more seeds as a
   pre-registered check?
2. Could the same nest-area effect affect the E2 random-failure control (random wrecks
   near the nest also get marked by C2)? Is it worth checking where E2's random wrecks
   were, and how much of C2's E2 field was near the nest?
3. Is the possible crowding near the nest (robots linger there; crowding itself was
   not measured) a flaw in the foraging model that the
   paper should mention as a limitation, separate from E7b?
4. E6b's null result may reflect that the information spread fully or nearly fully in
   most runs (a candidate, not tested). Is it
   worth one extra run with a shorter communication range (or a bigger arena), where
   C6 would not spread fully, or is that out of scope?
5. In E7b, how should a shift with equal medians and paired median difference 0 but A12
   about 0.60 (C2 and C3, cell 4) be described in words?
6. C2's lost-robots shift in cell 5 has Holm p = 0.05005. I am reporting it as not
   surviving correction. Is that right?
7. E8: should the AUC figure show the fraction of runs with marks near the new hazard,
   given that "marked runs" counts stale maps too?
8. E8 tested only one fast decay value. Is "no detectable difference at 0.002" enough
   for the paper, or is a hazard that moves several times needed before saying anything
   about decay (the addendum lists that as out of scope)?
