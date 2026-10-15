"""One simulation run.

Each step, in order:
  1. choose headings  - searchers random-walk or head for a visible item;
                        returners head for the nest; the controller bends headings
  2. move             - walls bounce robots; the oracle slides along hazard edges
  3. pick up          - a searcher within pickup_radius of an item takes it
  4. deliver          - a returner inside the nest drops its item
  5. hazard failures  - robots inside a hazard fail with probability `lethality`
  6. mark (MARKING)   - each robot that sees a wreck for the first time deposits
                        repellent on it; then the whole field decays
"""

from __future__ import annotations

import numpy as np

from swarmhazard.config import Config
from swarmhazard.controllers import MARKING, avoidance, blocks_move, hazard_tangent
from swarmhazard.pheromone import RepellentField
from swarmhazard.robots import RETURN, SEARCH, make_swarm, unit
from swarmhazard.world import hazard_failures, in_hazard, make_world, respawn_item


class Simulation:
    def __init__(self, cfg: Config, rng: np.random.Generator):
        self.cfg = cfg
        # Separate child streams, so that a behavioural difference in one part
        # of the simulation (e.g. a robot dying) cannot shift the random
        # numbers used anywhere else. Controllers then share randomness for
        # the whole run, not just until their first difference.
        layout_rng, self.motion_rng, self.respawn_rng, self.hazard_rng = rng.spawn(4)
        self.world = make_world(cfg, layout_rng)
        self.swarm = make_swarm(cfg, layout_rng)
        self.field = RepellentField(cfg.arena_size, cfg.grid_cell)
        n = cfg.n_robots
        self.seen = np.zeros((n, n), dtype=bool)  # seen[i, j]: robot i has already marked wreck j
        self.nest = np.asarray(cfg.nest_center, dtype=float)
        self.t = 0
        self.delivered = 0
        self.picked_up = 0
        self.items_lost = 0  # carried by a robot when it failed
        self.first_loss_step = -1

    def step(self) -> None:
        sw = self.swarm
        alive = sw.alive.copy()
        searching = alive & (sw.state == SEARCH)
        returning = alive & (sw.state == RETURN)

        self._choose_headings(searching, returning)
        self._move(alive)
        self._pick_up(searching)
        self._deliver(returning)
        self._fail(alive)
        if self.cfg.controller in MARKING:
            self._mark()
            self.field.decay(self.cfg.decay)
        self.t += 1

    def _choose_headings(self, searching: np.ndarray, returning: np.ndarray) -> None:
        cfg, sw = self.cfg, self.swarm
        noise = self.motion_rng.normal(0.0, cfg.turn_noise, len(sw.pos))  # one draw per robot, always
        sw.heading[searching] += noise[searching]
        if len(self.world.item_pos):
            to_items = self.world.item_pos[None, :, :] - sw.pos[:, None, :]
            dist = np.linalg.norm(to_items, axis=2)
            nearest = dist.argmin(axis=1)
            rows = np.arange(len(sw.pos))
            sees_item = searching & (dist[rows, nearest] < cfg.sense_range)
            v = to_items[rows, nearest]
            sw.heading[sees_item] = np.arctan2(v[sees_item, 1], v[sees_item, 0])
        v = self.nest - sw.pos
        sw.heading[returning] = np.arctan2(v[returning, 1], v[returning, 0])

        wrecks = sw.pos[~sw.alive]
        steer = unit(sw.heading) + avoidance(cfg, sw.pos, wrecks, self.field, self.world)
        sw.heading[:] = np.where(sw.alive, np.arctan2(steer[:, 1], steer[:, 0]), sw.heading)

    def _move(self, alive: np.ndarray) -> None:
        cfg, sw, world = self.cfg, self.swarm, self.world
        kick = self.motion_rng.normal(0.0, 0.5, len(sw.pos))  # one draw per robot, always
        step = cfg.speed * cfg.dt
        new = sw.pos + step * unit(sw.heading)
        hit_wall = ((new < 0) | (new > cfg.arena_size)).any(axis=1)
        new = np.clip(new, 0.0, cfg.arena_size)
        blocked = blocks_move(cfg, world, new)
        if blocked.any():
            # The oracle slides along the hazard edge instead of stepping in.
            slide = np.clip(sw.pos + step * hazard_tangent(world, sw.pos, unit(sw.heading)),
                            0.0, cfg.arena_size)
            slides = blocked & ~in_hazard(world, slide)
            new[slides] = slide[slides]
            blocked = blocked & ~slides
        moves = alive & ~blocked
        sw.pos[moves] = new[moves]
        bounce = alive & (hit_wall | blocked)
        sw.heading[bounce] += np.pi + kick[bounce]

    def _pick_up(self, searching: np.ndarray) -> None:
        # A loop, not a vectorised op: two robots must not take the same item.
        if len(self.world.item_pos) == 0:
            return
        sw = self.swarm
        for i in np.flatnonzero(searching):
            d = np.linalg.norm(self.world.item_pos - sw.pos[i], axis=1)
            j = int(d.argmin())
            if d[j] < self.cfg.pickup_radius:
                sw.state[i] = RETURN
                self.picked_up += 1
                respawn_item(self.world, j, self.respawn_rng)

    def _deliver(self, returning: np.ndarray) -> None:
        sw = self.swarm
        at_nest = returning & (np.linalg.norm(sw.pos - self.nest, axis=1) < self.cfg.nest_radius)
        sw.state[at_nest] = SEARCH
        fresh = self.motion_rng.uniform(-np.pi, np.pi, len(sw.pos))  # one draw per robot, always
        sw.heading[at_nest] = fresh[at_nest]
        self.delivered += int(at_nest.sum())

    def _fail(self, alive: np.ndarray) -> None:
        sw = self.swarm
        dies = hazard_failures(self.world, sw.pos, alive, self.cfg.lethality, self.hazard_rng)
        if dies.any():
            self.items_lost += int((dies & (sw.state == RETURN)).sum())
            sw.alive[dies] = False  # a carried item is lost with the robot
            if self.first_loss_step < 0:
                self.first_loss_step = self.t

    def _mark(self) -> None:
        cfg, sw = self.cfg, self.swarm
        dead = np.flatnonzero(~sw.alive)
        if len(dead) == 0:
            return
        dist = np.linalg.norm(sw.pos[:, None, :] - sw.pos[None, dead, :], axis=2)  # (N, D)
        visible = sw.alive[:, None] & (dist < cfg.sense_range)
        new = visible & ~self.seen[:, dead]
        for col in np.flatnonzero(new.any(axis=0)):
            amount = cfg.deposit_amount * new[:, col].sum()
            self.field.deposit(sw.pos[dead[col]], amount, cfg.deposit_sigma)
        self.seen[:, dead] |= visible

    def result(self) -> dict:
        return {
            "delivered": self.delivered,
            "picked_up": self.picked_up,
            "items_lost": self.items_lost,
            "carrying": int((self.swarm.alive & (self.swarm.state == RETURN)).sum()),
            "robots_lost": int((~self.swarm.alive).sum()),
            "first_loss_step": self.first_loss_step,
            "steps": self.t,
        }


def run(cfg: Config, rng: np.random.Generator) -> dict:
    sim = Simulation(cfg, rng)
    for _ in range(cfg.n_steps):
        sim.step()
    return sim.result()
