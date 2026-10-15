# Pre-registered hypotheses and analysis plan

Committed before any main experiment (E1–E7) runs. Changing anything here after
main results exist must be reported in the paper as a deviation.

## Primary metric

Items delivered to the nest per run (10,000 steps, ~17 simulated minutes).
Secondary: robots lost; items per robot lost; localisation AUC (marking controllers).

## Hypotheses (spec section 4)

| ID | Claim | Experiment | Test |
|---|---|---|---|
| H1 | C2 delivers more items than C0 | E1 | one-sided Mann–Whitney U, A12 > 0.5 |
| H2 | C2 loses fewer robots than C1 | E1 | one-sided Mann–Whitney U on robots lost |
| H3 | In the random-failure control, C2's item cost relative to C0 is small: \|A12 − 0.5\| < 0.14 | E2 (no-hazard level) | A12 with bootstrap 95% CI; supported if the whole CI lies inside 0.36–0.64 |
| H4 | C3 delivers more items than C2 when the hazard is next to a patch | E1 | one-sided Mann–Whitney U |

## Statistics

- 100 seeds per cell. α = 0.05; within each experiment, Holm correction across the pairwise comparisons.
- Report medians with bootstrap 95% CIs (10,000 resamples) and Vargha–Delaney A12 with bootstrap 95% CIs.
- Per experiment: Kruskal–Wallis across controllers, then pairwise Mann–Whitney U against C2.
- `first_loss_step = -1` means no robot was lost; treat it as missing, never as a number.

## Tuning protocol (spec section 3)

- Tuned at the baseline configuration only, on experiments `tune_c2` and `tune_c3`, whose
  random streams are independent of the gate and of E1–E7.
- C2 grid: repel_weight {0.5, 1, 2, 4} × deposit_sigma {0.2, 0.3, 0.5} × decay {0.0002, 0.0005, 0.002}; 20 seeds per cell.
- C3 grid: risk_k {0.25, 0.5, 1, 2, 4} on top of the chosen C2 values; 20 seeds per cell.
- Selection rule: highest median items delivered; ties → lowest mean robots lost.
- Fixed, not tuned: deposit_amount = 1 (redundant with repel_weight), wreck_weight = 1 (shared with C1).
- The chosen values are committed to `configs/tuned_params.yaml` before any main experiment runs.

## Reproducibility claim

Exact re-runs are claimed on the same machine and software environment (recorded per row).
Across machines, results are expected to agree statistically, not bit for bit.
