# Spec addendum: week 7 (site fidelity as the main foraging model)

**Date:** 2026-10-22
**Extends:** the base spec and the 2026-10-16, -19, -20 and -21 addenda
**Pre-registration:** `docs/hypotheses.md`, section "Week-7 replication under site fidelity" (added before any of its data exist)

## 1. Why

E9 (week 6) showed that restarting search at the nest after every delivery is the main
bottleneck of our foraging model and the source of the near-nest side effect. Site fidelity
(`search_start: last_pickup`) is the standard, more realistic rule; under it, foraging was about
three times more efficient, and the H1/H2 pattern held in E9's baseline cell. Week 7 makes site
fidelity the **main model** of the paper and repeats the study under it. The nest-restart results
(E1–E8) are kept and reported as a second foraging model (robustness).

Package (from the limitations review of 2026-10-22):
- #3 site fidelity as the main model; #9 re-tuning under it; #16 paired cells in the sweeps;
- #24 extra localisation measures; #26 tests on a second platform.

## 2. Re-tuning (before any main run)

- New experiments `tune_c2f` and `tune_c3f`: identical grids, seeds (20 per cell) and selection
  rule to `tune_c2` / `tune_c3`, but with `search_start: last_pickup`. Their names give them random
  streams independent of every other experiment.
- Selection rule unchanged: highest median items delivered; ties → lowest mean robots lost.
- Output: `configs/tuned_params_fidelity.yaml` (repel_weight, deposit_sigma, decay, risk_k, plus
  `search_start: last_pickup`), committed before the main batch. `configs/tuned_params.yaml` is not
  changed.

## 3. Main experiments under site fidelity

Every experiment below uses `overrides_file: configs/tuned_params_fidelity.yaml`, 100 seeds per
cell, the same controllers and cells as its nest-restart counterpart, and — new for E2F–E5F —
`paired_cells: true` (every cell uses cell 0's random streams). E6 and E7 are not repeated (E6b and
E7b superseded them).

| Exp | Counterpart | Controllers | Cells | Runs |
|---|---|---|---|---|
| E1F | E1 | C0–C4 | baseline | 500 |
| E2F | E2 | C0–C4 | next to patch; between patch and nest; far; no hazard + random failures | 2,000 |
| E3F | E3 | C0–C4 | n_robots 5, 10, 20, 40, 80 | 2,500 |
| E4F | E4 | C0–C4 | lethality 0.005, 0.02, 0.1, 1.0 | 2,000 |
| E5F | E5 | C0–C4 | radius 0.5, 1, 2 m | 1,500 |
| E6bF | E6b | C2, C5, C6 | n_robots 5, 10, 20, 40, 80 | 1,500 |
| E7bF | E7b | C0–C3 | the six E7b noise cells | 2,400 |
| E8F | E8 | C0, C1, C2, C4 | the three E8 cells | 1,200 |

Total 13,600 runs, plus tuning (720 + 100 runs).

The random-failure rate in E2F cell 3 stays q = 0.0000266 (it was matched to C0's losses under the
nest restart; E9 cell 1 showed C0 loses a similar number of robots under fidelity, median 4).

## 4. New observation metric

- `repellent_in_hazard`: at the end of a run, the share of the repellent field's total mass that
  lies inside the true hazard mask (C2, C3: shared field; C5, C6: mean of live robots' maps). NaN
  when the field is empty. Unlike AUC it is sensitive to how strongly the hazard is marked.
- AUC is additionally reported over marked runs only (runs with any mark), with the count.
Neither changes behaviour or random streams.

## 5. Second platform (#26)

- A GitHub Actions workflow runs the full test suite on Windows and Linux on every push.
- The golden test is bit-exact on the machine that recorded it; on another platform it may differ
  in the last bits. Before the repository goes public we run the suite once on Linux (Docker,
  locally) and record whether the golden cases match bit for bit. If they do not, the golden test is
  marked as platform-specific and the paper keeps its "statistical, not bitwise, across machines"
  claim.

## 6. Out of scope

Robot–robot collisions, a physics-based simulator, a literature baseline controller, arena and
communication-range sweeps, multiple hazards: planned for the journal stage.
