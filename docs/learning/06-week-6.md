# 06 — Week 6: why false sightings "helped", and site fidelity (E9)

Everything here is **exploratory**. E9 was pre-registered as exploratory in the last
section of `docs/hypotheses.md` ("Week-6 experiment"), committed at 8f2b01c on
2026-10-21 before any E9 data existed, and approved the same day. No p-value here is
confirmatory. Numbers come from `results/analysis/week6/` (E9_descriptive.csv,
E9_tests.csv, identity_checks.csv) and `results/mechanism/e2_random_wrecks.csv`.

## 1. The puzzle and the first check

Week 5 found that ten times more false sightings *raised* C2's deliveries (E7b cell 5).
Note 05 suggested robots "crowding" near the nest. That word was wrong: robots in our
model never collide, so they cannot crowd.

**First check (descriptive, not pre-registered):** `scripts/diag_e2_random_wrecks.py`
re-ran E2's random-failure cell (no hazard) for C0 and C2, 100 seeds. All 200 runs matched
`E2.csv` exactly on delivered and robots lost.

- 34% of C2's random wrecks fell within 1.5 m of the nest (39% for C0), although that disc
  covers only 7% of the arena. Robots spend a lot of time there, so random failures happen
  there often.
- A median of 52% of C2's final repellent lay within 1.5 m of the nest.
- C2's per-seed lead over C0 in items delivered correlated with the number of near-nest
  wrecks (Spearman ρ = 0.39). The median lead was +2 in the 82 runs with at least one
  near-nest wreck and −1 in the 18 runs without one.

So the H3 control was affected by the same thing as E7b cell 5. This was done after the fact
and is only a correlation.

## 2. The candidate mechanism (from reading the code)

After each delivery, a robot gets a random heading and restarts its random-walk search **at
the nest** (`Simulation._deliver`). A random walk drifts away slowly, so robots spend a lot of
time near the nest, and anything that pushes them outward, such as repellent near the nest,
makes their search shorter. If so, the "benefit" belongs to our foraging model, not to marking.

The test: switch on **site fidelity**, where a robot goes back to where it last picked up an
item after delivering (state OUTBOUND), as real ants and standard foraging models do
(Hecker & Moses 2015). If the candidate is right, the false-sighting gain and C2's lead in the
random-failure control should shrink.

## 3. What was run

E9: C0–C4, 100 seeds per cell, six cells that all share cell 0's random streams (paired):

| Cell | Condition | Search start |
|---|---|---|
| 0 | baseline (hazard next to a patch) | nest |
| 1 | baseline | last pickup (fidelity) |
| 2 | no hazard, random failures | nest |
| 3 | no hazard, random failures | fidelity |
| 4 | baseline + false sightings (q_false = 0.0001) | nest |
| 5 | baseline + false sightings | fidelity |

3,000 runs from commit 50aa7c6 (frozen worktree; simulator identical to the approved
9a14944, only the batch script's keep-awake changed). The provenance line says every golden
case from fe78c66 reproduced bit-identically. All six identity checks were True (C0, C1 and C4
identical in cells 0 and 4, and in cells 1 and 5). The batch took 23,740 s because the laptop
was suspended for most of the afternoon.

## 4. Results

### Site fidelity makes foraging about three times more efficient

| Controller | Delivered, nest (cell 0) | Delivered, fidelity (cell 1) |
|---|---|---|
| C0 | 43.5 [42, 45] | 133.5 [131, 137] |
| C1 | 45 [44, 46.5] | 135 [132.5, 140] |
| C2 | 46 [45, 47] | 139 [132, 143] |
| C3 | 46 [45, 47] | 138 [132, 142] |
| C4 | 48 [47, 50] | 149.5 [141.5, 154] |

The median search time (delivery to next pickup) for C2 fell from 2,619 to 837 steps, the
trip time (pickup to delivery) stayed about the same (260 vs 267 steps), and the robot-steps
within 1.5 m of the nest fell from 76,870.5 to 55,743.5. So restarting search at the nest was the
main bottleneck of our foraging model.

### The main pattern holds with fidelity (cell 1, tested, Holm over 82)

- **Robots lost:** C2 lost fewer than C0 (median 4 vs 2, A12 = 0.819, Holm p < 1e-10) and
  fewer than C1 (3 vs 2, A12 = 0.709, Holm p < 1e-6). This is the H2 pattern.
- **Delivered:** C2 delivered more than C0 (139 vs 133.5; paired median difference C0 − C2 =
  −2 [−5, 0]; A12(C0, C2) = 0.432; Holm p = 0.026). This is the H1 pattern, but smaller
  relative to the total (about 4% against about 6% with the nest restart).
- C2 vs C1 and C3 vs C2 on delivered: no detectable difference.
- Interaction tests (c) and (d): C2's lead over C0 and C1's excess losses over C2 showed **no
  detectable difference** between nest restart and fidelity (Holm p = 1 for both). So the H1/H2
  pattern does not detectably depend on the search rule.

### The random-failure control (cells 2 and 3)

- With the nest restart (cell 2), C2 again delivered more than C0 (46.5 vs 43; A12(C0, C2) =
  0.342; Holm p < 1e-4). Its median search time was shorter (2,408 vs 2,598 steps for C0)
  and its robots spent less time near the nest (66,341 vs 70,819 robot-steps). This fits the
  candidate mechanism directly.
- With fidelity (cell 3), C2's lead disappeared: 127 vs 128.5, A12(C0, C2) = 0.528, Holm p = 1.
  There was no detectable difference in either direction, so there was also no detectable
  false-alarm cost.
- Interaction (b): C2's per-seed lead over C0 was larger with the nest restart (median 3)
  than with fidelity (median −2); A12 = 0.635 [0.554, 0.714], raw p = 0.0012, **Holm p = 0.0503**.
  It just misses the 0.05 line after correcting for 82 tests, so I report it as not surviving
  correction, even though the direction matches the candidate.

### False sightings (cells 4 and 5)

- With the nest restart, false sightings again raised C2's deliveries: 54 vs 46 (cell 4 vs 0).
- With fidelity, the rise was smaller: 140.5 vs 139 (cell 5 vs 1).
- Interaction (a): the per-seed false-sighting gain had a median of 9 with the nest restart and
  2 with fidelity; A12 = 0.603, raw p = 0.011, **Holm p = 0.45**. Not significant after correction.
  With fidelity the deliveries also vary much more from seed to seed (C2's IQR is wide), which
  makes this test weaker.
- Robots spent less time near the nest with false sightings under both rules (C2: 61,079.5
  robot-steps in cell 4, 43,443.5 in cell 5), so the phantom repellent still pushes robots
  outward, but with fidelity that push no longer saves much search time.

## 5. Plain reading

- The descriptive pattern matches the candidate mechanism: with fidelity, the false-sighting
  gain and C2's lead in the random-failure control both shrank, robots spent less time near the
  nest, and C2's lead disappeared in the random-failure control. But neither interaction test
  survived Holm correction (p = 0.050 and 0.45), so "the mechanism is shown" is too strong.
  "Consistent with, not tested to significance" is right.
- The main results survive the more realistic foraging rule: C2 still loses fewer robots than
  C0 and C1, and still delivers slightly more than C0.
- For H3: with fidelity, marking in the random-failure control showed no detectable cost *and*
  no detectable benefit. That is the clean version of what H3 was trying to measure.

## 6. What this changes for the paper

- Section 6.8: replace "crowding" with the search-restart mechanism; report E9 with both
  interaction p-values and the caveat that they do not survive Holm.
- H3 discussion: add that with fidelity C2's lead in the control disappears (no detectable
  difference either way).
- Limitations: our default foraging model restarts search at the nest; with site fidelity,
  throughput triples and C2's relative item gain shrinks, but the robot savings remain.

## 7. Things to check with your mentor

1. Should the paper switch its *main* model to site fidelity, given it is more realistic and
   the main pattern survives? That would mean re-running E1–E8, a big change.
2. Interaction (b) at Holm p = 0.0503: report as "not significant" and stop, or pre-register a
   larger follow-up?
3. Should we also check C2's tuned parameters under fidelity (they were tuned with the nest
   restart)?
