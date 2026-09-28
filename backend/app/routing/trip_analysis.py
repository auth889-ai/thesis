"""ANALYZE TRAFFIC: one origin, one destination, one departure — current state, forecast, decision.

    job = start({"origin": "farmgate", "destination": "gulshan1", "horizon_min": 30})
    status(job)  -> {"stage": "Running forecast", ...} then {"stage": "done", "result": {...}}

This is the import surface; the work lives in `app.routing.trip` (geometry, places, corridors, routes,
pricing, analysis, jobs, models). Confidence is the model's measured class accuracy on this city's own
recorded data at that horizon, not a guess; the prediction is never extended to roads nobody measured.
"""
from __future__ import annotations

from app.routing.trip.corridors import corridor_polylines as _corridor_polylines, levels_from_speeds, usable as _usable  # noqa: F401
from app.routing.trip.geometry import BAND, HORIZONS, MIN_POINTS, NEAR_M, multiplier, runs_along  # noqa: F401
from app.routing.trip.jobs import _JOBS, _LOCK, _run, start, status  # noqa: F401
from app.routing.trip.models import models_for_city  # noqa: F401
from app.routing.trip.places import city_box, city_id_for, is_dhaka, places, resolve_place, suggest  # noqa: F401

__all__ = ["HORIZONS", "BAND", "NEAR_M", "MIN_POINTS", "multiplier", "runs_along", "levels_from_speeds",
           "start", "status", "models_for_city", "city_box", "city_id_for", "is_dhaka", "places", "resolve_place", "suggest"]
