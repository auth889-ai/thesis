"""Q3 (2026-10-11): the weak-signal profile from real OSM mast positions: the selection rule, the 3GPP UMa path loss, the bins at
Bartendr's anchors, the per-step verdicts, the energy arithmetic, and the app flag that is off by default."""
from __future__ import annotations

import json
import os

from core.networking.prefetch import masts
from core.networking.prefetch import results as pr
from core.simulation.routing import signal


def test_radio_sites_follow_the_recorded_rule():
    file = {"elements": [
        {"type": "node", "id": 1, "lat": 23.75, "lon": 90.40, "tags": {"man_made": "tower", "tower:type": "communication", "height": "30 m"}},
        {"type": "node", "id": 2, "lat": 23.75, "lon": 90.41, "tags": {"man_made": "mast", "communication:mobile_phone": "yes"}},
        {"type": "way", "id": 3, "lat": 23.75, "lon": 90.42, "tags": {"man_made": "tower", "tower:type": "minaret"}},
        {"type": "node", "id": 4, "lat": 23.75, "lon": 90.43, "tags": {"telecom": "exchange"}},
        {"type": "node", "id": 5, "lat": 23.75, "lon": 90.44, "tags": {"man_made": "mast"}}]}
    got = masts.radio_sites(file)
    assert [s["id"] for s in got] == ["node/1", "node/2"] and got[0]["height_m"] == 30.0 and got[1]["height_m"] is None


def test_path_loss_rises_with_distance_and_the_bins_sit_at_bartendrs_anchors():
    pl = [masts.path_loss_db(d) for d in (10, 50, 100, 500, 1000, 2000, 5000)]
    assert all(b > a for a, b in zip(pl, pl[1:])) and masts.path_loss_db(1) == masts.path_loss_db(10) and masts.path_loss_db(9000) == masts.path_loss_db(5000)
    # TR 38.901 UMa NLOS at 1 km, 1.8 GHz, hUT 1.5 m: 13.54 + 39.08 log10(d3D) + 20 log10(1.8); d3D = sqrt(1000^2 + 23.5^2)
    import math
    d3d = math.hypot(1000, 23.5)
    assert abs(masts.path_loss_db(1000) - (13.54 + 39.08 * math.log10(d3d) + 20 * math.log10(1.8))) < 0.01
    assert masts.bin_of_level(-69.9) == "strong" and masts.bin_of_level(-70) == "strong" and masts.bin_of_level(-80) == "medium" and masts.bin_of_level(-90.1) == "weak"
    assert masts.bin_of_level(masts.level_dbm(100)) == "strong" and masts.bin_of_level(masts.level_dbm(5000)) == "weak"


def test_step_bins_use_the_nearest_site_and_say_so():
    shape = [[90.40 + i * 0.001, 23.75] for i in range(30)]                   # about 3 km east-west
    st = signal.steps(shape)
    sites = [{"id": "node/1", "lat": 23.75, "lon": 90.40, "height_m": None}]
    sb = masts.step_bins(sites, st)
    assert sb[0]["bin"] == "strong" and sb[-1]["bin"] in ("medium", "weak") and sb[-1]["distance_m"] > sb[0]["distance_m"]
    assert all(b["site"] == "node/1" and "3GPP" in b["basis"] and "assumed EIRP" in b["basis"] for b in sb)
    assert masts.step_bins([], st)[0]["bin"] == "unknown"
    assert masts.road_override("x", st[0], ("none", "tunnel"), sites) == ("none", "tunnel")       # a tunnel still wins
    assert masts.road_override("x", st[0], (None, None), sites)[0] == "strong"


def test_energy_arithmetic_matches_results_energy_rows_on_the_same_profile():
    bins = pr.profile(85, 0.3, 1)
    secs = [40.0] * 85
    e = masts.energy_on(bins, secs, 10_201_674)
    assert e["bartendr_j"] <= e["as_needed_j"] + 1e-6 and e["now_j"] == 35.1 and e["chunks"] == 156


def test_app_flag_is_off_by_default(monkeypatch):
    from app.routing import signal_predict as sp
    monkeypatch.delenv("TRAFFICTWIN_SIGNAL_MASTS", raising=False)
    assert sp.masts_on() is False
    monkeypatch.setenv("TRAFFICTWIN_SIGNAL_MASTS", "1")
    assert sp.masts_on() is True
    out = masts.OUT / "summary.json"
    if out.exists():
        d = json.loads(out.read_text())
        assert d["label"] == masts.LABEL and d["radio_sites"] == len(d["sites"]) and sum(d["counts"].values()) == d["route"]["steps"] and d["counts"]["none"] == 0
        assert d["energy"]["saved_results_untouched"] == "results/networking/prefetch/summary.json"


def test_the_research_table_gets_the_mast_profile_row_from_the_q3_file_and_the_saved_summary_is_untouched(tmp_path):
    """R3 (2026-10-11): /api/networking/prefetch adds energy.masts, read from evidence/prefetch/masts/summary.json at request time; the saved
    synthetic rows and the summary's sha256 are the file's own, unchanged."""
    import hashlib
    import json
    from core.networking.prefetch import results as pr
    assert pr.masts_row(tmp_path / "none.json") is None
    row = pr.masts_row()
    assert row and row["radio_sites"] == 8 and row["now_j"] == 35.1 and row["as_needed_j"] == 140.3 and 0 < row["weak_share"] < 1 and row["sha256"] == hashlib.sha256(pr.MASTS.read_bytes()).hexdigest()
    got = pr.read()
    saved = json.loads((pr.RESULTS / "summary.json").read_text())
    assert got["energy"]["masts"] == row and got["energy"]["rows"] == saved["energy"]["rows"] and got["sha256"] == saved["sha256"]
    assert "masts" not in saved["energy"]
    assert pr.read(masts=tmp_path / "none.json")["energy"]["masts"] is None
