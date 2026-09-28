"""ANTI-HARDCODE GATES — inputs must change outputs; nothing may answer with a canned number.

GATE 3 A  same city, different origin/destination -> different routes (the router is called with the new
          coordinates; a live routing stub returns geometry that depends on them).
GATE 3 B  same O/D, modified CSV values -> the raw forecast changes (input window hash and raw hash differ).
GATE 3 C  same CSV, STID vs GWNet -> different resolved checkpoints.
GATE 3 D  same model, different horizon -> different requested forecast slice.
GATE 3 E  checkpoint removed -> the request fails as UNAVAILABLE, never a number.
GATE 1    every run leaves a provenance record with the required fields.
GATE 6    inference is recomputed per request (different input window -> different raw hash), and
          the training checkpoint reuse is flagged separately.
"""
import json
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
REPO = Path(__file__).resolve().parents[3]

REQUIRED = ["run_id", "city", "origin", "destination", "dataset_hash", "graph_hash", "requested_model", "resolved_model", "checkpoint_path",
            "checkpoint_sha256", "input_window_hash", "raw_prediction_hash", "postprocessed_prediction_hash", "start_time", "end_time"]


def _wide(n_nodes=5, steps=400, seed=0, bump=None):
    t = pd.date_range("2026-08-01", periods=steps, freq="5min", tz="UTC")
    x = 40 + 8 * np.sin(np.arange(steps) / 15)[:, None] + np.random.default_rng(seed).normal(0, 1.5, (steps, n_nodes))
    if bump is not None:                                     # modify "future-relevant" values: the last 30 steps
        x[-30:, :] = bump
    df = pd.DataFrame(x, columns=[f"R{i}" for i in range(n_nodes)]); df.insert(0, "time", t.strftime("%Y-%m-%d %H:%M"))
    return df.to_csv(index=False).encode()


COORDS = "road,lat,lon\n" + "\n".join(f"R{i},{23.70 + i * 0.004},{90.40 + i * 0.004}" for i in range(5))


@pytest.fixture
def city(tmp_path, monkeypatch):
    """An uploaded 5-road city with coordinates, prepared through the pinned harness, routed by a stub
    whose geometry depends on the origin/destination (so the network 'permits' a change)."""
    from traffictwin.data import uploads as user_datasets, forecast_inputs as dataset_ops
    from traffictwin.data import provenance
    from traffictwin.forecasting.training import basicts_train as bt
    if not bt.BTS.exists():
        pytest.skip("pinned BasicTS-legacy checkout missing")
    # Run the unmodified preparation script in an isolated workspace. A prior test's
    # prepared Gate City must not become this test's initial input.
    template = Path("scripts/data_preparation/METR-LA/generate_training_data.py")
    isolated = tmp_path / "basicts"
    (isolated / template).parent.mkdir(parents=True)
    shutil.copyfile(bt.BTS / template, isolated / template)
    monkeypatch.setattr(bt, "BTS", isolated)
    monkeypatch.setattr(user_datasets, "ROOT", tmp_path / "ud")
    monkeypatch.setattr(provenance, "DIR", tmp_path / "prov")
    monkeypatch.setattr(bt, "CARDS", tmp_path / "cards")
    from traffictwin.data.live_providers import google_routes as live
    def routes(o, d):
        (olat, olng), (dlat, dlng) = o, d
        mid = ((olat + dlat) / 2 + 0.001, (olng + dlng) / 2)
        seg = lambda pts: [{"coordinates": pts, "speed": "NORMAL"}]
        return {"is_live": True, "retrieved_at": "2026-09-05T00:00:00+00:00",
                "routes": [{"duration_s": 600 + abs(dlat - olat) * 1e5, "static_duration_s": 500, "distance_m": 4000 + abs(dlng - olng) * 1e5, "category": "NORMAL",
                            "segments": seg([[olat, olng], [dlat, dlng]])},
                           {"duration_s": 700 + abs(dlat - olat) * 1e5, "static_duration_s": 550, "distance_m": 4500, "category": "NORMAL",
                            "segments": seg([[olat, olng], list(mid), [dlat, dlng]])}]}
    monkeypatch.setattr(live.service, "routes", routes)
    from traffictwin.optimization import trip_analysis as analyze
    monkeypatch.setattr(analyze, "resolve_place", lambda text, city="": {"lat": float(text.split(",")[0]), "lng": float(text.split(",")[1]), "label": text, "source": "coordinates"})
    return user_datasets, dataset_ops, provenance


def _analyze(dataset_ops, scope, origin, dest, model="persistence", h=30, run_id="t"):
    log = []
    return dataset_ops.analyze_dataset({"origin": origin, "destination": dest, "model": model, "horizon_min": h, "departure_local": "2026-08-02T08:00"},
                                       scope, lambda **k: log.append(k), run_id=run_id), log


def test_gate3A_origin_destination_change_routes(city):
    user_datasets, dataset_ops, _ = city
    user_datasets.save("Gate City", _wide(), coords_bytes=COORDS.encode())
    r1, _ = _analyze(dataset_ops, "user:gate_city", "23.700, 90.400", "23.716, 90.416", run_id="a1")
    r2, _ = _analyze(dataset_ops, "user:gate_city", "23.704, 90.404", "23.712, 90.412", run_id="a2")
    assert r1["routes"][0]["segments"] != r2["routes"][0]["segments"]
    assert r1["routes"][0]["eta_now_s"] != r2["routes"][0]["eta_now_s"]
    assert r1["provenance"]["postprocessed_prediction_hash"] != r2["provenance"]["postprocessed_prediction_hash"]


def test_gate3B_modified_csv_changes_raw_forecast(city):
    user_datasets, dataset_ops, _ = city
    user_datasets.save("Gate City", _wide(), coords_bytes=COORDS.encode())
    r1, _ = _analyze(dataset_ops, "user:gate_city", "23.700, 90.400", "23.716, 90.416", run_id="b1")
    user_datasets.save("Gate City", _wide(bump=12.0), coords_bytes=COORDS.encode())
    from traffictwin.forecasting.training import basicts_train as bt
    bt.prepare("user:gate_city")                                # the new upload replaces the prepared data
    r2, _ = _analyze(dataset_ops, "user:gate_city", "23.700, 90.400", "23.716, 90.416", run_id="b2")
    assert r1["provenance"]["dataset_hash"] != r2["provenance"]["dataset_hash"]
    assert r1["provenance"]["input_window_hash"] != r2["provenance"]["input_window_hash"]
    assert r1["provenance"]["raw_prediction_hash"] != r2["provenance"]["raw_prediction_hash"]
    assert r1["sensors"][0]["pred"]["30"] != r2["sensors"][0]["pred"]["30"]


def test_gate3C_stid_vs_gwnet_resolve_to_different_checkpoints(monkeypatch):
    from traffictwin.forecasting.operations import model_registry as mr
    from traffictwin.forecasting.training import basicts_train as bt
    def card(arch):
        return {"dataset": "user:x", "bts_name": "DF_x", "arch": arch, "checkpoint": f"/ck/{arch}_best_val_MAE.pt", "trained_utc": "2026-09-05T00:00:00+00:00",
                "quality": {"passed": True}, "verification": {"passed": True},
                "evaluation": {"validation": {arch: {"overall": {"MAE": 3.0}}, "persistence": {"overall": {"MAE": 6.0}}},
                               "test": {arch: {"overall": {"MAE": 3.0, "skill_vs_persistence": 0.3}}}, "validation_MAE": {arch: 3.0, "persistence": 6.0}},
                "trust": {"eligible": True, "label": "ROUTING_ELIGIBLE", "skill": 0.3}}
    monkeypatch.setattr(bt, "cards", lambda: [card("STID"), card("GWNet")])
    a, b = mr.resolve("user:x", "STID"), mr.resolve("user:x", "GWNet")
    assert a["checkpoint_path"] != b["checkpoint_path"] and a["model"] == "STID" and b["model"] == "GWNet"


def test_gate3D_horizon_changes_requested_slice(city):
    user_datasets, dataset_ops, _ = city
    user_datasets.save("Gate City", _wide(seed=3), coords_bytes=COORDS.encode())
    r15, _ = _analyze(dataset_ops, "user:gate_city", "23.700, 90.400", "23.716, 90.416", model="historical_average", h=15, run_id="d15")
    r60, _ = _analyze(dataset_ops, "user:gate_city", "23.700, 90.400", "23.716, 90.416", model="historical_average", h=60, run_id="d60")
    assert r15["horizon_min"] == 15 and r60["horizon_min"] == 60
    assert r15["forecast"]["eta_s"] != r60["forecast"]["eta_s"] or r15["sensors"][0]["pred"]["15"] != r60["sensors"][0]["pred"]["60"]


def test_gate3E_missing_checkpoint_is_unavailable_not_a_number(city, monkeypatch):
    user_datasets, dataset_ops, _ = city
    from traffictwin.forecasting.operations import model_registry as mr
    user_datasets.save("Gate City", _wide(), coords_bytes=COORDS.encode())
    monkeypatch.setattr(mr, "resolve", lambda scope, m: {"model": "STID", "label": "STID", "eligible": False, "trained": False, "reason": "checkpoint file missing"})
    with pytest.raises(RuntimeError, match="UNAVAILABLE"):
        _analyze(dataset_ops, "user:gate_city", "23.700, 90.400", "23.716, 90.416", model="STID", run_id="e1")


def test_gate1_provenance_record_complete(city):
    user_datasets, dataset_ops, provenance = city
    user_datasets.save("Gate City", _wide(), coords_bytes=COORDS.encode())
    r, log = _analyze(dataset_ops, "user:gate_city", "23.700, 90.400", "23.716, 90.416", run_id="p1")
    rec = provenance.load("p1")
    missing = [k for k in REQUIRED if k not in rec]
    assert not missing, missing
    assert rec["result_source"] == "LIVE_COMPUTATION" and rec["inference_recomputed"] is True
    names = [s["name"] for s in rec["stages"]]
    assert names == provenance.STAGES and all(s["seconds"] is not None for s in rec["stages"])
    assert any(k.get("stages") for k in log), "the job must emit measured stages while it runs"
    assert r["run_id"] == "p1" and r["provenance"]["raw_prediction_hash"] == rec["raw_prediction_hash"]


def test_gate5_precomputed_endpoints_are_tagged(client):
    for path in ("/api/experiment/sweep?grid=compliance", "/api/experiment/ablation", "/api/forecast/dhaka/accuracy"):
        r = client.get(path).json()
        if r.get("available"):
            assert r.get("result_source") == "RESEARCH_BENCHMARK", path


def test_gate5_run_endpoint_unknown_id_is_unavailable(client):
    r = client.get("/api/runs/does_not_exist").json()
    assert "UNAVAILABLE" in r.get("error", "")
