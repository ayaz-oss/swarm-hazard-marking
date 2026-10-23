# Paper outline: arXiv preprint (cs.RO, cross-list cs.MA)

Built from `docs/learning/01`–`04` and `docs/hypotheses.md`. Every number below is
taken from `results/analysis/` (confirmatory.csv, E*_descriptive.csv,
E*_exploratory.csv) as regenerated in week 4. Target length: about 8 pages plus
appendix (Swarm Intelligence format later).

**Working title:** *Lost teammates as hazard sensors: stigmergic marking of robot
failures in a foraging swarm*

**One-sentence claim:** a foraging swarm with only local sensing can turn the
wrecks of failed teammates into a decaying repellent map of an unseen hazard, which
loses fewer robots than avoiding wrecks alone and costs nothing measurable when
failures are random.

**Rules for the whole paper**
- Confirmatory = H1–H4 on E1 and E2 (pre-registered). Everything else is labelled
  exploratory, in the text and in figure captions.
- Every deviation from the pre-registration is named where it matters and listed
  in Appendix A.
- "No detectable difference", never "equivalent".
- Robots lost is the strongest effect; items delivered is modest. Say so.

---

## Abstract (about 200 words)

1. Problem: robots fail near unknown hazards; failure-tolerant swarms simply absorb
   the losses.
2. Idea: a failed robot is a signal. Robots that see a wreck mark a decaying
   repellent field (stigmergy, as in Pharaoh ants' "no entry" pheromone).
3. Method: simulated 20-robot foraging swarm, six controllers (ignore, avoid wrecks,
   mark, mark + risk weighting, oracle, per-robot maps), seven pre-registered
   experiments, 11,100 runs, paired by seed.
4. Results: marking delivers more items than ignoring the hazard (median +3,
   A12 0.66) and loses fewer robots than avoiding wrecks alone (A12 0.79); in a
   hazard-free control with random failures it costs nothing measurable
   (A12 lower bound 0.52 > 0.36). Risk weighting showed no detectable benefit.
   Exploratory: savings grow with swarm size (80 robots: 3 lost vs 19).
5. All code, configs and raw results are released for exact re-runs.

## 1. Introduction (about 1 page)

- Motivation: swarms in unmapped environments (search and rescue, mines,
  planetary). Hazards are often invisible to cheap sensors until a robot is lost.
- Status quo: swarm robustness work treats failures as damage to tolerate; it does
  not use them as information about *where* danger is.
- Gap (one paragraph, citing the closest work): event-rate area choice (Aguirre et
  al. 2025) chooses between two areas but does no foraging and no inference from
  lost teammates; multi-robot hazard mapping with planning (Srivastava et al. 2025)
  is centralised-planning, not stigmergic foraging; "value at risk" swarms (Hunt,
  Cullen, Hauert) have robots warn before failing, not mark after.
- Research question, verbatim from the project: can a decentralised foraging swarm
  with only local sensing localise unknown hazards from teammates failing near them,
  and how much foraging performance and how many robots does that save compared
  with failure-tolerant swarms?
- Contributions (bulleted):
  1. A minimal failure-marking controller (C2) and four comparison controllers in an
     open simulator.
  2. A pre-registered evaluation with paired-by-seed statistics and a
     random-failure control that isolates the cost of false alarms.
  3. Sweeps over placement, swarm size, lethality, hazard size, information medium
     and detection noise.
  4. A reproducibility pipeline: frozen-commit batches, provenance per result row,
     bit-identical golden tests across code versions.

## 2. Related work (about 0.75 page)

- **Stigmergy and repellent pheromones:** Robinson et al. 2005 (Pharaoh ant
  no-entry pheromone) as inspiration; virtual pheromones in swarm robotics.
- **Pheromone density effects:** Hunt, Jones, Hauert 2019 (repellent pheromone
  degrades at high density). Motivates E3; our E3 does not show degradation up to
  80 robots (see 6.2).
- **Failure and fault tolerance in swarms:** fault detection (Bristol, UCL work),
  "value at risk".
- **Hazard mapping and risk-aware multi-robot exploration:** Srivastava et al. 2025
  (closest), Aguirre et al. 2025.
- Position: ours is the only one of these that infers hazard location from lost
  teammates with purely local, decentralised marking during foraging.
- TODO before submission: ICCCR 2024 "quarantine regions" stays out until a source
  is found (spec note). Run a final literature search for 2026 work.

## 3. Model (about 1 page)

**3.1 World.** 10 × 10 m walled arena, nest radius 0.75 m at the centre, timestep
0.1 s, 10,000 steps (about 17 simulated minutes). Item patches; a collected item
respawns in its own patch. One circular hazard, invisible to robots; each step
inside it a robot fails with probability *p* (baseline radius 1 m, *p* = 0.02,
next to a patch).

**3.2 Robots.** Point robots, speed 0.1 m/s, sensing range 0.5 m, know the nest
direction. Shared state machine: search (correlated random walk), pick up, return,
drop. A failed robot becomes a permanent wreck visible within sensing range. No
robot–robot collisions (limitation).

**3.3 Controllers** (table, one row each):
- C0 ignore wrecks.
- C1 steer away from visible wrecks (no memory).
- C2 C1 plus mark: the first time a robot sees a wreck it adds a Gaussian bump to a
  shared repellent grid (0.1 m cells, decays each step); robots steer down its
  gradient.
- C3 C2 with the push scaled by 1/(1 + k × items in view) (risk trade-off).
- C4 oracle: blocked from entering the hazard, slides along its edge. A reference,
  not a swarm method.
- C5 per-robot maps: each robot marks its own map; every 1 s it takes the cell-wise
  maximum with live robots within 1 m. Not tuned (uses C2's values).

**Fig. 1 (to make):** arena schematic (nest, patches, hazard positions used in E2
and E5) next to a snapshot of a C2 run with the repellent field overlaid. Source:
`scripts/animate.py` frame plus a drawn schematic.

**3.4 Noise (E7).** Misses with probability q_miss per robot–wreck–step; false
sightings at the robot's own position with probability q_false per robot-step.
State that misses are independent each step, so the noise is weak by construction.

## 4. Methods (about 1 page)

**4.1 Metrics.** Primary: items delivered. Secondary: robots lost; items per robot
lost; localisation AUC of the repellent map against the true hazard mask (rank-based;
C5 uses the mean of live robots' maps).

**4.2 Experiments.** Table of E1–E7 with cells and controllers (from
`hypotheses.md`, experiment levels). 100 seeds per cell; 11,100 runs in total
(8,500 for E1–E5, 2,600 for E6–E7).

**4.3 Random-failure control.** No hazard; each robot fails with q = 2.66 × 10⁻⁵ per
step, matching C0's baseline loss rate (4.67 of 20 robots). Isolates the cost of
marking when wrecks carry no information.

**4.4 Tuning.** Grid on held-out seeds at baseline; selection rule pre-registered.
Chosen: repel 0.5, deposit_sigma 0.3, decay 0.0002, risk_k 0.5. The landscape was
flat (SD of cell means 1.09 items vs 1.13 expected from seed noise alone), so C2
is insensitive to these parameters over the grid. Say this plainly.

**4.5 Statistics.** Paired by seed. Confirmatory: one-sided Wilcoxon signed-rank
(Pratt) for H1, H2, H4, Holm across the three; H3 by the bootstrap lower bound of
A12 > 0.36. Bootstrap: seed resampling, 10,000 resamples, fixed generator seed.
Exploratory: Friedman per cell, two-sided Wilcoxon vs C2, Holm within each
experiment. Effect size A12 (Vargha–Delaney).

**4.6 Pre-registration and deviations.** Hypotheses and analysis committed before
E1. Four deviations (gate miss, paired test, one-sided H3, deposit_sigma tuned) plus
the dated 2026-10-19 E6 clarification; all in Appendix A.

**4.7 Reproducibility.** Six independent random streams per run, seeded by
(experiment, cell, seed). Provenance per row (commit, package versions, import
path). E6–E7 ran from a frozen worktree at a later commit; accepted because every
golden case from E1's commit reproduces bit-identically. Caveat: checked on one
machine; across machines we claim statistical, not bitwise, agreement.

## 5. Results: confirmatory (about 1 page)

**Table 1:** H1–H4 (from `confirmatory.csv`): medians, median paired difference
[95% CI], A12 [95% CI], p, Holm p, verdict.

| | Claim | Result | Verdict |
|---|---|---|---|
| H1 | C2 delivers more than C0 | 45 vs 42; diff 3 [1.5, 4]; A12 0.661 [0.620, 0.706]; Holm p 5.0e-11 | supported |
| H2 | C2 loses fewer robots than C1 | 2 vs 3; diff 1 [1, 1]; A12 0.789 [0.742, 0.835]; Holm p 1.7e-14 | supported |
| H3 | C2's cost vs C0 small with random failures | 45 vs 43; diff 1 [0, 2.5]; A12 0.582, lower bound 0.519 > 0.36 | supported |
| H4 | C3 delivers more than C2 | 45 vs 45; diff 0 [0, 0]; A12 0.503; Holm p 0.156 | not supported |

What the section says:
- **H1:** marking helps foraging, modestly: +3 items of about 45; C2 ahead on 71
  seeds, tied on 15, behind on 14.
- **H2 (the clearest result):** C2 loses fewer robots than avoiding wrecks alone,
  ahead on 73 seeds, tied on 23, behind on 4. Memory of where robots died matters
  beyond reacting to wrecks in view.
- **H3:** with no hazard and random failures, marking costs nothing measurable. A
  one-sided bound, not a claim that C2 is better there.
- **H4:** risk weighting showed no detectable benefit. At the tuned k = 0.5, C3
  delivered the same as C2 on 96 of 100 seeds, so the test had little power; this is
  not evidence that risk weighting is useless at other settings.
- Context from the descriptive table: medians delivered C0–C4 42, 43, 45, 45, 48;
  robots lost 5, 3, 2, 2, 0; items per robot lost C0 8.4, C1 13.7, C2 21.9.
  C2 closes about half the gap between C0 and the oracle on items delivered.

**Fig. 2:** `e1_baseline` (box plots with seed dots, delivered and lost, C0–C4).

**Fig. 3:** `e1_auc_over_time`: the map localises the hazard. AUC 0.5 until about
300 s, about 0.71 by 350 s, about 0.80 at the end (median final 0.796, IQR
0.72–0.86). Caption notes C3 overlaps C2 exactly. Text flags the unexplained delay
between median first loss (~160 s) and the jump (~300 s) as open.

## 6. Results: exploratory sweeps (about 1.5 pages)

Opening sentence: all comparisons in this section are exploratory (Friedman, then
Wilcoxon vs C2, Holm within experiment).

**6.1 Placement (E2, Fig. 4 `e2_placement`).** Where the hazard sits matters most
for controllers without memory. Between patch and nest, C0 collapses (17 items,
17 of 20 robots lost), C1 reaches 32 items and 9 lost, C2 42 items and 4.5 lost,
oracle 46. Next to a patch and far from everything the gaps are small (C0 42/44,
C2 44/46). C2 vs C0 delivered differs in all three hazard cells (Holm p ≤ 7.4e-5).
Message: marking matters most when the hazard sits on a path the swarm must use.

**6.2 Swarm size (E3, Fig. 5 `e3_sweep`).** The headline exploratory result:
robots saved grow with swarm size. Median robots lost for C0: 1, 2, 5, 9, 19 at
5–80 robots; C1: 1, 2, 3, 4, 6; C2: 1, 1, 2, 3, 3. At 80 robots C2 delivers 164.5
vs 150 for C0, and items per robot lost are 54.7 vs 7.9. At 5 robots there is no
difference (all 12 items); few robots witness a loss (only 31 of 100 C2 runs mark
anything, so median AUC is 0.5). Relate to Hunt et al. 2019: no density degradation
visible up to 80 robots in this arena.

**6.3 Lethality (E4, Fig. S1 `e4_sweep`, supplementary).** C2 flat across
*p* = 0.005–1.0 (delivered 46, 44, 44.5, 45; lost 2). C0's mean losses rise about
50% from 0.005 to 0.1 (3.52 to 5.42), then flatten. Candidate explanation,
untested: saturation, since crossing the hazard takes about 100 steps, so above 0.1
almost every entrant dies.

**6.4 Hazard size (E5, Fig. 6 `e5_sweep`).** Against in-arena area (0.75, 3.18,
8.23 m²): C0 loses 2, 5, 8 robots and drops to 38 items; C2 holds at 1, 2, 2 lost
and 43 items; oracle 49–50. Note the 2 m hazard is clipped by the east wall. AUC
falls with area (0.995, 0.785, 0.666): the map marks the hazard's edge, not its
interior. (Phrase as a candidate reading.)

**6.5 Information medium (E6, Fig. 7a `e6_sweep`).** Per-robot maps with local
exchange (C5) showed no detectable difference from the shared field (C2) at any
swarm size after Holm correction (one raw p = 0.033 at N = 40, Holm p = 0.33). State
the confound in the same paragraph: sum vs max-merge plus own bumps, C5 untuned,
swarm-level AUC. Message for the paper: the shared field in C2 is not doing
anything a physically realisable local-exchange scheme cannot, in this set-up.
Do not say "equivalent".

**6.6 Detection noise (E7, Fig. 7b `e7_noise`).** Within every noise cell, C2 lost
fewer robots than C1 and C0 and C3 showed no detectable difference from C2 (paired,
Holm over 24 tests). Across noise levels: descriptive only, unpaired, and the
differences are within layout-to-layout variation (C1, unaffected by false
sightings by design, still moves by 2 items between cells). About 1.9 false
sightings per run. Say plainly the noise is weak by construction; no general
robustness claim.

**6.7 Replication checks (short paragraph or appendix).** E7 cell 0 vs E1 and E6
N=20 vs E3 N=20 agree within 1–2 items and 1 robot. AUC differs more (0.755 vs
0.796), with overlapping IQRs.

## 7. Discussion (about 1 page)

- **Failures as information works, mainly by saving robots.** Robots lost is the
  large, consistent effect (H2, E3, E5, E7); items delivered is a modest gain at
  baseline that grows with swarm size and with hazards on key paths.
- **Memory beyond avoidance.** C1 vs C2 isolates the value of marking: the wreck is
  visible only from 0.5 m, the mark persists and spreads.
- **No false-alarm penalty.** The random-failure control shows marking random
  wrecks costs nothing measurable, which matters because real robots also fail for
  reasons unrelated to place.
- **Risk weighting (H4 null).** Explain the low power; suggest tuning k on a steeper
  landscape or a scenario where items sit inside the hazard.
- **Medium (E6).** Decentralised exchange is enough here; caveat the confound.
- **Limitations:** point robots, no collisions; one static hazard; idealised wreck
  detection and nest direction; weak independent noise; flat tuning landscape; C4
  is a reference not a true optimum; E1 had zero items lost; bit-identity on one
  machine; simulation only.
- **Future work:** moving hazards (decay), correlated or stronger noise, a single
  factor E6 (C5 with summing or tuned), real robots or a physics simulator
  (ARGoS/Webots), heartbeat-loss cues.

## 8. Conclusion (1 paragraph)

Restate the question and the answer: yes, local marking of teammate failures
localises the hazard (final AUC about 0.8) and saves robots, more so in larger
swarms, at no measurable cost when failures are random.

## Code and data availability

GitHub repository plus Zenodo DOI (to mint at submission). Raw CSVs, analysis and
figure scripts, configs, golden tests, `docs/hypotheses.md` with commit history as
the pre-registration record. Tag the commits used (E1 fe78c66; E2 45b4ce5; E3–E5
4cf295a; E6–E7 5d8ca9e, tag batch-E6E7).

## Appendix

- **A. Deviations from the pre-registration:** (1) gate miss, A12 0.629 vs 0.64,
  proceeded by recorded decision; (2) Mann–Whitney → paired Wilcoxon; (3) H3 as a
  one-sided bound; (4) deposit_amount fixed, deposit_sigma tuned; (5) C0 added to
  E7; (6) 2026-10-19 clarification of the E6 confound, written after the batch
  started and before any data were examined.
- **B. Parameters:** full `Config` defaults and `tuned_params.yaml`.
- **C. Tuning landscape** (table or heat map).
- **D. Full exploratory tables** (E2–E7 descriptive and Wilcoxon vs C2).
- **E. Supplementary figures:** `e4_sweep`, AUC by swarm size, E7 AUC.

---

## Figure plan

| # | File | Section | Status |
|---|---|---|---|
| 1 | arena schematic + C2 snapshot | 3 | to make |
| 2 | `e1_baseline` | 5 | exists |
| 3 | `e1_auc_over_time` | 5 | exists |
| 4 | `e2_placement` | 6.1 | exists |
| 5 | `e3_sweep` | 6.2 | exists |
| 6 | `e5_sweep` | 6.4 | exists |
| 7 | `e6_sweep` + `e7_noise` (two panels) | 6.5–6.6 | exists, to combine |
| S1 | `e4_sweep` | 6.3 | exists |

## Open items before drafting

1. External read of this outline.
2. Literature: confirm related-work citations and search for 2026 work; ICCCR 2024
   stays out without a source.
3. Make Fig. 1; combine Fig. 7 panels.
4. Decide the AUC reporting rule (all runs vs marked runs only) — note 04, item 3.
5. arXiv endorser for cs.RO.
