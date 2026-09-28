"""OpenStreetMap public-transport routes via the Overpass API: fresh on every request."""
from __future__ import annotations

import json
import urllib.parse
import urllib.request

ENDPOINT = "https://overpass-api.de/api/interpreter"
USER_AGENT = "traffictwin/1.0 (research; commute planning)"
MODES = "subway|light_rail|monorail|train|tram"


def query(data: str, timeout_s: int = 60) -> dict:
    body = urllib.parse.urlencode({"data": data}).encode()
    req = urllib.request.Request(ENDPOINT, data=body, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout_s) as r:
        return json.loads(r.read().decode())


def _tag(tags: dict, *keys: str) -> str | None:
    for k in keys:
        if tags.get(k):
            return tags[k]
    return None


def _seconds(v: str | None) -> int | None:
    """OSM `interval` / `duration`: 'PT6M', '00:06', '6' (minutes) → seconds."""
    if not v:
        return None
    s = v.strip().upper()
    try:
        if s.startswith("PT"):
            h = m = 0
            if "H" in s:
                h, s = int(s[2:s.index("H")]), "PT" + s[s.index("H") + 1:]
            if "M" in s:
                m = int(s[2:s.index("M")])
            return h * 3600 + m * 60
        if ":" in s:
            parts = [int(x) for x in s.split(":")]
            return parts[0] * 3600 + parts[1] * 60 if len(parts) == 2 else parts[0] * 3600 + parts[1] * 60 + parts[2]
        return int(float(s) * 60)
    except ValueError:
        return None


def rail_lines(south: float, west: float, north: float, east: float) -> list[dict]:
    """Every rail-type route relation touching the box, with its ordered stops (name, lat, lon)."""
    data = f'[out:json][timeout:60];(relation["route"~"^({MODES})$"]({south},{west},{north},{east}););out body;>;out body qt;'
    payload = query(data)
    els = payload.get("elements", [])
    nodes = {e["id"]: e for e in els if e["type"] == "node"}
    lines = []
    for rel in (e for e in els if e["type"] == "relation"):
        t = rel.get("tags", {})
        stops = []
        for m in rel.get("members", []):
            if m["type"] != "node" or not str(m.get("role", "")).startswith("stop"):
                continue
            n = nodes.get(m["ref"])
            if not n or "lat" not in n:
                continue
            nt = n.get("tags", {})
            stops.append({"id": n["id"], "name": _tag(nt, "name:en", "name") or f"stop {n['id']}", "lat": n["lat"], "lon": n["lon"]})
        if len(stops) < 2:
            continue
        lines.append({"id": rel["id"], "mode": t.get("route"), "name": _tag(t, "name:en", "name") or f"line {rel['id']}", "network": _tag(t, "network:en", "network"),
                      "ref": t.get("ref"), "operator": _tag(t, "operator:en", "operator"), "interval_s": _seconds(t.get("interval")), "duration_s": _seconds(t.get("duration")),
                      "opening_hours": t.get("opening_hours"), "stops": stops, "source": "openstreetmap", "osm_timestamp": payload.get("osm3s", {}).get("timestamp_osm_base")})
    return lines
