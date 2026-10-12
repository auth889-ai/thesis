"""A city's OWN observed history as time-of-day profiles: per corridor, per 15-minute local slot, how much slower
than free flow the corridor ran. Source: the observatory's rows observed by our own opt-in phone sensing; speeds
derived from a route provider (Amazon Location, Google) are never read. Multipliers, not congestion classes: a corridor that ran at
half its free-flow speed is a 2.0, and a route's travel-time distribution is its free-flow time times the worst
touched corridor's multipliers at that slot."""
from __future__ import annotations

import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import numpy as np

SLOT_MIN = 15
SLOTS = 24 * 60 // SLOT_MIN
MIN_SAMPLES = 4                    # a slot needs this many own readings (pooled with its neighbours) to carry a distribution
_CACHE: dict[tuple[str, int], tuple[float, dict]] = {}
TTL_S = 60


def own_profiles(city_id: str, tz_offset_h: float) -> dict:
    """{"corridors": {corridor: {slot: [multiplier, ...]}}, "samples", "first_utc", "last_utc", "free_flow_mps": {corridor: v}}"""
    key = (city_id, int(round(tz_offset_h * 4)))
    hit = _CACHE.get(key)
    if hit and time.time() - hit[0] < TTL_S:
        return hit[1]
    from core.common.data.live_providers.observatory import OBSERVED_PROVIDERS, observatory
    rows, nodes = observatory.series(city_id)
    own = [r for r in rows if r.get("provider") in OBSERVED_PROVIDERS]
    per: dict[str, dict[int, list[float]]] = defaultdict(lambda: defaultdict(list))
    ff: dict[str, float] = {}
    values = np.array([r["v"] for r in own], dtype="float64") if own else np.zeros((0, len(nodes)))
    for j, cid in enumerate(nodes):
        col = values[:, j] if len(values) else np.array([])
        good = col[np.isfinite(col) & (col > 0)]
        if len(good) < MIN_SAMPLES:
            continue
        ff[cid] = float(np.percentile(good, 85))
    n = 0; first = last = None
    for r, v in zip(own, values):
        t = datetime.fromisoformat(r["utc"].replace("Z", "+00:00")).astimezone(timezone.utc) + timedelta(hours=tz_offset_h)
        slot = (t.hour * 60 + t.minute) // SLOT_MIN
        for j, cid in enumerate(nodes):
            if cid in ff and np.isfinite(v[j]) and v[j] > 0:
                per[cid][slot].append(max(1.0, ff[cid] / float(v[j]))); n += 1
        first = min(first, r["utc"]) if first else r["utc"]; last = max(last, r["utc"]) if last else r["utc"]
    out = {"city_id": city_id, "corridors": {c: dict(s) for c, s in per.items()}, "samples": n, "first_utc": first, "last_utc": last,
           "free_flow_mps": ff, "rule": "multiplier = corridor free-flow speed (85th pct of its own readings) / observed speed, by local 15-minute slot"}
    _CACHE[key] = (time.time(), out)
    return out


def multiplier_distribution(profiles: dict, corridor: str, slot: int, neighbours: int = 1) -> list[float] | None:
    prof = profiles["corridors"].get(corridor)
    if not prof:
        return None
    vals: list[float] = []
    for k in range(-neighbours, neighbours + 1):
        vals += prof.get((slot + k) % SLOTS, [])
    return vals if len(vals) >= MIN_SAMPLES else None


def level_of(multiplier: float) -> float:
    """A congestion class for the chart's colour, from the multiplier: free flow, slow, congested, severe."""
    return 0.0 if multiplier < 1.2 else 1.0 if multiplier < 1.5 else 2.0 if multiplier < 2.1 else 3.0


def forget(city_id: str | None = None) -> None:
    for k in [k for k in _CACHE if city_id is None or k[0] == city_id]:
        _CACHE.pop(k, None)
