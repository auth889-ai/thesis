"""The street base map and the satellite picture: where each comes from and the credit each requires.

Street map: OpenFreeMap's "liberty" style, OpenStreetMap vector tiles in the OpenMapTiles schema, served with no key
and no account. Its terms of service (https://openfreemap.org/tos/, read 2026-10-05) provide it "AS-IS", say it may be
discontinued "at any time without notice", and forbid collecting data from it "in automated ways without permission".
The browser removes the style's own building layers: buildings are drawn from Overture Maps (`buildings_source.py`),
where a height that was not recorded is shown as estimated.

Satellite: "Sentinel-2 cloudless layer for 2016 by EOX", which the service's own description says is "released under
Creative Commons Attribution 4.0 International License" (https://tiles.maps.eox.at/wmts/1.0.0/WMTSCapabilities.xml,
read 2026-10-05). It is a composite of images captured during 2016 at 10 metres per pixel: not one date, not live, and
a blur at street level. The later years' layers carry a non-commercial licence or are simply not needed; none is used.
"""
from __future__ import annotations

STREETS = {
    "provider": "openfreemap",
    "style": "https://tiles.openfreemap.org/styles/liberty",
    "attribution": ('<a href="https://openfreemap.org" target="_blank">OpenFreeMap</a> '
                    '<a href="https://www.openmaptiles.org/" target="_blank">© OpenMapTiles</a> '
                    'Data from <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap</a>'),
    "licence": "OpenStreetMap data: ODbL; OpenFreeMap terms of service: https://openfreemap.org/tos/",
}

SATELLITE = {
    "provider": "eox-s2cloudless-2016",
    "tiles": "https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless_3857/default/g/{z}/{y}/{x}.jpg",
    "attribution": ('<a href="https://s2maps.eu" target="_blank">Sentinel-2 cloudless</a> by '
                    '<a href="https://eox.at" target="_blank">EOX IT Services GmbH</a> (Contains modified Copernicus Sentinel data 2016)'),
    "licence": "CC BY 4.0",
    "captured": "2016",                      # a composite of that year's captures, not one date
    "composite": True,
    "resolution_m": 10,
    "maxzoom": 14,                           # beyond this the same pixels are only stretched
}
