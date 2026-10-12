"""Detectors for the live twin, generated from the city's own network (any city with a `live_twin` config entry).

One SUMO E1 induction loop in the middle of every lane of each road whose OpenStreetMap type is listed in the config and which is at
least `detector_min_edge_m` long. Each loop aggregates over one simulated minute (period 60 s); a road's speed for a minute is the
mean of its loops' mean speeds, over the loops that saw a vehicle. A minute in which no vehicle passed has no value (None): it is
not filled in.
"""
from __future__ import annotations

import hashlib
import statistics
from pathlib import Path

PERIOD_S = 60


def roads(net, road_types: list[str], min_len_m: float) -> list:
    """The edges that get detectors: normal edges (not internal), open to cars, of a listed OSM type, long enough."""
    wanted = {f"highway.{t}" for t in road_types}
    return sorted((e for e in net.getEdges() if e.getFunction() == "" and e.getType() in wanted and e.getLength() >= min_len_m
                   and e.allows("passenger")), key=lambda e: e.getID())


def write_additional(path: Path, edges: list) -> tuple[dict[str, list[str]], str]:
    """Write the loops; returns {road id: [loop ids]} and the file's sha256."""
    by_road: dict[str, list[str]] = {}
    lines = ["<additional>"]
    for e in edges:
        for lane in e.getLanes():
            lid = f"e1_{lane.getID()}"
            lines.append(f'  <inductionLoop id="{lid}" lane="{lane.getID()}" pos="{lane.getLength() / 2:.2f}" period="{PERIOD_S}" file="NUL"/>')
            by_road.setdefault(e.getID(), []).append(lid)
    lines.append("</additional>")
    text = "\n".join(lines) + "\n"
    path.write_text(text)
    return by_road, hashlib.sha256(text.encode()).hexdigest()


def read_minute(conn, by_road: dict[str, list[str]]) -> dict[str, float | None]:
    """Each road's mean speed (km/h) over the last completed minute; None when no vehicle passed any of its loops."""
    out = {}
    for road, loops in by_road.items():
        v = [s for s in (conn.inductionloop.getLastIntervalMeanSpeed(lid) for lid in loops) if s >= 0]
        out[road] = round(statistics.fmean(v) * 3.6, 2) if v else None
    return out
