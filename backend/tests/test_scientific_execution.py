"""Execution controls cannot change a frozen protocol or pass off cancellation as completion."""
import fcntl
import json
from pathlib import Path
import subprocess
import sys

import pytest

from core.simulation.closed_loop.control import jobs

JOB = "execution_20260920T120000_1234abcd"


@pytest.fixture
def isolated_jobs(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs, "ROOT", tmp_path)
    monkeypatch.setattr(jobs, "PROCESSES", {})
    monkeypatch.setattr(jobs, "observation_window", lambda: {"maximum": 34244})
    return tmp_path


def pending(root, status="running"):
    directory = root / JOB
    directory.mkdir()
    jobs.atomic(directory / "request.json", {"seed": 201, "observation_as_of_index": 28420, "protocol_version": "fresh_identical_state_v2"})
    jobs.atomic(directory / "status.json", {"status": status, "stage": "simulating"})
    return directory


@pytest.mark.parametrize("payload", [
    {"seed": True}, {"seed": "201"}, {"seed": 1}, {"arm": "oracle_v2x"},
    {"seed": 201, "horizon": 100}, {"seed": 201, "loss": .5},
    {"observation_as_of_index": True}, {"observation_as_of_index": "28420"},
    {"observation_as_of_index": 0}, {"observation_as_of_index": 34245},
])
def test_execution_rejects_protocol_changes(client, isolated_jobs, payload):
    assert client.post("/api/research/executions", json=payload).status_code == 422
    assert not list(isolated_jobs.glob("execution_*"))


def test_execution_lease_is_exclusive_across_processes(client, isolated_jobs):
    lock = isolated_jobs / ".controller.lock"
    child = subprocess.Popen([
        sys.executable, "-u", "-c",
        "import fcntl,sys,time; f=open(sys.argv[1],'a+'); fcntl.flock(f,fcntl.LOCK_EX); print('locked'); time.sleep(30)",
        str(lock),
    ], stdout=subprocess.PIPE, text=True)
    try:
        assert child.stdout.readline().strip() == "locked"
        response = client.post("/api/research/executions", json={"observation_as_of_index": 28420})
        assert response.status_code == 409
        assert not list(isolated_jobs.glob("execution_*"))
    finally:
        child.terminate()
        child.wait(timeout=5)


def test_cancel_is_a_worker_request_not_a_false_completed_state(client, isolated_jobs):
    directory = pending(isolated_jobs)
    response = client.post(f"/api/research/executions/{JOB}/cancel")
    assert response.status_code == 200
    assert response.json()["status"] == "cancelling"
    assert (directory / "cancel.request").exists()
    assert client.get(f"/api/research/executions/{JOB}").json()["status"] == "cancelling"
    assert json.loads((directory / "status.json").read_text())["status"] == "running"


def test_cancel_does_not_change_finished_evidence(client, isolated_jobs):
    directory = pending(isolated_jobs, "done")
    before = (directory / "status.json").read_bytes()
    assert client.post(f"/api/research/executions/{JOB}/cancel").json()["status"] == "done"
    assert not (directory / "cancel.request").exists()
    assert (directory / "status.json").read_bytes() == before


def test_queued_worker_honors_cancellation_before_loading_model(isolated_jobs, monkeypatch):
    from core.simulation.closed_loop.control import execution
    directory = pending(isolated_jobs, "queued")
    (directory / "cancel.request").touch()
    monkeypatch.setattr(execution, "JOBS", isolated_jobs)
    monkeypatch.setattr(execution.cl, "Forecaster", lambda *_: pytest.fail("cancelled worker loaded a model"))
    execution.execute(JOB)
    assert json.loads((directory / "status.json").read_text())["status"] == "cancelled"


def test_worker_failure_releases_launch_lease(isolated_jobs, monkeypatch):
    def fail(*args, **kwargs):
        raise OSError("test launch failure")
    monkeypatch.setattr(jobs.subprocess, "Popen", fail)
    with pytest.raises(OSError, match="test launch failure"):
        jobs.launch(28420)
    with (isolated_jobs / ".controller.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    assert jobs.recent()[0]["status"] == "failed"


def test_child_keeps_lease_after_launch_returns(isolated_jobs, monkeypatch):
    popen = subprocess.Popen
    def short_worker(command, **kwargs):
        return popen([sys.executable, "-c", "import time; time.sleep(1)"], **kwargs)
    monkeypatch.setattr(jobs.subprocess, "Popen", short_worker)
    launched = jobs.launch(28420)
    process = jobs.PROCESSES[launched["job_id"]]
    try:
        with pytest.raises(RuntimeError, match="already running"):
            jobs.launch(28420)
    finally:
        process.wait(timeout=5)


def test_job_path_traversal_is_rejected(client, isolated_jobs):
    assert client.get("/api/research/executions/not-a-job").status_code == 404


def test_completed_ui_comparison_keeps_reference_origins_explicit():
    source = (Path(__file__).resolve().parents[2] / "frontend/src/features/twin/ExecutionPanel.tsx").read_text()
    assert "result.arm_origins[arm]" in source
    assert "one seed; no new significance claim" in source


def test_vehicle_trace_preserves_logged_candidate_route_ids(client, tmp_path, monkeypatch):
    from core.common import evidence_paths as config
    monkeypatch.setattr(config, "REPO", tmp_path)
    arm = tmp_path / "results/v2x/closed_loop/test_run/s201/predictive_v2x"
    round_dir = arm / "routing_round_0"
    round_dir.mkdir(parents=True)
    (arm / "arm_result.json").write_text(json.dumps({"rounds": [
        {"round": 0, "sim_time_s": 1500, "routing_run_id": "test_round"},
    ]}))
    (round_dir / "routing_record.json").write_text(json.dumps({"decisions": [{
        "vehicle": "test_vehicle", "candidates": [{"route_id": "test_vehicle_c1", "edges": ["a", "b"],
        "base_tt_s": 20, "forecast_future_tt_s": 30}],
    }]}))
    response = client.get("/api/experiment/v2x_closed_loop/vehicle_trace", params={
        "run": "test_run", "seed": 201, "arm": "predictive_v2x", "vehicle": "test_vehicle",
    })
    assert response.status_code == 200
    candidate = response.json()["decisions"][0]["candidates"][0]
    assert candidate["id"] == "test_vehicle_c1"
    assert candidate["edges_n"] == 2
    assert candidate["forecast_future_tt_s"] == 30


def test_vehicle_trace_retains_message_join_and_does_not_score_unfinished_trips(client, tmp_path, monkeypatch):
    from core.common import evidence_paths as config
    monkeypatch.setattr(config, "REPO", tmp_path)
    root = tmp_path / "results/v2x/closed_loop/test_run/s201"
    arm = root / "predictive_v2x"
    arm.mkdir(parents=True)
    (arm / "arm_result.json").write_text('{"rounds": []}')
    (arm / "reroute_log.jsonl").write_text(json.dumps({"vehicle_id": "v", "message_id": "downlink-1", "routing_run_id": "round-1"}) + "\n")
    for name in ("predictive_v2x", "baseline"):
        path = root / name
        path.mkdir(exist_ok=True)
        (path / "tripinfo.xml").write_text('<tripinfos><tripinfo id="v" depart="100" arrival="-1" duration="300"/></tripinfos>')
    data = client.get("/api/experiment/v2x_closed_loop/vehicle_trace", params={
        "run": "test_run", "seed": 201, "arm": "predictive_v2x", "vehicle": "v",
    }).json()
    assert data["reroutes"][0]["message_id"] == "downlink-1"
    assert data["reroutes"][0]["routing_run_id"] == "round-1"
    assert data["outcome"]["travel_time_delta_s"] is None
    assert data["outcome"]["this_arm"]["duration"] == 300
