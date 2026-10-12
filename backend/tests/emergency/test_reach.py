"""Ambulance reach: the grid, the matrix decomposition (a path through a recorded site is delayed by exactly the stretch's delta; one that does
not pass is untouched), the plain numbers from the same per-point times as the table, and honest refusals."""
from __future__ import annotations

import json
from pathlib import Path

from core.safety import reach


def test_grid_covers_the_extent_at_the_step():
    pts = reach.grid([90.30, 23.66, 90.32, 23.68], 500)          # about 2.0 km x 2.2 km
    assert 12 <= len(pts) <= 20
    assert all(90.30 <= lon <= 90.32 and 23.66 <= lat <= 23.68 for lat, lon in pts)


def test_decomposition_delays_only_the_paths_through_the_site():
    t_ht = [[100, 300, None]]                                      # one hospital, three points; the third unreachable
    t_hs = [[120]]                                                 # hospital -> site
    t_st = [[400, 170, 50]]                                        # site -> each point: via the site costs 520 / 290 / -
    times, changed = reach.decompose(t_ht, t_hs, t_st, [45.0], tol=30)
    assert times == [[100, 345.0, None]] and changed == [1]      # 120+170 = 290 <= 300+30 passes; 120+400 = 520 > 130 does not


def test_plain_numbers_come_from_the_per_point_times():
    best = [60, 500, 1300, None, 1900]
    p = reach.plain_numbers(best, None, 5)
    assert p == {"map_pct": {"10": 40.0, "20": 40.0, "30": 60.0}, "recorded_pct": None, "grid_points": 5}   # 60 and 500 s within 10 min; 1300 s within 30


def test_the_built_dhaka_sentence_matches_its_table():
    f = Path(reach.RESULTS) / "dhaka/summary.json"
    if not f.exists():
        import pytest
        pytest.skip("no built reach for dhaka on this machine")
    d = json.loads(f.read_text())
    best_map = [p["map_s"] for p in d["points"]]
    best_rec = [p["recorded_s"] for p in d["points"]] if d["recorded"]["sites"] else None
    assert d["plain"] == reach.plain_numbers(best_map, best_rec, len(d["points"]))
    assert sum(r["map_cells"]["30"] for r in d["rows"]) >= sum(1 for t in best_map if t is not None and t <= 1800)


def test_refusals_say_no_data(tmp_path, monkeypatch):
    monkeypatch.setattr(reach.hosp, "load", lambda c, root=None: None)
    assert reach.build("dhaka", root=tmp_path, evidence=None)["available"] is False
    assert "no data for this city" in reach.read("nowhere", root=tmp_path)["reason"]
    assert reach.nearest("dhaka", 23.7, 90.4)["code"] == "no_hospitals"


def test_nearest_list_keeps_one_entry_per_hospital_and_only_places_for_a_patient():
    from core.safety import hospitals as hosp
    hs = [{"osm_id": "node/1", "name": "Padma General Hospital", "lat": 23.75, "lon": 90.39},
          {"osm_id": "way/2", "name": "Padma General Hospital, Sonargaon Road, Dhaka", "lat": 23.7501, "lon": 90.3901},
          {"osm_id": "node/3", "name": "PG Nursing Department", "lat": 23.74, "lon": 90.39},
          {"osm_id": "node/4", "name": "Meherun Homeo Pharmacy", "lat": 23.74, "lon": 90.38},
          {"osm_id": "node/5", "name": "Sazzad's Amazing Dental", "lat": 23.73, "lon": 90.38},
          {"osm_id": "node/6", "name": "Dhaka Medical College Hospital", "lat": 23.725, "lon": 90.397}]
    keep, out = hosp.for_a_patient(hs)
    assert [h["osm_id"] for h in out] == ["node/3", "node/4", "node/5"]
    assert [h["name"] for h in hosp.one_each(keep)] == ["Padma General Hospital", "Dhaka Medical College Hospital"]
