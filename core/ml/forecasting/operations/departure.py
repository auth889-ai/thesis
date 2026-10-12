"""Departure advice on a sensor corridor: "leave by T to arrive by D with 90 %".

The corridor is the shortest path between two sensors on the DCRNN release's sensor graph (`distances_la_2012.csv`,
metres along the road). Travel time is the sum of segment length / speed, where the speed of each segment is the
served model's fresh forecast at the horizon the traveller reaches that segment, and the worst-case speed is the
forecast minus the conformal half-width calibrated for that model, horizon and predicted regime
(`results/forecasting/conformal.json`, the same quantiles behind the coverage table). "Latest departure" is the
latest offset at which the worst-case arrival still meets the deadline. Nothing here is a probability of its own:
the 90 % is the conformal level and the coverage table says how honest it was at the transition.
"""
from __future__ import annotations

import csv
import json
from functools import lru_cache
from pathlib import Path

import networkx as nx
import numpy as np

from core.ml.forecasting.operations import onset_now
from core.common.paths import REPO

WORKSPACE = Path.home() / ".dhakaflow/upstream"
GRAPH = WORKSPACE / "DCRNN/data/sensor_graph"
CONFORMAL = REPO / "results/forecasting/conformal.json"
STEP_MIN = 5
MIN_SPEED_MPH = 3.0


@lru_cache(maxsize=1)
def sensor_graph() -> tuple[nx.DiGraph, dict[str, int], list[dict]]:
    ids = (GRAPH / "graph_sensor_ids.txt").read_text().strip().split(",")
    index = {sid: i for i, sid in enumerate(ids)}
    g = nx.DiGraph()
    with open(GRAPH / "distances_la_2012.csv") as f:
        for row in csv.DictReader(f):
            a, b, d = row["from"], row["to"], float(row["cost"])
            if a in index and b in index and a != b and d > 0:
                g.add_edge(f"S{index[a]}", f"S{index[b]}", metres=d)
    locs = []
    with open(GRAPH / "graph_sensor_locations.csv") as f:
        for row in csv.DictReader(f):
            locs.append({"node": f"S{row['index']}", "sensor_id": row["sensor_id"], "lat": float(row["latitude"]), "lon": float(row["longitude"])})
    return g, index, locs


def corridor(src: str, dst: str) -> list[tuple[str, str, float]]:
    g, _, _ = sensor_graph()
    path = nx.shortest_path(g, src, dst, weight="metres")
    return [(a, b, g[a][b]["metres"]) for a, b in zip(path[:-1], path[1:])]


def half_width(model: str, horizon_min: int, congested: bool) -> float | None:
    if not CONFORMAL.exists():
        return None
    from core.ml.forecasting.evaluation.conformal import summary
    s = summary("METR-LA")
    rows = [w for w in s["rows"] if w["model"] == model] if s else []
    if not rows:
        return None
    h = min((w["horizon_min"] for w in rows), key=lambda x: abs(x - horizon_min))
    q = next(w for w in rows if w["horizon_min"] == h)["quantiles"]
    return q["predicted_regime"]["congested" if congested else "free"] or q["global"]


def advise(src: str, dst: str, as_of: int, model: str | None = None, deadline_min: int | None = None) -> dict:
    from core.ml.forecasting.operations import scientific_prediction as sp
    now, pred, info = sp.forecast(int(as_of), model)
    thr = onset_now.thresholds("METR-LA")
    segs = corridor(src, dst)
    name = info["resolved_model"]
    t_nominal = t_worst = 0.0
    legs = []
    for a, b, metres in segs:
        i = int(a[1:])
        k = min(11, int(t_nominal // STEP_MIN))                         # the forecast step the traveller reaches this segment at
        v = float(pred[k, i]) if np.isfinite(pred[k, i]) and pred[k, i] > 0 else float(now[i])
        congested = bool(np.isfinite(thr[i]) and v < thr[i])
        q = half_width(name, (k + 1) * STEP_MIN, congested) if name != "persistence" else half_width("persistence", (k + 1) * STEP_MIN, congested)
        v_worst = max(MIN_SPEED_MPH, v - (q or 0.0))
        miles = metres / 1609.344
        dt, dt_worst = miles / max(v, MIN_SPEED_MPH) * 60, miles / v_worst * 60
        t_nominal += dt; t_worst += dt_worst
        legs.append({"from": a, "to": b, "metres": round(metres), "at_min": round(t_nominal - dt, 1), "horizon_min": (k + 1) * STEP_MIN,
                     "speed_mph": round(v, 1), "worst_speed_mph": round(v_worst, 1), "half_width_mph": None if q is None else round(q, 2),
                     "regime": "congested" if congested else "free", "minutes": round(dt, 2), "worst_minutes": round(dt_worst, 2)})
    out = {"dataset": "METR-LA", "as_of": int(as_of), "model": name, "checkpoint_sha256": info.get("checkpoint_sha256"), "from": src, "to": dst,
           "legs": legs, "distance_km": round(sum(s[2] for s in segs) / 1000, 2), "travel_min": round(t_nominal, 1), "travel_min_worst": round(t_worst, 1),
           "level": 0.9, "method": "forecast per leg at the horizon reached; worst case = forecast minus the conformal half-width for that model, horizon and predicted regime"}
    if deadline_min is not None:
        out["deadline_min"] = deadline_min
        out["latest_departure_min"] = round(deadline_min - t_worst, 1)
        out["buffer_min"] = round(t_worst - t_nominal, 1)
        out["advice"] = (f"leave within {out['latest_departure_min']} min to arrive by +{deadline_min} min even if every leg runs at its "
                         f"90 % worst case ({out['travel_min_worst']} min against {out['travel_min']} min expected)") if out["latest_departure_min"] >= 0 else \
                        f"too late: even the expected {out['travel_min']} min does not meet +{deadline_min} min" if t_nominal > deadline_min else \
                        f"leave now: the expected trip meets +{deadline_min} min but the 90 % worst case ({out['travel_min_worst']} min) does not"
    return out
