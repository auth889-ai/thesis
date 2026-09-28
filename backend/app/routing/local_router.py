"""LOCAL ROUTER — candidate routes on the frozen Dhaka SUMO network, with NO external API.

Used by the trip analysis whenever the Google Routes API is not configured, denied, or over quota,
so the application keeps working end to end without a paid key. Everything it returns is labelled:

    source            "local_sumo_router"           (never "google_routes")
    is_live           False                          (nothing here is a live measurement)
    request_status    "LOCAL_ROUTER"                 + the recorded traffic reference it priced with
    traffic_reference the as-of time of the LAST RECORDED corridor states (the project's own recorded
                      Google Routes history, replayed — it is not current traffic and is never called so)

Routing: sumolib shortest path on free-flow travel time (edge length / speed limit), K alternatives by
the penalty method (edges of an accepted route cost ×1.6 for the next search), the same idea SUMO's
duarouter uses for alternatives. Travel time under traffic = free-flow time × the congestion multiplier
of the worst recorded corridor the route runs along (the same bands the live path uses).
"""
from __future__ import annotations

import math
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from app.paths import REPO
NET_CANDIDATES = [REPO / "data/cities/dhaka_r1/dhaka_r1.net.xml.gz",
                  REPO / "data/cities/dhaka_full/dhaka.net.xml.gz"]
PENALTY = 1.6
K_ALTERNATIVES = 3
SNAP_RADIUS_M = 400.0
LEVEL_CATEGORY = [(2.0, "TRAFFIC_JAM"), (1.0, "SLOW"), (0.0, "NORMAL")]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def category_of_level(level: float | None) -> str:
    if level is None or (isinstance(level, float) and math.isnan(level)):
        return "UNKNOWN"
    for lo, cat in LEVEL_CATEGORY:
        if level >= lo:
            return cat
    return "NORMAL"


class LocalRouter:
    """One process-wide instance; the network is read once, corridor routes are cached."""

    def __init__(self) -> None:
        self._net = None
        self._net_path: Path | None = None
        self._lock = threading.RLock()
        self._corridor_edges: dict[str, list] = {}
        self._corridor_geom: dict[str, list[list[float]]] = {}

    # ------------------------------------------------------------------ network
    @property
    def available(self) -> bool:
        return any(p.exists() for p in NET_CANDIDATES)

    def net(self):
        with self._lock:
            if self._net is None:
                import sumolib
                path = next((p for p in NET_CANDIDATES if p.exists()), None)
                if path is None:
                    raise FileNotFoundError("no Dhaka SUMO network found for the local router")
                self._net = sumolib.net.readNet(str(path))
                self._net_path = path
            return self._net

    def describe(self) -> dict:
        net = self.net()
        return {"network": str(self._net_path.relative_to(REPO)), "edges": len(net.getEdges()), "provenance": "OpenStreetMap contributors (ODbL) → netconvert, frozen Lab 02 network"}

    def _nearest_edge(self, lat: float, lng: float):
        net = self.net()
        x, y = net.convertLonLat2XY(lng, lat)
        cands = [(d, e) for e, d in net.getNeighboringEdges(x, y, r=SNAP_RADIUS_M) if e.allows("passenger") and not e.isSpecial()]
        if not cands:
            raise LookupError(f"no drivable road within {SNAP_RADIUS_M:.0f} m of {lat:.4f},{lng:.4f}")
        return min(cands, key=lambda t: t[0])[1]

    def _shortest(self, a, b, penalised: set[str]):
        """Dijkstra on free-flow travel time with the penalty method; sumolib's own search only takes a
        static cost, so the penalised search is written out here (a few thousand edges — milliseconds)."""
        import heapq
        net = self.net()
        cost = lambda e: (e.getLength() / max(e.getSpeed(), 1.0)) * (PENALTY if e.getID() in penalised else 1.0)
        dist = {a.getID(): cost(a)}; prev = {}; heap = [(dist[a.getID()], a.getID())]; seen = set()
        while heap:
            d, eid = heapq.heappop(heap)
            if eid in seen:
                continue
            seen.add(eid)
            if eid == b.getID():
                break
            e = net.getEdge(eid)
            for nxt in e.getOutgoing():
                if not nxt.allows("passenger"):
                    continue
                nd = d + cost(nxt)
                if nd < dist.get(nxt.getID(), math.inf):
                    dist[nxt.getID()] = nd; prev[nxt.getID()] = eid; heapq.heappush(heap, (nd, nxt.getID()))
        if b.getID() not in dist:
            return None
        path, cur = [], b.getID()
        while cur != a.getID():
            path.append(net.getEdge(cur)); cur = prev[cur]
        path.append(a); path.reverse()
        return path

    def _geometry(self, edges) -> list[list[float]]:
        net = self.net(); pts = []
        for e in edges:
            for x, y in e.getShape():
                lng, lat = net.convertXY2LonLat(x, y)
                pt = [round(lat, 6), round(lng, 6)]
                if not pts or pts[-1] != pt:
                    pts.append(pt)
        return pts

    # ----------------------------------------------------------------- corridors
    def corridor_route(self, cid: str, origin: tuple[float, float], dest: tuple[float, float]):
        with self._lock:
            hit = self._corridor_edges.get(cid)
        if hit is not None:
            return hit
        path = self._shortest(self._nearest_edge(*origin), self._nearest_edge(*dest), set()) or []
        geom = self._geometry(path)                      # outside the lock: _geometry takes it for the network
        with self._lock:
            self._corridor_edges[cid] = path; self._corridor_geom[cid] = geom
        return path

    def corridors(self, defs: list[dict], observed: dict, as_of_utc: str | None) -> dict:
        """The same shape LiveService.corridors() returns, priced with the recorded corridor states."""
        from app.routing.trip_analysis import multiplier
        items = []
        for c in defs:
            o, d = (c["origin"]["lat"], c["origin"]["lng"]), (c["destination"]["lat"], c["destination"]["lng"])
            try:
                path = self.corridor_route(c["id"], o, d)
            except LookupError:
                path = []
            geom = self._corridor_geom.get(c["id"], [])
            static = sum(e.getLength() / max(e.getSpeed(), 1.0) for e in path) if path else None
            lvl = observed.get(c["id"])
            dur = static * multiplier(float(lvl)) if (static and lvl is not None) else None
            cat = category_of_level(lvl) if lvl is not None else "UNKNOWN"
            items.append({"id": c["id"], "name": c.get("name", c["id"]), "road": c.get("road"), "origin": {"lat": o[0], "lng": o[1]}, "destination": {"lat": d[0], "lng": d[1]},
                          "sumo_mapped": bool(path), "source": "local_sumo_router", "retrieved_at": _now(), "is_live": False, "has_state": lvl is not None, "recorded_utc": as_of_utc,
                          "request_status": "LOCAL_ROUTER", "routing_preference": "FREE_FLOW_x_RECORDED_LEVEL", "cache_age_s": 0.0,
                          "duration_s": round(dur) if dur else None, "static_duration_s": round(static) if static else None, "traffic_penalty_s": round(dur - static) if (dur and static) else None,
                          "distance_m": round(sum(e.getLength() for e in path)) if path else None, "category": cat, "level": lvl, "geometry": geom,
                          "segments": [{"speed": cat, "colour": {"NORMAL": "green", "SLOW": "yellow", "TRAFFIC_JAM": "red"}.get(cat, "grey"), "coordinates": geom}] if len(geom) >= 2 else [], "speed_intervals": []})
        with_state = [i for i in items if i["has_state"]]
        return {"source": "local_sumo_router", "retrieved_at": _now(), "is_live": False, "request_status": "LOCAL_ROUTER",
                "traffic_reference": {"kind": "RECORDED_CORRIDOR_STATES", "as_of_utc": as_of_utc, "corridors_with_state": len(with_state)},
                "corridors": items, "summary": {"total": len(items), "live": 0, "with_recorded_state": len(with_state), "unavailable": len(items) - len(with_state),
                                                "by_category": {cat: sum(1 for i in with_state if i["category"] == cat) for cat in ("NORMAL", "SLOW", "TRAFFIC_JAM")}}}

    # -------------------------------------------------------------------- routes
    def routes(self, origin: tuple[float, float], dest: tuple[float, float], corridor_state: dict | None = None, as_of_utc: str | None = None, k: int = K_ALTERNATIVES) -> dict:
        """K candidate routes in the shape LiveService.routes() returns. `corridor_state` maps corridor
        id → {"edges": set of edge ids, "level": recorded level}; a route's category is that of the
        worst corridor it shares edges with, its ETA the free-flow time scaled by that band."""
        from app.routing.trip_analysis import multiplier
        t0 = time.monotonic()
        try:
            a, b = self._nearest_edge(*origin), self._nearest_edge(*dest)
        except LookupError as exc:
            return {"source": "local_sumo_router", "retrieved_at": _now(), "is_live": False, "request_status": f"NO_ROAD_NEAR_POINT: {exc}", "routes": [], "alternatives": 0,
                    "origin": {"lat": origin[0], "lng": origin[1]}, "destination": {"lat": dest[0], "lng": dest[1]}}
        found, penalised = [], set()
        for _ in range(k):
            path = self._shortest(a, b, penalised)
            if not path:
                break
            ids = [e.getID() for e in path]
            if any(set(ids) == set(f[0]) for f in found):
                break
            found.append((ids, path)); penalised |= set(ids)
        routes = []
        for ids, path in found:
            static = sum(e.getLength() / max(e.getSpeed(), 1.0) for e in path)
            touched = {cid: st.get("level") for cid, st in (corridor_state or {}).items() if st["edges"] & set(ids)}      # every corridor the route shares edges with
            known = [v for v in touched.values() if v is not None]
            worst = max(known) if known else None
            dur = static * (multiplier(float(worst)) if worst is not None else 1.0)
            cat = category_of_level(worst) if worst is not None else "UNKNOWN"
            # segments coloured per edge by the recorded state of the corridor that edge belongs to
            segs, cur = [], None
            for e in path:
                eid = e.getID(); lvl = next((st["level"] for st in (corridor_state or {}).values() if eid in st["edges"] and st.get("level") is not None), None)
                c2 = category_of_level(lvl) if lvl is not None else "UNKNOWN"
                pts = self._geometry([e])
                if cur and cur["speed"] == c2:
                    cur["coordinates"] += [p for p in pts if p != cur["coordinates"][-1]]
                else:
                    cur = {"speed": c2, "colour": {"NORMAL": "green", "SLOW": "yellow", "TRAFFIC_JAM": "red"}.get(c2, "grey"), "coordinates": list(pts)}; segs.append(cur)
            geom = self._geometry(path)
            routes.append({"duration_s": round(dur), "static_duration_s": round(static), "traffic_penalty_s": round(dur - static), "traffic_penalty_pct": round((dur - static) / static * 100, 1) if static else None,
                           "distance_m": round(sum(e.getLength() for e in path)), "category": cat, "description": f"{len(path)} SUMO edges via {path[len(path) // 2].getName() or path[len(path) // 2].getID()}",
                           "geometry": geom, "segments": [s for s in segs if len(s["coordinates"]) >= 2], "edge_ids": ids, "corridors_touched": sorted(touched),
                           "speed_interval_counts": {c: sum(1 for s in segs if s["speed"] == c) for c in ("NORMAL", "SLOW", "TRAFFIC_JAM")}, "speed_intervals": []})
        routes.sort(key=lambda r: r["duration_s"])
        return {"source": "local_sumo_router", "retrieved_at": _now(), "is_live": False, "request_status": "LOCAL_ROUTER", "request_latency_ms": round((time.monotonic() - t0) * 1000, 1),
                "routing_preference": "FREE_FLOW_x_RECORDED_LEVEL", "traffic_reference": {"kind": "RECORDED_CORRIDOR_STATES", "as_of_utc": as_of_utc},
                "origin": {"lat": origin[0], "lng": origin[1]}, "destination": {"lat": dest[0], "lng": dest[1]}, "routes": routes, "alternatives": max(len(routes) - 1, 0), "network": self.describe()}


router = LocalRouter()


def recorded_state(city: str = "dhaka") -> tuple[dict, str | None]:
    """The last recorded corridor congestion levels (0 NORMAL · 1 SLOW · 2.5 TRAFFIC_JAM) and their
    as-of time, from the project's own recorded history. Returns ({}, None) when there is none."""
    try:
        from app.routing.forecast_costs import recorded_city_data
        _, observed = recorded_city_data(city, "latest")
        return dict(observed.get("levels") or {}), observed.get("as_of_utc")
    except (SystemExit, Exception):        # noqa: BLE001 - no recorded history: the router still routes, unpriced
        return {}, None
