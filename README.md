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

## Watch a run

    .venv/Scripts/python scripts/animate.py --controller C2 --seed 0

## Licence

MIT
