"""Making way for an ambulance BEFORE it is close enough for SUMO's bluelight device to act.

SUMO's bluelight device (docs: Simulation/Emergency) makes every vehicle within its reaction distance (25 m) form a
rescue lane; that is the no-alert world, and it stays switched on in every arm. The device has no per-vehicle switch,
so it cannot say "this vehicle was told earlier". This module is OUR code for exactly that: a vehicle that received
the alert is given, through TraCI, the same three settings the device gives a reacting vehicle (read from
MSDevice_Bluelight.cpp at SUMO v1_27_1):

    lane-change mode 1605            (no lane changes into the rescue lane)
    lateral alignment "left" on the edge's highest-index lane, "right" on every other lane
    lcStrategic -1                   (no strategic lane changes)

and gets its own settings back once the ambulance has passed. Nothing else is changed: no speed, no route.

Version 2 (configs/ambulance.yaml, alert.makeway; RQ2c): lcStrategic is left alone (keep_strategic), so a vehicle that moved aside
can still make the lane change its route needs, and only vehicles within distance_m ahead move aside (service.AmbulanceRun). Version 1,
the rule above unchanged, held a vehicle at a lane end until the ambulance passed it while the ambulance waited behind it.
"""
from __future__ import annotations

RESCUE_LANE_CHANGE_MODE = 1605


def side(lane_index: int, lanes: int) -> str:
    """The side the bluelight device moves a vehicle to: the highest-index lane goes left, every other lane right."""
    return "left" if lane_index == lanes - 1 else "right"


class MakeWay:
    def __init__(self, conn, keep_strategic: bool = False):
        self.conn, self.keep_strategic = conn, keep_strategic           # keep_strategic: RQ2b diagnostic variant; False = the device's settings, unchanged
        self.before: dict[str, tuple[int, str, str]] = {}          # vehicle -> (lane-change mode, alignment, lcStrategic) before the alert

    def alert(self, vid: str) -> bool:
        if vid in self.before:
            return False
        v = self.conn.vehicle
        self.before[vid] = (v.getLaneChangeMode(vid), v.getLateralAlignment(vid), v.getParameter(vid, "laneChangeModel.lcStrategic"))
        v.setLaneChangeMode(vid, RESCUE_LANE_CHANGE_MODE)
        v.setLateralAlignment(vid, side(v.getLaneIndex(vid), self.conn.edge.getLaneNumber(v.getRoadID(vid))) if not v.getRoadID(vid).startswith(":") else "right")
        if not self.keep_strategic:
            v.setParameter(vid, "laneChangeModel.lcStrategic", "-1")
        return True

    def keep_side(self, vid: str) -> None:
        """A vehicle that moved to another lane or road keeps the side the rule gives for where it is now."""
        v = self.conn.vehicle
        road = v.getRoadID(vid)
        if not road.startswith(":"):
            v.setLateralAlignment(vid, side(v.getLaneIndex(vid), self.conn.edge.getLaneNumber(road)))

    def release(self, vid: str, present: bool) -> None:
        mode, align, strategic = self.before.pop(vid)
        if present:
            v = self.conn.vehicle
            v.setLaneChangeMode(vid, mode)
            v.setLateralAlignment(vid, align)
            if strategic != "":
                v.setParameter(vid, "laneChangeModel.lcStrategic", strategic)
