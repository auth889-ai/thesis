"""Our own PMTiles basemap through the app: the browser's Range is forwarded to S3 and answered 206 with cache headers; a city without a
file answers 404 with the reason; the bucket name is never guessed when there is no AWS session."""
from __future__ import annotations

import io
import sys
import types

from fastapi.testclient import TestClient

from app.main import app
from app.platform import tiles


class FakeS3:
    def __init__(self, data: bytes):
        self.data, self.calls = data, []
    def head_object(self, Bucket, Key):
        if "nowhere" in Key:
            raise KeyError("NoSuchKey")
        return {"ContentLength": len(self.data), "ETag": '"e"'}
    def get_object(self, Bucket, Key, Range=None):
        self.calls.append(Range)
        a, b = (int(x) for x in Range.removeprefix("bytes=").split("-"))
        return {"Body": io.BytesIO(self.data[a:b + 1]), "ContentRange": f"bytes {a}-{b}/{len(self.data)}", "ETag": '"e"'}


def test_range_forwarded_and_missing_city_refused(monkeypatch, tmp_path):
    monkeypatch.setattr(tiles, "LOCAL", tmp_path)          # no local copy here: the test is about the S3 path (data/tiles/ has the real files since 2026-10-10)
    data = b"PMTiles\x03" + bytes(2000)
    s3 = FakeS3(data)
    monkeypatch.setitem(sys.modules, "boto3", types.SimpleNamespace(client=lambda *a, **k: s3))
    monkeypatch.setenv("TRAFFICTWIN_TILES_BUCKET", "dhakaflow-routing-test")
    tiles.info.cache_clear()
    c = TestClient(app)
    r = c.get("/api/tiles/dhaka/basemap.pmtiles", headers={"Range": "bytes=0-15"})
    assert r.status_code == 206 and r.content[:7] == b"PMTiles" and len(r.content) == 16
    assert r.headers["accept-ranges"] == "bytes" and "max-age" in r.headers["cache-control"] and r.headers["content-range"] == "bytes 0-15/2008"
    assert s3.calls == ["bytes=0-15"]
    miss = c.get("/api/tiles/nowhere/basemap.pmtiles", headers={"Range": "bytes=0-15"})
    assert miss.status_code == 404 and b"no offline map" in miss.content
    assert c.get("/api/tiles/dhaka/info").json()["available"] is True
    tiles.info.cache_clear()
