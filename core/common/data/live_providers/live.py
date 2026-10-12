"""Which live road provider serves a request, and how each is described to a person.

Order: Amazon Location (AWS credentials; any city; traffic only where it returns any) → Google Routes (a
Google key) → none, in which case the caller falls back to the local router on the frozen network
with recorded corridor states and says so. The choice is made per request, never remembered.
"""
from __future__ import annotations

WORDS = {
    "amazon_location": {"traffic": "Amazon Location Service", "backend_function": "core/common/data/live_providers/amazon_location.py: AmazonLocation.routes -> geo-routes CalculateRoutes"},
    "google_routes": {"traffic": "Google Routes API, TRAFFIC_AWARE_OPTIMAL (live)", "backend_function": "core/common/data/live_providers/google_routes.py: LiveService.routes -> Google Routes API computeRoutes"},
    "local_sumo_router": {"traffic": "local SUMO router on the frozen OSM network", "backend_function": "core/simulation/routing/local_router.py: LocalRouter.routes -> sumolib shortest paths, penalty-method alternatives"},
}


def provider():
    """The first configured live provider, or None."""
    from core.common.data.live_providers import amazon_location, google_routes
    if amazon_location.service.configured:
        return amazon_location.service
    if google_routes.service.configured:
        return google_routes.service
    return None


def answered(result: dict) -> bool:
    """The provider replied with something usable. Not the same as live: a reply can be a free-flow time (`is_live` false)."""
    return bool(result.get("answered", result.get("is_live")))


def traffic_words(routes: dict, basis: str | None = None) -> str:
    """One phrase for the page: the provider, and whether live traffic actually covered this trip."""
    src = routes.get("source") or "local_sumo_router"
    base = WORDS.get(src, {}).get("traffic", src)
    if src == "amazon_location":
        return base + (" · live traffic on this trip" if routes.get("traffic_coverage") else " · no live traffic coverage in this city: free-flow road times")
    if src == "local_sumo_router" and basis:
        return f"{base} · {basis}"
    return base


def backend_function(source: str | None) -> str:
    return WORDS.get(source or "local_sumo_router", {}).get("backend_function", str(source))
