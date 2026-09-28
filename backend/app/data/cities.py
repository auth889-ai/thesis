"""Cities created at runtime, not enumerated in source.

The old design hard-coded sixteen Dhaka places and twelve corridor pairs, so the application could
never be larger than that list. Here a city is created from a NAME (geocoded through OSM) or a
BOUNDING BOX (drawn on the map), its road graph is built on demand, and its capabilities are
derived from whatever data actually exists for it.

Three cities are seeded, and they are seeded because they carry EVIDENCE this project produced —
not to privilege them. Anything else the user asks for is created the same way at runtime.

Specs and graphs live under `data/cities/`, which is gitignored: a city is derived data, rebuildable
from its spec, and does not belong in version control.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .city_graph import CityGraph
from .city_spec import Capability, CityCapabilities, CitySpec

from app.paths import REPO
CITY_DIR = REPO / "data/cities"


def slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return s or "city"


class CityRegistry:
    """Create, persist and describe cities. No city is special-cased."""

    def __init__(self, root: Path = CITY_DIR):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------ discovery
    def list_ids(self) -> list[str]:
        return sorted(p.name for p in self.root.iterdir()
                      if p.is_dir() and (p / "spec.json").exists())

    def get(self, city_id: str) -> CitySpec | None:
        f = self.root / city_id / "spec.json"
        return CitySpec.from_dict(json.loads(f.read_text())) if f.exists() else None

    def save(self, spec: CitySpec) -> CitySpec:
        spec.created_utc = spec.created_utc or datetime.now(timezone.utc).isoformat()
        spec.save(self.root / spec.city_id / "spec.json")
        return spec

    # -------------------------------------------------------------- create
    def create_from_bbox(self, name: str, bbox: tuple[float, float, float, float],
                         **kw) -> CitySpec:
        """bbox is (south, west, north, east) — the convention used throughout this project."""
        s, w, n, e = bbox
        spec = CitySpec(city_id=kw.pop("city_id", None) or slug(name), display_name=name,
                        bbox=(s, w, n, e), center=((s + n) / 2, (w + e) / 2),
                        source="bbox", **kw)
        return self.save(spec)

    def create_from_name(self, name: str, **kw) -> CitySpec:
        """Geocode a place name through OSM/Nominatim and take its bounding box.

        This is what makes the system city-agnostic in practice: the user types a city and the
        system finds it, instead of an engineer adding a constant.
        """
        import osmnx as ox
        gdf = ox.geocode_to_gdf(name)
        if gdf.empty:
            raise ValueError(f"no place found for {name!r}")
        row = gdf.iloc[0]
        b = row.geometry.bounds                       # (minx, miny, maxx, maxy) = (w, s, e, n)
        bbox = (float(b[1]), float(b[0]), float(b[3]), float(b[2]))
        display = str(row.get("display_name", name))
        country = display.split(",")[-1].strip() if "," in display else ""
        spec = CitySpec(city_id=kw.pop("city_id", None) or slug(name), display_name=name,
                        country=country, bbox=bbox,
                        center=((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2),
                        source="geocoded", **kw)
        return self.save(spec)

    def ensure(self, name: str, **kw) -> CitySpec:
        cid = kw.get("city_id") or slug(name)
        return self.get(cid) or self.create_from_name(name, **kw)

    # --------------------------------------------------------------- graph
    def graph_dir(self, city_id: str) -> Path:
        return self.root / city_id / "graph"

    def has_graph(self, city_id: str) -> bool:
        return (self.graph_dir(city_id) / "nodes.json").exists()

    def build_graph(self, city_id: str, max_nodes: int = 250) -> dict:
        spec = self.get(city_id)
        if not spec:
            raise ValueError(f"unknown city {city_id!r}")
        g = CityGraph.build(city_id, bbox=spec.bbox, place=None if spec.bbox else spec.display_name,
                            max_nodes=max_nodes)
        summary = g.save(self.graph_dir(city_id))
        spec.osm_graph = str(self.graph_dir(city_id).relative_to(REPO))
        self.save(spec)
        return summary

    def graph_summary(self, city_id: str) -> dict | None:
        f = self.graph_dir(city_id) / "graph_summary.json"
        return json.loads(f.read_text()) if f.exists() else None

    def nodes(self, city_id: str) -> list[dict]:
        f = self.graph_dir(city_id) / "nodes.json"
        return json.loads(f.read_text()) if f.exists() else []

    # -------------------------------------------------------- capabilities
    def capabilities(self, city_id: str, catalog: dict | None = None) -> CityCapabilities:
        """Derived from evidence on disk — never asserted.

        `catalog` is the dataset catalog (src/pipeline/city/datasets.py); passing it lets a city that
        corresponds to a research dataset inherit that dataset's node count, exposure and
        reproduction verdict.
        """
        spec = self.get(city_id)
        cap = CityCapabilities()
        if not spec:
            return cap
        cap.has_live_provider = bool(spec.traffic_provider)
        cap.has_sumo_network = bool(spec.sumo_network and (REPO / spec.sumo_network).exists())

        entry = (catalog or {}).get(spec.dataset_adapter or "")
        if entry:
            cap.has_historical_dataset = True
            cap.dataset_nodes = entry.get("nodes")
            cap.dataset_timesteps = entry.get("timesteps")
            cap.in_foundation_pretraining = entry.get("in_opencity_pretraining")
            cap.schema_satisfies_foundation = entry.get("opencity_schema_ok")
            cap.blocking.extend(entry.get("opencity_schema_blocking") or [])
            cap.foundation_model = "OpenCity-plus" if entry.get("opencity_verdict") else None
            cap.reproduction_verdict = entry.get("opencity_verdict")
            cap.city_specific_models = list(entry.get("city_specific_models") or [])
        else:
            cap.blocking.append(
                "no historical dataset is registered for this city, so no forecast model can be "
                "evaluated on it — the system reports LIVE_ONLY rather than inventing one")
        if not cap.has_live_provider:
            cap.blocking.append("no live traffic provider is configured for this city")
        return cap

    def describe(self, city_id: str, catalog: dict | None = None) -> dict:
        spec = self.get(city_id)
        if not spec:
            return {"error": "unknown_city", "city_id": city_id}
        cap = self.capabilities(city_id, catalog)
        d = spec.to_dict()
        d["capabilities"] = cap.explain()
        d["forecast_capability"] = cap.best.value
        d["graph"] = self.graph_summary(city_id)
        d["graph_built"] = self.has_graph(city_id)
        return d


registry = CityRegistry()
