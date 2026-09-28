"""The candidate routes for a trip: the live provider when it answers, otherwise the local router on
the frozen Dhaka network with the last recorded corridor states — labelled RECORDED, never live."""
from __future__ import annotations

from .places import is_dhaka


def fetch_routes(o: dict, d: dict, city: str, run, emit) -> tuple[dict, dict, str]:
    """Returns (routes, corridor snapshot, traffic basis). Records every provenance fact on `run`."""
    from app.data import provenance as pv
    from app.data.live_providers.google_routes import service
    routes = service.routes((o["lat"], o["lng"]), (d["lat"], d["lng"])) if service.configured else {"is_live": False, "routes": [], "request_status": "NOT_CONFIGURED", "source": "google_routes"}
    corr = service.corridors() if routes.get("is_live") else {"is_live": False, "corridors": [], "request_status": routes.get("request_status")}
    traffic_basis = "LIVE"
    if not routes.get("is_live") or not routes.get("routes"):
        # NO KEY / DENIED / OVER QUOTA: the application keeps working on its own road network and its
        # own recorded corridor states. Everything downstream is labelled RECORDED, never live.
        from app.routing import local_router as local_routes
        live_status = routes.get("request_status")
        if not local_routes.router.available:
            run.finish("failed", f"live routing unavailable: {live_status}; no local road network either")
            raise RuntimeError(f"live routing unavailable: {live_status}; no local road network either")
        levels, as_of_utc = local_routes.recorded_state("dhaka") if is_dhaka(city) else ({}, None)
        from app.data import reference_corridors as _rc
        defs = [_rc.describe(c) for c in _rc.CORRIDORS] if is_dhaka(city) else []
        corr = local_routes.router.corridors(defs, levels, as_of_utc)
        state = {c["id"]: {"edges": set(e.getID() for e in local_routes.router.corridor_route(c["id"], (c["origin"]["lat"], c["origin"]["lng"]), (c["destination"]["lat"], c["destination"]["lng"]))), "level": c.get("level")}
                 for c in corr["corridors"] if c.get("sumo_mapped")}
        routes = local_routes.router.routes((o["lat"], o["lng"]), (d["lat"], d["lng"]), state, as_of_utc)
        if not routes.get("routes"):
            run.finish("failed", f"live routing unavailable: {live_status}; local router: {routes.get('request_status')}")
            raise RuntimeError(f"live routing unavailable: {live_status}; local router: {routes.get('request_status')}")
        traffic_basis = f"RECORDED corridor states as of {as_of_utc}" if as_of_utc else "FREE-FLOW (no recorded traffic for this city)"
        emit(traffic_basis=traffic_basis, live_status=live_status)
        run.set(live_routing_status=live_status, traffic_basis=traffic_basis)
    run.set(routes_retrieved_at=routes.get("retrieved_at"), routes_n=len(routes.get("routes") or []))
    run.set(routing_provider=routes.get("source"), routing_preference=routes.get("routing_preference"), routing_request_status=routes.get("request_status"),
            routing_backend_function=("backend/app/live/google_routes.py: LiveService.routes -> Google Routes API computeRoutes" if routes.get("source") == "google_routes"
                                      else "backend/app/routing/local_routes.py: LocalRouter.routes -> sumolib shortest paths on the frozen Dhaka network, penalty-method alternatives"), routing_latency_ms=routes.get("request_latency_ms"),
            route_geometry_hash=pv.sha_json([[pt for s in (r.get("segments") or []) for pt in (s.get("coordinates") or [])] for r in routes["routes"]]),
            routes_summary=[{"key": "ABC"[i], "distance_m": r.get("distance_m"), "duration_s": r.get("duration_s"), "static_duration_s": r.get("static_duration_s"),
                             "points": sum(len(s.get("coordinates") or []) for s in (r.get("segments") or []))} for i, r in enumerate(routes["routes"][:3])])
    return routes, corr, traffic_basis
