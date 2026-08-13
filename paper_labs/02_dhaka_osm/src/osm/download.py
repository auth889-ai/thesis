"""OSM acquisition via the official Overpass API, with full provenance."""
from __future__ import annotations

import datetime
import hashlib
import json
import urllib.request
from pathlib import Path

DEFAULT_ENDPOINT = "https://overpass-api.de/api/interpreter"

#: Public Overpass instances, tried in order. All serve the same OpenStreetMap
#: database; using a mirror changes throughput, never the data source. The
#: endpoint actually used is recorded in the manifest.
OVERPASS_MIRRORS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.osm.jp/api/interpreter",
)


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
                 endpoint: str | None = None, attempts_per_mirror: int = 2) -> dict:
    """Fetch the extract, rotating over public Overpass mirrors on 429/504/timeout.

    Every mirror serves the same OSM database; the one used is recorded so the
    download stays fully traceable.
    """
    import time

    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    query = overpass_query(bbox)
    endpoints = [endpoint] if endpoint else list(OVERPASS_MIRRORS)
    t0 = datetime.datetime.now(datetime.timezone.utc)

    used_endpoint, errors = None, []
    for ep in endpoints:
        for attempt in range(attempts_per_mirror):
            try:
                req = urllib.request.Request(
                    ep, data=query.encode(),
                    headers={"User-Agent": "DhakaFlowNexus-Lab02/1.0"})
                with urllib.request.urlopen(req, timeout=300) as r, open(dest, "wb") as f:
                    while True:
                        chunk = r.read(1 << 20)
                        if not chunk:
                            break
                        f.write(chunk)
                if dest.stat().st_size < 5000:
                    raise RuntimeError(f"suspiciously small extract "
                                       f"({dest.stat().st_size} bytes)")
                used_endpoint = ep
                break
            except Exception as exc:                      # noqa: BLE001 - reported
                errors.append(f"{ep} attempt {attempt + 1}: {type(exc).__name__}: {exc}")
                time.sleep(5 * (attempt + 1))
        if used_endpoint:
            break
    if not used_endpoint:
        raise RuntimeError("all Overpass endpoints failed:\n  " + "\n  ".join(errors))

    manifest = {
        "source": "OpenStreetMap via Overpass API",
        "endpoint": used_endpoint,
        "endpoints_tried": endpoints[:endpoints.index(used_endpoint) + 1],
        "transient_errors": errors,
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
