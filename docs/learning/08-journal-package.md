# 08 — Journal package: C7 alerts, arena scale, two hazards (E10–E12, E10b)

Everything here is **exploratory**. The pre-registration is the section
"Journal-package experiments" in `docs/hypotheses.md`, added 2026-10-22 before any data
existed. E10b was added the same day, but after seeing `tune_c7f` and E10 — that
post-hoc timing is disclosed wherever it matters. No p-value here is confirmatory.
Numbers come from `results/journal_chain.out`, `results/e10b_batch.out`,
`results/analysis_journal.log`, `results/analysis/journal/*.csv`, `results/E10.csv`,
`results/E10b.csv`, `results/E11.csv`, `results/E12.csv`, and
`configs/tuned_params_c7.yaml` / `configs/tuned_params_c7b.yaml`.

---

## 1. What was added and why

### C7: risk-limit alerts (limitation #13)

Hunt, Cullen and Hauert (2021, Proc. SPIE 11758) describe robots that track their own
accumulated hazard exposure and broadcast an alert to neighbours when a risk threshold is
exceeded. Their robots can sense the hazard directly; ours cannot — they only see wrecks.
C7 is an **adaptation inspired by that idea**, not a re-implementation of their method.
It uses exactly the same first-sighting evidence as C2's marking. The paper must say
"inspired by" rather than claim it reproduces their approach.

How C7 works: each robot keeps a decaying risk score (decay factor 1 − 0.001 per step).
Every time it first spots a wreck, it adds 1 to the score. When the score reaches
`alert_limit`, the robot broadcasts its current position to all live robots within
comm\_range (1 m), then resets its score to 0. Receivers avoid that position within
1 m for `alert_duration` steps, using the same repel\_weight as C2 scaled by distance.
There are no marks in the environment and no persistent shared field. C7 also avoids
visible wrecks exactly as C1 does.

What C2 vs C7 isolates: persistent environmental marks (C2) versus transient position
alerts passed between neighbours (C7), from the same evidence.

### E11: arena scale and communication range (limitations #7 and #8)

E6bF found no detectable difference among C2, C5 and C6 at any swarm size. A candidate
explanation is that information spread to nearly every robot in our small arena. E11 makes
spreading harder by introducing `arena_scale`: a multiplier on arena size, nest position,
and patch and hazard centres (radii stay fixed). Robot density is kept constant — at scale
2 the arena is 20 m × 20 m and n\_robots rises to 80. With `arena_scale` 1 the runs are
bit-identical to earlier experiments (verified by the golden test).

### E12: two hazards (limitation #5)

All earlier experiments used a single hazard. E12 adds a second hazard that is a mirror
image of the first, centred at (1.19, 3.81) next to the second patch at (2.5, 2.5). Cell 2
raises lethality to 0.1. Localisation AUC uses the union of both hazard masks; the
descriptive tables also report AUC against each hazard separately.

---

## 2. Provenance

**Code.** Every golden case from fe78c66 reproduced bit-identically:

| Experiment | Code | Note |
|---|---|---|
| tune\_c7f | 32e05a6 | tuning batch |
| E10 | 60c528d | |
| E11 | 60c528d | |
| E12 | 60c528d | |
| E10b | 5f07b60 | separate batch, different commit |

The four main runs (E10, E11, E12, and tune\_c7f) form one chain; E10b ran as a separate
batch after E10 was inspected.

**Run counts and batch times** (`results/journal_chain.out` and `results/e10b_batch.out`):

| Experiment | Runs | Batch time |
|---|---|---|
| tune\_c7f | 180 (9 cells × 20 seeds) | 538 s |
| E10 | 1,200 (4 controllers × 3 cells × 100 seeds) | 2,932 s |
| E11 | 1,500 (3 controllers × 5 cells × 100 seeds) | 12,012 s |
| E12 | 1,500 (5 controllers × 3 cells × 100 seeds) | 3,615 s |
| **Chain total** | **4,380** | start 16:49:31, done 22:10:58 |
| E10b | 1,200 | 822 s (separate batch) |

**Analysis provenance** (`results/analysis_journal.log`):

```
E10:  code 60c528d (every golden case from fe78c66 reproduced bit-identically)
E10b: code 5f07b60 (every golden case from fe78c66 reproduced bit-identically)
E11:  code 60c528d (every golden case from fe78c66 reproduced bit-identically)
E12:  code 60c528d (every golden case from fe78c66 reproduced bit-identically)
wrote E10:  25 tests (expected 25  OK)
wrote E10b: 25 tests (expected 25  OK)
wrote E11:  38 tests (expected 38  OK)
wrote E12:  28 tests (expected 28  OK)
```

---

## 3. C7 tuning and the flaw

**The tune\_c7f table** (20 seeds per cell; grid: `alert_limit` ∈ {1, 2, 3} ×
`alert_duration` ∈ {300, 1000, 3000}; `alert_decay` fixed at 0.001; selection rule:
highest median delivered, ties broken by lowest mean lost):

| alert\_limit | alert\_duration | Median delivered | Mean lost | Mean alerts\_sent |
|---:|---:|---:|---:|---:|
| 3 | 1000 | 142.0 | 2.50 | 0.00 |
| 2 | 1000 | 138.0 | 2.70 | 0.10 |
| 3 | 300 | 138.0 | 2.70 | 0.00 |
| 1 | 3000 | 137.5 | 3.95 | 4.55 |
| 3 | 3000 | 136.5 | 3.00 | 0.00 |
| 1 | 1000 | 135.5 | 3.75 | 3.70 |
| 2 | 3000 | 132.5 | 2.65 | 0.05 |
| 1 | 300 | 129.5 | 3.55 | 4.30 |
| 2 | 300 | 124.0 | 3.30 | 0.05 |

(Numbers computed from `results/tune_c7f.csv` and verified against
`results/journal_chain.out`.)

**The flaw.** With `alert_decay` 0.001, a robot's risk score decays by a factor of
0.999 every step and gains 1 only when it first sees a wreck. In the baseline scenario
a robot sees on average about 2 wrecks in a full 10,000-step run. The score therefore
almost never reaches 2 or 3. At `alert_limit` 2 the mean alerts\_sent per run was
0.05–0.10; at `alert_limit` 3 it was 0.00 in every cell — no robot ever sent an alert.
The selection rule chose `alert_limit` 3 on noise: the top-ranked cell had the highest
median delivered, but the mechanism was completely inactive.

The E10 run used `alert_limit` 3, `alert_duration` 1000 (the pre-registered winner, from
`configs/tuned_params_c7.yaml`). With 0 alerts sent in cells 0 and 2 and a mean of 0.08
per run in cell 1, C7 as run in E10 is effectively identical to C1: same first-sighting
wreck avoidance, no additional information in the network.

---

## 4. E10 results (as run)

Controllers C0, C1, C2, C7. Three cells: 0 baseline; 1 hazard between patch and nest
(6.25, 6.25); 2 no hazard + random failures.

Selected medians from `results/analysis/journal/E10_descriptive.csv`:

| Cell | C0 del / lost | C1 del / lost | C2 del / lost | C7 del / lost |
|---|---|---|---|---|
| 0: baseline | 130.5 / 3.5 | 134.5 / 3.0 | 137.0 / 2.0 | 134.5 / 3.0 |
| 1: between patch and nest | 77.0 / 12.0 | 106.0 / 7.0 | 129.0 / 4.0 | 106.0 / 7.0 |
| 2: random failures | 126.5 / 5.0 | 124.5 / 5.0 | 121.0 / 5.0 | 124.5 / 5.0 |

C7 and C1 are numerically identical in every cell — expected, since C7 sent no alerts.
C2 delivers more than C0 in cells 0 and 1 and loses fewer robots than C1 in cells 0 and 1
(all surviving Holm correction), consistent with E1F–E2F. The C7 vs C1 Holm-corrected
tests on robots\_lost all give p = 1.0: no detectable difference in any cell, which is
not a finding of ability — C7 was inactive.

---

## 5. E10b results: C7 with alerts that fire

**Disclosure.** E10b was pre-registered on 2026-10-22, after `tune_c7f` and E10 were
examined, and before any E10b data existed. The pre-registration records this timing
explicitly. The parameters (`alert_limit` 1, `alert_duration` 3000) were chosen because
`alert_limit` 1 was the only grid value where alerts fired, and `alert_duration` 3000
gave the highest median delivered at that limit in the pre-registered rule (137.5, from
the tune\_c7f table). Those values are in `configs/tuned_params_c7b.yaml`.

**Alerts sent per run** (computed from `results/E10b.csv`):

| Cell | Mean alerts\_sent | Median alerts\_sent |
|---|---|---|
| 0: baseline | 3.59 | 3.0 |
| 1: between patch and nest | 15.95 | 15.0 |
| 2: random failures | 16.63 | 15.0 |

Alerts fired much more often in cells 1 and 2. In cell 1 robots pass through the hazard
zone more often under site fidelity (returning to their last pickup point), so they see
more wrecks and their risk scores climb faster. In cell 2 there are random failures
distributed across the arena, so robots encounter about 16 wreck "sightings" per run on
average — all of those are spurious (no real hazard), so the cell 2 alert rate is almost
entirely false alerts.

**Medians from `results/analysis/journal/E10b_descriptive.csv`:**

| Cell | C0 del / lost | C1 del / lost | C2 del / lost | C7 del / lost |
|---|---|---|---|---|
| 0: baseline | 134.0 / 4.0 | 139.0 / 3.0 | 142.0 / 2.0 | 136.5 / 3.0 |
| 1: between patch and nest | 74.0 / 12.0 | 105.0 / 7.0 | 126.5 / 4.0 | 105.0 / 9.0 |
| 2: random failures | 130.0 / 4.0 | 127.0 / 4.0 | 129.0 / 4.0 | 127.5 / 4.0 |

**Within-cell tests vs C2** (`results/analysis/journal/E10b_tests.csv`, Holm over 25 tests):

- **Cell 0, robots\_lost:** C7 lost more than C2 (A12 = 0.784 [0.735, 0.833], Holm
  p = 9.25e-14); so did C1 (A12 = 0.717, Holm p = 1.06e-10) and C0 (A12 = 0.803,
  Holm p = 3.06e-14).
- **Cell 1, robots\_lost:** C7 lost more than C2 (A12 = 0.979, Holm p = 9.06e-17);
  C7 median lost 9.0 vs C2 median 4.0.
- **Cell 0, delivered:** C7 delivered fewer than C2 (median 136.5 vs 142.0; A12 = 0.435
  [0.378, 0.458], Holm p = 0.026).
- **Cell 1, delivered:** C7 delivered fewer than C2 (median 105 vs 126.5; A12 = 0.198,
  Holm p = 4.37e-11).
- **Cell 2:** no detectable difference between any controller on delivered or robots\_lost
  (all Holm p = 1.0).

**C7 vs C1 on robots\_lost** (the pre-registered comparison: does an alert beat plain avoidance?):

- Cell 0: C7 lost more than C1 (A12 = 0.618 [0.570, 0.666], Holm p = 3.17e-05). Median
  robots\_lost was 3 for both, but within paired seeds C7 tended to lose more.
- Cell 1: C7 lost more than C1 (A12 = 0.754 [0.690, 0.815], Holm p = 1.55e-08). Median
  C7 lost 9.0 vs C1 lost 7.0.
- Cell 2: no detectable difference (A12 = 0.5, Holm p = 1.0).

The answer to "does a risk-limit alert beat plain avoidance?" is that in E10b, C7 lost
**more** robots than C1 in cells 0 and 1, not fewer.

**Candidate explanations (all untested):**

1. **Alert position vs wreck position.** When the robot's score reaches `alert_limit`, it
   broadcasts its *own position at that moment*, not the wreck's position. Depending on the
   robot's heading, this position may be several steps away from any actual wreck. Receivers
   therefore avoid a location that may not be near the true hazard.

2. **Repel\_weight is large.** The week-7 tuning set repel\_weight to 4.0 for C2. C7 uses
   the same repel\_weight for the alert-based avoidance. A strong push from an imprecisely
   located alert could steer robots into inefficient search paths or even into the hazard
   via a roundabout route.

3. **False alerts in the random-failure cell.** In cell 2 there is no hazard, but C7 sent
   a mean of 16.63 alerts per run. Those alerts steer receivers away from random positions
   in the arena. This is unexpected — there is no hazard to avoid — but the Holm-corrected
   tests found no detectable effect on losses (all Holm p = 1.0), so the false alerts did
   not detectably help or hurt in this cell.

4. **Alert duration.** At `alert_duration` 3000 steps (30 s), a received alert repels the
   receiver for a long time. If the alerting robot was near a productive patch at the time
   of the alert, receivers might be repelled from a patch for half the run.

**Important limitation.** C7 is our adaptation of the Hunt, Cullen and Hauert (2021) idea,
not their method. Their robots can sense hazard exposure directly; ours infer it from
wrecks, which is noisier and geometrically imprecise. The poor performance of C7 in E10b
is therefore not evidence against their approach. It may reflect problems with our
adaptation.

---

## 6. E11: arena size and communication range

Controllers C2, C5, C6. Five cells: 0 scale 1, comm 1 m; 1 scale 1, comm 0.5 m; 2 scale
1, comm 0.25 m; 3 scale 2 (20 m arena, 80 robots), comm 1 m; 4 scale 2, comm 0.5 m.

**Medians from `results/analysis/journal/E11_descriptive.csv`:**

| Cell | C2 del / lost | C5 del / lost | C6 del / lost |
|---|---|---|---|
| 0: scale 1, comm 1 m | 133.0 / 2.0 | 136.0 / 2.0 | 135.5 / 2.0 |
| 1: scale 1, comm 0.5 m | 133.0 / 2.0 | 135.5 / 2.0 | 136.5 / 2.0 |
| 2: scale 1, comm 0.25 m | 133.0 / 2.0 | 135.0 / 2.0 | 135.0 / 2.0 |
| 3: scale 2, comm 1 m | 52.0 / 2.0 | 52.5 / 2.0 | 52.5 / 2.0 |
| 4: scale 2, comm 0.5 m | 52.0 / 2.0 | 52.5 / 2.0 | 52.5 / 2.0 |

**known\_frac for C6** (computed from `results/E11.csv`; share of wreck records known per
live robot at the end of the run, marked runs only):

| Cell | C6 known\_frac median (n) |
|---|---|
| 0: scale 1, comm 1 m | 0.905 (94) |
| 1: scale 1, comm 0.5 m | 0.582 (94) |
| 2: scale 1, comm 0.25 m | 0.504 (94) |
| 3: scale 2, comm 1 m | 0.500 (71) |
| 4: scale 2, comm 0.5 m | 0.115 (71) |

At scale 1 with comm 1 m, C6 spreads information to about 91% of robots (median
known\_frac 0.905). Reducing comm to 0.5 m roughly halves this (0.582), and at 0.25 m
spread is near 50%. At scale 2 with comm 1 m, information still spreads to about 50% of
robots on average, and at 0.5 m it reaches only about 12%. So information spreading is
genuinely harder at scale 2.

**Tests** (`results/analysis/journal/E11_tests.csv`, Holm over 38 tests): nothing between
C2, C5 and C6 survives Holm correction in any cell. Every vs-C2 Holm p is 1.0. C6 vs C5
Holm p is also 1.0 in every cell. The median differences are all 0, A12 values are within
[0.498, 0.545].

**Across-cell tests for C2** (cross\_cell rows in E11\_tests.csv): cells 1 and 2 vs cell 0
show no detectable difference in delivered or robots\_lost (all Holm p = 1.0). Cells 3
and 4 vs cell 0 show a very large delivery drop (median 52 vs 133; A12 = 0.0, Holm
p = 1.47e-16). Robots\_lost at scale 2 is median 2 — the same as at scale 1 — so the
delivery drop at scale 2 is not driven by more deaths; it reflects the larger arena
(more steps per trip, fewer items collected in 10,000 steps).

**Caveat.** At scale 2 the median robots\_lost is 2 in both cells 3 and 4. With so few
deaths per run, there is very little signal to localise. Even if C6 spread information
more effectively, there might not be enough wrecks to produce a useful map, so the
null result at scale 2 is hard to interpret as "information spreading doesn't matter".

**Plain reading.** No detectable difference among C2, C5 and C6 at any scale or comm
range after Holm correction (100 seeds per cell). This is not a finding of equivalence;
100 seeds cannot rule out small effects. The candidate explanation from E6bF still
applies: when C6's records spread widely (known\_frac near 1.0 in cell 0), C6 behaves
like C2, and even at lower spread rates the difference may be too small to detect with
this sample size. At scale 2 with comm 0.5 m (known\_frac 0.115), there is still no
detectable difference, but the low death count means the experiment has little power to
show one.

---

## 7. E12: two hazards

Controllers C0–C4. Three cells: 0 one hazard (baseline, next to patch (7.5, 7.5)); 1 two
hazards (adding a second near patch (2.5, 2.5) at (1.19, 3.81)); 2 two hazards with
lethality 0.1.

**Medians from `results/analysis/journal/E12_descriptive.csv`:**

| Cell | C0 del / lost | C2 del / lost | C3 del / lost | C4 del / lost |
|---|---|---|---|---|
| 0: 1 hazard | 134.0 / 3.0 | 139.0 / 2.0 | 140.5 / 2.0 | 148.0 / 0.0 |
| 1: 2 hazards | 120.0 / 7.0 | 128.0 / 4.0 | 127.0 / 4.0 | 150.5 / 0.0 |
| 2: 2 hazards, lethality 0.1 | 118.0 / 8.0 | 128.0 / 4.0 | 126.0 / 4.0 | 150.5 / 0.0 |

**Within-cell tests** (`results/analysis/journal/E12_tests.csv`, Holm over 28 tests):

- Cell 1: C2 delivers more than C0 (A12 = 0.622 [0.574, 0.671], Holm p = 2.16e-04) and
  loses fewer robots than C0 (A12 = 0.911, Holm p = 1.74e-16). Also loses fewer than C1
  (A12 = 0.808, Holm p = 5.07e-14). C3 shows no detectable difference from C2 in lost
  (A12 = 0.489, Holm p = 1.0) or delivered (A12 = 0.491, Holm p = 1.0).
- Cell 2: same pattern as cell 1 — C2 vs C0 survives Holm on delivered and lost; C3
  does not differ from C2 (Holm p = 1.0 for both metrics).
- Cell 0: C2 vs C0 on delivered does not survive Holm (A12 = 0.425, Holm p = 0.062).
  C0 vs C2 on robots\_lost survives (A12 = 0.835, Holm p = 2.90e-15). C4 delivers more
  than C2 in all cells (Holm p at most 2.43e-07) and loses 0 robots.

**Cross-cell tests for C2:**

- Cell 1 vs cell 0: delivered drops by 9.5 items [−11.5, −6] (A12 = 0.339, Holm
  p = 1.48e-06); robots\_lost rises (A12 = 0.927, Holm p = 9.23e-17).
- Cell 2 vs cell 0: delivered drops by 10.5 [−14.5, −5.5] (A12 = 0.328, Holm
  p = 2.30e-06); robots\_lost rises (A12 = 0.936, Holm p = 1.80e-16).

**Per-hazard AUC** (cells 1 and 2, C2 only; from the auc\_final\_h0 and auc\_final\_h1 columns):

| Cell | AUC union | AUC hazard 0 | AUC hazard 1 |
|---|---|---|---|
| 1: 2 hazards | 0.753 | 0.744 | 0.739 |
| 2: 2 hazards, lethality 0.1 | 0.753 | 0.726 | 0.734 |

Both hazards are localised to a similar quality. The union AUC (0.753) is close to the
baseline single-hazard AUC (0.772 in cell 0), suggesting that two hazards are not
detectably harder to localise than one when the robot population is large enough to mark
both.

**repellent\_in\_hazard for C2** (computed from `results/E12.csv`):

| Cell | Median repellent\_in\_hazard |
|---|---|
| 0: 1 hazard | 0.588 |
| 1: 2 hazards | 0.579 |
| 2: 2 hazards, lethality 0.1 | 0.503 |

At lethality 0.1 (cell 2) the share of the repellent field inside the two hazards drops
to 0.503 — roughly half. A candidate explanation is that at higher lethality robots die
near the edges of the hazards or immediately outside them, spreading wrecks more broadly
and leaving marks that are partly outside the true hazard area. This is a candidate only;
wreck positions were not examined.

---

## 8. What this changes for the paper

**C7 section.** The paper needs to be careful: the pre-registered C7 (E10) was
effectively C1 because the alert mechanism never triggered, so E10 does not test C7's
alerts at all. E10b is the real test. Suggested framing:

> C7 was tuned on a grid with alert\_decay 0.001 and limits {1, 2, 3}. At limits 2 and 3
> alerts almost never fired (mean per run 0.00–0.10); the grid selected limit 3 on noise.
> The C7 tested in E10 is therefore effectively C1. E10b repeated the experiment with
> limit 1, the only value at which alerts fired (mean 3.6–16.6 per run). In E10b, C7 lost
> more robots than C1 in the baseline and the strategically placed hazard cells (Holm p at
> most 3.2e-05). Candidate explanations include imprecise alert position (robots broadcast
> their own location, not the wreck's), strong repel\_weight, and — in the random-failure
> cell — high false-alert rates (~16 per run). C7 is an adaptation of Hunt, Cullen and
> Hauert (2021), not a re-implementation; the outcome is not evidence against their approach.

**E11 section.** The main finding for limitation #7/#8 is still null: no detectable
difference among C2, C5 and C6 at any scale or comm range. The paper should note the
caveat that at scale 2 median deaths are about 2 per run, so there is little signal to
localise and the test has limited power. The known\_frac table shows that information
spreading does reduce at smaller comm ranges (from 0.905 to 0.115 across cells), which
means the null result at scale 2 with comm 0.5 m is despite information being very sparse.

**E12 section.** The H1 and H2 patterns hold with two hazards: C2 delivers more than C0
and loses fewer robots than C1 in cells 1 and 2 (both Holm-corrected). The delivery cost
of a second hazard for C2 is about 9–10 items (from 139 to 128). C3 does not add
detectably to C2's performance even with two hazards, consistent with H4 and H4F.

---

## 9. Things to check

1. **Alert position vs wreck position.** Is it worth checking, in a diagnostic run,
   what the mean distance between a broadcaster's position at alert time and its nearest
   wreck is? That would test candidate explanation 1 directly.

2. **C7 repel\_weight.** C7 currently uses the site-fidelity repel\_weight (4.0) for
   alert-based avoidance. That value was tuned for C2's field-wide marks, not for
   point alerts. Should the paper mention this, or would a re-tune with a smaller
   repel\_weight for C7 be worth a note?

3. **E11 at scale 2.** Only about 2 robots die per run at scale 2, so the hazard-avoidance
   benefit is very small. Is it worth a larger swarm (or more seeds) to check whether the
   C2 vs C6 null result survives with more deaths?

4. **E12 repellent\_in\_hazard at lethality 0.1.** The field share drops to 0.503 in cell
   2. Is it worth examining wreck positions to see where the wrecks fall — near the hazard
   boundary or outside it?

5. **E10b pre-registration timing.** The paper should state explicitly that E10b was
   pre-registered after seeing tune\_c7f and E10. It should also say that the parameters
   were chosen by the pre-registered rule applied to the tune\_c7f table — not by
   inspecting E10b data. Is this enough for the methods section, or does the mentor want
   a clearer disclosure box?

6. **E12 C3 result.** C3 (risk-weighted avoidance using distance to nearest wreck) adds
   nothing to C2 even with two hazards. Is that worth a sentence in the limitations, or
   does it just repeat the H4/H4F null result?
