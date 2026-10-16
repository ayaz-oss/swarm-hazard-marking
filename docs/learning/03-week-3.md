# 03 — Week 3: the main experiments

## What we ran

Five pre-registered main experiments (E6 and E7 are pre-registered for later
weeks), each with controllers C0–C4 and 100 seeds per
cell (every controller sees the same seed, so results are paired):

| Experiment | Cells | Runs | Batch time (wall-clock, 4 parallel workers) |
|---|---|---|---|
| E1 baseline | 1 | 500 | 770 s |
| E2 hazard placement | 4 (next to patch, between patch and nest, far, no hazard with random failures) | 2,000 | 4,828 s |
| E3 swarm size | 5 (5, 10, 20, 40, 80 robots) | 2,500 | 18,675 s |
| E4 lethality | 4 (0.005, 0.02, 0.1, 1.0 per step) | 2,000 | 9,849 s |
| E5 hazard radius | 3 (0.5, 1, 2 m) | 1,500 | 8,941 s |

That is 8,500 runs of 10,000 steps. The laptop throttled its CPU during E2–E5,
so those times are slower than they could have been. In Task 2 we sped the
simulator up without changing any result (the golden test checks the output is
identical bit for bit): one 10,000-step C2 run went from 14.07 s to 3.85 s and
one C0 run from 3.48 s to 2.24 s.

Provenance: the result files carry different git commits (E1 fe78c66, E2
45b4ce5, E3–E5 4cf295a) because the scripts were committed between batches.
The analysis script checks that the simulator code is identical across all of
them, and it reported "simulator identical to fe78c66" for E2–E5. So all 8,500
runs come from the same model. Row counts were 500/2000/2500/2000/1500 with
equal counts per controller and no "-dirty" commits.

## The pre-registered answers

C2 = repellent marking, C0 = ignore the hazard, C1 = avoid wrecks, C3 = mark
plus risk weighting. A12 is the chance that a run of the first controller beats
a run of the second (0.5 = no difference). Square brackets are bootstrap 95%
CIs. The median paired difference is first minus second, per seed.

| Hypothesis | Claim | Result | Supported? |
|---|---|---|---|
| H1 (E1) | C2 delivers more items than C0 | medians 45 vs 42; median paired difference 3 [1.5, 4]; A12 = 0.661 [0.620, 0.706]; p = 2.5e-11, Holm p = 5.0e-11 | Yes |
| H2 (E1) | C2 loses fewer robots than C1 | medians C1 3, C2 2; median paired difference 1 [1, 1]; A12(C1, C2) = 0.789 [0.742, 0.835]; p = 5.5e-15, Holm p = 1.7e-14 | Yes |
| H3 (E2, no hazard) | C2's cost relative to C0 is small | medians 45 vs 43; median paired difference 1 [0, 2.5]; A12 = 0.582 [0.519, 0.646]; lower bound 0.519 against the 0.36 threshold (decided by the CI rule, so no p-value) | Yes |
| H4 (E1) | C3 delivers more items than C2 when the hazard is next to a patch | medians 45 vs 45; median paired difference 0 [0, 0]; A12 = 0.503 [0.499, 0.510]; p = 0.156, Holm p = 0.156 | No |

### Deviations from the pre-registration

These are recorded in `docs/hypotheses.md` and must be reported as deviations
in the paper:

- The week-2 go/no-go check narrowly missed its threshold (A12 0.629 against
  0.64); we proceeded by a recorded decision instead of revising the model.
- Confirmatory tests use the paired Wilcoxon signed-rank test instead of the
  Mann-Whitney U test first specified, because runs are paired by seed.
- H3 is a one-sided bound (lower CI bound of A12 above 0.36) instead of
  |A12 - 0.5| < 0.14.
- deposit_amount was fixed at 1 and deposit_sigma was tuned instead.

**H1.** Marking the hazard helped: C2 delivered a median of 3 more items than
C0 per seed, and a C2 run beat a C0 run about two times in three. The effect
is modest: per seed, C2 delivered more than C0 on 71 seeds, tied on 15 and
delivered less on 14 (the C2 and C0 boxes overlap a lot in the E1 figure).

**H2.** C2 lost fewer robots than C1 on most seeds (median 2 vs 3): C2
lost fewer on 73 of 100 seeds, tied on 23 and lost more on 4. This was the clearest result.

**H3.** In the no-hazard control, C2 did not do worse than C0; if anything it
was slightly ahead on delivered items. The lower CI bound (0.519) is well
above the 0.36 threshold, so the pre-registered non-inferiority rule is met.
Note that this test only shows C2 is not much worse than C0 here; it is a
one-sided cost bound, not a claim that C2 is better.

**H4 is not supported.** C3 and C2 delivered the same median (45) and the
effect size is essentially 0.5, with Holm p = 0.156. We did not find that
risk weighting helps. See "Things to check with your mentor" for why this
test probably had little power.

## What the sweeps show (exploratory)

Everything in this section is exploratory: it was not part of the confirmatory
family. Claims come from the descriptive tables (medians with bootstrap CIs).
Where p-values are mentioned they are two-sided Wilcoxon tests against C2,
Holm-adjusted within each experiment, and should be read as exploratory.

**E2, placement.** Placement mattered a lot, mostly for the controllers without
marking (C0, C1). With the hazard between the patch and the nest, C0 delivered
a median of 17 items and lost 17 of 20 robots; C1 delivered 32 and lost 9;
C2 and C3 delivered 42 and lost 4.5; C4 (the oracle) delivered 46. With the
hazard next to the patch, the medians were C0 42, C1 43, C2 44, C4 48. Far
from everything, C0 44, C1 45, C2 46, C4 49. C2 vs C0 on items delivered was
different in all three hazard cells (Holm p 7.4e-5, 1.0e-16 and 4.0e-10).
In the no-hazard cell, robots lost were a median of 5 for every controller
(see concerns: this comparison is degenerate by design), and delivered items
were close (C2 45, C0 43, C4 43).

**E3, swarm size.** Items delivered rise with swarm size for all controllers
(for C2: 12, 24, 44, 85.5, 164.5 for 5, 10, 20, 40, 80 robots). C0's
robot losses grow steeply (1, 2, 5, 9, 19), C1's more slowly (1, 2, 3, 4, 6),
and C2's flatten out (1, 1, 2, 3, 3). So the benefit of marking in robots
saved is bigger for larger swarms: at 80 robots C0 delivered 150 items against
164.5 for C2, with 19 vs 3 robots lost. At 5 robots, C0, C1, C2 and C3 all
delivered 12, with no difference in the medians.

**E4, lethality.** Changing lethality from 0.005 to 1.0 per step made little
visible difference to any controller. C2's median delivered was 46, 44, 44.5
and 45 across the four levels, and its median robots lost stayed at 2; C0
lost a median of 4, 4, 5, 5, but its mean robots lost rose from 3.52 to 4.46,
5.42 and 5.08 for lethality 0.005, 0.02, 0.1 and 1.0 (about 50% more from
0.005 to 0.1), and its mean first-loss step fell from about 3,029 to 2,129,
1,981 and 2,251. So lethality matters between 0.005 and 0.1 and then flattens.
A likely explanation, which we did not test, is saturation: crossing a 1 m
radius hazard takes on the order of 100 or more steps, so at 0.02 per step or
more a robot that enters almost certainly dies and raising lethality further
changes little.

**E5, radius.** Read against the in-arena hazard area (0.75, 3.18 and 8.23 m²;
the 2 m hazard extends past the east wall, so its full circle would be larger),
bigger hazards hurt the controllers that cannot avoid them. C0 delivered
45, 43, 38 and lost 2, 5, 8; C1 delivered 46, 44, 41 and lost 2, 3, 5; C2
delivered 46, 44.5, 43 and lost 1, 2, 2. C4 stayed at 49, 49, 50. C2's median
loss stayed at 2 from the middle to the largest hazard while C0's rose from 5
to 8.

## Figures

All in `results/figures/` (PNG and PDF; not committed because `results/` is
git-ignored).

- `e1_baseline.png`: box plots with every seed as a dot, items delivered and
  robots lost for C0–C4 at baseline. Items rise C0 to C4 (median 42, 43, 45,
  45, 48); robots lost fall (5, 3, 2, 2, 0).
- `e1_auc_over_time.png`: localisation AUC of the repellent map over time for
  C2 and C3. It sits at 0.5 (no information) until about 300 s, jumps to about
  0.71 by 350 s, and creeps up to about 0.80 by 1000 s; the band is wide
  (roughly 0.72 to 0.86 at the end). The C2 and C3 lines lie exactly on top of
  each other, so only one is visible.
- `e2_placement.png`: items delivered (top) and robots lost (bottom) for each
  of the four hazard placements. The "between patch and nest" column stands
  out: C0 collapses to a median of 17 items and 17 robots lost.
- `e3_sweep.png`: medians with interquartile bands against swarm size on a log
  axis. Items rise steeply with swarm size; C0's losses fan out from the other
  controllers as the swarm grows.
- `e4_sweep.png`: the same against lethality. All lines are nearly flat, and
  the interquartile bands overlap heavily.
- `e5_sweep.png`: the same against in-arena hazard area. C0 and C1 decline as
  the area grows; C2/C3 decline less; C4 does not decline.

## Things to check with your mentor

1. **H4 had little power.** At the tuned risk_k of 0.5, C3 behaved almost
   exactly like C2: C3 delivered the same number of items as C2 on 96 of 100
   E1 seeds. In every figure the C3 line sits on the C2 line. So the H4
   result is "no detectable difference", not evidence that risk weighting is
   useless at other settings; the tuning grid itself was flat.
2. **C2 and C3 AUC are identical in E1** (median 0.7956 for both). This is
   consistent with the point above but worth confirming is not a coincidence
   of the implementation.
3. **Zero items lost in E1.** items_lost is 0 in every E1 run at baseline,
   Candidate explanation (not checked): the return paths miss the hazard.
   Items are lost in 455 E2 runs, so this is specific to E1. Losing a robot therefore costs
   throughput (that robot stops working) but never an item in transit.
4. **E2's no-hazard robots_lost comparisons are degenerate by design.**
   Random failures share one random stream, so robots_lost is identical across
   controllers on every seed in that cell. Only delivered items can differ
   there.
5. **C2 and C3 slightly ahead of C0 with no hazard (exploratory).** In the
   no-hazard cell C4 behaves exactly like C0 by construction (identical
   delivered on all 100 seeds), so its 43 is not a separate result. C2 and C3
   delivered slightly more than C0 (C2 ahead on 57 seeds, tied on 4, behind on
   39; Holm p 0.097, not significant). This is unexplained; we only have
   candidate explanations (for example the marking spreading robots out) and
   have tested none.
6. **hazard_area is quantised.** It is measured on a 0.1 m grid, so the
   baseline is 3.18 m² rather than pi (3.14 m²). E2 cell 1 gives 3.07 m² and
   cell 2 gives 3.16 m² for the same 1 m radius, because the hazards sit at
   different positions relative to the grid and to the arena edge.
7. **H1's effect is modest** (3 items out of about 45), and the primary-metric
   gate was a narrow miss in week 2 (A12 0.629 vs the 0.64 threshold). The
   deviation is recorded in `docs/hypotheses.md` and has to be reported as one.
8. **E4 flatness above 0.02.** Candidate explanation: saturation, because the
   hazard crossing time (on the order of 100 or more steps) is long compared
   with the lethality time scale. Worth confirming, for example by logging
   steps spent inside the hazard.
9. **The AUC figure's step shape.** AUC is exactly 0.5 until about 300 s,
   although the median C2 first loss in E1 is at step 1605 (about 160 s). We
   have not checked why; a candidate is a delay before the map separates the
   hazard from its surroundings. Until then the curve says nothing about map
   quality.
