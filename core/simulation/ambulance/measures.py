"""RQ2, why the alert helps or not, measured in the simulation (docs/PAPER_MAP.md, RQ2). Stepped once per simulated second next to
AmbulanceRun, through the same TraCI connection; it only reads, never moves a vehicle.

  free_width_m      on the ambulance's road, within LOOK_M ahead: the road's width minus the widest band taken by vehicles in any
                    SLICE_M slice (the narrowest gap the ambulance would have to pass), averaged over the seconds it drives
  yield_share       of the vehicles alerted, the share whose lateral position moved at least half the ambulance's width
  blocked_s         seconds the ambulance moved below BLOCKED_MS
  queue_at_signals  halting vehicles on a route signal's incoming road while the ambulance is within QUEUE_M of it; the mean over
                    signals of each signal's peak
  section_density   vehicles per km on the counted section (DhaTraX INT, edge 691209729#5) between DENSITY_FROM_S and the ambulance's
                    departure, for the "Dhaka recorded level" anchor
"""
from __future__ import annotations

import statistics

LOOK_M = 50.0
SLICE_M = 5.0
BLOCKED_MS = 2.0
QUEUE_M = 200.0
DENSITY_FROM_S = 300
INT_SECTION = "691209729#5"


def narrowest_gap(road_width: float, ahead: list[tuple[float, float]], look: float = LOOK_M, slice_m: float = SLICE_M) -> float:
    """`ahead`: (metres ahead of the ambulance, width taken) for each vehicle on its road within `look`. The road's width minus the
    most taken in any slice: the narrowest gap left. Pure; tested."""
    if not ahead:
        return road_width
    worst = 0.0
    k = 0.0
    while k < look:
        worst = max(worst, sum(w for d, w in ahead if k <= d < k + slice_m))
        k += slice_m
    return max(0.0, road_width - worst)


class RouteObserver:
    def __init__(self, conn, scen: dict, ambulance_id: str):
        self.conn, self.scen, self.amb = conn, scen, ambulance_id
        self.gaps: list[float] = []
        self.blocked_s = 0
        self.lat0: dict[str, float] = {}
        self.moved: dict[str, float] = {}
        self.queue_peak: dict[str, int] = {}
        self.density: list[float] = []
        self.amb_width: float | None = None
        self.section_len = None

    def step(self, t: float, driving: bool, alerted: set[str]) -> None:
        c = self.conn
        if t >= DENSITY_FROM_S and not driving and self.amb_width is None:
            self._density()
        if not driving or self.amb not in c.vehicle.getIDList():
            return
        v = c.vehicle
        if self.amb_width is None:
            self.amb_width = v.getWidth(self.amb)
        if v.getSpeed(self.amb) < BLOCKED_MS:
            self.blocked_s += 1
        road = v.getRoadID(self.amb)
        if not road.startswith(":"):
            pos = v.getLanePosition(self.amb)
            width = sum(c.lane.getWidth(f"{road}_{i}") for i in range(c.edge.getLaneNumber(road)))
            ahead = [(v.getLanePosition(o) - pos, v.getWidth(o)) for o in c.edge.getLastStepVehicleIDs(road)
                     if o != self.amb and 0 < v.getLanePosition(o) - pos <= LOOK_M]
            self.gaps.append(narrowest_gap(width, ahead))
        present = set(v.getIDList())
        for o in alerted & present:
            lat = v.getLateralLanePosition(o)
            self.lat0.setdefault(o, lat)
            self.moved[o] = max(self.moved.get(o, 0.0), abs(lat - self.lat0[o]))
        self._queues()

    def _density(self) -> None:
        c = self.conn
        try:
            if self.section_len is None:
                self.section_len = c.lane.getLength(f"{INT_SECTION}_0") / 1000
            self.density.append(c.edge.getLastStepVehicleNumber(INT_SECTION) / self.section_len)
        except Exception:                                      # noqa: BLE001 - the section is not in this network
            self.section_len = 0

    def _queues(self) -> None:
        v = self.conn.vehicle
        i = v.getRouteIndex(self.amb)
        on_edge = not v.getRoadID(self.amb).startswith(":")
        pos = v.getLanePosition(self.amb) if on_edge else self.scen["lengths"][i]
        for s in self.scen["signals"]:
            if s["route_index"] < i:
                continue
            dist = sum(self.scen["lengths"][i:s["route_index"] + 1]) - pos         # to the end of the signal's incoming road
            if dist <= QUEUE_M:
                q = self.conn.edge.getLastStepHaltingNumber(s["in_edge"])
                self.queue_peak[s["tls"]] = max(self.queue_peak.get(s["tls"], 0), q)

    def summary(self) -> dict:
        half = (self.amb_width or 2.0) / 2
        moved = list(self.moved.values())
        return {"free_width_m": round(statistics.fmean(self.gaps), 3) if self.gaps else None, "blocked_s": self.blocked_s,
                "yield_share": round(sum(m >= half for m in moved) / len(moved), 3) if moved else None, "alerted_seen": len(moved),
                "queue_at_signals": round(statistics.fmean(self.queue_peak.values()), 2) if self.queue_peak else 0.0, "queue_peaks": self.queue_peak,
                "section_density_veh_km": round(statistics.fmean(self.density), 2) if self.density else None,
                "definitions": {"look_m": LOOK_M, "slice_m": SLICE_M, "blocked_below_ms": BLOCKED_MS, "queue_within_m": QUEUE_M, "section": INT_SECTION}}
