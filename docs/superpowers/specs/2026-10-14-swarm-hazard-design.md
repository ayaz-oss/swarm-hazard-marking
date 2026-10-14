# Design: Robot Failures as Hazard Information in a Foraging Swarm

**Date:** 2026-10-14
**Status:** Approved in brainstorming; awaiting written-spec review
**Target output:** arXiv preprint (cs.RO) by ~10 Jan 2027; then journal submission (Swarm Intelligence, Springer; alternative Frontiers in Robotics and AI)

## 1. Research question and contribution

**Question.** Can a decentralised foraging swarm, using only local sensing, localise an unknown hazard from teammates failing near it, and how many items and robots does that save versus swarms that merely tolerate failures?

**Contribution (framing).** Robot losses converted into *decaying stigmergic marks in the environment*, requiring no planning or global map, in a decentralised central-place foraging swarm, with an explicit trade-off between foraging yield and robot losses. Not claimed: "first to use robot loss as a hazard signal".

**Prior work to cite and contrast** (each citation re-verified before use in the paper):

| Work | Difference from ours |
|---|---|
| Aguirre et al. 2025, arXiv 2511.22225 | Chooses safer of two areas from hazard event rates; no foraging, no inference from lost teammates |
| Srivastava, Suresh, Nieto-Granda 2025, arXiv 2508.04537 | Multi-robot hazard mapping with planning (BAPP); not foraging, no stigmergy. Closest work |
| Hunt, Cullen, Hauert, "Value at Risk" swarms (Bristol) | Robots alert neighbours before failing via broadcast; no marking from losses |
| Hunt, Jones, Hauert 2019, R. Soc. Open Sci. | Repellent virtual pheromone degrades at high density; motivates density sweep |
| Di et al., risk-aware multirobot foraging (ACM TAAS 2022; partially verified) | Centralised task allocation |
| Tarapore et al. 2017; Christensen et al. 2009 | Fault detection for swarm health, not environment mapping |
| Robinson et al. 2005, Nature | Biological inspiration: "no entry" repellent pheromone in Pharaoh ants |
| ICCCR 2024 "quarantine regions" | **Not found; do not cite until the student supplies a source** |

## 2. World and robot model

- **Arena:** 2D continuous, 10 × 10 m, walled. Circular nest at centre. Timestep 0.1 s; episode 10,000 steps (~17 simulated min).
- **Robots:** point agents, e-puck-like. Speed 0.1 m/s. Sensing range 0.5 m (items, wrecks). Always know nest direction (light-beacon assumption). Baseline N = 20. No robot–robot collisions in v1 (stated limitation).
- **Items:** clustered patches. A collected item respawns uniformly within its own patch, keeping the resource distribution stationary.
- **Hazards:** circular, invisible to robots. Each step inside, a robot fails with probability *p* (lethality).
- **Failure cue:** a failed robot becomes a **wreck**: static, permanent, detectable by any robot within sensing range. (Heartbeat-loss cue is out of scope for v1.)
- **Repellent field (approach A):** grid of 0.1 m cells. The first time a given robot sees a given wreck, it deposits repellent (Gaussian footprint) at the wreck. Field decays at rate ρ per step. Robots read only nearby cells and steer down the gradient.
- **Random-failure control:** robots fail at the same overall rate, at uniformly random times and locations, independent of any hazard.
- **Detection noise (E7):** each step a wreck in range is missed with probability *q_miss*; a false wreck sighting occurs with probability *q_false* per robot-step at the robot's position.

## 3. Controllers

All controllers share one finite-state machine: SEARCH (correlated random walk) → item sensed → approach and pick up → RETURN (home toward nest) → drop → SEARCH. They differ only in response to wrecks and repellent.

| ID | Name | Behaviour |
|---|---|---|
| C0 | Ignore | Wrecks do not affect behaviour |
| C1 | Avoid wrecks | Local repulsion from currently visible wrecks; no memory, no marking |
| C2 | Mark (main method) | C1 + deposits repellent on seeing a wreck; avoids repellent gradient in SEARCH and RETURN |
| C3 | Mark + risk trade-off | C2 with repulsion scaled by 1 / (1 + k · items_sensed) |
| C4 | Oracle | Knows true hazard zones; never enters. Upper bound, not a swarm method |
| C5 | Shared map (approach B) | Like C2, but each robot holds its own danger grid and merges (element-wise max) with neighbours within 1 m; no shared field |

**Tuning.** Repulsion weight, deposit amount, ρ and k are tuned by a small grid search on seeds disjoint from all main experiments, at the baseline configuration. The chosen values are committed to `configs/tuned_params.yaml` before any main experiment runs.

## 4. Experiments

**Baseline:** N = 20, one hazard of radius 1 m, *p* = 0.02 per step, hazard adjacent to an item patch. One-factor-at-a-time sweeps around the baseline. 100 seeds per cell.

| ID | Factor | Levels | Controllers |
|---|---|---|---|
| E1 | Controller | — | C0–C4 |
| E2 | Hazard placement | next to a patch / between patch and nest / far from everything / none (random-failure control) | C0–C4 |
| E3 | Swarm size | 5, 10, 20, 40, 80 | C0–C4 |
| E4 | Lethality *p* | 0.005, 0.02, 0.1, 1.0 | C0–C4 |
| E5 | Hazard radius | 0.5, 1, 2 m | C0–C4 |
| E6 | Robustness of information medium | baseline + N sweep from E3 | C2, C5 |
| E7 | Detection noise | (*q_miss*, *q_false*) ∈ {(0,0), (0.2,0), (0,1e-5), (0.2,1e-5)} | C1, C2, C3 |

Optional if ahead of schedule: hazard relocates halfway through an episode (tests value of decay ρ).

**Metrics**
- Primary: items delivered to nest.
- Robots lost; items per robot lost.
- Localisation quality: ROC AUC of the repellent field (C5: mean of per-robot maps) against the true hazard mask, sampled every 500 steps.
- False-alarm cost: items lost relative to C0 in the random-failure control.

**Hypotheses** (committed to `docs/hypotheses.md` before the first main run)
- H1: C2 delivers more items than C0.
- H2: C2 loses fewer robots than C1.
- H3: In the random-failure control, C2's item cost relative to C0 is small (|A12 − 0.5| < 0.14).
- H4: C3 delivers more items than C2 when the hazard is next to a patch.

**Statistics.** Per experiment: Kruskal–Wallis; pairwise Mann–Whitney U vs C2 with Holm correction; Vargha–Delaney A12 effect sizes; medians with bootstrap 95% CIs. All figures regenerated from raw CSVs by one script.

## 5. Repository layout

The repository root is this project folder; `swarm-hazard` is the public GitHub name.

```
swarm-hazard/
  README.md               how to reproduce every figure
  pyproject.toml          pinned dependencies (numpy, scipy, pandas, matplotlib, pyyaml, pytest)
  configs/
    baseline.yaml         every parameter, with units
    experiments/E1..E7.yaml   deltas from baseline
    tuned_params.yaml     frozen after tuning
  src/swarmhazard/
    world.py              arena, nest, item patches, hazards
    robots.py             robot state arrays, FSM, movement
    sensing.py            local perception (items, wrecks, repellent)
    pheromone.py          repellent grid: deposit, decay, gradient
    controllers.py        C0–C5 as small, separate steering policies
    sim.py                run(config, seed) -> result record
    metrics.py            items, losses, localisation AUC
  scripts/
    run_experiment.py     sweep -> one CSV row per run, multiprocessing
    analyse.py            statistical tests -> tables
    make_figures.py       CSVs -> every paper figure
    animate.py            visualise a single run
  tests/                  pytest, one file per module
  docs/
    hypotheses.md
    learning/             plain-English note per milestone for the student
  results/                raw CSVs (git-ignored; archived on Zenodo)
```

Robot state is held as numpy arrays (positions, headings, FSM state, alive flag) and all robots update in one vectorised step.

## 6. Reproducibility

- Each run seeded via `numpy.random.SeedSequence` from (experiment ID, cell index, seed index); any single run is exactly re-runnable.
- Every result row records the config hash, git commit and package versions.
- `make_figures.py` reads CSVs only; it never re-simulates.
- Release: tagged GitHub release + Zenodo DOI for code and raw results. MIT licence.

## 7. Testing

Unit tests for deterministic properties: repellent decay matches ρ analytically; empirical failure rate inside a hazard matches *p*; oracle never enters a hazard; same (config, seed) gives identical output; items are conserved (delivered + carried + on-field is consistent with respawning).

## 8. First minimal version and go/no-go gate

**Scope (week 1):** world, robots, repellent grid, C0 / C2 / C4, baseline config only, `animate.py`, 30-seed comparison.

**Gate:** pass if C2 beats C0 on items delivered with A12 > 0.64, and C4 ≥ C2. If the gate fails, revise the model (parameters, hazard placement, detection) before building C1, C3, C5 or running sweeps.

## 9. Timeline

| Dates | Milestone |
|---|---|
| 14–20 Oct | Minimal version + go/no-go gate |
| 21 Oct – 3 Nov | C1, C3, all metrics, tuning on held-out seeds, commit hypotheses |
| 4–24 Nov | E1–E5, analysis, first-draft figures |
| 25 Nov – 8 Dec | C5 + E6, E7; optional moving hazard |
| 9 Dec – 5 Jan | Paper writing (student-led), citation verification, internal and mentor review |
| ~10 Jan | arXiv submission |

## 10. Risks

- **arXiv endorsement.** Since 21 Jan 2026 an institutional email no longer suffices for endorsement; secure an endorsing mentor early.
- **Null or trivial result.** Mitigated by the week-1 gate and by framing around *when* marking helps (C2 vs C1, density, false alarms).
- **Density degradation** (Hunt et al. 2019). Measured directly in E3; reported either way.
- **Realism.** Point robots, no collisions, simulation only. Partly addressed by E7; stated as limitations.

## 11. Working mode

Claude builds at full speed in small modules with explanatory docstrings. Each milestone gets a one-page note in `docs/learning/`. The student makes modelling decisions, runs the experiments and writes the paper.
