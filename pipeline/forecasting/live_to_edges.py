#!/usr/bin/env python3
"""Live corridor congestion -> real R1 edges -> SUMO travel-time weights.

    python pipeline/forecasting/live_to_edges.py --map                       # corridor -> edge path (once, cached)
    python pipeline/forecasting/live_to_edges.py --weights pipeline/routing/weights/live_now.xml
    python pipeline/forecasting/live_to_edges.py --weights w.xml --forecast persistence --horizon-min 15

Boxes 3->4 of the live chain:

    live APIs -> state builder -> [forecast] -> [FUTURE EDGE TRAVEL TIMES] -> router -> SUMO test

Each of the 6 recorded corridors is an origin/destination pair of coordinates. This module snaps
those coordinates onto the frozen Dhaka R1 network (`sumolib`), routes between them on free-flow
travel time, and caches the resulting EDGE PATH. A congestion level on a corridor then becomes a
travel-time multiplier on every edge of its path, written as a SUMO meanData table that
`pipeline/routing/predictive_routing.py --weights` and `duarouter --weight-files` already consume.

Level -> multiplier (documented, not tuned): the recorded verdict is an ordinal class derived from
the live/free-flow travel-time ratio, so it is inverted back to the MIDPOINT of the ratio band that
defines it (see GoogleDataPolicy.congestion_bucket):

    FREE_FLOW 0 -> ratio < 1.15          -> x 1.08
    SLOW      1 -> 1.15 <= ratio < 1.5   -> x 1.33
    CONGESTED 2 -> 1.5  <= ratio < 2.0   -> x 1.75
    SEVERE    3 -> ratio >= 2.0          -> x 2.50   (open band: 2.5 is a stated assumption)

Fractional levels (a forecast between classes) interpolate linearly between band midpoints. This
mapping is an ASSUMPTION and is recorded as such in the output header — it converts a class back to
a magnitude, which the class itself does not carry.

--forecast selects what is written: `now` = the latest observed level; `persistence` = the same
value projected --horizon-min ahead (the honest default when no learned model has beaten the floors
in results/forecasting/live_floors.md); `model` = levels from a prediction file (--pred, npz/json with
one level per corridor) once such a model exists.
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
from pipeline.core.live.providers import DHAKA_R1_CORRIDORS  # noqa: E402

NET = REPO / "paper_labs/02_dhaka_osm/outputs/lab02_v2/network/dhaka_r1.net.xml"


def ensure_net(net: Path = NET) -> Path:
    """The 16 MB network is too big to track, so the repo carries a 2 MB .gz. Expand it on first
    use, otherwise a fresh clone fails deep inside sumolib with 'unknown url type'."""
    if net.exists():
        return net
    gz = net.with_suffix(net.suffix + ".gz")
    if gz.exists():
        import gzip
        import shutil
        net.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(gz, "rb") as fi, open(net, "wb") as fo:
            shutil.copyfileobj(fi, fo)
        print(f"[net] expanded {gz.name} -> {net.name}")
        return net
    raise SystemExit(f"the Dhaka network is missing and {gz} is not present either")
SERIES = REPO / "data/forecasting/live_dhaka/series.npz"
MAP_FILE = REPO / "data/forecasting/live_dhaka/corridor_edges.json"
BAND_MID = {0: 1.08, 1: 1.33, 2: 1.75, 3: 2.50}
BAND_DOC = {0: "FREE_FLOW ratio<1.15", 1: "SLOW 1.15-1.5", 2: "CONGESTED 1.5-2.0", 3: "SEVERE >=2.0 (open band)"}


def multiplier(level: float) -> float:
    """Ordinal congestion level (may be fractional) -> travel-time multiplier."""
    lo = int(np.clip(np.floor(level), 0, 3))
    hi = int(np.clip(np.ceil(level), 0, 3))
    if lo == hi:
        return BAND_MID[lo]
    return BAND_MID[lo] + (level - lo) * (BAND_MID[hi] - BAND_MID[lo])


def build_map(net_path: Path = NET, radius: float = 300.0) -> dict:
    """corridor_id -> {edges, free_flow_s, snapped distances}. Uses free-flow shortest path."""
    import sumolib
    try:
        import pyproj  # noqa: F401
    except ImportError:
        raise SystemExit("pyproj is required to project corridor coordinates onto the network: "
                         "pip install pyproj")
    net = sumolib.net.readNet(str(ensure_net(Path(net_path))))
    out = {}
    for c in DHAKA_R1_CORRIDORS:
        rec = {"corridor_id": c["corridor_id"], "origin": c["origin"], "dest": c["dest"]}
        try:
            ends = []
            for lat, lon in (c["origin"], c["dest"]):
                x, y = net.convertLonLat2XY(lon, lat)
                cands = net.getNeighboringEdges(x, y, radius)
                cands = [(e, d) for e, d in cands if e.allows("passenger")]
                if not cands:
                    raise LookupError(f"no drivable edge within {radius} m")
                e, d = min(cands, key=lambda t: t[1])
                ends.append((e, round(d, 1)))
            path, cost = net.getOptimalPath(ends[0][0], ends[1][0])
            if path is None:
                raise LookupError("no path between snapped edges")
            # NOTE: sumolib's getOptimalPath cost is the path LENGTH in metres, not a duration.
            # Free-flow time is therefore summed from the edges themselves (length / speed limit).
            per_edge = {e.getID(): round(e.getLength() / max(e.getSpeed(), 0.1), 2) for e in path}
            rec |= {"status": "MAPPED", "edges": [e.getID() for e in path],
                    "path_length_m": round(float(cost), 1),
                    "free_flow_s": round(sum(per_edge.values()), 1),
                    "snap_m": [ends[0][1], ends[1][1]],
                    "edge_free_tt_s": per_edge}
        except Exception as ex:
            rec |= {"status": "UNMAPPED", "reason": f"{type(ex).__name__}: {ex}"[:200], "edges": []}
        out[c["corridor_id"]] = rec
        print(f"[map] {rec['corridor_id']:<28} {rec['status']:<9} "
              f"{len(rec['edges']):>3} edges  {rec.get('path_length_m', 0) / 1000:.2f} km  "
              f"free-flow {rec.get('free_flow_s', '-')}s")
    return out


def latest_levels(series: Path = SERIES, horizon_bins: int = 0) -> tuple[dict, dict]:
    """-> ({corridor: level}, provenance). Persistence: the last observed level per corridor."""
    z = np.load(series, allow_pickle=True)
    vals, mask, corridors, bins = z["values"], z["mask"], list(z["corridors"]), z["bins"]
    levels, ages = {}, {}
    for i, c in enumerate(corridors):
        obs = np.where(mask[:, i])[0]
        if obs.size:
            levels[str(c)] = float(vals[obs[-1], i])
            ages[str(c)] = int((bins[-1] - bins[obs[-1]]) // 300)
    prov = {"series": str(series.relative_to(REPO)), "bins": int(vals.shape[0]),
            "last_bin_utc": datetime.fromtimestamp(float(bins[-1]), timezone.utc).isoformat(),
            "staleness_bins": ages, "horizon_bins": horizon_bins}
    return levels, prov


def write_weights(levels: dict, cmap: dict, out: Path, begin: float, end: float, prov: dict) -> dict:
    """meanData table: every edge of a corridor's path gets free-flow x multiplier."""
    edge_tt, per_corridor = {}, {}
    for cid, level in levels.items():
        rec = cmap.get(cid, {})
        if rec.get("status") != "MAPPED":
            continue
        m = multiplier(level)
        per_corridor[cid] = {"level": level, "multiplier": round(m, 3), "edges": len(rec["edges"])}
        for eid, free in rec["edge_free_tt_s"].items():
            edge_tt[eid] = max(edge_tt.get(eid, 0.0), free * m)      # worst corridor wins on shared edges
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as fh:
        fh.write("<?xml version='1.0' encoding='UTF-8'?>\n<!-- DhakaFlow live->edges. "
                 "Source: REAL_LIVE derived congestion classes (RUNTIME_REFERENCE); levels converted to "
                 "travel-time multipliers by documented band midpoints (ASSUMPTION, see pipeline/forecasting/live_to_edges.py). "
                 f"Generated {datetime.now(timezone.utc).isoformat()} -->\n<meandata>\n")
        fh.write(f'  <interval begin="{begin:.2f}" end="{end:.2f}" id="live">\n')
        for eid, tt in sorted(edge_tt.items()):
            fh.write(f'    <edge id="{eid}" traveltime="{tt:.2f}" />\n')
        fh.write("  </interval>\n</meandata>\n")
    return {"out": str(out), "edges_written": len(edge_tt), "corridors": per_corridor, "provenance": prov,
            "band_midpoints": BAND_MID, "bands": BAND_DOC}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--map", action="store_true", help="(re)build the corridor->edge map and exit")
    p.add_argument("--weights", type=Path, help="write a SUMO meanData weight table here")
    p.add_argument("--forecast", choices=["now", "persistence", "model"], default="persistence")
    p.add_argument("--horizon-min", type=float, default=15.0)
    p.add_argument("--pred", type=Path, help="model prediction file (--forecast model)")
    p.add_argument("--begin", type=float, default=0.0)
    p.add_argument("--end", type=float, default=3600.0)
    p.add_argument("--net", type=Path, default=NET)
    p.add_argument("--series", type=Path, default=SERIES)
    a = p.parse_args()

    if a.map or not MAP_FILE.exists():
        cmap = build_map(a.net)
        MAP_FILE.parent.mkdir(parents=True, exist_ok=True)
        MAP_FILE.write_text(json.dumps(cmap, indent=1))
        n_ok = sum(r["status"] == "MAPPED" for r in cmap.values())
        print(f"[map] {n_ok}/{len(cmap)} corridors mapped -> {MAP_FILE}")
        if a.map:
            return 0 if n_ok else 1
    cmap = json.loads(MAP_FILE.read_text())

    if not a.weights:
        return 0
    if not a.series.exists():
        print(f"[live_to_edges] no live series at {a.series} — run pipeline/forecasting/live_state.py first"); return 1
    hb = 0 if a.forecast == "now" else int(round(a.horizon_min * 60 / 300))
    if a.forecast == "model":
        if not a.pred:
            print("[live_to_edges] --forecast model needs --pred"); return 2
        levels = json.loads(a.pred.read_text()) if a.pred.suffix == ".json" else \
            dict(zip(*[list(x) for x in np.load(a.pred, allow_pickle=True).values()][:2]))
        prov = {"source": str(a.pred), "forecast": "model", "horizon_min": a.horizon_min}
    else:
        levels, prov = latest_levels(a.series, hb)
        prov |= {"forecast": a.forecast, "horizon_min": a.horizon_min if a.forecast == "persistence" else 0.0,
                 "note": "persistence = last observed level projected forward; the floor a learned model must beat"}
    rec = write_weights(levels, cmap, a.weights, a.begin, a.end, prov)
    print(f"[live_to_edges] {a.forecast} (+{prov.get('horizon_min', 0)} min): "
          f"{len(rec['corridors'])} corridors -> {rec['edges_written']} edges -> {a.weights}")
    for cid, r in rec["corridors"].items():
        print(f"    {cid:<28} level {r['level']:.2f} -> x{r['multiplier']:.2f} on {r['edges']} edges")
    side = a.weights.with_suffix(".json")
    side.write_text(json.dumps(rec, indent=1))
    print(f"[live_to_edges] provenance -> {side}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
