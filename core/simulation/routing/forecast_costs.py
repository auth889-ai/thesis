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

from core.common.paths import REPO
sys.path.insert(0, str(REPO))

from core.simulation.twin.network_file import ensure_net              # noqa: E402
from core.ml.forecasting.adapters.base import CityData        # noqa: E402
from core.ml.forecasting.adapters.registry import forecast as run_forecast  # noqa: E402
from core.ml.forecasting.live import live_state as live_state      # noqa: E402
from core.ml.forecasting.live.live_to_edges import BAND_DOC, BAND_MID, multiplier  # noqa: E402

CORRIDOR_MAP = REPO / "data/forecasting/live_dhaka/corridor_edges.json"
OUT_DIR = REPO / "results/routing/weights"
NO_OBSERVED = "no observed traffic for this city yet"
# The only recorded series this module ever read was derived from Google Routes results. Google's terms do not allow
# keeping it or testing models on it, so it was withdrawn and deleted on 2026-10-05 (docs/proposals.md). Until the
# city's own opt-in phone sensing has history, there is no recorded series, and every caller is told so.
RECORDED_SRC: Path | None = None
# The recorder persists an ordinal congestion CLASS, not a speed; a table built from it is priced
# through the documented band midpoints instead of length/speed.
LEVEL_UNIT = "congestion_level_0_3"


def corridor_records() -> dict[str, dict]:
    """corridor_id -> the full mapping record (edges and their free-flow travel times)."""
    if not CORRIDOR_MAP.exists():
        raise SystemExit(f"missing {CORRIDOR_MAP}; run src/pipeline/forecasting/live_to_edges.py --map")
    raw = json.loads(CORRIDOR_MAP.read_text())
    out = {}
    for k, v in raw.items():
        rec = v if isinstance(v, dict) else {}
        if rec.get("status") == "MAPPED" and rec.get("edges"):
            out[rec.get("corridor_id", k)] = rec
    return out


def corridor_edges() -> dict[str, list[str]]:
    """corridor_id -> the SUMO edges it covers, from the mapping this project already computed."""
    return {k: list(v["edges"]) for k, v in corridor_records().items()}


# ---------------------------------------------------------------------------
# RECORDED HISTORY as the forecast input.
#
# The observatory's rolling buffer lives in the backend process and is lost on restart, so a chain
# run that depends on it can only ever see the few steps that happened to have accumulated. The
# recorder wrote a REAL_LIVE series to disk over days; replaying that window is the same quantity
# from the same provider, and it is what makes the chain runnable as one command.
# ---------------------------------------------------------------------------

def resolve_as_of(spec, vals, mask, bins) -> int:
    """Which recorded bin the forecast is made AT. Everything after it is unseen by the model."""
    T = int(vals.shape[0])
    s = str(spec if spec is not None else "latest").strip().lower()
    if s in ("latest", "last", "now"):
        obs = np.where(mask.any(axis=1))[0]
        return int(obs[-1]) if obs.size else T - 1
    if s == "peak":
        # the busiest observed bin: the state worth routing around, chosen from the record itself
        score = np.where(mask, np.nan_to_num(vals), 0.0).sum(axis=1)
        return int(np.argmax(score))
    if s.lstrip("-").isdigit():
        return int(np.clip(int(s) if int(s) >= 0 else T + int(s), 0, T - 1))
    t = datetime.fromisoformat(s.replace("z", "+00:00")).timestamp()
    return int(np.argmin(np.abs(np.asarray(bins) - t)))


def observed_levels(vals, mask, bins, idx: int) -> tuple[dict, dict]:
    """The congestion level actually recorded at the as-of bin, per corridor, with its staleness.

    A corridor the provider failed on at that bin carries its last observed level forward and the
    age of that reading is reported, rather than being silently treated as free flow.
    """
    levels, ages = {}, {}
    for n in range(vals.shape[1]):
        obs = np.where(mask[: idx + 1, n])[0]
        if not obs.size:
            continue
        levels[n] = float(vals[obs[-1], n])
        ages[n] = int(idx - obs[-1])
    return levels, ages


def recorded_city_data(city: str = "dhaka", as_of: str = "latest",
                       src: Path | None = RECORDED_SRC) -> tuple[CityData, dict]:
    """The recorded REAL_LIVE window cut at the as-of bin, as a CityData, plus what was observed
    there. This is the one place the recorder's file becomes model input."""
    if src is None or not src.exists():
        raise SystemExit(f"{NO_OBSERVED}: there is no recorded series to forecast from")
    rows = live_state.load_rows(src)
    if not rows:
        raise SystemExit(f"{src} holds no usable congestion rows")
    vals, mask, corridors, bins = live_state.build(rows)
    idx = resolve_as_of(as_of, vals, mask, bins)
    v, b = vals[: idx + 1], bins[: idx + 1]
    cd = CityData(city_id=city, node_ids=list(corridors), values=v.astype("float32"),
                  interval_s=live_state.BIN_S, target="corridor congestion level",
                  unit=LEVEL_UNIT,
                  timestamps=[datetime.fromtimestamp(float(x), timezone.utc).isoformat() for x in b],
                  reality="REAL_LIVE (recorded, replayed)")
    lv, ages = observed_levels(vals, mask, bins, idx)
    observed = {
        "as_of_bin": idx,
        "as_of_utc": datetime.fromtimestamp(float(bins[idx]), timezone.utc).isoformat(),
        "levels": {str(corridors[n]): lv[n] for n in lv},
        "staleness_bins": {str(corridors[n]): ages[n] for n in ages},
        "source": str(src.relative_to(REPO)),
        "reality": "REAL_LIVE (recorded derived congestion classes)",
        "bins_seen_by_model": idx + 1,
        "bins_available": int(vals.shape[0]),
    }
    return cd, observed


def recorded_forecast(city: str, horizon_min: int | list[int], model: str | None = None,
                      as_of: str = "latest", src: Path | None = RECORDED_SRC) -> dict:
    """Run a REAL model over the recorded live window, in this process.

    Returns the same shape the API returns, plus the observed state at the as-of bin so the SUMO
    scenario can reproduce exactly the congestion the model was forecasting FROM.
    """
    cd, observed = recorded_city_data(city, as_of, src)
    hs = list(horizon_min) if isinstance(horizon_min, (list, tuple)) else [int(horizon_min)]
    out = run_forecast(cd, hs, model)
    out["input"] = cd.describe()
    out["observed"] = observed
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
                   base: str = "http://127.0.0.1:8000", source: str = "recorded",
                   as_of: str = "latest") -> dict:
    """The forecast the edge costs are priced from — from the recorded window, or from the server.

    `source="recorded"` replays the REAL_LIVE series the recorder wrote to disk and runs the model
    in this process, which is what lets the whole chain be one command. `source="api"` asks the
    running backend instead, so the number used to price edges is the same number the interface is
    showing at that moment. Neither path invents a value: both go through the one registry.

    The rolling observation window belongs to the backend process, so a CLI that imported the
    observatory would always see an empty buffer — the same defect the audit found in the schema
    tool. Going through the API also guarantees there is exactly one forecast path: the number
    used to price edges is the same number the interface displays.
    """
    if source == "recorded":
        return recorded_forecast(city, horizon_min, model, as_of)
    if source != "api":
        raise SystemExit(f"unknown forecast source {source!r}; have 'recorded' or 'api'")
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
                         f"`python src/dashboard/backend/main.py` — the observation buffer lives "
                         f"there, so a forecast cannot be produced without it.")


def _price_from_speeds(f: dict, horizon_min: int, net_path: Path, cmap: dict) -> tuple[dict, set, dict]:
    """Predicted speed (m/s) per node -> per-edge travel time = length / predicted speed."""
    vals = f["values"].get(str(horizon_min)) or f["values"].get(horizon_min)
    speeds = dict(zip(f["node_ids"], vals))
    all_edges = {e for rec in cmap.values() for e in rec["edges"]}
    geo = edge_geometry(net_path, all_edges)
    edge_tt, covered = {}, set()
    for corridor, rec in cmap.items():
        v_pred = speeds.get(corridor)
        if v_pred is None or not np.isfinite(v_pred) or v_pred <= 0:
            continue
        for eid in rec["edges"]:
            g = geo.get(eid)
            if not g:
                continue
            # travel time at the predicted speed, floored at free flow: a forecast may not claim a
            # road is faster than its own limit.
            tt = g["length_m"] / max(float(v_pred), 0.1)
            edge_tt[eid] = round(max(tt, g["free_flow_s"]), 3)
            covered.add(eid)
    return edge_tt, covered, {"rule": "length / predicted speed, floored at free flow",
                              "predicted_speeds": {k: (round(float(v), 3)
                                                       if v is not None and np.isfinite(v) else None)
                                                   for k, v in speeds.items()}}


def expand_coverage(net_path: Path, edge_mult: dict[str, float], hops: int) -> tuple[dict, dict]:
    """Carry each corridor's multiplier outward to every drivable edge within `hops` connections.

    The recorder observes six corridors; the router sees 6,527 edges. With only the corridor
    edges priced, a forecast changes nothing off-corridor, and E3 showed the router then cannot
    tell a real forecast from noise. Propagating a corridor's state to its neighbourhood is a
    stated ASSUMPTION — congestion is spatially correlated, a corridor's neighbours are in a
    similar state — and it is the knob that tests whether pricing coverage is the bottleneck.
    Nearest corridor wins; where two are equally near, the worse one does.
    """
    import sumolib
    net = sumolib.net.readNet(str(net_path))
    mult = dict(edge_mult)
    frontier = set(edge_mult)
    for _ in range(int(hops)):
        nxt = {}
        for eid in frontier:
            try:
                e = net.getEdge(eid)
            except KeyError:
                continue
            for o in list(e.getOutgoing()) + list(e.getIncoming()):
                oid = o.getID()
                if oid in mult or not o.allows("passenger"):
                    continue
                nxt[oid] = max(nxt.get(oid, 0.0), mult[eid])
        mult.update(nxt)
        frontier = set(nxt)
    geo = {}
    for eid in mult:
        try:
            e = net.getEdge(eid)
        except KeyError:
            continue
        geo[eid] = max(e.getLength() / (e.getSpeed() or 13.9), 0.1)
    return mult, {"network_edges": len(net.getEdges()), "free_flow_s": geo}


def _price_from_levels(f: dict, horizon_min: int, cmap: dict, net_path: Path | None = None,
                       hops: int = 0) -> tuple[dict, set, dict]:
    """Predicted congestion CLASS per corridor -> per-edge travel time = free flow x multiplier.

    The recorder persists an ordinal class, so the forecast is a class too. Turning it back into a
    magnitude uses the documented band midpoints from src/pipeline/forecasting/live_to_edges.py — an
    ASSUMPTION, recorded as one, and the only honest conversion available from a class. Dividing a
    length by a "speed" that was never measured would be worse: it would look like a speed.
    """
    vals = f["values"].get(str(horizon_min)) or f["values"].get(horizon_min)
    levels = dict(zip(f["node_ids"], vals))
    edge_tt, covered, per_corridor, edge_mult = {}, set(), {}, {}
    for corridor, rec in cmap.items():
        lv = levels.get(corridor)
        if lv is None or not np.isfinite(lv):
            continue
        lv = float(np.clip(lv, 0.0, 3.0))
        m = multiplier(lv)
        per_corridor[corridor] = {"predicted_level": round(lv, 3), "multiplier": round(m, 3),
                                  "edges": len(rec["edges"])}
        for eid, free in (rec.get("edge_free_tt_s") or {}).items():
            # worst corridor wins where two corridors share an edge, as in live_to_edges
            edge_tt[eid] = round(max(edge_tt.get(eid, 0.0), float(free) * m), 3)
            edge_mult[eid] = max(edge_mult.get(eid, 0.0), m)
            covered.add(eid)
    propagation = {"hops": int(hops), "propagated_edges": 0, "network_edges": None}
    if hops and net_path is not None and edge_mult:
        mult, info = expand_coverage(net_path, edge_mult, hops)
        for eid, m in mult.items():
            if eid in edge_tt:
                continue
            free = info["free_flow_s"].get(eid)
            if free is None:
                continue
            edge_tt[eid] = round(free * m, 3)
            covered.add(eid)
        propagation.update(propagated_edges=len(edge_tt) - len(edge_mult),
                           network_edges=info["network_edges"],
                           assumption=("a corridor's congestion class is carried to every drivable "
                                       "edge within the given number of connections; nearest "
                                       "corridor wins, ties to the worse one"))
    return edge_tt, covered, {"rule": "free-flow travel time x congestion-class band midpoint"
                                      + (f", propagated {hops} hops" if hops else ""),
                              "propagation": propagation,
                              "band_midpoints": BAND_MID, "bands": BAND_DOC,
                              "assumption": ("a class carries no magnitude; the midpoint of the "
                                             "ratio band that defines it is used, and SEVERE is an "
                                             "open band capped at x2.5"),
                              "per_corridor": per_corridor,
                              "predicted_levels": {k: (round(float(v), 3)
                                                       if v is not None and np.isfinite(v) else None)
                                                   for k, v in levels.items()}}


def build_table(res: dict, horizon_min: int, net_path: Path, coverage_hops: int = 0) -> dict:
    """Turn the forecast's predicted values into per-edge travel times.

    Two units reach here and they are priced differently, never interchangeably: derived SPEEDS
    from the observatory, and derived congestion CLASSES from the recorder.
    """
    f = res.get("forecast")
    if not f:
        raise SystemExit("no model could produce a forecast: "
                         + str((res.get("decision") or {}).get("reason")))

    cmap = corridor_records()
    all_edges = {e for rec in cmap.values() for e in rec["edges"]}
    if str(f.get("unit", "")).startswith("congestion_level"):
        edge_tt, covered, pricing = _price_from_levels(f, horizon_min, cmap, net_path, coverage_hops)
    else:
        edge_tt, covered, pricing = _price_from_speeds(f, horizon_min, net_path, cmap)
    pricing["input_unit"] = f.get("unit")

    return {
        "edge_travel_times": edge_tt,
        "covered_edges": len(covered & all_edges),
        "priced_edges": len(edge_tt),
        "coverage_hops": int(coverage_hops),
        "mapped_edges": len(all_edges),
        "coverage": round(len(covered & all_edges) / len(all_edges), 4) if all_edges else 0.0,
        "pricing": pricing,
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
        "observed": res.get("observed"),
        "predicted_speeds": pricing.get("predicted_speeds"),
        "predicted_levels": pricing.get("predicted_levels"),
    }


def write_weights(table: dict, out: Path, begin: float, end: float) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    f = table["forecast"]
    lines = [
        "<!-- FORECAST-DERIVED travel times. Generated by src/pipeline/routing/forecast_to_costs.py -->",
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
    p.add_argument("--source", default="recorded", choices=["recorded", "api"],
                   help="recorded = replay the on-disk REAL_LIVE window in this process; "
                        "api = ask the running backend's rolling buffer")
    p.add_argument("--as-of", default="latest",
                   help="recorded source only: 'latest', 'peak', a bin index or an ISO timestamp")
    p.add_argument("--coverage-hops", type=int, default=0,
                   help="carry each corridor's state to edges within this many connections (0 = corridor edges only)")
    a = p.parse_args()

    res = fetch_forecast(a.city, a.horizon_min, a.model, a.api, a.source, a.as_of)
    net = ensure_net()
    table = build_table(res, a.horizon_min, net, a.coverage_hops)
    path = write_weights(table, a.out, a.begin, a.end)
    f = table["forecast"]
    print(f"[costs] model {f['model']} (baseline={f['is_baseline']}), horizon {f['horizon_min']} min")
    print(f"[costs] selection: {f['selection_reason']}")
    if table.get("observed"):
        o = table["observed"]
        print(f"[costs] as-of {o['as_of_utc']} (bin {o['as_of_bin']}, "
              f"{o['bins_seen_by_model']} bins seen by the model)")
    print(f"[costs] priced by: {table['pricing']['rule']} (input unit {table['pricing']['input_unit']})")
    print(f"[costs] {table['priced_edges']} edges priced in total (hops={table['coverage_hops']})")
    print(f"[costs] {table['covered_edges']}/{table['mapped_edges']} mapped edges priced "
          f"({table['coverage']:.0%} coverage)")
    print(f"[costs] wrote {path.relative_to(REPO)}")
    a.out.with_suffix(".json").write_text(json.dumps(table, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
