"""Cities and places: 'lat, lng', the known Dhaka places, the registered cities, or OpenStreetMap's
geocoder bounded to the city. Never silent: an unknown place is an error the page shows."""
from __future__ import annotations

import json
import re
import threading

from app.data import reference_corridors as cz

_CITY_BOX: dict[str, dict] = {}
_GEO_CACHE: dict[str, list] = {}
_GEO_LOCK = threading.Lock()
_GEO_LAST = [0.0]


def is_dhaka(city: str) -> bool:
    return re.sub(r"[^a-z]", "", (city or "").lower()) in ("dhaka", "dhakabangladesh", "dhakar")


def city_id_for(city: str) -> str | None:
    """The registry id of a typed city name, if it is registered (no geocoding here)."""
    if str(city or "").startswith("live:"):                 # the app's dataset id for a watched city
        return str(city)[5:]
    if is_dhaka(city):
        return "dhaka"
    from app.data.cities import registry, slug
    key = re.sub(r"[^a-z0-9]", "", (city or "").lower())
    hits = []
    for cid in registry.list_ids():
        sp = registry.get(cid)
        names = {cid, slug(sp.display_name or ""), (sp.display_name or "").split(",")[0]}
        if key in {re.sub(r"[^a-z0-9]", "", n.lower()) for n in names if n}:
            hits.append(cid)
    if not hits:
        return None
    try:                                    # the one already being observed wins
        from app.data.live_providers import observatory as obs_mod
        watched = set(obs_mod.observatory.cities())
        hits.sort(key=lambda c: (c not in watched, len(c)))
    except Exception:                       # noqa: BLE001
        pass
    return hits[0]


def _nominatim(params: dict) -> list[dict]:
    """One query to OpenStreetMap's geocoder, at most one per second (their usage policy), with the
    answer cached for the process: the same place typed twice is not two network calls, and a
    burst of suggestion requests cannot starve the resolve that follows."""
    import time
    import urllib.parse
    import urllib.request
    q = urllib.parse.urlencode({"format": "json", **params})
    with _GEO_LOCK:
        if q in _GEO_CACHE:
            return _GEO_CACHE[q]
        wait = 1.05 - (time.monotonic() - _GEO_LAST[0])
        if wait > 0:
            time.sleep(wait)                              # the geocoder's rate limit, not a cosmetic delay
        req = urllib.request.Request(f"https://nominatim.openstreetmap.org/search?{q}",
                                     headers={"User-Agent": "traffictwin/1.0 (research)"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                hits = json.loads(r.read().decode())
        finally:
            _GEO_LAST[0] = time.monotonic()
        if hits:
            _GEO_CACHE[q] = hits
        return hits


def reverse_geocode(lat: float, lng: float) -> dict:
    """The address at a point (OpenStreetMap's reverse geocoder, same rate limit and cache as the forward one)."""
    import time
    import urllib.parse
    import urllib.request
    q = urllib.parse.urlencode({"format": "json", "lat": f"{lat:.5f}", "lon": f"{lng:.5f}", "zoom": 10, "accept-language": "en"})
    with _GEO_LOCK:
        if q in _GEO_CACHE:
            return _GEO_CACHE[q][0]
        wait = 1.05 - (time.monotonic() - _GEO_LAST[0])
        if wait > 0:
            time.sleep(wait)
        req = urllib.request.Request(f"https://nominatim.openstreetmap.org/reverse?{q}", headers={"User-Agent": "traffictwin/1.0 (research)"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                hit = json.loads(r.read().decode())
        finally:
            _GEO_LAST[0] = time.monotonic()
        if "error" in hit:
            raise LookupError(hit["error"])
        _GEO_CACHE[q] = [hit]
        return hit


def city_box(city: str) -> dict | None:
    """The city itself, geocoded once: centre + bounding box, so places are searched INSIDE it."""
    key = re.sub(r"[^a-z0-9]", "", (city or "").lower())
    if key in _CITY_BOX:
        return _CITY_BOX[key]
    if is_dhaka(city):
        box = {"label": "Dhaka", "lat": 23.78, "lng": 90.40, "bbox": [90.30, 23.66, 90.52, 23.92]}
    else:
        hits = _nominatim({"q": city, "limit": 6, "accept-language": "en"})
        if not hits:
            return None
        # Nominatim's first hit is not always the city of that name (an alias can outrank it):
        # prefer a hit whose own name matches what was typed, then a settlement, then the first.
        def name_ok(h):
            return re.sub(r"[^a-z0-9]", "", h.get("display_name", "").split(",")[0].lower()) == key
        def settlement(h):
            return h.get("type") in ("city", "town", "administrative", "municipality", "village")
        h = next((x for x in hits if name_ok(x) and settlement(x)), None) or next((x for x in hits if name_ok(x)), None) \
            or next((x for x in hits if settlement(x)), None) or hits[0]
        bb = [float(x) for x in h["boundingbox"]]                        # south, north, west, east
        box = {"label": h.get("display_name", city).split(",")[0], "lat": float(h["lat"]), "lng": float(h["lon"]),
               "bbox": [bb[2], bb[0], bb[3], bb[1]]}                  # west, south, east, north
    _CITY_BOX[key] = box
    return box


def resolve_place(text: str, city: str = "dhaka") -> dict:
    """'lat, lng' | a known Dhaka place | the city itself | free text via OpenStreetMap's geocoder
    bounded to the city."""
    t = (text or "").strip()
    m = re.match(r"^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$", t)
    if m:
        return {"lat": float(m.group(1)), "lng": float(m.group(2)), "label": t, "source": "coordinates"}
    key = re.sub(r"[^a-z0-9]", "", t.lower())
    if is_dhaka(city):
        for name, (lat, lng) in cz.PLACES.items():
            if key == re.sub(r"[^a-z0-9]", "", name.lower()):
                return {"lat": lat, "lng": lng, "label": name, "source": "known place"}
    box = city_box(city)
    if box is None:
        raise ValueError(f"could not find the city '{city}'")
    if key == re.sub(r"[^a-z0-9]", "", box["label"].lower()) or key == re.sub(r"[^a-z0-9]", "", (city or "").lower()):
        return {"lat": box["lat"], "lng": box["lng"], "label": f"{box['label']} (centre)", "source": "city centre"}
    hits = _search_in(box, t, 1)
    if not hits:
        raise ValueError(f"'{t}' was not found inside {box['label']}. Type a place in {box['label']} "
                         f"(pick one of the suggestions as you type), or 'lat, lng'.")
    return {"lat": float(hits[0]["lat"]), "lng": float(hits[0]["lon"]),
            "label": hits[0].get("display_name", t).split(",")[0], "source": "OpenStreetMap geocoder"}


def _search_in(box: dict, q: str, limit: int) -> list[dict]:
    """Places matching `q` inside the city: first strictly bounded to its box, then the looser
    '<q>, <city>' query (Nominatim needs the city word for short names) filtered to the box."""
    w, s_, e, n = box["bbox"]
    common = {"limit": limit, "accept-language": "en"}
    hits = _nominatim({"q": q, "viewbox": f"{w},{n},{e},{s_}", "bounded": 1, **common})
    if not hits:
        cand = _nominatim({"q": f"{q}, {box['label']}", "viewbox": f"{w},{n},{e},{s_}", **common})
        hits = [h for h in cand if w <= float(h["lon"]) <= e and s_ <= float(h["lat"]) <= n]
    return hits


def suggest(city: str, q: str, limit: int = 8) -> list[dict]:
    """Place suggestions for the origin / destination inputs, inside the named city."""
    q = (q or "").strip()
    out = []
    if is_dhaka(city):
        for k, v in cz.PLACES.items():
            lab = k.replace("_", " ").title()
            if not q or q.lower() in lab.lower():
                out.append({"label": lab, "lat": v[0], "lng": v[1], "source": "known place"})
    if len(q) < 2:
        return out[:limit]
    box = city_box(city)
    if box is None:
        return out[:limit]
    try:
        hits = _search_in(box, q, limit)
    except Exception:                                   # noqa: BLE001 - suggestions are best effort
        hits = []
    seen = {o["label"] for o in out}
    for h in hits:
        parts = [x.strip() for x in h.get("display_name", "").split(",")]
        lab = ", ".join(parts[:2]) if parts else q
        if lab not in seen:
            seen.add(lab)
            out.append({"label": lab, "lat": float(h["lat"]), "lng": float(h["lon"]), "source": "OpenStreetMap"})
    return out[:limit]


def places() -> list[dict]:
    return [{"id": k, "label": k.replace("_", " ").title(), "lat": v[0], "lng": v[1]}
            for k, v in cz.PLACES.items()]
