# Spec: physics-based replication in Webots (limitation #1, #2)

**Date:** 2026-10-23
**Status:** design. The replication experiment is pre-registered in `docs/hypotheses.md` only after
the user approves; no Webots data before that.

## 1. Why

Every result so far comes from our own point-robot simulator, in which robots never collide. The
most likely reviewer objection is that the effect could depend on that simplification. Webots
(open source, Apache 2.0, Cyberbotics; official release R2025a, `webots-R2025a_setup.exe`,
263 MB, from github.com/cyberbotics/webots) simulates real robot bodies with physics and
collisions, and ships a model of the e-puck, the robot our speed and sensing range were modelled on.
ARGoS, the usual swarm simulator, runs on Linux/macOS only, so Webots is the practical choice here.

## 2. What is replicated

The site-fidelity baseline (E1F) with the controllers that carry the main claims:
C0 (ignore), C1 (avoid wrecks in view), C2 (marking), C4 (oracle reference).
100 seeds each = 400 runs. If time allows: the hazard-between-patch-and-nest cell of E2F.

## 3. What changes and what stays the same

Real in Webots:
- e-puck bodies (7 cm diameter) with differential-drive physics and **collisions** between robots,
  walls and wrecks (a wreck is a stopped e-puck: a physical obstacle);
- motion through wheel speeds (max 0.1 m/s, as in our model), so turning takes time;
- local obstacle avoidance with the e-puck's 8 infrared proximity sensors, used by every controller.

Kept virtual (provided by a Webots *supervisor*, as virtual pheromones usually are in swarm
robotics): the invisible hazard and its lethality; items and patches; the nest beacon; wreck
detection within 0.5 m; the shared repellent field (same deposit, decay and gradient rule and the
same site-fidelity tuned parameters as C2 in E1F). Arena 10 × 10 m, same nest, patches and hazard,
10,000 control steps of 0.1 s.

## 4. Implementation plan

1. Install Webots R2025a (user approved on 2026-10-23).
2. `webots/` folder in this repository: one world file (arena, walls, 20 e-pucks), one supervisor
   controller (Python) that owns the hazard, items, field, deaths and logging, and one robot
   controller (Python) implementing C0, C1, C2, C4 on top of the e-puck's sensors and motors.
   Reuse the existing `swarmhazard` code for the field, metrics and seeding where possible.
3. A runner script that launches Webots headless (`--batch --mode=fast --no-rendering`) per run,
   with the seed passed in, and writes one CSV row per run in the existing result format
   (with `simulator = webots`).
4. Tests: the supervisor's field and hazard logic against the existing unit tests; a smoke run.
5. Calibration check (descriptive, before any pre-registered run): with no hazard, compare C0's
   deliveries and trip times with our simulator to document how much collisions slow foraging.

## 5. Proposed pre-registration (to be approved)

H1W: C2 delivers more items than C0. H2W: C2 loses fewer robots than C1. Same one-sided paired
Wilcoxon tests, Holm across the two, bootstrap CIs and A12 as for H1F/H2F. The paper reports the
Webots replication as a robustness check of the main effect under physics and collisions.

## 6. Risks

- Runtime: 20 e-pucks with physics may run only 10–50× faster than real time headless, so one
  1,000-second run could take 20–100 s; 400 runs = 2–11 hours. Measured in the smoke run first.
- Effect sizes may shrink with collisions (crowding near the nest and patches). That is a result,
  not a failure.
