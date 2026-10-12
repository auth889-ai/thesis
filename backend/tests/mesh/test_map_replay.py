"""The mesh study on the map: the study's own phones and positions, contacts within the study's radio range, sha256 as recorded."""
from __future__ import annotations

import hashlib
import math

import pytest
from fastapi.testclient import TestClient

from app.main import app
from core.common.paths import REPO
from core.networking.mesh.map_replay import contacts

client = TestClient(app)
F = REPO / "results/networking/mesh/dhaka/map_replay.json"


def test_contacts_are_pairs_within_range():
    pos = {"a": (0.0, 0.0), "b": (6.0, 8.0), "c": (30.0, 0.0)}
    assert contacts(pos, 10) == [("a", "b")]
    assert contacts(pos, 9.9) == []


def test_city_without_mesh_study_says_no_data():
    r = client.get("/api/mesh/replay/berlin").json()
    assert r["available"] is False and "no data" in r["reason"]


@pytest.mark.skipif(not F.exists(), reason="not built: python -m core.networking.mesh.map_replay")
def test_dhaka_replay_matches_its_evidence_and_the_study():
    want = (REPO / "evidence/mesh/dhaka/map_replay/SHA256SUMS").read_text().split()[0]
    assert hashlib.sha256(F.read_bytes()).hexdigest() == want
    r = client.get("/api/mesh/replay/dhaka").json()
    assert r["available"] and r["label"] == "SIMULATED" and r["phones"] == 17 and len(r["frames"]) == 300
    assert r["plain"]["vehicles"] == 17
    rng = r["radio"]["range_m"]
    for fr in r["frames"][::25]:
        for a, b in fr["contacts"]:
            (x1, y1), (x2, y2) = fr["phones"][a], fr["phones"][b]
            d = math.dist((x1 * 111320 * math.cos(math.radians(y1)), y1 * 110540), (x2 * 111320 * math.cos(math.radians(y2)), y2 * 110540))
            assert d <= rng * 1.05 + 1                          # lon/lat back to metres, approximately
