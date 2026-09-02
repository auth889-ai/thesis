from __future__ import annotations

import hashlib
import json
from pathlib import Path

from results.build_asset_manifest import build_manifest
from legacy.scripts.restore_assets import main as restore_main


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_build_asset_manifest_records_existing_known_assets(tmp_path: Path):
    net = tmp_path / "paper_labs/02_dhaka_osm/outputs/lab02_v2/network/dhaka_r1.net.xml"
    net.parent.mkdir(parents=True)
    net.write_text("<net/>")

    manifest = build_manifest(tmp_path)

    assert manifest["schema"] == "dhakaflow.asset-manifest.v1"
    assert manifest["assets"] == [
        {
            "path": "paper_labs/02_dhaka_osm/outputs/lab02_v2/network/dhaka_r1.net.xml",
            "bytes": 6,
            "sha256": _sha(b"<net/>"),
            "category": "frozen-network",
            "required_for": "make results / active rebuild demo",
        }
    ]


def test_restore_assets_copies_and_verifies_from_source(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    source = tmp_path / "asset-root"
    rel = Path("data/forecasting/dhaka_twin/data.npz")
    payload = b"asset bytes"
    (source / rel).parent.mkdir(parents=True)
    (source / rel).write_bytes(payload)
    manifest = {
        "schema": "dhakaflow.asset-manifest.v1",
        "assets": [{"path": str(rel), "sha256": _sha(payload), "bytes": len(payload)}],
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest))
    monkeypatch.setattr(
        "sys.argv",
        ["restore_assets.py", "--repo", str(repo), "--manifest", str(manifest_path), "--source", str(source)],
    )

    assert restore_main() == 0
    assert (repo / rel).read_bytes() == payload


def test_restore_assets_fails_on_mismatch(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    rel = Path("results/routing/arms_h7200.json")
    (repo / rel).parent.mkdir(parents=True)
    (repo / rel).write_text("{}")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps({"schema": "dhakaflow.asset-manifest.v1", "assets": [{"path": str(rel), "sha256": "0" * 64}]})
    )
    monkeypatch.setattr(
        "sys.argv",
        ["restore_assets.py", "--repo", str(repo), "--manifest", str(manifest_path), "--check-only"],
    )

    assert restore_main() == 1
