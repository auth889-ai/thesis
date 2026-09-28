"""Corridor states: levels from observatory speeds, corridor polylines, the observatory fill-in for
corridors the recorder never sampled, and the backtest accuracy that labels the confidence."""
from __future__ import annotations

import json
import math

from app import evidence_paths as config
from app.data import reference_corridors as cz

from .geometry import HORIZONS

LEVEL = {"NORMAL": 0.0, "SLOW": 1.0, "TRAFFIC_JAM": 2.5}


def usable(c: dict) -> bool:
    """A corridor the analysis may price from: live now, or carrying a recorded state."""
    return bool(c.get("is_live") or c.get("has_state"))


def levels_from_speeds(cd, forecast: dict | None, live: dict) -> tuple[dict, dict]:
    """Observatory speeds (m/s) -> congestion levels per corridor, now and per horizon, using
    each corridor's own free-flow speed from the live snapshot. Same bands as the recorder."""
    import numpy as np
    from app.data.live_providers.google_routes import classify
    free = {}
    for c in live.get("corridors", []):
        if c.get("static_duration_s") and c.get("distance_m"):
            free[c["id"]] = float(c["distance_m"]) / float(c["static_duration_s"])
    obs, pred = {}, {hh: {} for hh in HORIZONS}
    vals = np.asarray(cd.values) if cd.shape[0] else None
    for i, cid in enumerate(cd.node_ids):
        f0 = free.get(cid)
        if not f0:
            continue
        if vals is not None:
            col = vals[:, i]; fin = col[np.isfinite(col)]
            if fin.size:
                obs[cid] = LEVEL[classify(f0 / max(float(fin[-1]), 0.1), 1.0)]
        if forecast:
            for hh in HORIZONS:
                v = (forecast["values"].get(hh) or forecast["values"].get(str(hh)) or [None] * len(cd.node_ids))[i]
                if v is not None and v == v:
                    pred[hh][cid] = LEVEL[classify(f0 / max(float(v), 0.1), 1.0)]
    return obs, pred


def corridor_polylines(live: dict) -> dict[str, list]:
    """Each corridor's road geometry from the live snapshot; the straight axis if it has none."""
    live_by_id = {c["id"]: c for c in live.get("corridors", [])}
    out = {}
    for c in cz.CORRIDORS:
        poly = [tuple(p) for s in ((live_by_id.get(c["id"]) or {}).get("segments") or [])
                for p in (s.get("coordinates") or [])]
        if len(poly) < 2:
            poly = list(cz.coords(c))
        out[c["id"]] = poly
    return out


def accuracy(model: str) -> dict:
    f = config.REPO / "results/forecasting/live_backtest.json"
    if not f.exists():
        return {}
    bt = json.loads(f.read_text())
    return {r["horizon_min"]: r for r in bt["rows"] if r["model"] == model}


def observatory_fill(city: str, corr: dict, pred: dict, observed: dict) -> None:
    """Corridors the recorder never sampled are forecast from the persisted observatory window
    instead — shorter history, same model, same units after conversion. Fills `pred` and
    `observed` in place; raises when the observatory cannot serve this city."""
    from app.data.live_providers import observatory as obs_mod
    from app.data.live_providers.google_routes import classify
    from app.forecasting.adapters.registry import forecast as run_forecast
    cd = obs_mod.observatory.city_data(city)
    if cd.shape[0] < 8:
        return
    import numpy as np
    fo = (run_forecast(cd, HORIZONS) or {}).get("forecast")
    if not fo:
        return
    last = np.asarray(cd.values)[-1]
    for hh in HORIZONS:
        vals = fo["values"].get(hh) or fo["values"].get(str(hh)) or []
        for cid, v in zip(fo["node_ids"], vals):
            if cid in pred[hh] and pred[hh][cid] is not None:
                continue
            if v is None or (isinstance(v, float) and math.isnan(v)):
                continue
            # the observatory forecasts a SPEED (m/s); the level is the class the live/free-flow
            # ratio would fall in, using the corridor's static speed
            live_c = next((c for c in corr.get("corridors", []) if c["id"] == cid), None)
            if not live_c or not live_c.get("static_duration_s") or not live_c.get("distance_m"):
                continue
            free_ms = float(live_c["distance_m"]) / float(live_c["static_duration_s"])
            pred[hh][cid] = LEVEL.get(classify(free_ms / max(float(v), 0.1), 1.0), 0.0)
            if cid not in observed:
                now_v = last[fo["node_ids"].index(cid)]
                now_ratio = free_ms / max(float(now_v), 0.1) if now_v == now_v else 1.0
                observed[cid] = LEVEL.get(classify(now_ratio, 1.0), 0.0)
