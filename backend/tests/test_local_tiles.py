"""Own basemap tiles from a local copy: byte ranges served from disk, no AWS session needed."""
from __future__ import annotations

from app.platform import tiles


def test_parse_range():
    assert tiles.parse_range("bytes=0-99", 1000) == (0, 99)
    assert tiles.parse_range("bytes=900-", 1000) == (900, 999)
    assert tiles.parse_range("bytes=-10", 1000) == (990, 999)
    assert tiles.parse_range("bytes=950-2000", 1000) == (950, 999)
    assert tiles.parse_range("bytes=2000-", 1000) is None
    assert tiles.parse_range("items=0-1", 1000) is None


def test_local_copy_is_served_by_range_without_aws(tmp_path, monkeypatch):
    (tmp_path / "testcity").mkdir()
    data = b"PMTiles" + bytes(range(256)) * 4
    (tmp_path / "testcity" / "basemap.pmtiles").write_bytes(data)
    monkeypatch.setattr(tiles, "LOCAL", tmp_path)
    monkeypatch.setattr(tiles, "bucket", lambda: (_ for _ in ()).throw(AssertionError("S3 must not be asked")))
    tiles.info.cache_clear()
    assert tiles.info("testcity")["source"] == "local copy"
    status, body, headers = tiles.read_range("testcity", "bytes=0-6")
    assert status == 206 and body == b"PMTiles" and headers["Content-Range"] == f"bytes 0-6/{len(data)}"
    assert tiles.read_range("testcity", None)[1] == data
    assert tiles.read_range("testcity", "bytes=99999-")[0] == 416
    tiles.info.cache_clear()


def test_city_id_cannot_leave_the_tiles_folder():
    assert tiles.local_file("../etc") is None and tiles.local_file("dhaka/../x") is None
