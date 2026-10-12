"""The hospitals of a city, from OpenStreetMap (ODbL) through the Overpass API: one query per city, kept in a file with
its date, its query and its sha256, never asked again while the file exists (Overpass's guidance is quoted in
third_party/SOURCES.md, "Add your city"). A city without the file has no hospitals in the app: "no data for this city".

    python -m core.safety.hospitals --city dhaka          # the one query, then the file under data/cities/<city>/
"""
from __future__ import annotations

import argparse
import hashlib
import re
import json
from datetime import datetime, timezone
from pathlib import Path

from core.simulation.ambulance import service

DATA = service.REPO / "data/cities"
QUERY = '[out:json][timeout:60];(node["amenity"="hospital"]({s},{w},{n},{e});way["amenity"="hospital"]({s},{w},{n},{e});relation["amenity"="hospital"]({s},{w},{n},{e}););out center;'


def path(city_id: str, root: Path = DATA) -> Path:
    return Path(root) / city_id / "hospitals.json"


def city_extent(city_id: str) -> tuple[float, float, float, float]:
    """(west, south, east, north) of the whole city — the geocoded city, not the built corridor of the config."""
    from core.common.data import city_config
    from core.simulation.routing.trip import places
    cfg = city_config.load(city_id)
    box = places.city_box(cfg.label("en") if cfg.display_name else city_id)
    if not box:
        raise ValueError(f"the city '{city_id}' could not be placed on the map")
    return tuple(box["bbox"])  # type: ignore[return-value]


def parse(elements: list[dict]) -> list[dict]:
    """Overpass elements → hospitals with a name and a point (a way or relation by its centre). Unnamed ones are kept
    as 'Hospital (unnamed)' so the count is honest; nothing is invented about emergency departments: the tag is copied."""
    out = []
    for el in elements:
        tags = el.get("tags", {})
        lat, lon = (el.get("lat"), el.get("lon")) if el.get("type") == "node" else (el.get("center", {}).get("lat"), el.get("center", {}).get("lon"))
        if lat is None or lon is None:
            continue
        out.append({"osm_id": f"{el['type']}/{el['id']}", "name": tags.get("name:en") or tags.get("name") or "Hospital (unnamed)", "lat": round(float(lat), 6), "lon": round(float(lon), 6),
                    "emergency": tags.get("emergency"), "operator_type": tags.get("operator:type"), "speciality": tags.get("healthcare:speciality")})
    out.sort(key=lambda h: (h["name"], h["osm_id"]))
    return out


VET_NAME = re.compile(r"\bvet(erinary)?\b|\banimal hospital\b|পশু", re.I)


def for_people(hs: list[dict]) -> tuple[list[dict], list[dict]]:
    """(hospitals for people, animal hospitals left out). OpenStreetMap tags some animal hospitals amenity=hospital; one is left
    out when it is tagged healthcare:speciality=veterinary or its name says so (QA 2026-10-07, rank 8: "Vet-RX" was offered as
    the third nearest hospital in Dhaka). Nothing else about a hospital is judged here."""
    vet = [h for h in hs if "veterinary" in (h.get("speciality") or "").lower() or VET_NAME.search(h.get("name") or "")]
    ids = {h["osm_id"] for h in vet}
    return [h for h in hs if h["osm_id"] not in ids], vet


NOT_FOR_EMERGENCY = re.compile(r"\b(department|pharmacy|dental|dentist|tooth|homeo\w*|homio\w*|diagnostic|outdoor)\b", re.I)


def for_a_patient(hs: list[dict]) -> tuple[list[dict], list[dict]]:
    """(places an ambulance would take a patient to, the rest): OpenStreetMap also tags departments, pharmacies, dental and
    homeopathy clinics and diagnostic centres amenity=hospital. Used by the everyday "nearest hospitals" list only (the map app's
    Hospitals chip, QA 2026-10-09: "PG Nursing Department" was offered as a hospital); the reach results keep the whole file."""
    out = [h for h in hs if NOT_FOR_EMERGENCY.search(h.get("name") or "")]
    ids = {h["osm_id"] for h in out}
    return [h for h in hs if h["osm_id"] not in ids], out


def base_name(name: str) -> str:
    """A hospital's own name without the address OpenStreetMap sometimes appends ("Padma General Hospital, Sonargaon Road, Dhaka")."""
    return (name or "").split(",")[0].strip().lower()


SAME_PLACE_M = 200


def one_each(hs: list[dict], within_m: float = SAME_PLACE_M) -> list[dict]:
    """One entry per hospital: OpenStreetMap sometimes holds the same hospital twice (two points, or a point and an outline) with
    the same name a few metres apart. A same-name entry within `within_m` of one already kept is dropped; branches of one name
    further apart stay (QA 2026-10-08: "General Medical Hospital", two points 35 m apart, filled two of the three nearest)."""
    import math
    kept: list[dict] = []
    for h in hs:
        twin = next((k for k in kept if base_name(k["name"]) == base_name(h["name"]) and h["name"] != "Hospital (unnamed)"
                     and math.hypot((k["lat"] - h["lat"]) * 111_320, (k["lon"] - h["lon"]) * 111_320 * math.cos(math.radians(h["lat"]))) <= within_m), None)
        if twin is None:
            kept.append(h)
    return kept


def fetch(city_id: str, root: Path = DATA, answer: Path | None = None, endpoint: str | None = None) -> dict:
    """The one Overpass query for the city, written to the file. Refuses to ask again while the file exists. `answer` is
    a saved Overpass answer to the same query (when the query had to be run by hand, e.g. on a mirror while the main
    instance was down); then nothing is asked and the file records the endpoint given."""
    target = path(city_id, root)
    if target.exists():
        return json.loads(target.read_text())
    w, s, e, n = city_extent(city_id)
    q = QUERY.format(s=s, w=w, n=n, e=e)
    if answer:
        raw = json.loads(Path(answer).read_text())
        raw["_endpoint"] = endpoint or "saved answer"
    else:
        from core.common.data import osm
        raw = osm.query(q)
    hospitals = parse(raw.get("elements", []))
    body = {"city_id": city_id, "source": "OpenStreetMap contributors (ODbL), through the Overpass API", "endpoint": raw.get("_endpoint"), "fetched_utc": datetime.now(timezone.utc).isoformat(),
            "extent_wsen": [w, s, e, n], "query": q, "osm3s": raw.get("osm3s"), "count": len(hospitals), "hospitals": hospitals}
    body["sha256"] = hashlib.sha256(json.dumps(body["hospitals"], sort_keys=True).encode()).hexdigest()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(body, indent=1, ensure_ascii=False))
    return body


def load(city_id: str, root: Path = DATA) -> dict | None:
    """The city's hospitals file, or None: the app never fetches on a page request."""
    target = path(city_id, root)
    return json.loads(target.read_text()) if target.exists() else None


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--city", required=True)
    ap.add_argument("--answer", help="a saved Overpass answer to the same query, when it was run by hand")
    ap.add_argument("--endpoint", help="the instance that answered, recorded with --answer")
    a = ap.parse_args()
    got = fetch(a.city, answer=Path(a.answer) if a.answer else None, endpoint=a.endpoint)
    print(f"{got['count']} hospitals for {a.city} in {path(a.city)} (sha256 {got['sha256'][:12]}…, fetched {got['fetched_utc']})")
