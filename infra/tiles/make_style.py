"""Our own map style for the trip pack: OpenFreeMap's "liberty" style (BSD-3-Clause, from OSM Bright) with every remote reference
replaced by ours: the OpenMapTiles-schema vector source becomes our PMTiles file (__PMTILES__, filled per city at run time), the
sprite and the Noto glyphs are served from this app. The Natural Earth shaded-relief raster (an OpenFreeMap raster) is dropped.
    python infra/tiles/make_style.py        # frontend/public/liberty/style.src.json -> frontend/public/liberty/style.json
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "frontend/public/liberty"
src = json.loads((ROOT / "style.src.json").read_text())
src["name"] = "TrafficTwin own tiles (liberty)"
src["sprite"] = "/liberty/sprite/ofm"
src["glyphs"] = "/fonts/{fontstack}/{range}.pbf"
src["sources"] = {"openmaptiles": {"type": "vector", "url": "__PMTILES__", "attribution": "© OpenStreetMap contributors (ODbL) · tiles built with Planetiler"}}
src["layers"] = [l for l in src["layers"] if l.get("source") in (None, "openmaptiles")]
(ROOT / "style.json").write_text(json.dumps(src, indent=1))
print(f"{len(src['layers'])} layers -> {ROOT / 'style.json'}")
