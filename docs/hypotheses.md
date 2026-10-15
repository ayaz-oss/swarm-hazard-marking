# Pre-registered hypotheses and analysis plan

Committed before any main experiment (E1–E7) runs. Changing anything here after
main results exist must be reported in the paper as a deviation.

## Primary metric

Items delivered to the nest per run (10,000 steps, ~17 simulated minutes).
Secondary: robots lost; items per robot lost; localisation AUC (marking controllers).

## Hypotheses (spec section 4)

A12(X, Y) is the probability that a run of X scores higher than a run of Y on the named metric (ties count half).

| ID | Claim | Experiment | Confirmatory test |
|---|---|---|---|
| H1 | C2 delivers more items than C0 | E1 | one-sided Mann–Whitney U, alternative C2 > C0 on items delivered; effect size A12(C2, C0) |
| H2 | C2 loses fewer robots than C1 | E1 | one-sided Mann–Whitney U, alternative C1 > C2 on robots lost; effect size A12(C1, C2) |
| H3 | In the random-failure control, C2's item cost relative to C0 is small | E2 (no-hazard level) | non-inferiority: supported if the lower bound of the bootstrap 95% CI of A12(C2, C0) on items delivered is above 0.36 |
| H4 | C3 delivers more items than C2 when the hazard is next to a patch | E1 | one-sided Mann–Whitney U, alternative C3 > C2 on items delivered; effect size A12(C3, C2) |

H3 operationalises the spec's |A12 − 0.5| < 0.14 as a one-sided bound, because the hypothesis is about a cost: C2 doing better than C0 in the control does not count against it.

## Statistics

- 100 seeds per cell.
- Confirmatory family: H1, H2 and H4, tested on E1 with Holm correction across these three tests at α = 0.05. A hypothesis is supported if its Holm-adjusted p-value is below 0.05. Effect sizes are reported with bootstrap 95% CIs but no A12 threshold is required for support.
- H3 is decided only by its CI rule above (not part of the Holm family).
- Bootstrap: percentile method, 10,000 resamples, 95% two-sided intervals, for medians and A12.
- Everything else is exploratory and labelled as such: per experiment, Kruskal–Wallis across controllers, then two-sided pairwise Mann–Whitney U against C2 with Holm correction within that experiment.
- `first_loss_step = -1` means no robot was lost; treat it as missing, never as a number.

## Tuning protocol (spec section 3)

- Tuned at the baseline configuration only, on experiments `tune_c2` and `tune_c3`, whose
  random streams are independent of the gate and of E1–E7.
- C2 grid: repel_weight {0.5, 1, 2, 4} × deposit_sigma {0.2, 0.3, 0.5} × decay {0.0002, 0.0005, 0.002}; 20 seeds per cell.
- C3 grid: risk_k {0.25, 0.5, 1, 2, 4} on top of the chosen C2 values; 20 seeds per cell.
- Selection rule: highest median items delivered; ties → lowest mean robots lost.
- Deviation from spec section 3: the spec lists deposit amount as a tuned parameter. It is fixed at 1 because the repellent push is proportional to deposit_amount × repel_weight, so tuning repel_weight covers it; deposit_sigma (the footprint width), which the spec does not list, is tuned instead. wreck_weight is fixed at 1 because C1 shares it.
- The chosen values are committed to `configs/tuned_params.yaml` before any main experiment runs.

## Reproducibility claim

Exact re-runs are claimed on the same machine and software environment (recorded per row).
Across machines, results are expected to agree statistically, not bit for bit.
