#!/usr/bin/env python3
"""FORECAST -> CONTINUOUS FUTURE EDGE TRAVEL TIME, with per-edge provenance.

    future_tt_s = edge_length_m / bounded_predicted_speed_mps

The forecast value for a corridor becomes a live/free-flow ratio (a congestion level is interpolated
between the documented band midpoints; a speed forecast is free_speed / predicted_speed), the ratio
becomes a predicted speed per edge (speed limit / ratio, bounded to [lower bound, speed limit]),
and the speed becomes a travel time. No class step is used as a cost: a level of 1.9 prices
differently from 2.0 and from 2.1.

Coverage is controlled and labelled. Edges a corridor covers are DIRECT. Edges within 1 or 2
connections of a covered edge are DERIVED: their ratio is decayed towards free flow by the
configured weight, and each carries its graph distance, decay weight and source corridor. Nothing
else is priced; unpriced edges keep their free-flow time in SUMO and are reported as such.

Every number comes from src/pipeline/routing/routing_config.json, which is copied into the output.
The output feeds `duarouter --weight-files` / `traci.edge.adaptTraveltime`; SUMO does the routing.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np

from traffictwin.paths import REPO

from pipeline.forecasting.live_to_edges import BAND_MID, multiplier as level_ratio  # noqa: E402

CONFIG_FILE = REPO / "src/pipeline/routing/routing_config.json"


def load_config(path: Path = CONFIG_FILE) -> dict:
    cfg = json.loads(path.read_text())
    cfg["_config_file"] = str(path.relative_to(REPO)) if path.is_relative_to(REPO) else str(path)
    cfg["_config_hash"] = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
    return cfg


def sha(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# forecast value -> live/free-flow ratio
# ---------------------------------------------------------------------------

def ratio_from_forecast(value: float, unit: str, free_speed_mps: float | None = None) -> float | None:
    """The travel-time ratio (>= 1) a forecast value implies. None when the value is unusable."""
    if value is None or not np.isfinite(value):
        return None
    if str(unit).startswith("congestion_level"):
        return float(level_ratio(float(np.clip(value, 0.0, 3.0))))
    # a speed forecast (m/s): ratio of free-flow speed to predicted speed
    if free_speed_mps is None or free_speed_mps <= 0 or value <= 0:
        return None
    return max(1.0, float(free_speed_mps) / float(value))


# ---------------------------------------------------------------------------
# the table
# ---------------------------------------------------------------------------

_NETS: dict = {}


def _read_net(net_path: Path):
    """sumolib network parsed once per (path, mtime) — parsing a large network on every call dominated the round time."""
    import sumolib
    key = (str(net_path), Path(net_path).stat().st_mtime)
    if key not in _NETS:
        _NETS.clear(); _NETS[key] = sumolib.net.readNet(str(net_path))
    return _NETS[key]


def build(forecast_values: dict[str, float], unit: str, corridor_map: dict[str, dict], net_path: Path,
          horizon_min: int, cfg: dict | None = None, hops: int | None = None, model: str | None = None,
          analysis_run_id: str | None = None, corridor_free_speed: dict[str, float] | None = None) -> dict:
    """forecast_values: corridor_id -> forecast value at this horizon (level or speed).
    corridor_map: corridor_id -> {"edges": [...]} (the project's corridor-to-edge mapping).
    Returns the priced table with one provenance row per edge."""
    import sumolib
    cfg = cfg or load_config()
    ec = cfg["edge_costs"]
    hops = int(ec["coverage_hops"] if hops is None else hops)
    v_min = float(ec["speed_lower_bound_mps"])
    decay = {int(k): float(v) for k, v in ec["decay_weight_by_hop"].items()}
    net = _read_net(net_path)

    def geo(eid):
        try:
            e = net.getEdge(eid)
        except KeyError:
            return None
        return e

    rows: dict[str, dict] = {}
    corridor_ratio: dict[str, float | None] = {}
    # ---- DIRECT: the edges each forecast corridor covers
    for cid, rec in corridor_map.items():
        v = forecast_values.get(cid)
        r = ratio_from_forecast(v, unit, (corridor_free_speed or {}).get(cid))
        corridor_ratio[cid] = r
        if r is None:
            continue
        for eid in rec.get("edges", []):
            e = geo(eid)
            if e is None:
                continue
            prev = rows.get(eid)
            if prev and prev["ratio"] >= r:          # two corridors share an edge: the worse one wins
                continue
            rows[eid] = _row(e, r, "DIRECT", 0, 1.0, cid, v, analysis_run_id, model, horizon_min, v_min)
    direct = set(rows)
    # ---- DERIVED: spatial propagation, h = 1..hops
    frontier = set(direct)
    for h in range(1, hops + 1):
        w = decay.get(h)
        if w is None:
            raise ValueError(f"routing_config.json has no decay weight for hop {h}")
        nxt: dict[str, tuple[float, str, float]] = {}
        for eid in frontier:
            e = geo(eid)
            src = rows[eid]
            for o in list(e.getOutgoing()) + list(e.getIncoming()):
                oid = o.getID()
                if oid in rows or not o.allows("passenger"):
                    continue
                r_direct = src["direct_ratio"]
                if oid not in nxt or nxt[oid][0] < r_direct:      # nearest wins (this hop), ties to the worse
                    nxt[oid] = (r_direct, src["corridor"], src["forecast_value"])
        for oid, (r_direct, cid, v) in nxt.items():
            r_h = 1.0 + w * (r_direct - 1.0)
            rows[oid] = _row(geo(oid), r_h, "DERIVED", h, w, cid, v, analysis_run_id, model, horizon_min, v_min, direct_ratio=r_direct)
        frontier = set(nxt)

    edge_tt = {eid: r["future_tt_s"] for eid, r in rows.items()}
    return {
        "analysis_run_id": analysis_run_id, "model": model, "horizon_min": horizon_min, "unit": unit,
        "coverage_hops": hops, "config": cfg,
        "corridor_ratio": {k: (round(v, 4) if v is not None else None) for k, v in corridor_ratio.items()},
        "corridors_unusable": [k for k, v in corridor_ratio.items() if v is None],
        "priced_edges": len(rows), "direct_edges": len(direct), "derived_edges": len(rows) - len(direct),
        "network_edges": len(net.getEdges()),
        "unpriced_policy": "edges outside the coverage keep their free-flow travel time in SUMO; they are not written to the weight file",
        "edge_travel_times": edge_tt,
        "edges": rows,
        "future_cost_hash": sha({k: round(v, 3) for k, v in edge_tt.items()}),
        "raw_forecast_hash": sha({k: (round(float(v), 4) if v is not None and np.isfinite(v) else None) for k, v in forecast_values.items()}),
    }


def _row(e, ratio, source, dist, weight, cid, v, run_id, model, horizon, v_min, direct_ratio=None):
    limit = float(e.getSpeed() or 13.9)
    pred = limit / max(ratio, 1.0)
    bounded = min(max(pred, v_min), limit)
    length = float(e.getLength())
    return {"edge": e.getID(), "length_m": round(length, 2), "speed_limit_mps": round(limit, 3),
            "analysis_run_id": run_id, "model": model, "horizon_min": horizon,
            "corridor": cid, "forecast_value": (round(float(v), 4) if v is not None else None),
            "ratio": round(ratio, 4), "direct_ratio": round(direct_ratio if direct_ratio is not None else ratio, 4),
            "predicted_speed_mps": round(pred, 3), "bounded_speed_mps": round(bounded, 3),
            "free_flow_tt_s": round(length / limit, 3), "future_tt_s": round(length / bounded, 3),
            "source": source, "graph_distance": dist, "decay_weight": weight}


def oracle_table(edgedata_xml: Path, net_path: Path, cfg: dict | None = None, begin: float | None = None,
                 end: float | None = None) -> dict:
    """The ceiling: MEASURED per-edge travel times from a SUMO run of the same seed and demand, in
    the same table shape the forecast produces. Intervals overlapping [begin, end) are aggregated
    per edge weighted by sampledSeconds (vehicle presence), so an edge's value is the mean travel
    time vehicles actually experienced there in that window. Every row is MEASURED_ORACLE; no
    forecast, no propagation; edges no vehicle used stay unpriced (free flow)."""
    import xml.etree.ElementTree as ET
    import sumolib
    cfg = cfg or load_config()
    net = sumolib.net.readNet(str(net_path))
    num, den, used = {}, {}, 0
    for iv in ET.parse(edgedata_xml).getroot().iter("interval"):
        b, e = float(iv.get("begin")), float(iv.get("end"))
        if (begin is not None and e <= begin) or (end is not None and b >= end):
            continue
        used += 1
        for el in iv.iter("edge"):
            tt, w = el.get("traveltime"), el.get("sampledSeconds")
            if tt is None:
                continue
            w = float(w) if w else 1.0
            num[el.get("id")] = num.get(el.get("id"), 0.0) + float(tt) * w
            den[el.get("id")] = den.get(el.get("id"), 0.0) + w
    rows = {}
    for eid, n in num.items():
        try:
            e = net.getEdge(eid)
        except KeyError:
            continue
        free = e.getLength() / max(e.getSpeed(), 0.1)
        tt = max(n / den[eid], free) if den[eid] > 0 else free
        rows[eid] = {"edge": eid, "length_m": round(e.getLength(), 2), "speed_limit_mps": round(e.getSpeed(), 3),
                     "future_tt_s": round(tt, 3), "free_flow_tt_s": round(free, 3), "measured_speed_mps": round(e.getLength() / tt, 3),
                     "sampled_seconds": round(den[eid], 1), "source": "MEASURED_ORACLE", "graph_distance": 0, "decay_weight": 1.0,
                     "corridor": None, "forecast_value": None, "model": "oracle", "ratio": round(tt / free, 4)}
    edge_tt = {k: r["future_tt_s"] for k, r in rows.items()}
    return {"model": "oracle", "unit": "measured_traveltime_s", "coverage_hops": None, "config": cfg,
            "window": [begin, end], "intervals_aggregated": used,
            "aggregation": "sampledSeconds-weighted mean of edgeData traveltime over the window, floored at free flow",
            "priced_edges": len(rows), "direct_edges": len(rows), "derived_edges": 0, "network_edges": len(net.getEdges()),
            "edge_travel_times": edge_tt, "edges": rows, "future_cost_hash": sha({k: round(v, 3) for k, v in edge_tt.items()}),
            "raw_forecast_hash": "(measured edge travel times: " + str(edgedata_xml) + ")", "source": str(edgedata_xml)}


def write_weights(table: dict, out: Path, begin: float = 0.0, end: float = 3600.0) -> Path:
    """The meanData file `duarouter --weight-files` and `sumo --weight-files` consume."""
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"<!-- forecast-derived future travel times: model={table.get('model')} horizon={table.get('horizon_min')}min "
             f"hops={table.get('coverage_hops')} analysis={table.get('analysis_run_id')} cost_hash={table['future_cost_hash']} -->",
             "<meandata>", f'  <interval begin="{begin}" end="{end}" id="forecast">']
    for eid, tt in sorted(table["edge_travel_times"].items()):
        lines.append(f'    <edge id="{eid}" traveltime="{tt}"/>')
    lines += ["  </interval>", "</meandata>", ""]
    out.write_text("\n".join(lines))
    return out
