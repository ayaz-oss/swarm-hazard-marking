# 01 — The minimal version

## What we built

A simulator for 20 robots in a 10 m × 10 m arena. Robots wander (a "correlated
random walk": they keep roughly their heading, with a small random turn each
step), grab any item they see within 0.5 m, carry it straight back to the nest
in the middle, and repeat. One hidden circle next to an item patch kills a robot
with 2% probability for every 0.1 s it spends inside. A dead robot stays where
it died as a "wreck" that others can see.

## The three controllers

- **C0 Ignore:** wrecks change nothing. This is a swarm that just tolerates losses.
- **C2 Mark:** the first time a robot sees a wreck, it drops a blob of virtual
  repellent on it. The repellent slowly fades (half-life about 2 minutes). Robots
  feel the slope of the repellent around them and turn away from where it is
  stronger. This is our idea: failures become information.
- **C4 Oracle:** knows exactly where the hazard is and never goes in. No real
  swarm can do this; it shows the best possible result, so we can say how much
  of that best case C2 achieves.

## Where to look in the code

| Question | File |
|---|---|
| What are all the numbers? | `configs/baseline.yaml` |
| What happens in one time step? | `src/swarmhazard/sim.py` (`Simulation.step`) |
| How do controllers differ? | `src/swarmhazard/controllers.py` (`avoidance`) |
| How does repellent spread and fade? | `src/swarmhazard/pheromone.py` |
| How do we know it's correct? | `tests/` — run `.venv/Scripts/python -m pytest` |

## Why it's reproducible

Every random number comes from one generator, seeded from
(experiment name, configuration number, seed number). Running the same command
again gives the same numbers, bit for bit. Each CSV row also records the git
commit and the exact configuration (as a hash), so any figure can be traced to
the code that made it.

## The go/no-go gate

We ran 30 seeds of each controller. The gate passes if C2 beats C0 on items
delivered with A12 > 0.64, and the oracle does at least as well as C2.
A12 is the chance that a random C2 run delivers more than a random C0 run:
0.5 means no difference, 0.64 is a "medium" effect.

One full run takes 12.3 s (a single 10,000-step C2 run, timed on its own). The
whole gate, 90 runs spread across the computer's cores, took 211 s.

Result:

```
            delivered  robots_lost
controller                        
C0               44.0          5.0
C2               46.5          2.0
C4               48.0          0.0
           delivered              robots_lost            
              median   mean   std      median  mean   std
controller                                               
C0              44.0  43.23  4.66         5.0  4.70  1.74
C2              46.5  46.20  4.79         2.0  1.87  0.78
C4              48.0  47.47  3.96         0.0  0.00  0.00

A12(C2 vs C0, delivered) = 0.673  (needs > 0.64)
median C4 >= median C2: True
GATE: PASS
```

## What this means

The gate passes: at baseline, marking wrecks with repellent beats ignoring them
(A12 = 0.673, just above the 0.64 line), and C2 loses fewer robots (median 2
against 5) while the oracle sits on top as it should. So the effect exists and
we can move on to C1, C3 and tuning. Be careful, though: the margin is thin,
and C2 delivers only about 2.5 more items than C0 out of roughly 44, so
anything that weakens the signal could erase it. On the seed we animated, the
robots die at about steps 2,950 and 3,970, but no live robot gets within
0.5 m of a wreck until step 6,262, and only one robot–wreck sighting happens in
the whole run. These figures come from seed 0 of the gate (`make_rng("gate", 0, 0)`),
controller C2, baseline config, one full 10,000-step run. The repellent signal is sparse because wrecks lie inside the
hazard, where few robots go to look. That is worth keeping in mind when we tune.

## Questions to think about

1. Why do we give every controller the same seeds?
2. C2's wrecks pile up at the edge of the hazard. Would just steering around
   visible wrecks (C1, next week) already get most of the benefit? Why does that
   matter for the paper?
3. What would go wrong if the repellent never faded?
