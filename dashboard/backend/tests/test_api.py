"""Every endpoint the interface depends on answers with the shape the interface reads.

These run against the real app object with the observatory and scheduler disabled. Evidence
endpoints are tested in both states — file present, file absent — because the interface must
render an honest "not generated yet, here is the command" in the second case, never a blank.
"""
from __future__ import annotations

import json
import time

import pytest
from pathlib import Path

REPO_FILES = {
    "/api/forecast/dhaka/accuracy": "results/forecasting/live_backtest.json",
    "/api/experiment/chain": "results/routing/integrated_chain_ideal.json",
    "/api/experiment/sweep": "results/routing/sweep_compliance.json",
    "/api/experiment/ablation": "results/routing/ablation_forecast_quality.json",
}

needs_recorded = pytest.mark.skipif(not (Path(__file__).resolve().parents[3] / "artifacts/live_dhaka/normalized/google_routes_runtime_reference.jsonl").exists(), reason="recorded live series is git-ignored; absent on CI")


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


@pytest.mark.parametrize("path,rel", list(REPO_FILES.items()))
def test_evidence_endpoints_are_honest_in_both_states(client, path, rel):
    import config
    d = client.get(path).json()
    exists = (config.REPO / rel).exists()
    assert d["available"] is exists
    if exists:
        assert "generated_utc" in d
    else:
        assert d["missing"] == rel and d["command"]       # the interface shows how to make it


def test_accuracy_payload_has_every_model_on_identical_pairs(client):
    d = client.get("/api/forecast/dhaka/accuracy").json()
    if not d["available"]:
        pytest.skip("backtest not generated in this checkout")
    for h in d["horizons_min"]:
        pairs = {r["n_pairs"] for r in d["rows"] if r["horizon_min"] == h}
        assert len(pairs) == 1, "every model must be scored on the same pairs"
    assert any(r["model"] == "persistence" and r["skill_vs_persistence"] == 0.0 for r in d["rows"])


def test_accuracy_for_an_unknown_city_is_not_invented(client):
    d = client.get("/api/forecast/nowhere/accuracy").json()
    assert d["available"] is False and d["command"]


@needs_recorded
def test_forecast_uses_recorded_window_when_buffer_is_empty_and_logs_it(client):
    d = client.get("/api/forecast/dhaka?horizons=15").json()
    assert d["source"] == "recorded"
    assert d["input"]["shape"][0] >= 8 and d["input"]["unit"] == "congestion_level_0_3"
    assert d["forecast"] and d["forecast"]["model"]
    assert d["logged_rows"] == len(d["forecast"]["node_ids"])          # one row per corridor
    sb = client.get("/api/forecast/dhaka/scoreboard").json()
    assert sb["logged"] == d["logged_rows"] and sb["scored"] == 0      # target time not reached yet


def test_a_requested_model_that_does_not_exist_is_refused_not_swapped(client):
    d = client.get("/api/forecast/dhaka?horizons=15&model=NoSuchModel").json()
    assert d["forecast"] is None
    assert "not a registered model" in d["decision"]["reason"]


@needs_recorded
def test_history_falls_back_to_the_recorded_day_with_accuracy_attached(client):
    d = client.get("/api/history/dhaka?horizons=15,30").json()
    assert d["unit"] == "congestion_level_0_3"
    assert 8 <= len(d["history"]) <= 288
    assert d["forecast"] and d["observed"]["as_of_utc"]
    assert all(v is None or 0 <= v <= 3 for row in d["history"] for v in row["values"])
    assert "recorded" in d["source"]


def test_chain_run_executes_the_real_function_in_the_background(client, tmp_path, monkeypatch):
    """POST starts a run, GET reports its progress, and the result is what run_chain returned."""
    from pipeline.routing import integrated_chain as ic
    monkeypatch.setattr(ic, "RUNS", tmp_path)
    calls = {}

    def fake_run_chain(**opts):
        calls.update(opts)
        d = tmp_path / opts["run_id"]
        d.mkdir(parents=True, exist_ok=True)
        (d / "status.json").write_text(json.dumps({"run_id": opts["run_id"], "status": "running",
                                                   "stage": "sumo", "arms_done": 3, "arms_total": 3}))
        rec = {"run_id": opts["run_id"], "summary": {"arms": [{"arm": "baseline"}], "verdict": {}}}
        (d / "run.json").write_text(json.dumps(rec))
        return rec
    monkeypatch.setattr(ic, "run_chain", fake_run_chain)

    r = client.post("/api/experiment/chain/run", json={"seeds": "11", "horizon": 600, "tag": "t"}).json()
    assert r["started"] and r["run_id"].startswith("chain_")
    for _ in range(200):                                  # up to 20 s under a loaded machine
        st = client.get(r["poll"]).json()
        if st["status"] == "done":
            break
        time.sleep(0.1)
    assert st["found"] and st["status"] == "done" and st["arms_done"] == 3
    assert st["result"]["run_id"] == r["run_id"]
    assert calls["seeds"] == "11" and calls["horizon"] == 600
    assert client.get("/api/experiment/chain/runs").json()["runs"][0]["run_id"] == r["run_id"]


def test_chain_run_rejects_unknown_options_and_paths(client, tmp_path, monkeypatch):
    for bad in ("no_such_run", "chain_..x", "%2e%2e%2fetc"):
        r = client.get(f"/api/experiment/chain/run/{bad}")
        assert r.status_code == 404 or r.json().get("found") is False
    # unknown keys are dropped before the run starts — and no real chain is launched here
    from pipeline.routing import integrated_chain as ic
    monkeypatch.setattr(ic, "RUNS", tmp_path)
    seen = {}
    monkeypatch.setattr(ic, "run_chain", lambda **o: seen.update(o) or {"summary": {}})
    r = client.post("/api/experiment/chain/run", json={"__class__": "x", "seeds": "11"}).json()
    assert r["started"] and "__class__" not in r["config"]
    for _ in range(50):
        if seen: break
        time.sleep(0.1)
    assert seen.get("seeds") == "11" and "__class__" not in seen


# ------------------------------------------------------------------ the operations screen

def test_places_and_place_resolution(client):
    p = client.get("/api/places").json()["places"]
    assert any(x["id"] == "farmgate" for x in p)
    import analyze
    assert analyze.resolve_place("23.75, 90.39")["source"] == "coordinates"
    assert analyze.resolve_place("Farmgate")["source"] == "known place"
    assert analyze.resolve_place("karwan bazar")["label"] == "karwanbazar"


def test_runs_along_needs_coverage_not_just_a_touch():
    import analyze
    a, b = (23.7573, 90.3854), (23.7389, 90.3958)              # farmgate -> shahbagh
    poly = [(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t) for t in (0, .25, .5, .75, 1)]
    along = [(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t) for t in (0.1, 0.3, 0.5, 0.7, 0.9)]
    touch = [(a[0] + 0.0005 * k, a[1]) for k in range(5)]        # hovers near one end only
    assert analyze.runs_along(along, poly) and not analyze.runs_along(touch, poly)


def test_analyze_job_reports_real_stages_and_refuses_honestly(client, monkeypatch):
    import analyze
    monkeypatch.setattr(analyze, "resolve_place", lambda t, city="dhaka": (_ for _ in ()).throw(ValueError(f"could not find '{t}'")))
    j = client.post("/api/analyze", json={"origin": "nowhere-xyz", "destination": "shahbagh"}).json()
    for _ in range(100):
        s = client.get(f"/api/analyze/{j['job']}").json()
        if s["status"] != "running": break
        time.sleep(0.1)
    assert s["status"] == "failed" and "could not find" in s["error"]
    assert s["stage"] in ("failed", "Fetching traffic")


def test_verdict_ci_labels_from_paired_seeds():
    from pipeline.routing import integrated_chain as ic
    def run(arm, seed, vh):
        return {"arm": arm, "seed": seed, "routes_changed": 0, "advisories_delivered": 0,
                "metrics": {"total_vehicle_hours": vh, "mean_travel_time_s": 1, "p95_travel_time_s": 1,
                            "total_waiting_s": 1, "mean_time_loss_s": 1, "mean_queue_veh": 1, "max_queue_veh": 1,
                            "arrived": 1, "teleports": 0}}
    runs = [run("baseline", s, 100.0) for s in (1, 2, 3)] + [run("prediction_aware", s, v) for s, v in ((1, 95.0), (2, 96.0), (3, 94.0))] \
         + [run("reactive", s, v) for s, v in ((1, 90.0), (2, 110.0), (3, 100.0))]
    ci = ic.summarise(runs)["verdict_ci"]
    assert ci["prediction_aware"]["label"] == "HELPED" and ci["prediction_aware"]["wins"] == 3
    assert ci["prediction_aware"]["ci95"][1] < 0
    assert ci["reactive"]["label"] == "INCONCLUSIVE"


def test_operate_cities_starts_with_dhaka(client):
    c = client.get("/api/operate/cities").json()["cities"]
    assert c[0] == {"id": "dhaka", "label": "Dhaka", "forecast": True}
    # any other city is forecastable only once it is being observed (and says how many samples)
    assert all(("steps" in x) and (x["forecast"] == (x["steps"] > 0)) for x in c[1:])


def test_twin_compare_requires_a_network(client):
    assert "error" in client.post("/api/twin/compare", json={}).json()


def test_prediction_lab_lists_real_datasets_and_runs_the_floor(client):
    d = client.get("/api/predict-lab/datasets").json()["datasets"]
    ids = {x["id"] for x in d}
    if "METR_LA" not in ids:
        pytest.skip("OpenCity datasets not present")
    metr = next(x for x in d if x["id"] == "METR_LA")
    assert metr["nodes"] == 207 and "OpenCity-plus" in metr["models"] and "GWNet" in metr["models"]
    j = client.post("/api/predict-lab/run", json={"dataset": "METR_LA", "model": "persistence", "region": 3, "as_of": 20000}).json()
    for _ in range(300):
        s = client.get(f"/api/predict-lab/{j['job']}").json()
        if s["status"] != "running": break
        time.sleep(0.2)
    assert s["status"] == "done", s.get("error")
    r = s["result"]
    assert len(r["history"]) == 72 and len(r["prediction"]) == 12 and r["as_of_utc"].startswith("2012-")
    assert r["metrics"]["15"]["abs_error"] is not None if "15" in r["metrics"] else r["metrics"][15]["abs_error"] is not None


def test_city_id_resolution_and_level_conversion():
    import analyze
    assert analyze.city_id_for("Dhaka") == "dhaka"
    assert analyze.city_id_for("Nairobi") in ("nairobi_kenya", None)
    from pipeline.forecasting.adapters.base import CityData
    import numpy as np
    cd = CityData(city_id="x", node_ids=["a", "b"], values=np.array([[10.0, 5.0]], dtype="float32"))
    live = {"corridors": [{"id": "a", "distance_m": 1000, "static_duration_s": 100},     # free-flow 10 m/s
                          {"id": "b", "distance_m": 1000, "static_duration_s": 100}]}
    obs, pred = analyze.levels_from_speeds(cd, {"values": {15: [4.0, 10.0]}}, live)
    assert obs == {"a": 0.0, "b": 2.5} and pred[15] == {"a": 2.5, "b": 0.0}


def test_observe_endpoint_refuses_an_unknown_city_honestly(client, monkeypatch):
    """Two honest refusals, both environment-independent: a city whose road graph cannot be
    derived (registered here, corridors fail), and a name that cannot be created at all."""
    import city_corridors
    from types import SimpleNamespace
    from pipeline.city.registry import registry
    monkeypatch.setattr(city_corridors, "ensure", lambda cid, k=12: (_ for _ in ()).throw(RuntimeError("no graph")))
    # the city is registered on this machine or not (CI has no data/cities): make it registered either way
    real_get = registry.get
    monkeypatch.setattr(registry, "get", lambda cid: SimpleNamespace(city_id=cid, display_name="Nairobi, Kenya") if cid == "nairobi_kenya" else real_get(cid))
    d = client.post("/api/city/nairobi_kenya/observe", json={}).json()
    assert d["ok"] is False and "corridors" in d["error"]
    monkeypatch.setattr(registry, "create_from_name", lambda name, **kw: (_ for _ in ()).throw(RuntimeError("geocoder unavailable")))
    d2 = client.post("/api/city/nowhere_town_xyz/observe", json={}).json()
    assert d2["ok"] is False and "cannot find city" in d2["error"]


def test_learned_gate_endpoint_reads_the_newest_report_or_says_it_is_missing(client, tmp_path, monkeypatch):
    """Blocker #6: the learned-model outcome is read as-is from the frozen protocol's report; the oracle arm stays research-only."""
    import json
    import config
    from pipeline.routing import learned_gate as lg
    monkeypatch.setattr(config, "REPO", tmp_path)
    r = client.get("/api/experiment/learned_gate").json()
    assert r["available"] is False and "learned_gate.py" in r["command"]
    def arm(v):
        return {"metrics": {k: v for k in ("total_vehicle_hours_incl_never_inserted", "total_vehicle_hours", "mean_travel_time_all", "mean_travel_time_s", "p95_travel_time_s", "total_waiting_s", "mean_queue_veh", "max_queue_veh")}
                | {"arrived": 100, "teleports": 0, "top_route_share": 0.1, "top_edge_flow_concentration": 0.1, "teleport_events": [], "teleport_rate_per_1000_inserted": 0.0, "teleport_edges": {}, "probe": {}},
                "routing": {"mean_predicted_saving_s": 10.0, "routes_changed": 1}, "decisions": {}}
    recs = [{"seed": s, "same_population": True, "arms": {"baseline": arm(100), "reactive": arm(101), "persistence_predictive": arm(99), "learned_predictive": arm(97 + 0.01 * s), "oracle": arm(90)},
             "quality_vs_outcome": {"skill_vs_persistence": 0.2, "realized_saving_pct_learned_vs_baseline": 3.0, "realized_saving_pct_persistence_vs_baseline": 1.0}} for s in range(10)]
    P = {"primary_metric_key": "total_vehicle_hours_incl_never_inserted", "with_oracle": True, "protocol_id": "FINAL_LEARNED_PROTOCOL_v1", "model_label": "Graph WaveNet", "checkpoint_sha256": "abc", "checkpoint": "GraphWaveNet_best_val_MAE.pt"}
    d = tmp_path / "results/routing/learned_gate/FINAL_LEARNED_PROTOCOL_v1_final_cfgx_cky"; d.mkdir(parents=True)
    (d / "report.json").write_text(json.dumps(lg.report(P, recs, "final"), default=str))
    r = client.get("/api/experiment/learned_gate").json()
    assert r["available"] and r["verdict"] == "HELPED" and r["learned_vs_persistence"]["pair"] == "learned_predictive vs persistence_predictive"
    assert r["oracle_research_only"]["label"] == "HELPED" and r["provenance"]["checkpoint_sha256"] == "abc" and len(r["per_seed"]) == 10
    assert r["outcome"].startswith("A")
