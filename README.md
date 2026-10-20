# swarmhazard

Simulation code for a study of whether a decentralised foraging robot swarm can
treat teammates' failures as information about where hidden hazards are.

Design: `docs/superpowers/specs/2026-10-14-swarm-hazard-design.md`

## Install

    python -m venv .venv
    .venv/Scripts/python -m pip install -e ".[dev]"     # Windows (Git Bash)
    # .venv/bin/python -m pip install -e ".[dev]"       # macOS / Linux

## Test

    .venv/Scripts/python -m pytest

## Reproduce the week-1 gate

    .venv/Scripts/python scripts/run_experiment.py configs/experiments/gate.yaml
    .venv/Scripts/python scripts/check_gate.py results/gate.csv

## Tune parameters (week 2)

    .venv/Scripts/python scripts/run_experiment.py configs/experiments/tune_c2.yaml
    .venv/Scripts/python scripts/select_params.py results/tune_c2.csv C2 repel_weight deposit_sigma decay
    git add configs/tuned_params.yaml && git commit -m "Record tuned C2 parameters"
    .venv/Scripts/python scripts/run_experiment.py configs/experiments/tune_c3.yaml
    .venv/Scripts/python scripts/select_params.py results/tune_c3.csv C3 risk_k
    git add configs/tuned_params.yaml && git commit -m "Record tuned C3 risk_k"

The analysis plan and hypotheses are in `docs/hypotheses.md`.

## Run experiments from a frozen copy (week 4)

    .venv/Scripts/python scripts/run_batch.py E6 E7

Checks out the current commit into `.batch/<sha>/`, runs the golden test there, then runs
each experiment from that copy, so later edits or commits cannot change a running batch.

Week 5 (after the user approves the pre-registration): `python scripts/run_batch.py E6b E7b E8 --workers 4`,
then `python scripts/analyse_week5.py` and `python scripts/make_figures.py`.
Mechanism checks (small, descriptive): `python scripts/mechanism_checks.py --reference-dir <dir with E1.csv and E4.csv>`.

## Watch a run

    .venv/Scripts/python scripts/animate.py --controller C2 --seed 0

## Licence

MIT
