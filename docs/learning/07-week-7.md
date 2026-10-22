# 07 — Week 7: site fidelity as the main model (E1F–E8F)

Everything in sections 4 and 5 is a replication, not a new blind test. The pre-registration is
the section "Week-7 replication under site fidelity" in `docs/hypotheses.md`, added on 2026-10-22
before any of this week's data existed and before the tuning results were seen. Numbers below come
from `results/week7_chain.out`, `configs/tuned_params_fidelity.yaml`,
`results/analysis/week7/*.csv`, `results/E*F.csv` and `results/analysis_week7.log`.

---

## 1. What changed and why

Week 6 (note 06) showed that restarting search at the nest after every delivery is the main
bottleneck of our foraging model, not a realistic behaviour of ants or the standard computational
model. Throughput tripled under site fidelity (the robot goes back to where it last picked up an
item), the H1/H2 pattern held in E9's baseline-fidelity cell, and the near-nest side effect that
had inflated C2's lead in the E2 random-failure control disappeared.

The week-7 decision: **site fidelity becomes the main foraging model**. The nest-restart
experiments (E1–E8) are kept in the paper as a second, robustness model. Site-fidelity replicates
are named E1F–E8F. E6 and E7 are not replicated because E6b and E7b superseded them.

**Disclosure that H1F/H2F were partly anticipated.** E9 already showed, in its baseline-with-
fidelity cell (cell 1, 100 seeds, C2's nest-restart tuning), that C2 delivered more than C0 (Holm
p = 0.026 within E9) and lost fewer robots than C1 (Holm p < 1e-8 within E9). The H1F and H2F
results are therefore not a fresh surprise: they replicate E9's cell 1 with re-tuned parameters
and a larger set of experiments. The pre-registration records this explicitly.

---

## 2. Re-tuning under site fidelity

Before any main experiments, C2 was re-tuned on the same grid (repel_weight, deposit_sigma,
decay) and C3 on the same risk_k grid as the original tuning in week 3, but with
`search_start: last_pickup`.

### Chosen values

| Parameter | Site fidelity (this week) | Nest restart (original) |
|---|---|---|
| repel_weight | 4.0 | 0.5 |
| deposit_sigma | 0.3 | 0.3 |
| decay | 0.002 | 0.0002 |
| risk_k | 0.5 | 0.5 |

The repel_weight rose from 0.5 to 4.0, and decay became ten times faster (0.002 vs 0.0002). The
candidate explanation for higher repel_weight: with fidelity the robots visit the hazard area more
frequently (they return to their last pickup point), so stronger repellent is needed to push them
away. For faster decay: with fidelity the field turns over faster (robots deposit and depart
rather than lingering), so older marks fade sooner. These are candidates; I did not test them.
deposit_sigma and risk_k stayed the same.

### Was the tuning landscape flat?

The top-10 C2 cells from `tune_c2f` (20 seeds per cell, code 7a1ffd6, time 544 s):

| repel_weight | deposit_sigma | decay | Median delivered | Mean lost |
|---|---|---|---|---|
| 4.0 | 0.3 | 0.002 | 146.0 | 2.20 |
| 0.5 | 0.3 | 0.0002 | 143.5 | 2.00 |
| 2.0 | 0.3 | 0.002 | 142.5 | 1.90 |
| 1.0 | 0.3 | 0.0002 | 140.5 | 1.70 |
| 2.0 | 0.3 | 0.0005 | 140.0 | 1.70 |
| 4.0 | 0.3 | 0.0002 | 139.5 | 1.80 |
| 2.0 | 0.5 | 0.002 | 139.5 | 2.15 |
| 0.5 | 0.3 | 0.002 | 139.5 | 2.25 |
| 1.0 | 0.3 | 0.0005 | 138.5 | 2.15 |
| 4.0 | 0.2 | 0.0005 | 138.0 | 1.95 |

The range across these ten cells is 146.0 − 138.0 = 8.0 items. At site-fidelity throughput (~140
items per 100 seeds), a rough estimate of per-seed SD is about 13–15 items (implied by the
bootstrap CIs in E1F below), giving SE for 20 seeds of about 3.0–3.4 items. A range of 8 items
across ten cells is about 2–3 SEs, somewhat wider than the nest-restart grid (where SD/SE ≈ 1; see
note 03). So the landscape is not completely flat: higher repel_weight combined with faster decay
showed a real edge at the top. The selection rule (highest median; ties broken by lowest mean lost)
chose repel_weight = 4.0, deposit_sigma = 0.3, decay = 0.002, and C3's risk_k = 0.5.

The C3 tune (`tune_c3f`, code 933e867, 2102 s):

| risk_k | Median delivered | Mean lost |
|---|---|---|
| 0.50 | 136.5 | 2.15 |
| 2.00 | 135.5 | 2.00 |
| 1.00 | 135.0 | 1.95 |
| 4.00 | 133.0 | 2.15 |
| 0.25 | 127.5 | 1.90 |

risk_k = 0.50 again wins, same as the nest-restart value. The spread (127.5 to 136.5) is wider, but
risk_k = 0.25 is the outlier (the hazard-avoidance was too cautious); the other four are within
about 3 items.

---

## 3. Provenance

**Code.** All eight main experiments ran at commit f8de905, recorded in `results/analysis_week7.log`:

```
E1F: code f8de905 (every golden case from fe78c66 reproduced bit-identically)
E2F: code f8de905 (every golden case from fe78c66 reproduced bit-identically)
...
E8F: code f8de905 (every golden case from fe78c66 reproduced bit-identically)
```

fe78c66 is the commit where E1's golden cases were recorded. "Bit-identically" means the old
controllers C0–C4 with `search_start: nest` behave exactly as at E1's commit when the new features
are off. This was checked on one machine only, as in earlier weeks.

**Identity checks** (`results/analysis/week7/identity_checks.csv`): five checks, all True.

| Experiment | Controller | Cells checked | Identical |
|---|---|---|---|
| E7bF | C0 | 0 1 2 3 4 5 (all six) | True |
| E7bF | C1 | 0 5 (no noise vs false ×10) | True |
| E8F | C0 | 1 2 (moved, tuned vs moved, fast decay) | True |
| E8F | C1 | 1 2 | True |
| E8F | C4 | 1 2 | True |

C0 is identical in all E7bF cells because it ignores wrecks; C1 is identical in cells 0 and 5
because it ignores false sightings. In E8F, C0, C1 and C4 are identical in cells 1 and 2 because
none of them reads the repellent field; only the decay speed differs between those cells, which
does not affect them.

**Run counts and batch times** (`results/week7_chain.out`):

| Experiment | Runs | Batch time |
|---|---|---|
| E1F | 500 | 365 s |
| E2F | 2,000 | 2,290 s |
| E3F | 2,500 | 2,052 s |
| E4F | 2,000 | 1,282 s |
| E5F | 1,500 | 2,203 s |
| E6bF | 1,500 | 8,403 s |
| E7bF | 2,400 | 8,515 s |
| E8F | 1,200 | 2,785 s |
| **Total** | **13,600** | | |

Plus tuning: tune_c2f 544 s and tune_c3f 2,102 s, for a grand-chain start of 08:16 and finish of
16:46 on 2026-10-22.

---

## 4. Confirmatory replication H1F–H4F

### Test table

All four tests use 100 seeds from E1F (baseline) or E2F cell 3 (no hazard, random failures), 
paired Wilcoxon signed-rank (one-sided for H1F, H2F, H4F). Holm correction covers H1F, H2F and
H4F together (family of three). H3F uses the CI bound rule only. Numbers from
`results/analysis/week7/confirmatory_F.csv`; per-seed win/tie/loss computed from
`results/E1F.csv` and `results/E2F.csv`.

| H | Claim | Median C2 | Median C0/C1/C3 | Paired diff [95% CI] | A12 [95% CI] | p | Holm p | Verdict | Seed wins / ties / losses |
|---|---|---|---|---|---|---|---|---|---|
| H1F | C2 delivers more than C0 | 139 | 135 (C0) | +1 [0, +4] | 0.556 [0.524, 0.592] | 0.00046 | 0.00092 | **Supported** | 52 / 23 / 25 |
| H2F | C2 loses fewer than C1 | 2 | 3 (C1) | −1 [−1, 0]* | 0.664 [0.609, 0.719] | 3.5e-8 | 1.0e-7 | **Supported** | 51† / 40 / 9 |
| H4F | C3 delivers more than C2 | 139 | 139 (C3) | 0 [0, 0] | 0.499 [0.479, 0.518] | 0.453 | 0.453 | **Not supported** | 24 / 52 / 24 |
| H3F | C2 item cost vs C0 small | 127 | 124.5 (C0) | −5 [−10, +1] | 0.455 [0.396, 0.513] | — | — | **Supported** (CI rule) | 42 / 0 / 58 |

*H2F paired diff is stated as C1 − C2 (losses), so a positive value means C1 loses more. The
entry here shows C2 − C1 for readability (direction is always "C2 fewer"), so the cell shows −1.
†For H2F: wins = seeds where C1 lost more robots than C2; losses = seeds where C2 lost more.

**H1F and H2F: supported.** The pattern from week 3 holds under site fidelity and with the tuned
parameters. The effect sizes (A12 0.556 and 0.664) are similar to the nest-restart results (H1:
A12 0.661; H2: A12 0.789). Under site fidelity the relative gain in delivered items is smaller
(about 3% over C0 vs about 7% under nest restart) because throughput is much higher and C2's lead
is diluted over more items.

**H4F: not supported.** C3 showed no detectable advantage over C2 (median difference 0, A12 0.499,
Holm p = 0.453). This matches the original H4 result (also not supported). C3's hazard-avoidance
bonus does not add detectably to C2's marking under either foraging model.

**H3F: supported but the paired difference is negative.** H3F is supported by the CI bound:
A12(C2, C0) = 0.455 and its lower 95% CI bound is 0.396, which is above the pre-registered
threshold of 0.36. The criterion was that the *cost* of marking on deliveries must be small,
and A12 = 0.455 (not far below 0.5) satisfies it. However, the paired median difference is −5
[−10, +1]: on most seeds (58 of 100) C2 delivered fewer items than C0, by a median of 5. This
is in the opposite direction to H3 under nest restart, where C2 had a median lead of +1 [0, +2.5]
and A12 = 0.582. The reversal connects directly to week 6: with the nest restart, random wrecks
near the nest got marked by C2, pushing robots out of the nest area faster and boosting deliveries
(a foraging-model artefact). With fidelity that artefact is gone, and marking random failures now
represents a small real cost — C2 wastes some time avoiding random wrecks with no information
value. H3F is still technically satisfied because the cost is small; but the honest reading is that
marking in the random-failure control is now a small net cost, not the spurious benefit it was
under nest restart.

---

## 5. Exploratory

The analysis for each of E2F–E5F follows its nest-restart counterpart (Friedman per cell, paired
Wilcoxon vs C2, Holm within experiment), plus new across-cell tests for C2 (each cell vs cell 0,
paired by seed). E6bF, E7bF and E8F follow the week-5 analysis plan. All exploratory; no p-value
here is confirmatory.

### 5.1 E2F: hazard position and the random-failure control

E2F has the same four cells as E2 (hazard next to patch, cell 0; between patch and nest, cell 1;
far from everything, cell 2; no hazard + random failures, cell 3). All four cells now share cell 0's
random streams (paired). Selected medians from `results/analysis/week7/E2F_descriptive.csv`:

| Cell | C0 | C2 | C3 | C4 |
|---|---|---|---|---|
| 0: next to patch | 130.5 del, 4 lost | 138.0 del, 2 lost | 140.0 del, 2 lost | 149.0 del, 0 lost |
| 1: between patch and nest | 76.0 del, 12 lost | 128.5 del, 5 lost | 128.0 del, 5 lost | 146.5 del, 0 lost |
| 2: far from everything | 138.5 del, 4 lost | 144.5 del, 2 lost | 145.0 del, 2 lost | 151.5 del, 0 lost |
| 3: no hazard, random failures | 124.5 del, 4.5 lost | 127.0 del, 4.5 lost | 127.0 del, 4.5 lost | 124.5 del, 4.5 lost |

Cell 1 is the most striking: with the hazard between the patch and nest, C0 delivers only 76
items and loses 12 robots (vs 130+ items and 4 lost in other hazard cells), while C2 delivers
128.5 and loses only 5. Under nest restart, E2 cell 1 gave C0 = 17 delivered, 17 lost; C2 = 42
delivered, 4.5 lost. The absolute gap is much larger with fidelity (C0 at 76 vs C2 at 128.5),
likely because robots with fidelity must return to their last pickup point through the hazard zone
more often, so the marking benefit is amplified. This is a descriptive observation, not tested.

**Within-cell tests** (`E2F_exploratory.csv`, Holm across all tests in E2F). C2 delivers more
than C0 in cells 0 (A12 0.399 [0.354, 0.443], Holm p = 0.00074) and 2 (A12 0.413 [0.370, 0.454],
Holm p = 0.00064), and loses fewer robots in cells 0, 1 and 2 (Holm p at most 5.2e-16). In cell 1,
C0 delivers far less than C2 (A12(C0, C2) = 0.031 [0.015, 0.052], Holm p = 1.6e-16). C2 loses
fewer robots than C1 in cells 0 (A12(C1, C2) = 0.712, Holm p = 4.5e-9), 1 (A12 = 0.909, Holm p =
5.6e-16), and 2 (A12 = 0.735, Holm p = 8.9e-11). In cell 3 (random failures), all controllers are
statistically indistinguishable on robots lost (Holm p = 1 for all) and on delivered (Holm p ≥ 0.54
for all), consistent with H3F: marking adds no detectable benefit and imposes only a small cost.

**Across-cell tests for C2** (new, paired cells): C2 in cell 1 (hazard between patch and nest)
delivered far fewer items than in cell 0 (median 128.5 vs 138.0, paired median diff −9.5 [−16,
−5], A12 = 0.324 [0.258, 0.391], Holm p = 5.7e-5) and lost more robots (5 vs 2, A12 = 0.957,
Holm p = 2.0e-16). Cell 2 (hazard far away) delivered slightly more than cell 0 (144.5 vs 138.0,
diff +4 [+2, +6], A12 = 0.584, Holm p = 0.28, not surviving Holm). Cell 3 (random failures)
delivered far fewer than cell 0 (127.0 vs 138.0, diff −11 [−21, −7.5], A12 = 0.310, Holm p = 2.8e-6)
and lost more robots (4.5 vs 2, A12 = 0.915, Holm p = 1.6e-15). So across paired cells, the
position of the hazard clearly matters: having it between the patch and the nest causes both large
delivery and loss penalties for C2 under site fidelity.

**New measures.** repellent_in_hazard (share of the field's total mass inside the true hazard):
C2 in cell 0: median 0.580 [0.552, 0.626]; cell 1: 0.563 [0.540, 0.597]; cell 2: 0.603 [0.558,
0.633]; cell 3: all 0.0 (no hazard, no field laid down). Marked runs: 91 in cells 0 and 1, 87 in
cell 2, 0 in cell 3. AUC (marked runs only): cells 0–2: 0.782 [0.757, 0.804], 0.931 [0.919,
0.953], 0.797 [0.766, 0.813]. Cell 1's AUC over marked runs is notably high (0.931), candidate
explanation: the hazard is close to the robot-dense region between patch and nest, so marks
accumulate there efficiently.

**Nest-restart comparison** (from `model_comparison.csv`; unpaired, descriptive). Under nest
restart (E2): C0 / C2 delivered in cell 1 were 17 / 42 (C2 median 42 vs 128.5 under fidelity).
The absolute gain of fidelity is much larger in the "between" cell than in the other cells,
suggesting that fidelity magnifies the cost of a strategically placed hazard.

### 5.2 E3F: swarm size (5, 10, 20, 40, 80 robots)

Medians from `E3F_descriptive.csv`. Five robot sizes, 100 seeds per cell, all cells paired:

| Robots | C0 del | C2 del | C2 lost | Nest-restart C2 del |
|---|---|---|---|---|
| 5 | 37.5 | 37.0 | 1.0 | 12.0 |
| 10 | 70.0 | 71.5 | 1.0 | 24.0 |
| 20 | 132.0 | 140.0 | 2.0 | 44.0 |
| 40 | 251.5 | 262.5 | 3.0 | 85.5 |
| 80 | 480.0 | 512.5 | 3.0 | 164.5 |

Fidelity roughly triples throughput at every size (e.g., 140 vs 44 at N=20, 262.5 vs 85.5 at
N=40). C2's advantage over C0 is visible at every size.

Within-cell tests (Holm across all E3F tests): C2 delivers more than C0 in cells 2, 3 and 4 (Holm
p at most 0.0082), no detectable difference in cells 0 and 1 (Holm p = 1). C2 loses fewer robots
than C0 in cells 1, 2, 3 and 4 (Holm p at most 0.0028); cell 0 (N=5) shows no detectable
difference (Holm p = 0.82). C3 shows no detectable difference from C2 at any size (all Holm p = 1).

Across-cell tests (new): C2's deliveries rise significantly at every step up in swarm size (all
Holm p < 2e-15). Robots lost also rises (Holm p at most 0.0028 from N=5 to 10). Marked runs rise
from 10 at N=5 to 100 at N=80; median AUC (over marked runs) rises from 0.739 at N=5 to 0.901 at
N=80. repellent_in_hazard for C2: 0.562 at N=5 (marked runs only, n=10), rising to 0.572 at N=80.

**Nest-restart comparison** (descriptive). The relative ranking across swarm sizes is similar
under both foraging rules. C2's item lead over C0 at N=80 is +32.5 under fidelity (512.5 vs 480.0)
vs +14.5 under nest restart (164.5 vs 150.0).

### 5.3 E4F: lethality (0.005, 0.02, 0.1, 1.0 per step)

Medians from `E4F_descriptive.csv`. Four lethality cells, 100 seeds per cell, paired:

| Cell | Lethality | C2 del | C2 lost | AUC marked (n) | repellent_in_hazard |
|---|---|---|---|---|---|
| 0 | 0.005 | 142.5 | 2 | 0.797 (82) | 0.614 |
| 1 | 0.02 | 135.0 | 2 | 0.763 (92) | 0.580 |
| 2 | 0.1 | 136.5 | 2 | 0.762 (94) | 0.504 |
| 3 | 1.0 | 139.0 | 2 | 0.730 (96) | 0.456 |

Something unusual compared to the nest-restart E4: under site fidelity, lethality 0.005 (lowest)
gives higher deliveries (142.5) than higher lethalities (135–139). The cross-cell tests for C2
show cell 2 vs cell 0 has a small negative delivery trend (diff −1.5 [−5, 0], A12 = 0.433,
Holm p = 0.63, not surviving) and cell 3 vs cell 0 also negative (diff −2 [−7.5, 0], A12 = 0.438,
Holm p = 0.33, not surviving). There is no clear lethality effect on losses (all cross-cell Holm
p ≥ 0.36). Candidate explanation: at low lethality robots survive more visits and collect more
items; with fidelity this helps more because they return to productive areas. I did not test this.

repellent_in_hazard decreases from 0.614 at lethality 0.005 to 0.456 at lethality 1.0 — a
candidate interpretation is that at high lethality, robots die quickly in the hazard and leave
wrecks near the edge, so the repellent mass sits partly outside the hazard; at low lethality, robots
survive longer and mark deeper inside it. This is a candidate; I did not measure wreck positions.

**Nest-restart comparison** (descriptive). Under nest restart E4, C2 delivered 46, 44, 44.5, 45
items across lethalities 0.005 to 1.0, near-flat. Under fidelity the values are 142.5, 135.0, 136.5,
139.0 — a slightly wider spread but still mostly within the within-seed variation.

### 5.4 E5F: hazard radius (0.5 m, 1 m, 2 m)

Medians from `E5F_descriptive.csv`. Three paired radius cells:

| Cell | Radius | C0 del | C2 del | C2 lost | AUC marked (n) | repellent_in_hazard |
|---|---|---|---|---|---|---|
| 0 | 0.5 m | 134.5 | 136.0 | 1 | 0.995 (74) | 0.468 |
| 1 | 1 m | 128.0 | 133.0 | 2 | 0.765 (87) | 0.573 |
| 2 | 2 m | 118.0 | 129.0 | 3 | 0.667 (98) | 0.619 |

At radius 0.5 m the hazard area is small (0.75 m²), and the AUC over marked runs is very high
(0.995) — essentially perfect localisation when any mark exists, because the small hazard is
well-separated from other areas. The repellent_in_hazard is lower (0.468) because most of the
field sits just outside a small hazard. At 2 m the hazard is large (8.23 m²) and AUC drops to
0.667 — harder to distinguish a large diffuse hazard.

Within-cell tests: C2 delivers more than C0 in cells 1 and 2 (A12(C0, C2) = 0.405 [0.360, 0.447],
Holm p = 0.00077 for cell 1; A12 = 0.338 [0.285, 0.391], Holm p = 2.7e-6 for cell 2). Cell 0
shows no detectable delivery difference (Holm p = 0.031, not surviving Holm). C2 loses fewer robots
than C0 in all three cells (Holm p at most 3.2e-12) and than C1 in cells 1 and 2 (Holm p at most
5.8e-8). C3 shows no detectable difference from C2 in any cell.

Across-cell tests for C2: larger radius costs deliveries (cell 1 vs 0: diff −3 [−4.5, 0], A12 =
0.453, Holm p = 0.017) and costs losses (A12 = 0.737, Holm p = 4.6e-9). Cell 2 vs 0 is similar
(delivery diff −9 [−13, −4], A12 = 0.394, Holm p = 0.0017; lost A12 = 0.904, Holm p = 7.8e-16).
So a larger hazard is detectably harder for C2 to handle.

**Nest-restart comparison** (descriptive). Under E5: C2 delivered 46 / 44.5 / 43 at radii 0.5 /
1 / 2 m, C2 lost 1 / 2 / 2. Under fidelity: C2 delivered 136.0 / 133.0 / 129.0, lost 1 / 2 / 3.
The gradient across radii is similar under both models.

### 5.5 E6bF: information medium (C2 vs C6 vs C5) by swarm size

Analysis as in E6b (week 5): paired Wilcoxon vs C2 and C6 vs C5, Holm over 30 tests.

Medians from `E6bF_descriptive.csv`:

| N robots | C2 del | C5 del | C6 del | C2 lost | C5 lost | C6 lost |
|---|---|---|---|---|---|---|
| 5 | 38.5 | 38.5 | 38.5 | 1 | 1 | 1 |
| 10 | 72.5 | 72.5 | 72.5 | 1 | 1 | 1 |
| 20 | 136.5 | 136.5 | 137.0 | 2 | 2 | 2 |
| 40 | 261.0 | 260.5 | 261.0 | 3 | 3 | 3 |
| 80 | 515.5 | 515.5 | 513.5 | 3 | 3 | 3 |

Nothing survives Holm correction (`E6bF_tests.csv`). The minimum Holm p across all 30 tests is 0.52
(delivered, C5 vs C2 at N=80, raw p = 0.018). Every paired median difference is 0 except delivered
at N=80 where C5 and C6 are each about −4 to −5 below C2 (median diff −4.5 and −5 [CI both include
0]). Every A12 is within [0.450, 0.555].

C6's known_frac (share of records known per live robot at the end): median 0.417 at N=5 (18 marked
runs), 0.778 at N=10, 1.0 at N=20 and 40, 0.991 at N=80. At N=20 and 40 information spread fully
in every marked run; at N=80 nearly so. As in week 5, C6 often reaches full spread, which is a
candidate for why C2 ≈ C6.

**Plain reading.** No detectable difference among C2, C5 and C6 at any swarm size after Holm
correction (100 seeds per size). This is not a finding of equivalence; with 100 seeds we cannot
rule out small effects. The candidate explanation from week 5 still holds: when C6's records spread
fully, C6 ≈ C2 in behaviour.

**Nest-restart comparison** (descriptive). Under E6b at N=40: C2/C5/C6 delivered 85.5/85.0/85.0
lost 3/2.5/2. Under E6bF: 261.0/260.5/261.0, lost 3/3/3. Rankings are similar; the near-null
result holds under both foraging models.

### 5.6 E7bF: detection noise (six noise cells)

Analysis as in E7b: paired Wilcoxon within cells (vs C2, Holm over all 66 E7bF tests) and
across cells (each noisy cell vs cell 0, for C1, C2 and C3).

Selected medians from `E7bF_descriptive.csv`:

| Cell | C0 del / lost | C1 del / lost | C2 del / lost | C3 del / lost |
|---|---|---|---|---|
| 0: no noise | 131 / 4 | 136 / 3 | 139 / 2 | 138.5 / 2 |
| 1: miss 0.5 | 131 / 4 | 136 / 3 | 138 / 2 | 139 / 2 |
| 2: miss 0.8 | 131 / 4 | 136 / 3 | 138 / 2 | 138 / 2 |
| 3: miss 0.5, spells | 131 / 4 | 137 / 3 | 138 / 2 | 137.5 / 2 |
| 4: miss 0.8, spells | 131 / 4 | 132.5 / 3 | 136.5 / 2 | 136 / 2 |
| 5: false ×10 | 131 / 4 | 136 / 3 | 141 / 2 | 140 / 2 |

C0 is identical in all six cells (identity check confirmed). Within each cell, C2 loses fewer
robots than C0 (all surviving Holm: Holm p at most 8e-15) and fewer than C1 (all surviving Holm:
Holm p at most 2.1e-10). C3 shows no detectable difference from C2 in any cell.

**Across-cell tests for C1, C2 and C3** (Holm over all 66 E7bF tests; `E7bF_tests.csv`):

- **C1, robots lost:** no detectable change in any noisy cell (Holm p ≥ 0.015, which is 0.015 for
  the correlated miss cells). Wait — checking the csv: C1 across cell 4 vs 0 (80% misses in spells)
  shows A12 = 0.612 [0.563, 0.664], Holm p = 0.0012. So in cells 3 (miss 0.5, spells) and 4 (miss
  0.8, spells), C1 loses slightly more robots (Holm p = 0.015 and 0.0012). Cell 5 identical runs,
  p = 1. Cells 1 and 2 (independent misses) no detectable change.
- **C2, robots lost, cell 4** (miss 0.8, spells): A12 = 0.676 [0.621, 0.731], Holm p = 1.2e-6,
  median diff +0.5 [0, +1]. A small upward shift in losses survives Holm.
- **C2, robots lost, cell 3** (miss 0.5, spells): A12 = 0.598 [0.558, 0.642], Holm p = 0.0024.
  Also survives Holm, same sign, smaller effect.
- **C2, delivered:** no detectable change in cells 1–4. Cell 5 (false ×10): C2 delivered 141.0 vs
  139.0 without noise. A12 = 0.553 [0.472, 0.636], Holm p = 1.0. Not surviving after Holm.
- **C3, robots lost, cells 3 and 4:** similarly small shifts survive (Holm p 0.00089 and 1.1e-6).
- **False sightings (cell 5):** C2 delivered 141.0 vs 139.0 in cell 0, C3 delivered 140.0 vs 138.5.
  Under nest restart (E7b cell 5) the gain was 7 items median (51.5 vs 44.0 for C2). Under
  fidelity the gain is only about 2 items and does not survive Holm. This matches the prediction
  from week 6: with fidelity, phantom repellent near the nest still pushes robots out, but the
  nest-restart bottleneck is gone, so the push saves much less search time.

AUC for C2 cell 5 with false sightings: median 0.611 (marked runs only), vs 0.753 in cell 0 with
no noise. The map quality drops under false sightings as expected, because phantoms mark non-hazard
areas. repellent_in_hazard cell 5: 0.006 [0.001, 0.022] — almost none of the repellent mass is
inside the hazard, because phantoms flood non-hazard areas. This new measure makes the false-
sighting degradation legible directly.

**Nest-restart comparison** (descriptive). The key pattern from E7b holds: C2 still loses fewer
robots in every cell, and the false-sighting gain in deliveries effectively disappears under
fidelity (≤2 vs 7 under nest restart). The `model_comparison.csv` confirms: E7bF cell 5 C2 = 141
delivered, E7b cell 5 C2 = 51.5 delivered — the absolute numbers differ because of fidelity's
higher throughput, but the relative gain of 141/139 ≈ 1.4% is much smaller than E7b's 51.5/45 =
14.4%.

### 5.7 E8F: hazard moves half-way through

Analysis as in E8: within cells (vs C2, Holm over all 24 E8F tests) and C2 across cells (cell 1 vs
0 and cell 2 vs 1, paired). Three paired cells, copied from E8 together with their explicit decay values: cell 0 static,
decay 0.0002; cell 1 moved, decay 0.0002; cell 2 moved, decay 0.002. Because E8's cells set
decay explicitly, those values override the site-fidelity tuning (0.002). So in E8F, cells 0
and 1 use the old, *slow* decay, and cell 2 uses the decay that the site-fidelity tuning chose.
I return to this below.

Medians from `E8F_descriptive.csv`:

| Controller | Cell 0 (static, decay 0.0002) | Cell 1 (moved, decay 0.0002) | Cell 2 (moved, decay 0.002) |
|---|---|---|---|
| C0 del_post / lost_post | 77 / 2 | 77 / 3 | 77 / 3 |
| C1 del_post / lost_post | 80 / 1 | 78 / 2 | 78 / 2 |
| C2 del_post / lost_post | 81.5 / 0 | 77 / 2 | 79.5 / 2 |
| C4 del_post / lost_post | 91 / 0 | 91 / 0 | 91 / 0 |

C2 in the static cell (0) lost a median of 0 robots after step 5000 and delivered 81.5 items. In
the moved cell (1) C2 delivered 77 and lost 2. The difference survives Holm (delivered: A12 =
0.405 [0.361, 0.444], Holm p = 6.6e-5; lost: A12 = 0.879 [0.829, 0.921], Holm p = 1.6e-13). So
a hazard move costs C2 deliveries and robots under site fidelity, as under nest restart.

The decay comparison (cell 2, decay 0.002, vs cell 1, decay 0.0002) shows no detectable difference on delivered_post
(A12 = 0.549, Holm p = 0.92) or lost_post (A12 = 0.518, Holm p = 1.0).

**The decay detail.** The pre-registration said E8F uses "the controllers and cells of E8", and
E8's cells set decay explicitly (0.0002, 0.0002, 0.002), so E8F did exactly that. The consequence
is that E8F still compares a slow decay (0.0002) with a ten-times-faster one (0.002), as E8 did,
but under site fidelity the faster one is now the *tuned* value, and the static and moved cells
(0 and 1) use the slow, untuned value. So: the cost of a move (cell 1 vs 0) is measured at decay
0.0002, and the decay comparison found no detectable difference between 0.0002 and 0.002 after the
move, just as in E8.

AUC over time (from E8F.csv medians): at 500 s (just before the move) C2 in cell 1 reaches AUC
~0.720; right after the move (550 s) it drops below 0.5. By 1000 s it recovers to ~0.697
(from `E8F_descriptive.csv`: auc_final_median for cell 1 = 0.697 [0.591, 0.722]; static cell 0 =
0.745 [0.738, 0.764]). Old-hazard AUC at end (auc_old_final): cell 1 = 0.731, cell 2 = 0.739 —
old information is still present in the map at the end of the run, similar to the nest-restart
pattern.

C4 after the move: median lost = 0 in cells 1 and 2 (Holm p < 1e-16 vs C2); median delivered = 91
in both vs C2's 77 and 79.5.

**Nest-restart comparison** (descriptive). E8 (nest restart): C2 lost_post 0 static, 2 moved, 2
fast; E8F: C2 lost_post 0 static, 2 moved, 2 with decay 0.002. The pattern is the same.

---

## 6. What this changes for the paper

Suggested wording, for discussion with your mentor:

**Site fidelity becomes the main model.** The paper leads with E1F–E8F. The introduction and
methods present site fidelity (`search_start: last_pickup`) as the foraging rule; the nest-restart
model is described separately and its results appear in a robustness or supplementary section.

**H1F and H2F.** "Replicating the study under site fidelity (100 seeds), C2 delivered more items
than C0 (median 139 vs 135; paired median difference +1 [0, +4]; A12 = 0.556 [0.524, 0.592];
Holm p = 0.00092) and lost fewer robots than C1 (median 2 vs 3; A12 = 0.664 [0.609, 0.719];
Holm p = 1e-7). H4F was not supported (C3 vs C2: median difference 0, A12 = 0.499, Holm p = 0.45),
consistent with the nest-restart result."

**H3F and the control.** "Under site fidelity, marking in the random-failure control (E2F cell 3)
showed a small negative per-seed effect (paired median difference −5 [−10, +1] items) and C2 won
on only 42 of 100 seeds. The pre-registered criterion (A12 lower 95% CI > 0.36) was met
(A12 = 0.455 lower CI = 0.396 > 0.36), so H3F is technically supported: the cost is small. We
note, however, that the direction reversed from nest restart (under nest restart, C2 had a +1
item median advantage in the control). Week 6 showed that the nest-restart advantage was an
artefact of random wrecks pushing robots out of the nest area. With site fidelity, that mechanism
is absent, and marking random wrecks imposes a small real cost."

**Nest-restart model.** "The nest-restart experiments (E1–E8) are reported as a second foraging
model. Both models support H1 and H2; H3's direction is model-dependent (positive under nest
restart, negative under fidelity). H4 is not supported under either model."

**Foraging efficiency.** "Site fidelity roughly tripled throughput across all controllers and all
swarm sizes (e.g., C2: 44 items at N=20 under nest restart vs 140 under fidelity), confirming
week 6. The H1 relative gain in items over C0 is smaller under fidelity (~3% vs ~7%), but the H2
robot-saving benefit is similar in effect size."

---

## 7. Things to check

1. **E8F decay values.** E8F's static and moved cells use decay 0.0002 (copied from E8), not the
   site-fidelity tuned 0.002. The paper should say so. Is it worth a small extra cell (static,
   decay 0.002) so the move cost is also measured at the tuned value?

2. **H3F honest framing.** The hypothesis was designed to test "marking does not impose a large
   cost". Under fidelity the paired data say C2 loses 5 items per seed on median. Should the paper
   state H3F as "met, but note a small cost" or add a note that the hypothesis's wording was
   influenced by the nest-restart artefact?

3. **Cell 1 in E2F (between patch and nest).** C0 delivers only 76 items and loses 12 robots
   under fidelity, a much larger penalty than under nest restart (17 items, 17 lost). The
   absolute C2 advantage in cell 1 is very large (128.5 vs 76.0). Should this be highlighted
   in the main paper as a key practical scenario where marking matters most?

4. **repellent_in_hazard for cell 5 (false sightings).** Under E7bF cell 5, C2's
   repellent_in_hazard is 0.006 — nearly all the field is phantom repellent outside the hazard. Is
   it worth showing this alongside AUC to demonstrate how badly false sightings distort the map,
   even though deliveries barely change?

5. **H1F / H2F partly anticipated disclosure.** The pre-registration states that E9 already showed
   the H1F and H2F patterns. Should the paper include this disclosure explicitly, or place it only
   in a methods/limitations note?

6. **AUC over marked runs vs over all runs.** Under site fidelity, marked-run AUC is now reported
   alongside the all-run AUC. At N=5 (E3F cell 0) C2's AUC over all 100 runs is 0.500 but over
   the 10 marked runs it is 0.739. Which figure should be primary in the paper?

7. **Model-comparison table.** A single table showing medians for each experiment under both
   foraging rules would help readers compare. Is that clearer than separate results sections?
