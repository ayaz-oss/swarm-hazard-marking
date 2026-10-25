# Lost teammates as hazard sensors

Simulation code, pre-registration and data for a study of whether a decentralised foraging robot
swarm, using only local sensing, can locate an invisible hazard from where its teammates fail. A
robot that finds a teammate's wreck leaves a decaying "keep away" mark (like the "no entry"
pheromone of Pharaoh ants), and the other robots steer away from strong marks.

Author: Ayaz Nasyrov (Foundation Year, University College London).
Paper (working draft): [`docs/paper/draft.pdf`](docs/paper/draft.pdf).
Archived release: [doi.org/10.5281/zenodo.23637280](https://doi.org/10.5281/zenodo.23637280) (v1.1; v1.0-preprint: 10.5281/zenodo.23591454).

## What is here

| Path | Contents |
|---|---|
| `src/swarmhazard/` | The simulator: arena, robots, controllers C0–C7, repellent field, metrics, statistics |
| `configs/` | Baseline configuration, tuned parameters, and one YAML file per experiment |
| `scripts/` | Running experiments, tuning, analysis, figures, diagnostics, frozen batches |
| `tests/` | Unit tests, plus bit-exact "golden" regression tests |
| `docs/hypotheses.md` | The pre-registration: hypotheses, statistics and every later addition, each dated before its data existed |
| `docs/superpowers/specs/` | Design spec and dated addenda |
| `docs/learning/` | Plain-language notes on each stage of the study (01–08) |
| `data/` | Snapshot of every result used in the paper: raw per-run CSVs, analysis tables, diagnostics, figures |

## Controllers

| ID | Behaviour |
|---|---|
| C0 | Ignores wrecks |
| C1 | Avoids wrecks currently in view |
| C2 | C1 plus marking a shared, decaying repellent field (main method) |
| C3 | C2 with the push weakened when items are in view |
| C4 | Oracle: cannot enter the hazard (reference only) |
| C5 | Per-robot maps, max-merged with neighbours |
| C6 | Per-robot sighting records, shared with neighbours |
| C7 | Risk-limit alerts broadcast to neighbours (inspired by Hunt, Cullen and Hauert 2021) |

## Install

Python 3.11.

    python -m venv .venv
    .venv/Scripts/python -m pip install -e ".[dev]"     # Windows
    # .venv/bin/python -m pip install -e ".[dev]"       # macOS / Linux

## Test

    .venv/Scripts/python -m pytest

The golden tests compare full simulation runs bit for bit with recorded values. They were recorded
on Windows; on another platform results are expected to agree statistically, not necessarily
bit for bit.

## Reproduce the results

Every experiment is one YAML file in `configs/experiments/`; each run's random streams depend only
on (experiment, cell, seed), so any run can be repeated exactly on the same platform.

    # one experiment
    .venv/Scripts/python scripts/run_experiment.py configs/experiments/E1F.yaml --workers 4

    # several, from a frozen copy of the current commit (as used for the paper)
    .venv/Scripts/python scripts/run_batch.py E1F E2F E3F --workers 4

Analysis and figures (results are written to `results/`):

    .venv/Scripts/python scripts/analyse.py          # nest-restart model, H1–H4, E1–E7
    .venv/Scripts/python scripts/analyse_week5.py    # E6b, E7b, E8
    .venv/Scripts/python scripts/analyse_week6.py    # E9
    .venv/Scripts/python scripts/analyse_week7.py    # site-fidelity model, H1F–H4F, E1F–E8F
    .venv/Scripts/python scripts/analyse_journal.py  # E10, E10b, E11, E12
    .venv/Scripts/python scripts/make_figures.py

To analyse the published data instead of re-running, copy `data/raw/*.csv` into `results/`.

The commit each experiment ran from is recorded in every result row (`git_commit`) and listed in
the paper's "Code and data availability" section.

Tuning (parameters are committed before the main experiments that use them):

    .venv/Scripts/python scripts/run_experiment.py configs/experiments/tune_c2f.yaml
    .venv/Scripts/python scripts/select_params.py results/tune_c2f.csv C2 repel_weight deposit_sigma decay

## Watch a run

    .venv/Scripts/python scripts/animate.py --controller C2 --seed 0

## Use of AI tools

The code was written with the help of an AI coding assistant (Claude, Anthropic) under the
author's direction; see the paper.

## Licence

Code: MIT (see `LICENSE`). Text, figures and data (`docs/`, `data/`): CC BY 4.0 (see
`LICENSE-CC-BY-4.0.md`). Please cite using `CITATION.cff`.
