"""One simulation run.

Each step, in order:
  1. choose headings  - searchers random-walk or head for a visible item;
                        returners head for the nest; the controller bends headings
  2. move             - walls bounce robots; the oracle slides along hazard edges
  3. pick up          - a searcher within pickup_radius of an item takes it
  4. deliver          - a returner inside the nest drops its item
  5. failures         - robots inside a hazard fail with probability `lethality`;
                        every robot also fails with probability `random_fail_rate`
  6. mark (MARKING)   - each robot that sees a wreck for the first time deposits
                        repellent on it; then the whole field decays
  7. noise (E7)       - robots may miss wrecks in range, or mark wrecks that are not there
"""

from __future__ import annotations

import numpy as np

from swarmhazard.config import Config
from swarmhazard.controllers import MARKING, avoidance, blocks_move, hazard_tangent
from swarmhazard.geometry import norm
from swarmhazard.metrics import field_auc, hazard_mask
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
        (layout_rng, self.motion_rng, self.respawn_rng, self.hazard_rng,
         self.background_rng, self.noise_rng) = rng.spawn(6)  # earlier children unchanged by later ones
        self.world = make_world(cfg, layout_rng)
        self.swarm = make_swarm(cfg, layout_rng)
        self.field = RepellentField(cfg.arena_size, cfg.grid_cell)
        self.hazard_mask = hazard_mask(self.world, self.field)
        self.auc_series: list[float] = []
        n = cfg.n_robots
        self.seen = np.zeros((n, n), dtype=bool)  # seen[i, j]: robot i has already marked wreck j
        self.nest = np.asarray(cfg.nest_center, dtype=float)
        self.t = 0
        self.delivered = 0
        self.picked_up = 0
        self.items_lost = 0  # carried by a robot when it failed
        self.first_loss_step = -1
        self.false_sightings = 0

    def step(self) -> None:
        sw = self.swarm
        n = len(sw.pos)
        # Detection noise draws: a fixed number per step, whatever the robots are doing.
        self._detected = self.noise_rng.random((n, n)) >= self.cfg.q_miss  # [i, j]: robot i detects wreck j
        false_draw = self.noise_rng.random(n)
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
        self._false_sightings(false_draw)
        if self.cfg.controller in MARKING:
            self.field.decay(self.cfg.decay)
        self.t += 1
        if self.cfg.controller in MARKING and self.t % self.cfg.metric_every == 0:
            self.auc_series.append(field_auc(self.field.grid, self.hazard_mask))

    def _choose_headings(self, searching: np.ndarray, returning: np.ndarray) -> None:
        cfg, sw = self.cfg, self.swarm
        noise = self.motion_rng.normal(0.0, cfg.turn_noise, len(sw.pos))  # one draw per robot, always
        sw.heading[searching] += noise[searching]
        if len(self.world.item_pos):
            to_items = self.world.item_pos[None, :, :] - sw.pos[:, None, :]
            dist = norm(to_items)
            nearest = dist.argmin(axis=1)
            rows = np.arange(len(sw.pos))
            sees_item = searching & (dist[rows, nearest] < cfg.sense_range)
            v = to_items[rows, nearest]
            sw.heading[sees_item] = np.arctan2(v[sees_item, 1], v[sees_item, 0])
        v = self.nest - sw.pos
        sw.heading[returning] = np.arctan2(v[returning, 1], v[returning, 0])

        dead = np.flatnonzero(~sw.alive)
        steer = unit(sw.heading) + avoidance(cfg, sw.pos, sw.pos[dead], self.field, self.world,
                                             detected=self._detected[:, dead])
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
        # Same rule as before: robots in index order take an item within
        # pickup_radius; a taken item respawns at once and may then be taken by
        # a later robot. Distances are computed once; after the first pickup in
        # a step, later robots re-check against the moved item.
        if len(self.world.item_pos) == 0:
            return
        sw = self.swarm
        idx = np.flatnonzero(searching)
        if len(idx) == 0:
            return
        items = self.world.item_pos
        dist = norm(items[None, :, :] - sw.pos[idx][:, None, :])  # (S, M)
        close = np.flatnonzero(dist.min(axis=1) < self.cfg.pickup_radius)
        if len(close) == 0:
            return
        changed = False
        for row in range(close[0], len(idx)):  # rows before the first close one cannot pick up
            i = idx[row]
            d = norm(items - sw.pos[i]) if changed else dist[row]
            j = int(d.argmin())
            if d[j] < self.cfg.pickup_radius:
                sw.state[i] = RETURN
                self.picked_up += 1
                respawn_item(self.world, j, self.respawn_rng)
                changed = True

    def _deliver(self, returning: np.ndarray) -> None:
        sw = self.swarm
        at_nest = returning & (norm(sw.pos - self.nest) < self.cfg.nest_radius)
        sw.state[at_nest] = SEARCH
        fresh = self.motion_rng.uniform(-np.pi, np.pi, len(sw.pos))  # one draw per robot, always
        sw.heading[at_nest] = fresh[at_nest]
        self.delivered += int(at_nest.sum())

    def _fail(self, alive: np.ndarray) -> None:
        sw = self.swarm
        dies = hazard_failures(self.world, sw.pos, alive, self.cfg.lethality, self.hazard_rng)
        background = self.background_rng.random(len(sw.pos))  # one draw per robot, always
        dies |= alive & (background < self.cfg.random_fail_rate)
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
        dist = norm(sw.pos[:, None, :] - sw.pos[None, dead, :])  # (N, D)
        visible = sw.alive[:, None] & (dist < cfg.sense_range) & self._detected[:, dead]
        new = visible & ~self.seen[:, dead]
        for col in np.flatnonzero(new.any(axis=0)):
            amount = cfg.deposit_amount * new[:, col].sum()
            self.field.deposit(sw.pos[dead[col]], amount, cfg.deposit_sigma)
        self.seen[:, dead] |= visible

    def _false_sightings(self, false_draw: np.ndarray) -> None:
        """Robots that 'see' a non-existent wreck where they stand (E7 noise)."""
        cfg, sw = self.cfg, self.swarm
        phantom = sw.alive & (false_draw < cfg.q_false)
        self.false_sightings += int(phantom.sum())
        if cfg.controller in MARKING:
            for i in np.flatnonzero(phantom):
                self.field.deposit(sw.pos[i], cfg.deposit_amount, cfg.deposit_sigma)

    def result(self) -> dict:
        return {
            "delivered": self.delivered,
            "picked_up": self.picked_up,
            "items_lost": self.items_lost,
            "carrying": int((self.swarm.alive & (self.swarm.state == RETURN)).sum()),
            "robots_lost": int((~self.swarm.alive).sum()),
            "first_loss_step": self.first_loss_step,
            "steps": self.t,
            "false_sightings": self.false_sightings,
            "auc_final": self.auc_series[-1] if self.auc_series else float("nan"),
            "auc_mean": float(np.mean(self.auc_series)) if self.auc_series else float("nan"),
            "auc_series": ";".join(f"{a:.4f}" for a in self.auc_series),
            "hazard_area": float(self.hazard_mask.sum() * self.cfg.grid_cell ** 2),
        }


def run(cfg: Config, rng: np.random.Generator) -> dict:
    sim = Simulation(cfg, rng)
    for _ in range(cfg.n_steps):
        sim.step()
    return sim.result()
