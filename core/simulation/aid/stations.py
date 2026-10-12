"""Detector stations for automatic incident detection (AID, step J, 2026-10-11): E1 induction loops every `spacing` metres along the
corridor's ambulance route, one loop per lane, aggregated every 30 s. A "pair" is two consecutive stations; the road between them is the
segment an incident is detected on. Works for any city whose corridor route is known (core/simulation/ambulance/service.scenario)."""
from __future__ import annotations

import hashlib
import statistics
from pathlib import Path

PERIOD_S = 30
SPACING_M = 300.0


def stations(net, edges: list[str], spacing: float = SPACING_M) -> list[dict]:
    """Walk the route; at every `spacing` metres of chainage put a station on the edge that holds that point (never inside the first or
    last 5 m of a lane). Returns [{id, edge, pos, chainage, lanes, segment_edges}], segment_edges being the route edges from this
    station to the next (the road an incident between them lies on)."""
    out, cum = [], 0.0
    k = 1
    spans = []
    for eid in edges:
        e = net.getEdge(eid)
        if e.getFunction() != "" or e.getLength() <= 0:
            continue
        spans.append((eid, cum, cum + e.getLength()))
        cum += e.getLength()
    for eid, a, b in spans:
        while k * spacing < b:
            ch = k * spacing
            if ch >= a:
                e = net.getEdge(eid)
                pos = min(max(ch - a, 5.0), e.getLength() - 5.0)
                out.append({"id": f"s{k}", "edge": eid, "pos": round(pos, 1), "chainage": ch, "lanes": [lane.getID() for lane in e.getLanes()]})
            k += 1
    for i, st in enumerate(out):
        nxt = out[i + 1]["chainage"] if i + 1 < len(out) else cum
        st["segment_edges"] = [eid for eid, a, b in spans if b > st["chainage"] and a < nxt]
    return out


def write_additional(path: Path, sts: list[dict], period: int = PERIOD_S) -> tuple[dict[str, list[str]], str]:
    lines, loops = ["<additional>"], {}
    for st in sts:
        loops[st["id"]] = []
        for i, lane in enumerate(st["lanes"]):
            lid = f"{st['id']}_{i}"
            lines.append(f'  <inductionLoop id="{lid}" lane="{lane}" pos="{st["pos"]}" period="{period}" file="NUL"/>')
            loops[st["id"]].append(lid)
    lines.append("</additional>")
    text = "\n".join(lines) + "\n"
    path.write_text(text)
    return loops, hashlib.sha256(text.encode()).hexdigest()


def read_interval(conn, loops: dict[str, list[str]]) -> dict[str, dict]:
    """Each station over the last completed interval: mean speed (km/h, over lanes that saw a vehicle), mean occupancy (%), flow (vehicles)."""
    out = {}
    for sid, lids in loops.items():
        sp = [s for s in (conn.inductionloop.getLastIntervalMeanSpeed(l) for l in lids) if s >= 0]
        occ = [conn.inductionloop.getLastIntervalOccupancy(l) for l in lids]
        flow = sum(conn.inductionloop.getLastIntervalVehicleNumber(l) for l in lids)
        out[sid] = {"speed": round(statistics.fmean(sp) * 3.6, 2) if sp else None, "occ": round(statistics.fmean(occ), 3), "flow": int(flow)}
    return out


def pair_features(up: dict, down: dict, down_prev: dict | None, down_prev2: dict | None, limit_kmh: float) -> dict:
    """The row for one pair and one 30 s window: raw readings of both stations, the California-style differences, and the downstream
    occupancy's temporal change. A missing speed (no vehicle passed) is encoded as the speed limit with a flag, never as 0."""
    us = up["speed"] if up["speed"] is not None else limit_kmh
    ds = down["speed"] if down["speed"] is not None else limit_kmh
    occdf = up["occ"] - down["occ"]
    occrdf = occdf / up["occ"] if up["occ"] > 0 else 0.0
    d2 = down_prev2["occ"] if down_prev2 else down["occ"]
    docctd = (d2 - down["occ"]) / d2 if d2 > 0 else 0.0
    return {"up_speed": us, "up_occ": up["occ"], "up_flow": up["flow"], "down_speed": ds, "down_occ": down["occ"], "down_flow": down["flow"],
            "up_empty": int(up["speed"] is None), "down_empty": int(down["speed"] is None),
            "occdf": round(occdf, 3), "occrdf": round(occrdf, 4), "docctd": round(docctd, 4), "speed_diff": round(us - ds, 2),
            "flow_diff": up["flow"] - down["flow"], "down_occ_prev": down_prev["occ"] if down_prev else down["occ"]}


FEATURES = ["up_speed", "up_occ", "up_flow", "down_speed", "down_occ", "down_flow", "up_empty", "down_empty", "occdf", "occrdf", "docctd", "speed_diff", "flow_diff", "down_occ_prev"]
