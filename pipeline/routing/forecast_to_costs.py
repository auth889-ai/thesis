#!/usr/bin/env python3
"""The missing link: an ACTUAL model forecast becomes the future travel-time table SUMO routes on.

    CITY -> TRAFFIC DATA -> ML/DL FORECAST -> FUTURE ROUTE COST -> ROUTING -> SUMO

Until now the "predictive" routing arm was fed a table derived from persistence over four
congestion CLASSES. That is not a forecast in any useful sense, and it meant the prediction half of
this project never actually reached the control half. This module closes that gap: it calls the
common forecast interface, takes the NUMERIC predicted speed per observation node, maps it onto the
SUMO edges those nodes cover, and writes the meanData XML that `duarouter --weight-files` and
`traci.edge.adaptTraveltime` already consume.

HOW A PREDICTED SPEED BECOMES AN EDGE COST
    For each mapped edge, predicted travel time = length / predicted speed, floored at the free-flow
    time so a forecast can never claim a road is faster than its speed limit. Edges no node covers
    keep their free-flow time and are recorded as uncovered rather than silently guessed at — a
    weight table that quietly invents costs for the whole network would make the routing result
    meaningless.

WHAT IS RECORDED WITH EVERY TABLE
    The model that produced it, its checkpoint, whether it was a baseline, the horizon, and the
    coverage. A weight file with no provenance is indistinguishable from a fabricated one.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from pipeline.core.network_file import ensure_net              # noqa: E402
from pipeline.forecasting.adapters.base import CityData        # noqa: E402
from pipeline.forecasting.adapters.registry import forecast as run_forecast  # noqa: E402

CORRIDOR_MAP = REPO / "data/forecasting/live_dhaka/corridor_edges.json"
OUT_DIR = REPO / "results/routing/weights"


def corridor_edges() -> dict[str, list[str]]:
    """corridor_id -> the SUMO edges it covers, from the mapping this project already computed."""
    if not CORRIDOR_MAP.exists():
        raise SystemExit(f"missing {CORRIDOR_MAP}; run pipeline/forecasting/live_to_edges.py --map")
    raw = json.loads(CORRIDOR_MAP.read_text())
    out = {}
    for k, v in raw.items():
        rec = v if isinstance(v, dict) else {}
        if rec.get("status") == "MAPPED" and rec.get("edges"):
            out[rec.get("corridor_id", k)] = list(rec["edges"])
    return out


def edge_geometry(net_path: Path, edges: set[str]) -> dict[str, dict]:
    """Per edge: free-flow travel time and the speed limit it implies. Read once."""
    import sumolib
    net = sumolib.net.readNet(str(net_path))
    out = {}
    for eid in edges:
        try:
            e = net.getEdge(eid)
        except KeyError:
            continue
        v = e.getSpeed() or 13.9
        out[eid] = {"free_flow_s": max(e.getLength() / v, 0.1), "speed_limit_ms": v,
                    "length_m": e.getLength()}
    return out


def fetch_forecast(city: str, horizon_min: int, model: str | None,
                   base: str = "http://127.0.0.1:8000") -> dict:
    """Ask the RUNNING server for the forecast.

    The rolling observation window belongs to the backend process, so a CLI that imported the
    observatory would always see an empty buffer — the same defect the audit found in the schema
    tool. Going through the API also guarantees there is exactly one forecast path: the number
    used to price edges is the same number the interface displays.
    """
    import urllib.parse
    import urllib.request
    q = f"{base}/api/forecast/{urllib.parse.quote(city)}?horizons={horizon_min}"
    if model:
        q += f"&model={urllib.parse.quote(model)}"
    try:
        with urllib.request.urlopen(q, timeout=120) as r:
            return json.loads(r.read().decode())
    except Exception as exc:                      # noqa: BLE001 - reported, never silently faked
        raise SystemExit(f"cannot reach the forecast API at {base} ({exc}). Start it with "
                         f"`python dashboard/backend/main.py` — the observation buffer lives "
                         f"there, so a forecast cannot be produced without it.")


def build_table(res: dict, horizon_min: int, net_path: Path) -> dict:
    """Turn the forecast's predicted node speeds into per-edge travel times."""
    f = res.get("forecast")
    if not f:
        raise SystemExit("no model could produce a forecast: "
                         + str((res.get("decision") or {}).get("reason")))

    vals = f["values"].get(str(horizon_min)) or f["values"].get(horizon_min)
    speeds = dict(zip(f["node_ids"], vals))
    cmap = corridor_edges()
    all_edges = {e for es in cmap.values() for e in es}
    geo = edge_geometry(net_path, all_edges)

    edge_tt, covered = {}, set()
    for corridor, edges in cmap.items():
        v_pred = speeds.get(corridor)
        if v_pred is None or not np.isfinite(v_pred) or v_pred <= 0:
            continue
        for eid in edges:
            g = geo.get(eid)
            if not g:
                continue
            # travel time at the predicted speed, floored at free flow: a forecast may not claim a
            # road is faster than its own limit.
            tt = g["length_m"] / max(float(v_pred), 0.1)
            edge_tt[eid] = round(max(tt, g["free_flow_s"]), 3)
            covered.add(eid)

    return {
        "edge_travel_times": edge_tt,
        "covered_edges": len(covered),
        "mapped_edges": len(all_edges),
        "coverage": round(len(covered) / len(all_edges), 4) if all_edges else 0.0,
        "uncovered_note": ("edges no observation node covers keep their free-flow time and are NOT "
                           "included here; inventing costs for them would make the routing result "
                           "meaningless"),
        "forecast": {
            "model": f["model"], "checkpoint": f["checkpoint"],
            "is_baseline": f["is_baseline"], "horizon_min": horizon_min,
            "unit": f["unit"], "inference_utc": f["inference_utc"],
            "input_window_steps": f["input_window_steps"],
            "selection_reason": (res.get("decision") or {}).get("reason"),
            "fallback": (res.get("decision") or {}).get("fallback"),
        },
        "predicted_speeds": {k: (round(float(v), 3) if v is not None and np.isfinite(v) else None)
                             for k, v in speeds.items()},
    }


def write_weights(table: dict, out: Path, begin: float, end: float) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    f = table["forecast"]
    lines = [
        "<!-- FORECAST-DERIVED travel times. Generated by pipeline/routing/forecast_to_costs.py -->",
        f"<!-- model={f['model']} checkpoint={f['checkpoint']} baseline={f['is_baseline']} "
        f"horizon={f['horizon_min']}min inferred={f['inference_utc']} -->",
        f"<!-- coverage {table['covered_edges']}/{table['mapped_edges']} mapped edges -->",
        "<meandata>",
        f'  <interval begin="{begin}" end="{end}" id="forecast">',
    ]
    for eid, tt in sorted(table["edge_travel_times"].items()):
        lines.append(f'    <edge id="{eid}" traveltime="{tt}"/>')
    lines += ["  </interval>", "</meandata>", ""]
    out.write_text("\n".join(lines))
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--city", default="dhaka")
    p.add_argument("--horizon-min", type=int, default=15)
    p.add_argument("--model", default=None, help="force a model; default is the registry's choice")
    p.add_argument("--out", type=Path, default=OUT_DIR / "forecast_weights.xml")
    p.add_argument("--begin", type=float, default=0.0)
    p.add_argument("--end", type=float, default=3600.0)
    p.add_argument("--api", default="http://127.0.0.1:8000")
    a = p.parse_args()

    res = fetch_forecast(a.city, a.horizon_min, a.model, a.api)
    net = ensure_net()
    table = build_table(res, a.horizon_min, net)
    path = write_weights(table, a.out, a.begin, a.end)
    f = table["forecast"]
    print(f"[costs] model {f['model']} (baseline={f['is_baseline']}), horizon {f['horizon_min']} min")
    print(f"[costs] selection: {f['selection_reason']}")
    print(f"[costs] {table['covered_edges']}/{table['mapped_edges']} mapped edges priced "
          f"({table['coverage']:.0%} coverage)")
    print(f"[costs] wrote {path.relative_to(REPO)}")
    a.out.with_suffix(".json").write_text(json.dumps(table, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
