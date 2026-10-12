"""The map app (Headway's web frontend, Apache-2.0, vendored unchanged in frontend/map; third_party/SOURCES.md "Map app
(Headway)") pointed at OUR services. Adapters only: they translate, they never decide anything.

    GET /tileserver/style/basic-v3      Headway's own style, its tile source pointed at the city's map provider (the style
                                        /api/config/map names), its fonts at that provider's glyphs (which cover Bengali)
                                        and its icons at the sprite martin rendered once from Headway's own SVGs
    GET /pelias/v1/autocomplete|search  Pelias-shaped GeoJSON from our Photon search (photon_features), focused on the map
    GET /pelias/v1/place?ids=...        one OpenStreetMap object (Nominatim lookup) with phone, website and opening hours
    GET /pelias/v1/reverse              the object at a point (Nominatim reverse, street level)
    GET /travelmux/{path}               Headway's travelmux, unchanged, one per city in front of that city's Valhalla; the
                                        city is the one whose area holds the trip's start, never a guess

A point outside every routed city gets "no data for this city", never another city's server.
"""
from __future__ import annotations

import json
import math
import urllib.error
import urllib.parse
import urllib.request
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, Response

from core.common import credentials
from core.common.data import city_config
from core.common.paths import REPO
from core.simulation.routing.trip import places

router = APIRouter()
STYLE = REPO / "frontend/map/upstream/tileserver/styles/basic-v3.json"   # Headway's style at the vendored commit, unchanged
CITY_RADIUS_KM = 60.0                                                     # a point belongs to a routed city within this distance of its centre
FONTS = {"Roboto Regular": "Noto Sans Regular", "Roboto Medium": "Noto Sans Bold", "Roboto Condensed Italic": "Noto Sans Italic",
         "Overpass Heavy": "Noto Sans Bold", "Overpass Bold": "Noto Sans Bold"}   # Headway's fonts have no Bengali; the provider's Noto Sans has
OSM_TYPE = {"N": "node", "W": "way", "R": "relation"}
VENUE_KEYS = {"amenity", "shop", "tourism", "leisure", "office", "healthcare", "craft", "historic", "building", "man_made", "emergency", "aeroway", "railway", "public_transport"}
PLACE_LAYER = {"city": "locality", "town": "locality", "village": "locality", "hamlet": "locality", "suburb": "neighbourhood",
               "neighbourhood": "neighbourhood", "quarter": "neighbourhood", "state": "region", "country": "country", "county": "county"}


# ------------------------------------------------------------------ which city
def routed_cities() -> list[str]:
    out = []
    for p in sorted((REPO / "config/cities").glob("*.yaml")):
        try:
            c = city_config.load(p.stem)
        except Exception:                                                  # noqa: BLE001 - a broken config is not a routed city
            continue
        if c.routing:
            out.append(c.city_id)
    return out


def _km(a: tuple[float, float], b: tuple[float, float]) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (*a, *b))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(h))


@lru_cache(maxsize=32)
def _centre(city_id: str) -> tuple[float, float] | None:
    name = city_config.load(city_id).display_name.get("en", city_id)
    box = places.city_box(name)
    return (box["lat"], box["lng"]) if box else None


def city_at(lat: float, lng: float, cities: list[str] | None = None, centre=None) -> str | None:
    """The routed city whose centre is nearest to the point, within CITY_RADIUS_KM; None when no routed city is that near. Pure given `centre`."""
    centre = centre or _centre
    best = None
    for c in cities if cities is not None else routed_cities():
        ce = centre(c)
        if ce is None:
            continue
        d = _km((lat, lng), ce)
        if d <= CITY_RADIUS_KM and (best is None or d < best[0]):
            best = (d, c)
    return best and best[1]


@router.get("/api/map/city", tags=["map app"])
def map_city(lat: float, lng: float):
    """The routed city at a point, for the map app's Start, hospitals and SOS: its id, name and emergency numbers (config only;
    shown, never dialled). No routed city near: "no data for this city", never another city's numbers."""
    city = city_at(lat, lng)
    if not city:
        return {"available": False, "note": "no data for this city: no routed city covers this place"}
    c = city_config.load(city)
    return {"available": True, "city_id": city, "display_name": c.display_name, "emergency_numbers": c.emergency_numbers or {}}


# ------------------------------------------------------------------ the map app's own config (Headway reads /static/headway-config.json)
@router.get("/static/headway-config.json", tags=["map app"])
def headway_config():
    """No transit server (travelmux runs with Valhalla only), no hard map bounds (any city), and the first view on the first
    routed city in config/cities (a returning visitor sees where they last were: Headway's own memory)."""
    first = next(iter(routed_cities()), None)
    ce = first and _centre(first)
    return {"maxBounds": None, "transitRoutingEnabled": False, "aboutUrl": "/app/lab", "aboutLinkText": "Research",
            "initialCenter": [ce[1], ce[0]] if ce else None, "initialZoom": 11 if ce else 1}


# ------------------------------------------------------------------ map style
def style_for(provider_style: dict, headway: dict, base_url: str) -> dict:
    """Headway's style with its sources, glyphs and sprite pointed at our provider and our static sprite. Pure; tested.
    Layers whose source the provider does not have (Headway's separate landcover and terrain) are left out and listed."""
    vec = next((v for v in provider_style["sources"].values() if v.get("type") == "vector"), None)
    if vec is None:
        raise ValueError("the map provider's style has no vector source")
    src = {k: v for k, v in vec.items() if k in ("url", "tiles", "minzoom", "maxzoom", "attribution")}
    style = json.loads(json.dumps(headway))
    style["sources"] = {"openmaptiles": {"type": "vector", **src}}
    dropped = [l["id"] for l in style["layers"] if l.get("source") not in (None, "openmaptiles")]
    style["layers"] = [l for l in style["layers"] if l.get("source") in (None, "openmaptiles")]
    for l in style["layers"]:
        tf = (l.get("layout") or {}).get("text-font")
        if isinstance(tf, list):
            l["layout"]["text-font"] = [FONTS.get(f, "Noto Sans Regular") for f in tf]
    style["glyphs"] = provider_style["glyphs"]
    style["sprite"] = base_url.rstrip("/") + "/tileserver/sprite/sprites"
    style.setdefault("metadata", {})["traffictwin"] = {"adapter": "backend/app/routing/headway_adapter.py", "layers_left_out": dropped,
                                                      "fonts": FONTS, "tiles_from": src.get("url") or src.get("tiles")}
    return style


@lru_cache(maxsize=4)
def _fetch_json(url: str) -> dict:
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": places.USER_AGENT}), timeout=15) as r:
        return json.loads(r.read().decode())


@router.get("/tileserver/style/{name}", tags=["map app"])
def map_style(name: str, request: Request):
    if name != "basic-v3":
        raise HTTPException(404, "only Headway's basic-v3 style is served")
    from app.platform.router import map_config
    cfg = map_config()
    if not cfg.get("style"):
        raise HTTPException(503, "no map provider style is configured (/api/config/map)")
    base = str(request.base_url)
    return JSONResponse(style_for(_fetch_json(cfg["style"]), json.loads(STYLE.read_text()), base), headers={"Cache-Control": "public, max-age=3600"})


# ------------------------------------------------------------------ search (Pelias-shaped)
def _layer(p: dict) -> str:
    if p.get("osm_key") == "place":
        return PLACE_LAYER.get(p.get("osm_value", ""), "locality")
    if p.get("osm_key") == "highway":
        return "street"
    if p.get("housenumber") and not p.get("name"):
        return "address"
    return "venue" if p.get("osm_key") in VENUE_KEYS or p.get("name") else "address"


def from_photon(f: dict) -> dict | None:
    """One Photon feature as the Pelias feature Headway reads (gid, name, label, layer, address parts). Pure; tested."""
    p, g = f.get("properties") or {}, f.get("geometry") or {}
    if not g.get("coordinates") or not p.get("osm_type") or not p.get("osm_id"):
        return None
    layer = _layer(p)
    gid = f"openstreetmap:{layer}:{OSM_TYPE.get(p['osm_type'], 'node')}/{p['osm_id']}"
    name = p.get("name") or " ".join(x for x in (p.get("housenumber"), p.get("street")) if x)
    parts = [name, p.get("district") or p.get("locality"), p.get("city"), p.get("state"), p.get("country")]
    props = {"gid": gid, "source": "openstreetmap", "layer": layer, "name": name, "label": ", ".join(dict.fromkeys(x for x in parts if x)),
             "country_code": (p.get("countrycode") or "").upper(), "country": p.get("country"), "region": p.get("state"), "county": p.get("county"),
             "city": p.get("city"), "locality": p.get("city"), "neighbourhood": p.get("district") or p.get("locality"),
             "street": p.get("street"), "road": p.get("street"), "housenumber": p.get("housenumber"), "postcode": p.get("postcode"),
             "category": [p.get("osm_value")] if p.get("osm_value") else None}
    out = {"type": "Feature", "geometry": g, "properties": {k: v for k, v in props.items() if v not in (None, "", [])}}
    if p.get("extent") and len(p["extent"]) == 4:
        w, n, e, s = p["extent"]
        out["bbox"] = [w, s, e, n]
    return out


def from_nominatim(h: dict) -> dict:
    """One Nominatim lookup/reverse hit as a Pelias feature, with phone, website and opening hours in addendum.osm. Pure; tested."""
    a, x = h.get("address") or {}, h.get("extratags") or {}
    t = {"node": "node", "way": "way", "relation": "relation"}.get(h.get("osm_type"), "node")
    layer = "venue" if h.get("class") in VENUE_KEYS or h.get("category") in VENUE_KEYS else ("street" if h.get("class") == "highway" else "address")
    name = h.get("name") or (h.get("display_name") or "").split(",")[0]
    props = {"gid": f"openstreetmap:{layer}:{t}/{h.get('osm_id')}", "source": "openstreetmap", "layer": layer, "name": name, "label": h.get("display_name"),
             "country_code": (a.get("country_code") or "").upper(), "country": a.get("country"), "region": a.get("state"),
             "city": a.get("city") or a.get("town") or a.get("village"), "neighbourhood": a.get("suburb") or a.get("neighbourhood"),
             "street": a.get("road"), "road": a.get("road"), "housenumber": a.get("house_number"), "postcode": a.get("postcode"),
             "category": [h["type"]] if h.get("type") and h.get("type") != "yes" else None,
             "addendum": {"osm": {k: v for k, v in {"phone": x.get("phone") or x.get("contact:phone"), "website": x.get("website") or x.get("contact:website"),
                                                      "opening_hours": x.get("opening_hours")}.items() if v}}}
    out = {"type": "Feature", "geometry": {"type": "Point", "coordinates": [float(h["lon"]), float(h["lat"])]},
           "properties": {k: v for k, v in props.items() if v not in (None, "", {}, {"osm": {}})}}
    if h.get("boundingbox"):
        s, n, w, e = map(float, h["boundingbox"])
        out["bbox"] = [w, s, e, n]
    return out


def _collection(features: list) -> dict:
    return {"type": "FeatureCollection", "geocoding": {"engine": {"name": "TrafficTwin adapter (Photon / Nominatim)"}},
            "features": [f for f in features if f]}


def _lang(request: Request) -> str:
    return "en" if request.headers.get("accept-language", "en").lower().startswith("en") else "default"   # Photon's "default" = the local name


def _search(request: Request, text: str, limit: int = 10) -> dict:
    q = request.query_params
    params = {"q": text, "limit": limit, "lang": _lang(request)}
    lat, lon = q.get("focus.point.lat"), q.get("focus.point.lon")
    if lat and lon:
        city = city_at(float(lat), float(lon))
        box = city and places.city_box(city_config.load(city).display_name.get("en", city))
        if box:
            w, s, e, n = box["bbox"]
            params["bbox"] = f"{w},{s},{e},{n}"
        params.update({"lat": lat, "lon": lon})
    try:
        feats = places.photon_features(params)
    except Exception as exc:                                               # noqa: BLE001 - the page shows the failure, never invented results
        raise HTTPException(502, f"place search failed: {type(exc).__name__}") from None
    return _collection([from_photon(f) for f in feats])


@router.get("/pelias/v1/autocomplete", tags=["map app"])
def pelias_autocomplete(request: Request, text: str = ""):
    return _search(request, text) if len(text.strip()) >= 2 else _collection([])


@router.get("/pelias/v1/search", tags=["map app"])
def pelias_search(request: Request, text: str = ""):
    return _search(request, text) if text.strip() else _collection([])


@router.get("/pelias/v1/place", tags=["map app"])
def pelias_place(ids: str):
    """ids = "openstreetmap:<layer>:<node|way|relation>/<id>" (one, as Headway sends)."""
    try:
        typ, num = ids.split(":")[-1].split("/")
        hit = places.osm_lookup(f"{typ[0].upper()}{int(num)}")
    except ValueError:
        raise HTTPException(400, "ids must be openstreetmap:<layer>:<type>/<id>") from None
    except Exception as exc:                                               # noqa: BLE001
        raise HTTPException(502, f"place lookup failed: {type(exc).__name__}") from None
    return _collection([from_nominatim(hit)] if hit else [])


@router.get("/pelias/v1/reverse", tags=["map app"])
def pelias_reverse(request: Request):
    q = request.query_params
    try:
        hit = places.reverse_detail(float(q["point.lat"]), float(q["point.lon"]))
    except (KeyError, ValueError):
        raise HTTPException(400, "point.lat and point.lon are required") from None
    except Exception as exc:                                               # noqa: BLE001
        raise HTTPException(502, f"reverse lookup failed: {type(exc).__name__}") from None
    return _collection([] if "error" in hit else [from_nominatim(hit)])


# ------------------------------------------------------------------ directions (travelmux per city)
def _travelmux_url(city_id: str) -> str | None:
    r = city_config.load(city_id).routing
    return credentials.load(r.travelmux_url_env) if r and r.travelmux_url_env else None


@router.get("/travelmux/{path:path}", tags=["map app"])
def travelmux_proxy(path: str, request: Request):
    """Headway's travelmux for the city that holds the trip's start (fromPlace = "lon,lat", as travelmux v8 writes it)."""
    q = request.query_params
    point = q.get("fromPlace") or q.get("point") or ""
    try:
        lon, lat = (float(x) for x in point.split(",")[:2])
    except ValueError:
        return JSONResponse({"error": {"statusCode": 400, "message": "no start point"}}, status_code=400)
    city = city_at(lat, lon)
    url = city and _travelmux_url(city)
    if not url:
        return JSONResponse({"error": {"statusCode": 404, "message": "no data for this city: no directions server covers this place"}}, status_code=404)
    target = f"{url.rstrip('/')}/{path}?{urllib.parse.urlencode(list(q.multi_items()))}"
    try:
        with urllib.request.urlopen(urllib.request.Request(target, headers={"Accept-Language": request.headers.get("accept-language", "en")}), timeout=60) as r:
            return Response(r.read(), status_code=r.status, media_type=r.headers.get("content-type", "application/json"))
    except urllib.error.HTTPError as e:
        return Response(e.read(), status_code=e.code, media_type=e.headers.get("content-type", "application/json"))
    except Exception as exc:                                               # noqa: BLE001
        return JSONResponse({"error": {"statusCode": 502, "message": f"the directions server did not answer: {type(exc).__name__}"}}, status_code=502)
