"""One simulation run.

Each step, in order:
  0. hazard move (E8) - at hazard_move_step the hazards are replaced
  1. choose headings  - searchers random-walk or head for a visible item;
                        returners head for the nest; the controller bends headings
  2. move             - walls bounce robots; the oracle slides along hazard edges
  3. pick up          - a searcher within pickup_radius of an item takes it
  4. deliver          - a returner inside the nest drops its item
  5. failures         - robots inside a hazard fail with probability `lethality`;
                        every robot also fails with probability `random_fail_rate`
  6. mark            - MARKING: deposit on the shared field; PERSONAL (C5): on the observer's
                        own map; maps decay; C5 robots exchange maps every share_every steps;
                        RECORDS (C6): sighting records known by the observer, shared with
                        neighbours every share_every steps
  7. noise (E7)       - robots may miss wrecks in range (correlated spells if miss_run > 0),
                        or mark wrecks that are not there
"""

from __future__ import annotations

import numpy as np

from swarmhazard.config import Config
from swarmhazard.controllers import MAPPED, MARKING, PERSONAL, RECORDS, avoidance, blocks_move, hazard_tangent
from swarmhazard.geometry import norm
from swarmhazard.metrics import field_auc, hazard_mask
from swarmhazard.noise import next_blind
from swarmhazard.pheromone import RepellentField
from swarmhazard.records import SightingRecords
from swarmhazard.robots import OUTBOUND, RETURN, SEARCH, make_swarm, unit
from swarmhazard.world import hazard_failures, in_hazard, make_world, respawn_item, set_hazards


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
        self.maps = (np.zeros((cfg.n_robots, self.field.n, self.field.n))
                     if cfg.controller in PERSONAL else None)  # C5: maps[i] is robot i's own map
        self.records = (SightingRecords(cfg.n_robots, self.field, cfg.deposit_amount, cfg.deposit_sigma)
                        if cfg.controller in RECORDS else None)  # C6
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
        self._blind = None  # E7b: per-pair blind state for correlated misses
        self.first_loss_post_step = -1  # E8
        self._pre = None
        self._old_mask = None
        # Observation metrics (week 6): do not affect behaviour or random streams
        n = cfg.n_robots
        self._pickup_step = np.full(n, -1, dtype=np.int64)       # step of last pickup per robot
        self._last_event_step = np.zeros(n, dtype=np.int64)      # delivery step (or 0 at start)
        self._trip_steps_total = np.int64(0)
        self._trip_count = np.int64(0)
        self._search_steps_total = np.int64(0)
        self._search_count = np.int64(0)
        self.nest_steps = np.int64(0)

    def step(self) -> None:
        if self.t == self.cfg.hazard_move_step:
            self._move_hazard()
        sw = self.swarm
        n = len(sw.pos)
        # Detection noise draws: a fixed number per step, whatever the robots are doing.
        draws = self.noise_rng.random((n, n))
        if self.cfg.miss_run > 0:
            self._blind = next_blind(self._blind, draws, self.cfg.q_miss, self.cfg.miss_run)
            self._detected = ~self._blind  # [i, j]: robot i detects wreck j
        else:
            self._detected = draws >= self.cfg.q_miss  # [i, j]: robot i detects wreck j
        false_draw = self.noise_rng.random(n)
        alive = sw.alive.copy()
        searching = alive & (sw.state == SEARCH)
        returning = alive & (sw.state == RETURN)

        # Observation: count live-robot-steps within 1.5 m of the nest (before movement)
        dist_to_nest = norm(sw.pos - self.nest)
        self.nest_steps += int((alive & (dist_to_nest < 1.5)).sum())

        self._choose_headings(searching, returning)
        self._move(alive)
        self._pick_up(searching)
        self._deliver(returning)
        self._fail(alive)
        if self.cfg.controller in MARKING:
            self._mark()
        elif self.cfg.controller in PERSONAL:
            self._mark_personal()
        elif self.cfg.controller in RECORDS:
            self._mark_records()
        self._false_sightings(false_draw)
        if self.cfg.controller in MARKING:
            self.field.decay(self.cfg.decay)
        elif self.cfg.controller in PERSONAL:
            self.maps *= 1.0 - self.cfg.decay
        self.t += 1
        if self.cfg.controller in PERSONAL and self.t % self.cfg.share_every == 0:
            self._share()
        if self.cfg.controller in RECORDS and self.t % self.cfg.share_every == 0:
            self.records.share(self.swarm.alive, self.swarm.pos, self.cfg.comm_range)
        if self.cfg.controller in MAPPED and self.t % self.cfg.metric_every == 0:
            self.auc_series.append(field_auc(self._map_for_metrics(), self.hazard_mask))

    def _move_hazard(self) -> None:
        """E8: the hazard moves; wrecks and marks stay where they are."""
        mapped = self.cfg.controller in MAPPED
        self._pre = {
            "delivered_pre": self.delivered,
            "lost_pre": int((~self.swarm.alive).sum()),
            "auc_pre": field_auc(self._map_for_metrics(), self.hazard_mask) if mapped else float("nan"),
        }
        self._old_mask = self.hazard_mask
        set_hazards(self.world, self.cfg.hazards_after)
        self.hazard_mask = hazard_mask(self.world, self.field)

    def _map_for_metrics(self) -> np.ndarray:
        if self.records is not None:
            return self.records.mean_map(self.swarm.alive, self.t, self.cfg.decay)
        if self.maps is None:
            return self.field.grid
        live = self.swarm.alive
        return self.maps[live].mean(axis=0) if live.any() else self.maps.mean(axis=0)

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
        # OUTBOUND: head straight toward last_pickup; switch to SEARCH when close enough
        outbound = sw.alive & (sw.state == OUTBOUND)
        if outbound.any():
            idx = np.flatnonzero(outbound)
            v_ob = sw.last_pickup[idx] - sw.pos[idx]
            dist_ob = norm(v_ob)
            arrived = dist_ob < cfg.sense_range
            sw.state[idx[arrived]] = SEARCH
            still_out = ~arrived
            if still_out.any():
                i_out = idx[still_out]
                sw.heading[i_out] = np.arctan2(v_ob[still_out, 1], v_ob[still_out, 0])

        dead = np.flatnonzero(~sw.alive)
        steer = unit(sw.heading) + avoidance(cfg, sw.pos, sw.pos[dead], self.field, self.world,
                                             detected=self._detected[:, dead], maps=self.maps,
                                             records=self.records, t=self.t)
        sw.heading[:] = np.where(sw.alive, np.arctan2(steer[:, 1], steer[:, 0]), sw.heading)

    def _move(self, alive: np.ndarray) -> None:
        cfg, sw, world = self.cfg, self.swarm, self.world
        kick = self.motion_rng.normal(0.0, 0.5, len(sw.pos))  # one draw per robot, always
        step = cfg.speed * cfg.dt
        new = sw.pos + step * unit(sw.heading)
        hit_wall = ((new < 0) | (new > cfg.arena_size)).any(axis=1)
        new = np.clip(new, 0.0, cfg.arena_size)
        blocked = blocks_move(cfg, world, new, sw.pos)
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
                # Observation: record search-leg steps and pickup position
                self._search_steps_total += self.t - self._last_event_step[i]
                self._search_count += 1
                self._pickup_step[i] = self.t
                sw.last_pickup[i] = sw.pos[i].copy()
                respawn_item(self.world, j, self.respawn_rng)
                changed = True

    def _deliver(self, returning: np.ndarray) -> None:
        sw = self.swarm
        at_nest = returning & (norm(sw.pos - self.nest) < self.cfg.nest_radius)
        fresh = self.motion_rng.uniform(-np.pi, np.pi, len(sw.pos))  # one draw per robot, always
        if at_nest.any():
            # Observation: record trip-leg steps
            for i in np.flatnonzero(at_nest):
                if self._pickup_step[i] >= 0:
                    self._trip_steps_total += self.t - self._pickup_step[i]
                    self._trip_count += 1
                self._last_event_step[i] = self.t
            if self.cfg.search_start == "last_pickup":
                # Robots with a recorded last_pickup go OUTBOUND; others go SEARCH.
                has_pickup = at_nest & ~np.isnan(sw.last_pickup[:, 0])
                sw.state[has_pickup] = OUTBOUND
                no_pickup = at_nest & np.isnan(sw.last_pickup[:, 0])
                sw.state[no_pickup] = SEARCH
                sw.heading[no_pickup] = fresh[no_pickup]
                # Fresh heading is drawn but not used for OUTBOUND robots (stream preserved).
            else:
                sw.state[at_nest] = SEARCH
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
            if 0 <= self.cfg.hazard_move_step <= self.t and self.first_loss_post_step < 0:
                self.first_loss_post_step = self.t

    def _new_sightings(self):
        """(dead indices, visible[N, D], new[N, D]) for this step's wreck detections."""
        cfg, sw = self.cfg, self.swarm
        dead = np.flatnonzero(~sw.alive)
        dist = norm(sw.pos[:, None, :] - sw.pos[None, dead, :])  # (N, D)
        visible = sw.alive[:, None] & (dist < cfg.sense_range) & self._detected[:, dead]
        return dead, visible, visible & ~self.seen[:, dead]

    def _mark(self) -> None:
        cfg, sw = self.cfg, self.swarm
        if sw.alive.all():
            return
        dead, visible, new = self._new_sightings()
        for col in np.flatnonzero(new.any(axis=0)):
            amount = cfg.deposit_amount * new[:, col].sum()
            self.field.deposit(sw.pos[dead[col]], amount, cfg.deposit_sigma)
        self.seen[:, dead] |= visible

    def _mark_personal(self) -> None:
        cfg, sw = self.cfg, self.swarm
        if sw.alive.all():
            return
        dead, visible, new = self._new_sightings()
        for i, col in zip(*np.nonzero(new)):
            b = self.field.bump(sw.pos[dead[col]], cfg.deposit_amount, cfg.deposit_sigma)
            if b is not None:
                sx, sy, values = b
                self.maps[i, sx, sy] += values
        self.seen[:, dead] |= visible

    def _mark_records(self) -> None:
        sw = self.swarm
        if sw.alive.all():
            return
        dead, visible, new = self._new_sightings()
        for i, col in zip(*np.nonzero(new)):
            j = int(dead[col])
            self.records.add(("wreck", j), sw.pos[j], int(i), self.t)
        self.seen[:, dead] |= visible

    def _share(self) -> None:
        """Synchronous one-hop exchange: each live robot keeps the cell-wise max of its map
        and the maps its live neighbours held before this exchange."""
        sw = self.swarm
        live = np.flatnonzero(sw.alive)
        if len(live) < 2:
            return
        close = np.triu(norm(sw.pos[live][:, None, :] - sw.pos[live][None, :, :]) < self.cfg.comm_range, k=1)
        pairs = np.argwhere(close)
        if len(pairs) == 0:
            return
        old = self.maps.copy()
        for a, b in live[pairs]:
            np.maximum(self.maps[a], old[b], out=self.maps[a])
            np.maximum(self.maps[b], old[a], out=self.maps[b])

    def _false_sightings(self, false_draw: np.ndarray) -> None:
        """Robots that 'see' a non-existent wreck where they stand (E7 noise)."""
        cfg, sw = self.cfg, self.swarm
        phantom = sw.alive & (false_draw < cfg.q_false)
        self.false_sightings += int(phantom.sum())
        if cfg.controller in MARKING:
            for i in np.flatnonzero(phantom):
                self.field.deposit(sw.pos[i], cfg.deposit_amount, cfg.deposit_sigma)
        elif cfg.controller in PERSONAL:
            for i in np.flatnonzero(phantom):
                b = self.field.bump(sw.pos[i], cfg.deposit_amount, cfg.deposit_sigma)
                if b is not None:
                    sx, sy, values = b
                    self.maps[i, sx, sy] += values
        elif cfg.controller in RECORDS:
            for i in np.flatnonzero(phantom):
                self.records.add(("phantom", self.t, int(i)), sw.pos[i].copy(), int(i), self.t)

    def result(self) -> dict:
        out = {
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
            # Week-6 observation metrics (do not affect behaviour or random streams)
            "trip_steps_mean": (float(self._trip_steps_total) / float(self._trip_count)
                                if self._trip_count > 0 else float("nan")),
            "search_steps_mean": (float(self._search_steps_total) / float(self._search_count)
                                  if self._search_count > 0 else float("nan")),
            "nest_steps": int(self.nest_steps),
        }
        if self.records is not None:
            out["known_frac"] = self.records.known_frac(self.swarm.alive)
        if self.cfg.hazard_move_step >= 0:
            pre = self._pre or {"delivered_pre": self.delivered, "lost_pre": out["robots_lost"],
                                "auc_pre": float("nan")}
            moved = self._old_mask is not None and self.cfg.controller in MAPPED
            out.update(pre)
            out["delivered_post"] = self.delivered - pre["delivered_pre"]
            out["lost_post"] = out["robots_lost"] - pre["lost_pre"]
            out["first_loss_post_step"] = self.first_loss_post_step
            out["auc_old_final"] = (field_auc(self._map_for_metrics(), self._old_mask)
                                    if moved else float("nan"))
        return out


def run(cfg: Config, rng: np.random.Generator) -> dict:
    sim = Simulation(cfg, rng)
    for _ in range(cfg.n_steps):
        sim.step()
    return sim.result()
