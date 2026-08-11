"""OSM acquisition via the official Overpass API, with full provenance."""
from __future__ import annotations

import datetime
import hashlib
import json
import urllib.request
from pathlib import Path

DEFAULT_ENDPOINT = "https://overpass-api.de/api/interpreter"


def overpass_query(bbox: dict) -> str:
    """All highway ways + their nodes in bbox. bbox keys: south west north east."""
    b = f"{bbox['south']},{bbox['west']},{bbox['north']},{bbox['east']}"
    return (
        f"[out:xml][timeout:180];"
        f"(way[\"highway\"]({b}););"
        f"(._;>;);"
        f"out body;"
    )


def sha256_file(p: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def download_osm(bbox: dict, dest: Path, manifest_path: Path,
                 endpoint: str = DEFAULT_ENDPOINT) -> dict:
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    query = overpass_query(bbox)
    req = urllib.request.Request(
        endpoint, data=query.encode(),
        headers={"User-Agent": "DhakaFlowNexus-Lab02/1.0"})
    t0 = datetime.datetime.now(datetime.timezone.utc)
    with urllib.request.urlopen(req, timeout=300) as r, open(dest, "wb") as f:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
    manifest = {
        "source": "OpenStreetMap via Overpass API",
        "endpoint": endpoint,
        "query": query,
        "bbox": bbox,
        "downloaded_utc": t0.isoformat(),
        "bytes": dest.stat().st_size,
        "sha256": sha256_file(dest),
        "license": "ODbL 1.0 (OpenStreetMap contributors)",
    }
    manifest_path = Path(manifest_path)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2))
    return manifest
