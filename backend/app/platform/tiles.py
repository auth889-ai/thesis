"""Our own map tiles for the trip pack: one PMTiles file per city, built with Planetiler (Apache-2.0) from the city's
OpenStreetMap extract (infra/tiles/build.sh) and kept in the routing bucket. The browser reads it through the pmtiles
protocol with HTTP Range requests. A local copy (data/tiles/<city>/basemap.pmtiles, fetched once and checked against the build's
sha256 in evidence/tiles/TILES_BASEMAP.txt) is served from disk first, so the app on this laptop needs no AWS session; without one,
each Range is forwarded to S3 (the bucket keeps public access blocked; the hosted app). A city with neither has no offline map, and
the answer says so. OpenFreeMap (normal viewing) is never read through here."""
from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path

BUCKET_PREFIX = "dhakaflow-routing-"
REGION = "ap-south-1"
MAGIC = b"PMTiles"
CACHE_CONTROL = "public, max-age=86400"


def bucket() -> str | None:
    """The routing bucket: named from the account, or set outright (the hosted app, the tests)."""
    from core.common import credentials
    explicit = credentials.load("TRAFFICTWIN_TILES_BUCKET") or os.environ.get("TRAFFICTWIN_TILES_BUCKET")
    if explicit:
        return explicit
    try:
        import boto3
        return BUCKET_PREFIX + boto3.client("sts").get_caller_identity()["Account"]
    except Exception:                                   # noqa: BLE001 - no AWS session on this machine: no own tiles
        return None


LOCAL = Path(__file__).resolve().parents[3] / "data/tiles"


def local_file(city_id: str) -> Path | None:
    """The city's local PMTiles copy, if there is one (a city id is a plain name: no path tricks)."""
    if not re.fullmatch(r"[a-z0-9_]+", city_id):
        return None
    f = LOCAL / city_id / "basemap.pmtiles"
    return f if f.is_file() else None


def parse_range(header: str | None, size: int) -> tuple[int, int] | None:
    """(first, last) inclusive byte offsets of a single 'bytes=a-b' / 'bytes=a-' / 'bytes=-n' range, clipped to the file. Pure."""
    m = re.fullmatch(r"bytes=(\d*)-(\d*)", (header or "").strip())
    if not m or (m[1] == "" and m[2] == ""):
        return None
    if m[1] == "":
        n = int(m[2]); return (max(0, size - n), size - 1)
    a, b = int(m[1]), (int(m[2]) if m[2] else size - 1)
    return (a, min(b, size - 1)) if a <= b and a < size else None


def key(city_id: str) -> str:
    return f"tiles/{city_id}/basemap.pmtiles"


@lru_cache(maxsize=16)
def info(city_id: str) -> dict:
    """Whether the city has a PMTiles file, and its size (the local copy, else one HEAD on S3, remembered while the app runs)."""
    f = local_file(city_id)
    if f:
        return {"city_id": city_id, "available": True, "bytes": f.stat().st_size, "source": "local copy", "path": str(f.relative_to(LOCAL.parents[1]))}
    b = bucket()
    if not b:
        return {"city_id": city_id, "available": False, "reason": "no data for this city: no AWS session on this machine, so the own tiles cannot be read"}
    try:
        import boto3
        head = boto3.client("s3", region_name=REGION).head_object(Bucket=b, Key=key(city_id))
        return {"city_id": city_id, "available": True, "bytes": head["ContentLength"], "etag": head.get("ETag"), "bucket": b, "key": key(city_id)}
    except Exception as exc:                            # noqa: BLE001
        return {"city_id": city_id, "available": False, "reason": f"no offline map for this city: {type(exc).__name__}"}


def read_range(city_id: str, range_header: str | None) -> tuple[int, bytes, dict]:
    """(status, body, headers): the requested byte range of the city's PMTiles file from S3, as the pmtiles protocol asks for it."""
    meta = info(city_id)
    if not meta["available"]:
        return 404, meta["reason"].encode(), {"Content-Type": "text/plain"}
    f = local_file(city_id)
    if f:
        size = f.stat().st_size
        headers = {"Content-Type": "application/octet-stream", "Accept-Ranges": "bytes", "Cache-Control": CACHE_CONTROL, "ETag": f'"{size}-{int(f.stat().st_mtime)}"'}
        rng = parse_range(range_header, size)
        if range_header and rng is None:
            return 416, b"", {**headers, "Content-Range": f"bytes */{size}"}
        a, z = rng or (0, size - 1)
        with f.open("rb") as fh:
            fh.seek(a)
            body = fh.read(z - a + 1)
        if rng:
            return 206, body, {**headers, "Content-Range": f"bytes {a}-{z}/{size}"}
        return 200, body, headers
    import boto3
    s3 = boto3.client("s3", region_name=REGION)
    kwargs = {"Bucket": meta["bucket"], "Key": meta["key"]}
    if range_header:
        kwargs["Range"] = range_header
    obj = s3.get_object(**kwargs)
    body = obj["Body"].read()
    headers = {"Content-Type": "application/octet-stream", "Accept-Ranges": "bytes", "Cache-Control": CACHE_CONTROL, "ETag": obj.get("ETag", "")}
    if range_header and obj.get("ContentRange"):
        headers["Content-Range"] = obj["ContentRange"]
        return 206, body, headers
    return 200, body, headers
