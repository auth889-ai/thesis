"""Find a city by name in Overture Maps' divisions theme, and propose a small area around it.

One DuckDB query reads Overture's divisions file where it is published (ODbL; © OpenStreetMap contributors, Overture
Maps Foundation). A place is matched on its main name, its English name, or its name in a language the app ships, so a city whose
main name is in its own script is still found by its English name. The side of the road a country drives on is stored
on the country's record, which is read in a second pass.

The file is large and the first search for a name can take about a minute; each answer is kept in a small local cache,
so the same name answers at once the next time. What Overture does not hold (time zone, languages, emergency numbers,
units) is not looked up anywhere else and stays unknown.
"""
from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path

from core.common.paths import REPO

STAC = "https://stac.overturemaps.org/{release}/divisions/division/collection.json"
CACHE = REPO / "data/cities/_search_cache.json"
PLACE_TYPES = ("locality", "localadmin", "county")
BOX_DEG = 0.04                      # the proposed area: about 4 x 4 km, the size of the first city's corridor
MAX_RESULTS = 10
ATTRIBUTION = "© OpenStreetMap contributors, Overture Maps Foundation (divisions theme, ODbL)"


def app_languages() -> list[str]:
    """The languages the web app ships (its locale files); a city gets a display name in each when Overture has one."""
    found = sorted(p.stem for p in (REPO / "frontend/src/i18n/locales").glob("*.json"))
    return found or ["en"]


def divisions_file(release: str) -> str:
    """The address of the divisions file of a release, read from Overture's catalogue."""
    def get(url: str) -> dict:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "dhakaflow/1.0"}), timeout=20) as r:
            return json.loads(r.read())
    collection = STAC.format(release=release)
    item = next(l["href"] for l in get(collection)["links"] if l.get("rel") == "item")
    item = item if item.startswith("http") else collection.rsplit("/", 1)[0] + "/" + item.lstrip("./")
    return get(item)["assets"]["aws"]["href"]


def proposed_box(lon: float, lat: float, size: float = BOX_DEG) -> list[float]:
    """[south, west, north, east] of a square of `size` degrees centred on the point."""
    h = size / 2
    return [round(lat - h, 5), round(lon - h, 5), round(lat + h, 5), round(lon + h, 5)]


def connect():
    """A DuckDB connection that can install its httpfs extension even when the process has no home directory (the hosted
    app runs as a system service without one; QA 2026-10-07 rank 5: "Can't find the home directory at ''")."""
    import os
    import tempfile
    import duckdb
    home = os.environ.get("HOME") or os.path.join(tempfile.gettempdir(), "traffictwin-duckdb")
    os.makedirs(home, exist_ok=True)
    con = duckdb.connect(config={"home_directory": home})       # at creation: the automatic install inside read_parquet ignores a later SET
    con.execute("INSTALL httpfs")
    con.execute("LOAD httpfs")
    return con


def _names(primary: str | None, common) -> dict:
    """A division's names in the app's languages (and English), from Overture's own record; none is translated by us."""
    common = dict(common or {})
    out = {lang: common[lang] for lang in set(app_languages()) | {"en"} if common.get(lang)}
    if primary:
        out.setdefault("en", primary)
    return out


def _query(name: str, release: str) -> list[dict]:
    """Two passes over the file: the places with this name, then the country records of the countries found (the
    driving side is stored on the country). Matching every language's name for every place needs the whole names
    column and took more than ten minutes, so a place is matched on its main name, its English name, or its name
    in a language the app ships."""
    url = divisions_file(release)
    con = connect()
    languages = sorted(set(app_languages()) | {"en"})
    by_language = " or ".join(f"lower(names.common['{lang}']) = lower($1)" for lang in languages if lang.isalpha())
    rows = con.execute(f"""
        select id, names.primary, names.common, subtype, country, region, population, bbox.xmin, bbox.ymin
        from read_parquet('{url}')
        where subtype in {PLACE_TYPES} and (lower(names.primary) = lower($1) or {by_language})""", [name]).fetchall()
    countries = sorted({r[4] for r in rows if r[4]})
    side, country_names = {}, {}
    if countries:
        for country, driving_side, cprimary, ccommon in con.execute(f"select country, norms.driving_side, names.primary, names.common from read_parquet('{url}') where subtype = 'country' and country in ({','.join('?' * len(countries))})", countries).fetchall():
            side[country] = driving_side
            country_names[country] = _names(cprimary, ccommon)
    regions = sorted({r[5] for r in rows if r[5]})                  # the region's own names, from the same file, so a code like BD-G reads as its name
    region_names = {region: _names(rprimary, rcommon) for region, rprimary, rcommon in con.execute(
        f"select region, names.primary, names.common from read_parquet('{url}') where subtype = 'region' and region in ({','.join('?' * len(regions))})", regions).fetchall()} if regions else {}
    out = []
    for did, primary, common, subtype, country, region, population, lon, lat in rows:
        common = dict(common or {})
        names = {lang: common[lang] for lang in app_languages() if common.get(lang)}
        names.setdefault("en", common.get("en") or primary)
        out.append({"division_id": did, "name": names["en"], "main_name": primary, "display_name": names, "kind": subtype, "country": country, "region": region,
                    "country_names": country_names.get(country, {}), "region_names": region_names.get(region, {}),
                    "population": population, "lon": round(lon, 6), "lat": round(lat, 6), "drive_side": side.get(country),
                    "proposed_box": proposed_box(lon, lat), "release": release, "source": f"Overture Maps divisions theme, release {release}, division {did}"})
    return sorted(out, key=lambda c: -(c["population"] or 0))[:MAX_RESULTS]


def search(name: str, release: str | None = None, cache: Path = CACHE) -> dict:
    """Candidates for a city name, most populous first, each with a proposed box. Cached per name and release."""
    name = " ".join(name.split())
    if len(name) < 2:
        return {"query": name, "candidates": [], "note": "type at least two letters"}
    if release is None:
        from core.simulation.twin import buildings_source
        release = buildings_source.source()["release"]
    store = json.loads(cache.read_text()) if cache.exists() else {}
    key = f"{release}|v2|{name.lower()}"                                  # v2: candidates carry the country's and region's own names
    if key not in store:
        t0 = time.time()
        store[key] = {"query": name, "release": release, "candidates": _query(name, release), "searched_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                      "seconds": round(time.time() - t0, 1), "attribution": ATTRIBUTION}
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(store, ensure_ascii=False, indent=1))
    return {**store[key], "cached": "seconds" in store[key] and key in store, "box_deg": BOX_DEG}
