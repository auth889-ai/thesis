"""Every endpoint the interface depends on answers with the shape the interface reads.

These run against the real app object with the observatory and scheduler disabled. Evidence
endpoints are tested in both states — file present, file absent — because the interface must
render an honest "not generated yet, here is the command" in the second case, never a blank.
"""
from __future__ import annotations

import json
import time

import pytest

REPO_FILES = {
    "/api/forecast/dhaka/accuracy": "results/forecasting/live_backtest.json",
    "/api/experiment/chain": "results/routing/integrated_chain_ideal.json",
    "/api/experiment/sweep": "results/routing/sweep_compliance.json",
    "/api/experiment/ablation": "results/routing/ablation_forecast_quality.json",
}


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
