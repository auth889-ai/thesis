"""data/MANIFEST.yaml: every folder kept off the Mac can be brought back, and nothing in it is code."""
from __future__ import annotations

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("offload", REPO / "scripts/storage/offload.py")
offload = importlib.util.module_from_spec(spec)
spec.loader.exec_module(offload)


def test_every_entry_can_be_restored():
    m = offload.load()
    assert m["drive_remote"] and m["drive_root"] and m["keep_local_bytes"] >= 1 << 20
    for e in m["entries"]:
        assert e["class"] in ("public", "ours", "document"), e
        if e["class"] == "public":
            assert e.get("source") and e.get("licence"), e        # public data names where it came from and under what licence
        assert offload.remote(m, e["path"]).startswith(f"{m['drive_remote']}:{m['drive_root']}/")  # and has a Drive copy


def test_no_entry_holds_code():
    for e in offload.load()["entries"]:
        p = e["path"]
        assert not p.startswith(("core", "backend", "frontend", "scripts", "research", "config", "tests")), p


def test_drive_paths_keep_where_a_folder_came_from():
    m = {"drive_remote": "r", "drive_root": "root"}
    assert offload.remote(m, "results/v2x") == "r:root/thesis/results/v2x"
    assert offload.remote(m, "~/Documents/blobs") == "r:root/home/Documents/blobs"


def test_only_large_files_are_candidates_for_removal(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "a/summary.json").write_text("{}")
    (tmp_path / "a/run.xml").write_bytes(b"x" * (1 << 20))
    (tmp_path / "link").symlink_to(tmp_path / "a/run.xml")
    assert [p.name for p in offload.large_files(tmp_path, 1 << 20)] == ["run.xml"]


aspec = importlib.util.spec_from_file_location("archive", REPO / "scripts/storage/archive.py")
archive = importlib.util.module_from_spec(aspec)
aspec.loader.exec_module(archive)


def test_busy_folders_go_as_one_archive_each_with_distinct_names():
    m = {"drive_remote": "r", "drive_root": "root"}
    assert archive.drive_path(m, "results/v2x") == "r:root/archives/results__v2x.tar.zst"
    assert archive.name_of("~/.dhakaflow/upstream/mosaic/logs") == ".dhakaflow__upstream__mosaic__logs"
    names = [archive.name_of(e["path"]) for e in offload.load()["entries"] if e.get("archive")]
    assert names and len(names) == len(set(names))


def test_hash_list_covers_every_file_but_not_links(tmp_path):
    (tmp_path / "d/sub").mkdir(parents=True)
    (tmp_path / "d/a.txt").write_text("a")
    (tmp_path / "d/sub/b.txt").write_text("b")
    (tmp_path / "d/link").symlink_to(tmp_path / "d/a.txt")
    out = tmp_path / "files.md5"
    assert archive.file_hashes(tmp_path / "d", out) == 2
    assert out.read_text().splitlines()[0] == "0cc175b9c0f1b6a831c399e269772661  d/a.txt"
