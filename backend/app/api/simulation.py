"""Simulation HTTP endpoints."""
from __future__ import annotations

import threading
from backend.app import config
from backend.app.simulation import runtime as live_sim_mod
from backend.app.simulation import command_handler as sim_agent
from backend.app.simulation import network_comparison as twin_compare
from fastapi import APIRouter

router = APIRouter()
_NET_JOBS: dict[str, dict] = {}


@router.post("/api/sim/live/start", tags=["twin"])
def sim_live_start(payload: dict | None = None):
    """Start a live SUMO run: scale, duration_s, seed, compliance, arm, step_delay_ms."""
    return live_sim_mod.live_sim.start(payload or {})


@router.post("/api/sim/live/screenshot", tags=["twin"])
def sim_live_screenshot(payload: dict | None = None):
    """sumo-gui writes its own view to a PNG (TraCI gui.screenshot)."""
    return live_sim_mod.live_sim.screenshot((payload or {}).get("path"))


@router.post("/api/sim/live/follow", tags=["twin"])
def sim_live_follow(payload: dict | None = None):
    """Follow one simulated vehicle in the sumo-gui window."""
    return live_sim_mod.live_sim.follow((payload or {}).get("vehicle_id"))


@router.post("/api/sim/live/pause", tags=["twin"])
def sim_live_pause():
    return live_sim_mod.live_sim.pause()


@router.post("/api/sim/live/resume", tags=["twin"])
def sim_live_resume():
    return live_sim_mod.live_sim.resume()


@router.post("/api/sim/live/stop", tags=["twin"])
def sim_live_stop():
    return live_sim_mod.live_sim.stop()


@router.get("/api/sim/live/state", tags=["twin"])
def sim_live_state(vehicles: bool = True):
    """KPIs and every vehicle's position, as SUMO computed them this step."""
    return live_sim_mod.live_sim.state(with_vehicles=vehicles)


@router.get("/api/sim/live/history", tags=["twin"])
def sim_live_history():
    return {"runs": live_sim_mod.live_sim.history()}


@router.post("/api/sim/agent", tags=["twin"])
def sim_agent_chat(payload: dict):
    """Natural language -> the same start/pause/resume/stop the buttons call."""
    return sim_agent.chat(str(payload.get("message", "")), payload.get("history") or [])


@router.post("/api/twin/test", tags=["twin"])
def twin_test_start(payload: dict | None = None):
    """TEST IN DIGITAL TWIN for one AnalysisRun: the run's own city, resolved O/D, model and
    forecast become the SUMO scenario (probe vehicle for that exact trip in every arm).
    404 ANALYSIS_RUN_NOT_FOUND when the run id is unknown; SUMO_OD_MAPPING_FAILED when the
    trip cannot be snapped to drivable edges — never a stored or fixed scenario."""
    from backend.app.simulation import trip_comparison as twin_test
    r = twin_test.start(payload or {})
    if not r.get("started") and r.get("http") == 404:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=404, content=r)
    return r


@router.get("/api/twin/test/{simulation_run_id}", tags=["twin"])
def twin_test_status(simulation_run_id: str):
    from backend.app.simulation import trip_comparison as twin_test
    return twin_test.status(simulation_run_id)


@router.post("/api/twin/compare", tags=["twin"])
def twin_compare_start(payload: dict):
    """Baseline vs reactive on any generated network, paired seeds, CI verdict. Background job."""
    if not payload.get("network"):
        return {"error": "network required"}
    return {"job": twin_compare.start(payload), "poll": "/api/twin/compare/{job}"}


@router.get("/api/twin/compare/{job}", tags=["twin"])
def twin_compare_status(job: str):
    return twin_compare.status(job)


@router.get("/api/twin/networks", tags=["twin"])
def twin_networks():
    """Every network the twin can run — the calibrated one, then cities generated from OSM."""
    return {"networks": live_sim_mod.networks()}


@router.post("/api/twin/network", tags=["twin"])
def twin_generate_network(payload: dict):
    """Any area on Earth -> a runnable SUMO scenario: OSM extract -> netconvert -> trips -> duarouter.

    Body: {"city_id": ...} for a registered city, or {"name": ..., "bbox": [south, west, north, east]}
    from the map view. The network is REAL (OSM geometry, SUMO's own converter); the demand is
    GENERATED and every artefact says so. Runs in the background; poll the job."""
    import sys as _sys
    import uuid as _uuid
    _sys.path.insert(0, str(config.REPO))
    from pipeline.city import sumo_scenario
    from pipeline.city.registry import registry
    job = "net_" + _uuid.uuid4().hex[:8]
    _NET_JOBS[job] = {"job": job, "status": "running", "stage": "creating city"}

    def work():
        try:
            cid = payload.get("city_id")
            if not cid:
                name, bbox = (payload.get("name") or "").strip(), payload.get("bbox")
                if not name or not bbox or len(bbox) != 4:
                    raise ValueError("give city_id, or name + bbox [south, west, north, east]")
                spec = registry.create_from_bbox(name, tuple(float(x) for x in bbox))
                cid = spec.city_id
            _NET_JOBS[job].update(city_id=cid, stage="OSM extract -> netconvert -> demand")
            man = sumo_scenario.build(cid, seed=int(payload.get("seed", 11)),
                                      period=float(payload.get("period", 2.0)),
                                      end=int(payload.get("end", 3600)))
            _NET_JOBS[job].update(status="done", stage="done", manifest=man)
        except BaseException as exc:                       # noqa: BLE001
            _NET_JOBS[job].update(status="failed", error=f"{type(exc).__name__}: {exc}")
    threading.Thread(target=work, name=job, daemon=True).start()
    return {"started": True, "job": job, "poll": f"/api/twin/network/{job}"}


@router.get("/api/twin/network/{job}", tags=["twin"])
def twin_network_job(job: str):
    return _NET_JOBS.get(job) or {"job": job, "status": "unknown"}
