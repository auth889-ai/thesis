"""17-agent SUMO signal env in the official MAPPO (on-policy) MPE contract.

One agent per traffic light on the frozen R1 network. Matches the interface
consumed by onpolicy's runners/vec-wrappers (lists per agent; shared obs =
concatenation), so the OFFICIAL trainer runs unmodified — this file is the
adapter, per policy.

Design (declared):
  * Action  : Discrete(2) — 0 = hold/extend current green, 1 = switch.
              The env ENFORCES min-green (safety floor): a switch request
              before min_green becomes a hold. Yellow handled by SUMO phases.
  * Obs     : [phase_onehot(8) | halting counts of up to 8 incoming lanes /10
               | elapsed_green/60 | FORECAST_SLOT] — the forecast slot is 0 in
              baseline arms; FA arms fill it via forecast_fn (GWNet-in-loop).
  * Reward  : shared/global = −(total halting vehicles)/100 each decision —
              the coordination objective (per-junction greed is what made
              Max-Pressure 13% worse than fixed-time here).
  * Episode : warmup 300 s then decisions every 5 s until end_s (default
              3600 s) over the FIXED fair demand (E4 v200 converged routes).
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
from gymnasium import spaces

REPO = Path(__file__).resolve().parents[2]
NET = str(REPO / "paper_labs/02_dhaka_osm/outputs/lab02_v2/network/dhaka_r1.net.xml")
DEFAULT_ROUTES = "/tmp/due_routes.rou.xml.gz"

MAX_PHASES = 8
MAX_LANES = 8
MIN_GREEN = 10.0
MAX_GREEN = 60.0
DECISION_S = 5.0


class SumoSignalMultiEnv:
    def __init__(self, routes: str = DEFAULT_ROUTES, end_s: int = 3600,
                 warmup_s: int = 300, seed: int = 1, gui: bool = False,
                 forecast_fn=None, use_pressure: bool = False,
                 label: str = "env"):
        self.use_pressure = use_pressure
        self.routes, self.end_s, self.warmup_s = routes, end_s, warmup_s
        self._seed0, self._episode = seed, -1   # first reset -> seed0 exactly
        self._gui = gui
        self.forecast_fn = forecast_fn            # (traci, tls_ids) -> np.array[n]
        self.label = label
        self._traci = None
        self._boot_probe()

        obs_dim = MAX_PHASES + MAX_LANES + 1 + 1 + 1   # +pressure slot
        self.n = len(self._tls_ids)
        self.observation_space = [
            spaces.Box(-np.inf, np.inf, (obs_dim,), np.float32)] * self.n
        self.share_observation_space = [
            spaces.Box(-np.inf, np.inf, (obs_dim * self.n,), np.float32)] * self.n
        self.action_space = [spaces.Discrete(2)] * self.n

    # ------------------------------------------------------------------ sumo
    def _start(self, seed: int):
        import traci
        from sumolib import checkBinary
        binary = checkBinary("sumo-gui" if self._gui else "sumo")
        label = f"{self.label}_{os.getpid()}_{self._episode}"
        traci.start([binary, "-n", NET, "-r", self.routes,
                     "--seed", str(seed), "--end", str(self.end_s + 10),
                     "--no-warnings", "--no-step-log",
                     "--time-to-teleport", "300"], label=label)
        self._traci = traci.getConnection(label)

    def _boot_probe(self):
        """One throwaway boot to learn TLS ids and incoming lanes."""
        self._start(self._seed0)
        t = self._traci
        self._tls_ids = sorted(t.trafficlight.getIDList())
        self._lanes, self._out_lanes = {}, {}
        for tls in self._tls_ids:
            lanes, outs = [], []
            for link in t.trafficlight.getControlledLinks(tls):
                if link:
                    if link[0][0] not in lanes:
                        lanes.append(link[0][0])
                    if link[0][1] not in outs:
                        outs.append(link[0][1])
            self._lanes[tls] = lanes[:MAX_LANES]
            self._out_lanes[tls] = outs[:MAX_LANES]
        t.close()
        self._traci = None

    # ------------------------------------------------------------------- api
    def reset(self):
        if self._traci is not None:
            try:
                self._traci.close()
            except Exception:                      # noqa: BLE001
                pass
        self._episode += 1
        self._start(self._seed0 + self._episode)
        t = self._traci
        while t.simulation.getTime() < self.warmup_s:
            t.simulationStep()
        self._green_start = {tls: self.warmup_s for tls in self._tls_ids}
        return self._obs()

    def step(self, actions):
        t = self._traci
        now = t.simulation.getTime()
        for tls, a in zip(self._tls_ids, np.asarray(actions).reshape(-1)):
            elapsed = now - self._green_start[tls]
            if int(a) == 1 and elapsed >= MIN_GREEN:
                t.trafficlight.setPhaseDuration(tls, 0.0)   # advance phase
                self._green_start[tls] = now
            elif int(a) == 0 and elapsed < MAX_GREEN:
                # REAL hold: keep the current phase through this decision
                # interval (audit fix: the program must not auto-advance
                # underneath a "hold" action); max-green still enforced
                if t.trafficlight.getNextSwitch(tls) - now < DECISION_S:
                    t.trafficlight.setPhaseDuration(tls, DECISION_S)
        target = now + DECISION_S
        while t.simulation.getTime() < target and \
                t.simulation.getMinExpectedNumber() > 0:
            t.simulationStep()

        obs = self._obs()
        halting = sum(t.lane.getLastStepHaltingNumber(l)
                      for lanes in self._lanes.values() for l in lanes)
        reward = -halting / 100.0
        done = (t.simulation.getTime() >= self.end_s
                or t.simulation.getMinExpectedNumber() == 0)
        rewards = [[reward]] * self.n
        dones = [done] * self.n
        infos = [{"halting_total": halting} for _ in range(self.n)]
        return obs, rewards, dones, infos

    def _obs(self):
        t = self._traci
        now = t.simulation.getTime()
        fc = np.zeros(self.n, dtype=np.float32)
        if self.forecast_fn is not None:
            fc = np.asarray(self.forecast_fn(t, self._tls_ids),
                            dtype=np.float32)
        out = []
        for i, tls in enumerate(self._tls_ids):
            phase = t.trafficlight.getPhase(tls)
            ph = np.zeros(MAX_PHASES, dtype=np.float32)
            ph[min(phase, MAX_PHASES - 1)] = 1.0
            q = np.zeros(MAX_LANES, dtype=np.float32)
            for j, lane in enumerate(self._lanes[tls]):
                q[j] = t.lane.getLastStepHaltingNumber(lane) / 10.0
            elapsed = np.float32((now - self._green_start[tls]) / 60.0)
            pressure = np.float32(0.0)
            if self.use_pressure:
                inn = sum(t.lane.getLastStepHaltingNumber(l)
                          for l in self._lanes[tls])
                outn = sum(t.lane.getLastStepHaltingNumber(l)
                           for l in self._out_lanes[tls])
                pressure = np.float32((inn - outn) / 10.0)
            out.append(np.concatenate([ph, q, [elapsed], [fc[i]], [pressure]]))
        return out

    def close(self):
        if self._traci is not None:
            self._traci.close()
            self._traci = None

    def seed(self, s):
        self._seed0 = int(s)
