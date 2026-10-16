# 02 — Week 2: fixing, extending and tuning

## What changed and why

1. **Separate random streams.** Before, one stream of random numbers fed
   everything, so when one robot died, every later random number shifted and
   the controllers stopped facing the same luck. Now movement, item respawns,
   hazard failures and the starting layout each have their own stream, drawn
   the same amount every step. Comparisons between controllers are now paired
   for the whole run, which makes differences easier to detect.
2. **A fair oracle.** The week-1 oracle kept 0.5 m clear of the hazard and so
   skipped part of a nearby item patch, which meant it was not really "the best
   possible". It now only refuses to step inside, and slides along the hazard
   edge when blocked.
3. **Item bookkeeping.** We now count every pickup and check it ends up
   delivered, lost with a robot, or still being carried.
4. **Provenance.** Every result row records the code version, the machine and
   every package version, and the runner refuses to run on uncommitted code.
5. **Two new controllers.** C1 only steers around wrecks it can see (no
   memory). C3 marks like C2 but pushes less when items are in view.
6. **Localisation AUC.** A score from 0.5 (the repellent map says nothing) to
   1.0 (it outlines the hazard perfectly).

## Tuning

We fixed the rule before running: pick the setting with the highest median
items delivered; break ties by fewer robots lost. Tuning used its own random
streams, so the main experiments are a fresh test.

delivered = median items delivered, lost = mean robots lost, over 20 seeds; p_
columns are the tuned parameters; the C2 table shows the best 10 of 36 settings.

C2 result (720 runs: 36 settings x 20 seeds; grid repel_weight 0.5/1/2/4,
deposit_sigma 0.2/0.3/0.5, decay 0.0002/0.0005/0.002):

```
                                        delivered  lost  runs
p_repel_weight p_deposit_sigma p_decay
0.5            0.3             0.0002        47.0  1.85    20
               0.2             0.0005        47.0  1.95    20
4.0            0.5             0.0020        46.5  1.55    20
2.0            0.3             0.0002        46.5  1.65    20
4.0            0.2             0.0005        46.5  1.85    20
2.0            0.3             0.0005        46.5  2.05    20
1.0            0.2             0.0020        46.5  2.20    20
2.0            0.5             0.0002        46.0  1.45    20
0.5            0.5             0.0005        46.0  1.70    20
2.0            0.5             0.0005        45.5  1.65    20

chosen: {'repel_weight': 0.5, 'deposit_sigma': 0.3, 'decay': 0.0002}
```

`repel_weight` (0.5) and `decay` (0.0002) are the SMALLEST values in their
grids, so the true best values may lie outside the grid. `deposit_sigma` (0.3)
is in the middle.

C3 result (100 runs: 5 settings x 20 seeds; grid risk_k 0.25/0.5/1/2/4):

```
          delivered  lost  runs
p_risk_k
0.50           48.0  2.00    20
1.00           45.5  1.80    20
2.00           45.0  1.80    20
0.25           44.5  1.85    20
4.00           43.0  1.80    20

chosen: {'risk_k': 0.5}
```

`risk_k` = 0.5 is inside its grid (not at an edge).

Final `configs/tuned_params.yaml`:

```
# Tuned parameters (spec section 3). Written by scripts/select_params.py.
# Last update: C3 from tune_c3.csv, code 02c30bd.
# Rule: highest median items delivered; ties -> lowest mean robots lost.
decay: 0.0002
deposit_sigma: 0.3
repel_weight: 0.5
risk_k: 0.5
```

## Three things to decide before the main experiments

(a) **C2's tuning is weak.** `repel_weight` and `decay` were chosen at the
smallest values in their grids, and the top 10 settings span only 1.5 items of
median delivered (47.0 down to 45.5), from 20 seeds each; we have not shown
this spread is larger than seed-to-seed variation. An extended, documented grid
(smaller `repel_weight` and `decay`) is an option, as long as we write down
that we did it and why. Any extended grid should use fresh seeds (a new
experiment name) to avoid tuning on the same random draws twice.

(b) **The runner is slow.** `tune_c2` took 62 minutes. A matched benchmark
(2,000-step C2 runs, same machine) measured throughput of 0.41 runs/s with 1
worker, 1.12 with 4, 0.81 with 8, 0.71 with 12 and 0.63 with 16. So 4 workers
was fastest; a likely cause (not confirmed) is that the laptop mixes fast and
slow cores and throttles when hot. At the benchmarked 4-worker rate (about 1.12
short runs/s, i.e. about 4.5 s per full 10,000-step run), the roughly 11,000
main runs would take about 14 hours, so we need to speed up the code or run
overnight. `tune_c2` used 16 workers; `tune_c3` and the gate re-check used 4
(the worker count does not affect results, only speed).

(c) **The go/no-go check now narrowly fails.** On items delivered the
pre-registered check fails narrowly (A12 0.629 vs 0.64; 95% bootstrap CI about
0.49-0.77), while robots lost shows a large effect (C2 loses fewer robots in
about 87% of paired comparisons). Whether to proceed, and whether items
delivered should stay the primary metric, is a decision for you and your
mentor, and must be made, and written into `docs/hypotheses.md`, before any
main experiment runs.

## The gate after the fixes

```
           delivered              robots_lost
              median   mean   std      median  mean   std
controller
C0              41.0  41.30  5.52         5.0  4.67  1.83
C2              44.0  44.03  5.54         2.0  2.27  0.87
C4              46.0  47.13  4.88         0.0  0.00  0.00

A12(C2 vs C0, delivered) = 0.629  (needs > 0.64)
median C4 >= median C2: True
GATE: FAIL
```

The gate re-check used the default parameters (not the tuned ones), as in week
1, so the two are comparable.

**The gate FAILED after the fixes.** A12 for C2 vs C0 is 0.629, below the 0.64
threshold (week 1: 0.673, PASS). Median delivered moved from 44 / 46.5 / 48
(C0 / C2 / C4) to 41 / 44 / 46; median robots lost stayed 5 / 2 / 0. The
ordering C0 < C2 < C4 still holds and the robot-loss pattern is unchanged. The
gap in medians (C2 minus C0) rose from 2.5 to 3 items, but A12, which compares
whole distributions, fell from 0.673 to 0.629, and is now just under the
pre-set line. We did not change anything to make it pass. Possible
explanations: (1) the week-1 A12 of 0.673 was partly luck from a shared random
stream, and the paired streams give a less inflated estimate, if this
explanation is right; (2) the fair oracle and the new counters changed what
every controller delivers, so C0 itself moved; (3) with only 30 seeds per
controller, A12 has a wide margin of error, so 0.629 versus 0.64 is not a clear
difference.

## Questions to think about

1. Why must the tuning rule be written down before tuning runs?
2. Why tune on different random streams from the main experiments?
3. If C2's best `decay` is the smallest value in the grid, what does that suggest we should try?
