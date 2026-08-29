"""Physical traffic-state estimation from tracked vehicles (Gate 1).

Absolute evidence only — a vehicle is STOPPED when its own displacement over a
time window is small relative to its own size. No rolling-percentile speed
reference, so a video that BEGINS with a standing queue is still measured as
queued (the failure mode of relative logic).

Outputs per approach zone and per 5-s window every field Gate 1 requires, with
quality flags for anything the camera registration cannot support (physical
speed without homography, turning movements without exit zones).
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

# Declared constants. Queue definition follows the standard "speed below
# ~5-10 km/h" criterion, expressed calibration-free in units of the vehicle's
# OWN size: a car creeping less than half its own diagonal per second is in
# stop-and-go queue; free-flow traffic moves several own-lengths per second
# (measured on real footage: queued creep ~0.1-0.4 diag/s, ramp free flow >1).
QUEUE_SPEED_DIAG_S = 0.5   # queued if median speed < 0.5 own-diagonals/s
STOP_SPEED_DIAG_S = 0.12   # hard-stopped below this
SPEED_WINDOW_S = 4.0       # median window
QUEUE_MIN_STOP_S = 4.0  # a vehicle counts toward the queue after this long
CONG_MIN_QUEUE = 5      # >=5 concurrently-queued vehicles in an approach
WINDOW_S = 5.0
AVG_VEH_LEN_M = 5.5     # queue-length estimate only when homography present


def _in_poly(x, y, poly):
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def _side(p, a, b):
    return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])


class StateEstimator:
    def __init__(self, registration: dict | None, fps_effective: float):
        self.reg = registration or {}
        self.fps = fps_effective
        self.hom = self.reg.get("homography")
        self.zones = self.reg.get("approach_zones", {})
        self.arr_line = self.reg.get("arrival_line")
        self.dis_line = self.reg.get("discharge_line")
        self.hist = defaultdict(list)          # tid -> [(t,cx,cy,diag)]
        self.speed_hist = defaultdict(list)    # tid -> [(t, diag/s)]
        self.queued_since = {}                 # tid -> t when queueing began
        self.crossed = {"arrival": set(), "discharge": set()}
        self.moves = defaultdict(int)          # (zone,movement) -> count
        self.zone_of = {}                      # tid -> first approach zone
        self.windows = []
        self._win = None
        self.flags = set()
        if self.hom is None:
            self.flags.add("SPEED_PIXEL_ONLY_NO_HOMOGRAPHY")
            self.flags.add("QUEUE_METERS_UNAVAILABLE")
        if not self.zones:
            self.flags.add("ZONES_REQUIRED_FOR_APPROACH_METRICS")

    # ---- per sampled frame ------------------------------------------------
    def ingest(self, t: float, tracks, classes: dict[int, str]):
        """tracks: [(tid,(x1,y1,x2,y2),score)] · classes: tid->class name."""
        queued_now, speeds_px = {}, []
        for tid, (x1, y1, x2, y2), _s in tracks:
            cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
            diag = max(((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5, 1.0)
            self.hist[tid].append((t, cx, cy, diag))
            h = self.hist[tid]
            if len(h) >= 2:
                (ta, xa, ya, _), (tb, xb, yb, _) = h[-2], h[-1]
                if tb > ta:
                    v_px = (((xb - xa) ** 2 + (yb - ya) ** 2) ** 0.5) / (tb - ta)
                    speeds_px.append(v_px)
                    self.speed_hist[tid].append((t, v_px / diag))
            sw = [v for tt, v in self.speed_hist[tid]
                  if t - tt <= SPEED_WINDOW_S]
            if len(sw) >= 3:
                med = sorted(sw)[len(sw) // 2]
                if med < QUEUE_SPEED_DIAG_S:
                    self.queued_since.setdefault(tid, t - SPEED_WINDOW_S)
                    queued_now[tid] = t - self.queued_since[tid]
                else:
                    self.queued_since.pop(tid, None)
            # zone membership + movements + line crossings
            for zname, z in self.zones.items():
                if _in_poly(cx, cy, z["polygon"]):
                    self.zone_of.setdefault(tid, zname)
                for mv, spec in z.get("movements", {}).items():
                    if (self.zone_of.get(tid) == zname
                            and _in_poly(cx, cy, spec["exit_polygon"])
                            and (tid, mv) not in self.moves):
                        self.moves[(zname, mv)] += 1
            for key, line in (("arrival", self.arr_line),
                              ("discharge", self.dis_line)):
                if line and tid not in self.crossed[key] and len(h) >= 2:
                    pa, pb = h[-2][1:3], h[-1][1:3]
                    if _side(pa, *line) * _side(pb, *line) < 0:
                        self.crossed[key].add(tid)
        # ---- 5-s windows ---------------------------------------------------
        if self._win is None or t - self._win["t0"] >= WINDOW_S:
            if self._win is not None:
                self.windows.append(self._flush())
            self._win = {"t0": t, "frames": 0, "n": [], "stopped": [],
                         "stop_durs": [], "speeds": [], "occ": [],
                         "arr0": len(self.crossed["arrival"]),
                         "dis0": len(self.crossed["discharge"]),
                         "classes": defaultdict(int)}
        w = self._win
        w["frames"] += 1
        w["n"].append(len(tracks))
        in_zone = [tid for tid, _, _ in tracks
                   if not self.zones or self.zone_of.get(tid)]
        q = [tid for tid in in_zone
             if queued_now.get(tid, 0) >= QUEUE_MIN_STOP_S]
        w["stopped"].append(len(q))
        w["stop_durs"] += [queued_now[tid] for tid in q]
        w["speeds"] += speeds_px
        for tid, (x1, y1, x2, y2), _s in tracks:
            w["classes"][classes.get(tid, "vehicle")] += 1
        if self.zones:
            zarea = sum(abs(sum(p[0][0]*p[1][1]-p[1][0]*p[0][1]
                        for p in zip(z["polygon"],
                                     z["polygon"][1:]+z["polygon"][:1])))/2
                        for z in self.zones.values())
            barea = sum((b[2]-b[0])*(b[3]-b[1]) for _, b, _ in tracks)
            w["occ"].append(min(barea / zarea, 1.0) if zarea else 0.0)

    def _flush(self):
        w = self._win
        qv = max(w["stopped"]) if w["stopped"] else 0
        return {
            "t0": round(w["t0"], 1),
            "tracked_mean": round(sum(w["n"]) / max(len(w["n"]), 1), 1),
            "queue_veh": qv,
            "queue_m": (round(qv * AVG_VEH_LEN_M, 1) if self.hom else None),
            "stopped_duration_max_s":
                round(max(w["stop_durs"]), 1) if w["stop_durs"] else 0.0,
            "arrivals": len(self.crossed["arrival"]) - w["arr0"],
            "discharges": len(self.crossed["discharge"]) - w["dis0"],
            "occupancy": round(sum(w["occ"]) / len(w["occ"]), 3)
                if w["occ"] else None,
            "speed_px_s_median":
                round(sorted(w["speeds"])[len(w["speeds"]) // 2], 1)
                if w["speeds"] else None,
            "speed_m_s": None if not self.hom else "TODO_HOMOGRAPHY",
            "classes": dict(w["classes"]),
            "state": "CONGESTED" if qv >= CONG_MIN_QUEUE else
                     ("SLOWING" if qv > 0 else "FREE_FLOW"),
        }

    def finalize(self) -> dict:
        if self._win is not None:
            self.windows.append(self._flush())
        cong = [w for w in self.windows if w["state"] == "CONGESTED"]
        movements = {f"{z}:{m}": c for (z, m), c in self.moves.items()}
        if self.zones and not movements:
            self.flags.add("NO_MOVEMENTS_OBSERVED")
        return {
            "windows": self.windows,
            "congestion_detected": bool(cong),
            "first_congested_window_t0": cong[0]["t0"] if cong else None,
            "turning_movements": movements,
            "quality_flags": sorted(self.flags),
            "rule": (f"QUEUED = median speed < {QUEUE_SPEED_DIAG_S} own-"
                     f"diagonals/s over {SPEED_WINDOW_S}s (calibration-free "
                     f"~5-10 km/h criterion; no video-relative reference); "
                     f"CONGESTED = >={CONG_MIN_QUEUE} vehicles queued "
                     f">={QUEUE_MIN_STOP_S}s in the approach"),
        }


def load_registration(camera_id: str) -> dict | None:
    p = (Path(__file__).resolve().parents[2] / "configs" / "cameras"
         / "registry.json")
    if not p.exists():
        return None
    return json.loads(p.read_text()).get("cameras", {}).get(camera_id)
