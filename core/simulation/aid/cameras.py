"""J2 camera sensor for AID (2026-10-11): a camera on the approach edge of every signalised junction on the corridor, in the manner of
IncidentNet (Chintareddy et al., arXiv 2408.00996; github.com/MPSLab-ASU/IncidentNet, Apache-2.0, commit 7d73a229, read through the
GitHub API only). What their sensing records, and what we mirror:
    - per junction edge: mean speed, vehicle count, occupancy (traci.edge.getLastStep*), rolled over a window;
    - per vehicle: id, lane, speed at the junction;
    - between two sensors: the travel time of the vehicles seen at both (their process_raw_data.py merges the two sightings by id).
Ours, every 30 s per camera pair: vehicles seen at each camera, their mean speed, how many stood still, their mean waiting time,
and the mean travel time of the vehicles whose second sighting fell in the window (plus the previous window's mean). A camera "sees"
the vehicles on its edge at every step (TraCI); nothing is read off the incident plan. The corridor has 2 signalised junctions, so
there is one camera pair covering the stretch between them; its label is "an incident is active anywhere on the corridor"
(IncidentNet's own task: detection from sparse sensors), and a second label says whether it lies between the cameras.
"""
from __future__ import annotations

import statistics

STOPPED_MPS = 0.1


def cameras(scen: dict, net) -> list[dict]:
    """One camera per signalised junction on the route, on its approach edge, with the chainage of that edge's start."""
    out = []
    for s in scen["signals"]:
        i = scen["edges"].index(s["in_edge"])
        ch = sum(net.getEdge(e).getLength() for e in scen["edges"][:i])
        out.append({"id": f"cam{len(out)}", "tls": s["tls"], "edge": s["in_edge"], "chainage": round(ch, 1), "limit_kmh": round(net.getEdge(s["in_edge"]).getSpeed() * 3.6, 1)})
    return out


class Observer:
    """Per-step sightings at the cameras; `window()` reduces them to one row per camera pair and clears the window."""

    def __init__(self, cams: list[dict]):
        self.cams = cams
        self.first_seen: dict[tuple[str, str], float] = {}            # (camera, vehicle) -> first step seen
        self.win: dict[str, dict] = {c["id"]: {"veh": {}, "tt": []} for c in cams}
        self.prev_tt: dict[str, float | None] = {}

    def step(self, conn, t: float) -> None:
        for i, cam in enumerate(self.cams):
            w = self.win[cam["id"]]
            for v in conn.edge.getLastStepVehicleIDs(cam["edge"]):
                sp = conn.vehicle.getSpeed(v)
                rec = w["veh"].setdefault(v, {"speeds": [], "stopped": False, "wait": 0.0})
                rec["speeds"].append(sp)
                rec["stopped"] = rec["stopped"] or sp < STOPPED_MPS
                rec["wait"] = max(rec["wait"], conn.vehicle.getWaitingTime(v))
                if (cam["id"], v) not in self.first_seen:
                    self.first_seen[(cam["id"], v)] = t
                    if i > 0:
                        t0 = self.first_seen.get((self.cams[i - 1]["id"], v))
                        if t0 is not None:
                            w["tt"].append(t - t0)                    # second sighting: the travel time from the camera upstream

    def _cam(self, cam: dict) -> dict:
        w = self.win[cam["id"]]
        veh = w["veh"]
        sp = [statistics.fmean(r["speeds"]) * 3.6 for r in veh.values()]
        return {"seen": len(veh), "speed": round(statistics.fmean(sp), 2) if sp else None, "stopped": sum(r["stopped"] for r in veh.values()),
                "wait": round(statistics.fmean(r["wait"] for r in veh.values()), 1) if veh else 0.0, "tt": w["tt"]}

    def window(self) -> list[dict]:
        """One row per consecutive camera pair for the window just completed; then the window is cleared."""
        rows = []
        for i in range(len(self.cams) - 1):
            up, down = self.cams[i], self.cams[i + 1]
            a, b = self._cam(up), self._cam(down)
            tt = round(statistics.fmean(b["tt"]), 1) if b["tt"] else None
            prev = self.prev_tt.get(down["id"])
            us = a["speed"] if a["speed"] is not None else up["limit_kmh"]
            ds = b["speed"] if b["speed"] is not None else down["limit_kmh"]
            rows.append({"cam_pair": i, "cam_up": up["id"], "cam_down": down["id"],
                         "cam_up_seen": a["seen"], "cam_up_speed": us, "cam_up_stopped": a["stopped"], "cam_up_wait": a["wait"], "cam_up_empty": int(a["speed"] is None),
                         "cam_down_seen": b["seen"], "cam_down_speed": ds, "cam_down_stopped": b["stopped"], "cam_down_wait": b["wait"], "cam_down_empty": int(b["speed"] is None),
                         "cam_tt_mean": tt if tt is not None else (prev if prev is not None else 0.0), "cam_tt_n": len(b["tt"]), "cam_tt_missing": int(tt is None),
                         "cam_tt_prev": prev if prev is not None else 0.0, "cam_speed_diff": round(us - ds, 2), "cam_seen_diff": a["seen"] - b["seen"]})
            self.prev_tt[down["id"]] = tt if tt is not None else prev
        for w in self.win.values():
            w["veh"], w["tt"] = {}, []
        return rows


CAM_FEATURES = ["cam_up_seen", "cam_up_speed", "cam_up_stopped", "cam_up_wait", "cam_up_empty", "cam_down_seen", "cam_down_speed", "cam_down_stopped", "cam_down_wait",
                "cam_down_empty", "cam_tt_mean", "cam_tt_n", "cam_tt_missing", "cam_tt_prev", "cam_speed_diff", "cam_seen_diff"]


def covers(cams: list[dict], pair_chainage: tuple[float, float]) -> bool:
    """Whether a station pair's segment [a, b) overlaps the stretch between the first and the last camera."""
    if len(cams) < 2:
        return False
    lo, hi = cams[0]["chainage"], cams[-1]["chainage"]
    a, b = pair_chainage
    return a < hi and b > lo
