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

## 2. E6b, E7b and E8

These wait for the pre-registration approval. Nothing has been run beyond
one-seed smoke tests, and nothing will be until the pre-registration in
`docs/hypotheses.md` is approved.

For later: in E8 a run counts as "marked" if any AUC sample differs from 0.5, so
after the move a stale map read against the new hazard also counts. The E8
AUC-over-time figure measures against the old hazard before 500 s and the new one
after, and its caption must say so.
