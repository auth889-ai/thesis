"""Pricing every candidate route from the forecast, and choosing one with a stated reason.

A route is priced from the forecast only where it actually runs along an observed corridor; a route
with no observed corridor keeps its current ETA and says "no forecast coverage" — the prediction is
never extended to roads nobody measured."""
from __future__ import annotations

import math

from core.simulation.routing.trip.corridors import usable
from core.simulation.routing.trip.geometry import HORIZONS, multiplier, runs_along


def price_routes(routes: dict, axes: dict[str, list], pred: dict, observed: dict) -> list[dict]:
    """One card per route (up to three): ETA now, and per horizon the forecast-moved ETA, level, risk, coverage."""
    cards = []
    for i, r in enumerate(routes["routes"][:3]):
        pts = [tuple(pt) for s in (r.get("segments") or []) for pt in (s.get("coordinates") or [])]
        touched = [cid for cid, poly in axes.items() if runs_along(pts, poly)]
        # a provider without live traffic coverage here returns free-flow times: the recorded band of the
        # worst corridor the route runs along prices it NOW, and the forecast band prices it later
        free_flow = r.get("traffic_coverage") is False
        now_levels = [float(observed[cid]) for cid in touched if observed.get(cid) is not None]
        eta_now = float(r["duration_s"]) * (multiplier(max(0.0, min(3.0, max(now_levels)))) if (free_flow and now_levels) else 1.0)
        per_h = {}
        for hh in HORIZONS:
            pairs = [(float(pred[hh][cid]), observed.get(cid))
                     for cid in touched if pred[hh].get(cid) is not None and not math.isnan(float(pred[hh][cid]))]
            if pairs:
                # the forecast moves the CURRENT ETA by the ratio of the predicted to the
                # observed congestion band on the worst corridor the route runs along
                lvl_pred = max(0.0, min(3.0, max(x for x, _ in pairs)))
                lvl_now = max(0.0, min(3.0, max(float(o) if o is not None else x for x, o in pairs)))
                factor = max(0.7, min(3.0, multiplier(lvl_pred) / multiplier(lvl_now)))
                eta, level, covered = eta_now * factor, lvl_pred, True
            else:
                eta, level, covered = eta_now, None, False
            per_h[hh] = {"eta_s": round(eta), "level": None if level is None else round(level, 2),
                         "risk": ("—" if level is None else "HIGH" if level >= 2 else "MEDIUM" if level >= 1 else "LOW"),
                         "covered": covered}
        cards.append({"key": "ABC"[i], "index": i, "eta_now_s": round(eta_now), "free_flow_s": r.get("static_duration_s"),
                      "static_s": r.get("static_duration_s"), "distance_m": r.get("distance_m"),
                      "category_now": r.get("category"), "corridors": touched,
                      "forecast": per_h, "segments": r.get("segments") or []})
    return cards


def decide(cards: list[dict], h: int, forecastable: bool, city: str) -> tuple[dict, dict, int, str]:
    """Marks every card RECOMMENDED / AVOID / ACCEPTABLE. Returns (fastest now, best at +h, saving_s, reason)."""
    best_now = min(cards, key=lambda c: c["eta_now_s"])
    best_pred = min(cards, key=lambda c: c["forecast"][h]["eta_s"])
    saving = best_now["forecast"][h]["eta_s"] - best_pred["forecast"][h]["eta_s"]
    for c in cards:
        c["recommended"] = c["key"] == best_pred["key"]
        c["status"] = ("RECOMMENDED" if c["key"] == best_pred["key"] else
                       "AVOID" if c["forecast"][h]["risk"] == "HIGH" else "ACCEPTABLE")
    covered_any = any(c["forecast"][h]["covered"] for c in cards)
    if not forecastable:
        reason = (f"no forecast history for {city} yet — the fastest live route stands; "
                  f"start observing {city} to get one, or simulate this area to test rerouting")
    elif not covered_any:
        reason = "no forecast-covered corridor on these routes; the fastest route now stands"
    elif best_pred["key"] == best_now["key"]:
        reason = (f"the forecast keeps route {best_pred['key']} fastest at +{h} min "
                  f"({best_pred['forecast'][h]['risk'].lower()} congestion risk)")
    else:
        reason = (f"route {best_now['key']} is fastest now but its corridor is forecast "
                  f"{best_now['forecast'][h]['risk']} at +{h} min; route {best_pred['key']} "
                  f"saves about {round(saving / 60)} min")
    return best_now, best_pred, saving, reason


def layers_for(corr: dict, axes: dict, pred: dict, with_now: bool) -> dict:
    """Map layers: the corridors' current state, and per horizon the predicted level on each priced corridor."""
    live_by_id = {c["id"]: c for c in corr.get("corridors", [])}
    layers = {"now": [{"id": c["id"], "level": c.get("level"), "category": c.get("category"),
                       "segments": c.get("segments") or []} for c in corr.get("corridors", []) if usable(c)]
              if with_now else []}
    for hh in HORIZONS:
        layers[str(hh)] = [{"id": cid, "level": (None if pred[hh].get(cid) is None else round(float(pred[hh][cid]), 2)),
                            "segments": (live_by_id.get(cid) or {}).get("segments") or []}
                           for cid in axes if cid in pred[hh]]
    return layers


def bbox_of(cards: list[dict], pad: float = 0.006) -> list[float] | None:
    pts = [tuple(q) for c in cards for sgm in c["segments"] for q in (sgm.get("coordinates") or [])]
    if not pts:
        return None
    lats, lngs = [p[0] for p in pts], [p[1] for p in pts]
    return [min(lats) - pad, min(lngs) - pad, max(lats) + pad, max(lngs) + pad]
