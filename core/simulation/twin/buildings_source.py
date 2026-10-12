"""Where the worldwide 3D buildings come from: Overture Maps' buildings theme, as public PMTiles.

Overture publishes one file per release and removes old releases, so the address is looked up, not written down:
the release catalogue names the latest release, and the file is checked before it is offered. When the catalogue or
the file cannot be reached, the last release known to work is used, and the answer says so.

Buildings with no recorded height are drawn at an assumed height and labelled "estimated height". The two assumed
numbers are the same ones the city scene uses (`twin/scene.py`), so there is one rule in the project.

Licence of the data: ODbL. Attribution the map must show: OpenStreetMap contributors and the Overture Maps Foundation;
the buildings theme also draws on Microsoft, Google Open Buildings (CC BY 4.0), Esri Community Maps and others, listed
at https://docs.overturemaps.org/attribution/ (read 2026-10-05).
"""
from __future__ import annotations

import json
import os
import time
import urllib.request

from core.simulation.twin.scene import DEFAULT_M, LEVEL_M

CATALOGUE = "https://stac.overturemaps.org/catalog.json"
TILES = "https://overturemaps-extras-us-west-2.s3.us-west-2.amazonaws.com/tiles/{release}/buildings.pmtiles"
KNOWN_RELEASE = "2026-09-23.1"                       # read tile by tile on 2026-10-05 (evidence/basemap/comparison.json)
ATTRIBUTION = ('<a href="https://www.openstreetmap.org/copyright" target="_blank">© OpenStreetMap contributors</a>, '
               '<a href="https://docs.overturemaps.org/attribution/" target="_blank">Overture Maps Foundation</a>')
OFFLINE_ENV = "DHAKAFLOW_NO_OBSERVATORY"             # set in tests and in the container: no outside request is made
TTL_S = 24 * 3600
_cache: dict = {}


def _get(url: str, headers: dict | None = None) -> tuple[int, bytes]:
    req = urllib.request.Request(url, headers={"User-Agent": "dhakaflow/1.0", **(headers or {})})
    with urllib.request.urlopen(req, timeout=6) as r:
        return r.status, r.read()


def latest_release() -> str:
    """The newest release whose buildings file answers; raises when the catalogue or the file cannot be reached."""
    release = json.loads(_get(CATALOGUE)[1])["latest"]
    status, head = _get(TILES.format(release=release), {"Range": "bytes=0-6"})
    if status not in (200, 206) or head[:7] != b"PMTiles":
        raise OSError(f"no buildings file for release {release}")
    return release


def source() -> dict:
    """What the browser needs to draw the buildings, and how the address was found."""
    now = time.time()
    if _cache and now - _cache["at"] < TTL_S:
        return _cache["value"]
    release, found = KNOWN_RELEASE, "the last release known to work (the catalogue was not asked)"
    if not os.environ.get(OFFLINE_ENV):
        try:
            release, found = latest_release(), "the latest release in Overture's catalogue"
        except Exception as exc:                        # noqa: BLE001 - the map still gets buildings, and says which
            found = f"the last release known to work (the catalogue could not be read: {type(exc).__name__})"
    value = {"provider": "overture", "release": release, "url": TILES.format(release=release), "found": found, "source_layer": "building",
             "attribution": ATTRIBUTION, "licence": "ODbL", "minzoom": 14,
             "heights": {"rule": "recorded height; else recorded floors x storey height; else a default", "assumed_storey_m": LEVEL_M, "assumed_default_m": DEFAULT_M}}
    _cache.update(at=now, value=value)
    return value
