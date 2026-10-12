"""The weak-signal prediction along a whole-city route (Q3), for the web app: the route from our Valhalla server, each 100 m step judged
from the road (tunnel, density) and from the signal history in the app's own probe store. The rules are research code, in
core/simulation/routing/signal.py (Bartendr: prediction along a track, per direction, in 100 m steps); this half reads the app's
database."""
from __future__ import annotations

import os

from core.networking.prefetch import masts
from core.simulation.routing.signal import BINS, MAPPING, STEP_M, combine, history_bin, octant, refresh_points, road_bin, steps


def masts_on() -> bool:
    """Off by default: the mast-based road bin is used only when TRAFFICTWIN_SIGNAL_MASTS=1."""
    return os.environ.get("TRAFFICTWIN_SIGNAL_MASTS", "0") == "1"


def predict(city_id: str, origin: tuple[float, float], destination: tuple[float, float], profile: str = "car", db_url: str | None = None) -> dict:
    """The prediction for the whole-city route between two points, step by step."""
    import h3
    from app.probes import service as probes
    from core.simulation.routing import valhalla
    route = valhalla.route(city_id, origin, destination, profile=profile, alternates=0)
    if not route.get("available"):
        return route
    r0 = route["routes"][0]
    shape = r0["geometry"]
    parts = steps(shape)
    every = max(1, len(shape) // 300)
    traced = valhalla.trace(city_id, [{"lat": p[1], "lng": p[0]} for p in shape[::every]], profile=profile, attributes=True)
    edges = traced.get("edges", []) if traced.get("available") else []
    cells = probes.cells(city_id, minutes=60 * 24 * 30, db_url=db_url)["cells"]
    by_key = {c["cell"]: c for c in cells}
    secs_per_m = r0["summary"]["time_s"] / max(r0["summary"]["length_m"], 1)
    sites = masts.load_sites(city_id) if masts_on() else None                  # Q3 (2026-10-11): real OSM mast positions + path loss, only with TRAFFICTWIN_SIGNAL_MASTS=1
    out = []
    for st in parts:
        under = [e for e in edges if st["start_m"] <= e.get("at_m", -1) < st["end_m"]]
        oc = octant(st["heading"])
        keys = {f"{h3.latlng_to_cell(pt[1], pt[0], probes.H3_RES)}:{oc}" for pt in st["geometry"]}
        road = road_bin(under)
        if sites:
            road = masts.road_override(city_id, st, road, sites)
        verdict = combine(road, history_bin([by_key[k] for k in keys if k in by_key]))
        out.append({**{k: st[k] for k in ("i", "start_m", "end_m", "geometry")}, "heading": round(st["heading"]), "t_s": round(st["start_m"] * secs_per_m), **verdict})
    bins = [s["bin"] for s in out]
    return {"city_id": city_id, "available": True, "profile": profile, "length_m": r0["summary"]["length_m"], "time_s": r0["summary"]["time_s"], "step_m": STEP_M,
            "steps": out, "refresh_at": refresh_points(bins), "counts": {b: bins.count(b) for b in BINS},
            "metres": {b: sum(s["end_m"] - s["start_m"] for s in out if s["bin"] == b) for b in BINS},
            "history_missing_m": sum(s["end_m"] - s["start_m"] for s in out if s["history"].startswith(("no signal", "only"))),
            "road_source": ("the city's own routing server: tunnel and density of each road edge" if edges else "the routing server gave no edge attributes for this route")
                           + (f"; and {len(sites)} OpenStreetMap radio sites with a path-loss model ({masts.LABEL})" if sites else ""),
            "history_source": f"{sum(1 for c in cells if c.get('n_signal'))} probe cells with signal readings in the last 30 days" if cells else "no signal history recorded in this city yet",
            "mapping": MAPPING, "reference": "Bartendr (Schulman et al., ACM MobiCom 2010): prediction along a track, per direction, in 100 m steps"}
