"""Continuous mode: the calibrated hour of demand replayed every hour, and the live corridor state
from the provider applied to the corridor edges at the provider's own cadence."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from core.simulation.twin.live.settings import DEMAND_PERIOD_S


class ContinuousDemand:
    def __init__(self, conn, cfg: dict, routes: Path, cmap: dict, note) -> None:
        from core.simulation.closed_loop.protocols.chains import live_chain as lc
        self.conn, self.cfg, self.cmap, self.note = conn, cfg, cmap, note
        # SUMO loads (and scales) hour 0 itself; later hours are re-inserted through TraCI with the
        # same deterministic per-vehicle selection at the same scale
        self.replay = sorted(((vid, float(dep), edges) for vid, dep, edges in lc.read_routes(routes)
                              if (int(hashlib.md5(vid.encode()).hexdigest()[:8], 16) % 10_000) < cfg["scale"] * 10_000), key=lambda r: r[1])
        self.route_ids: dict[str, str | None] = {}
        self.next_hour, self.replay_i = 1, 0
        self.base_speed: dict[str, float] = {}
        self.live_applied_utc: str | None = None
        self.live_mult: dict[str, float] = {}
        self._capture_base_speeds()

    def _capture_base_speeds(self) -> None:
        """Remember every corridor lane's free speed, then lift the as-of slowdowns: from here the live road rules."""
        import traci
        for eid in {e for edges in self.cmap.values() for e in (edges.get("edges") or [])}:
            try:
                for i in range(self.conn.edge.getLaneNumber(eid)):
                    self.base_speed[f"{eid}_{i}"] = self.conn.lane.getMaxSpeed(f"{eid}_{i}")
            except traci.TraCIException:
                pass
        for lid, v0 in self.base_speed.items():
            self.conn.lane.setMaxSpeed(lid, v0)

    def apply_live(self) -> None:
        """Corridor speeds from the live provider, on the corridor edges, right now."""
        import traci
        from core.common.data.live_providers.google_routes import service
        snap = service.corridors()
        mult = {}
        for c in snap.get("corridors", []):
            d, st = c.get("duration_s"), c.get("static_duration_s")
            if c.get("is_live") and d and st and st > 0:
                mult[c["id"]] = max(1.0, float(d) / float(st))
        if not mult:
            return
        edge_m: dict[str, float] = {}
        for cid, m in mult.items():
            for eid in (self.cmap.get(cid) or {}).get("edges") or []:
                edge_m[eid] = max(edge_m.get(eid, 1.0), m)
        for lid, v0 in self.base_speed.items():
            m = edge_m.get(lid.rsplit("_", 1)[0], 1.0)
            try:
                self.conn.lane.setMaxSpeed(lid, max(v0 / m, 0.5))
            except traci.TraCIException:
                pass
        self.live_mult = {k: round(v, 3) for k, v in mult.items()}
        self.live_applied_utc = datetime.now(timezone.utc).isoformat()
        self.note(f"live state applied: {self.live_mult}")

    def insert_due(self, t: int) -> None:
        """Insert every selected vehicle whose (shifted) departure has come, cycling the hour's list."""
        import traci
        if not self.replay:
            return
        while True:
            vid, dep, edges = self.replay[self.replay_i]
            if dep + self.next_hour * DEMAND_PERIOD_S > t:
                break
            rid = self.route_ids.get(edges)
            if rid is None:
                rid = f"r{len(self.route_ids)}"
                try:
                    self.conn.route.add(rid, edges.split()); self.route_ids[edges] = rid
                except traci.TraCIException:
                    self.route_ids[edges] = rid = None
            if rid:
                try:
                    self.conn.vehicle.add(f"{vid}_h{self.next_hour}", rid)
                except traci.TraCIException:
                    pass
            self.replay_i += 1
            if self.replay_i >= len(self.replay):
                self.replay_i, self.next_hour = 0, self.next_hour + 1

    def hour(self, t: int) -> int:
        return t // DEMAND_PERIOD_S + 1
