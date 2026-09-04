"""DhakaFlow dashboard — FastAPI application.

    cd dashboard/backend && python main.py        # http://127.0.0.1:8000
                                                  # OpenAPI at /api/docs

Four files, because the backend has one job: read the evidence this project produced and serve it.

    config.py    where every evidence file lives and the command that regenerates it
    schemas.py   the response contract (Pydantic v2) — what each endpoint promises
    readers.py   one function per panel: open the file, shape it, attach provenance
    main.py      routes and the SSE stream

Every response carries `provenance` (source file, regenerating command, reality label). A panel
with no evidence returns `available: false` and the command to produce it, so the interface can
never show an invented number.

Real-time uses Server-Sent Events, not WebSocket: this dashboard is display-only, so a
bidirectional socket buys nothing. SSE is plain HTTP, the browser's EventSource reconnects on its
own, and the stream sends a diff-sized payload only when something changed.

Open source used, with thanks: FastAPI (MIT), Uvicorn (BSD-3), Pydantic (MIT); in the browser
MapLibre GL JS (BSD-3), Chart.js (MIT), OpenStreetMap tiles (ODbL).
"""
from __future__ import annotations

import asyncio
import json
import threading
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

import config
import corridors as corridor_registry
import observatory as observatory_mod
import live as live_service
import predict_live
import readers
import schemas
import credentials as key_store
import simulate
import forecast_log
import live_sim as live_sim_mod
import sim_agent

app = FastAPI(title="DhakaFlow", version="1.0.0", docs_url="/api/docs",
              description="Live Dhaka traffic, forecasting, routing and V2X evidence.")


@app.get("/api/traffic", response_model=schemas.TrafficResponse, tags=["traffic"])
def traffic():
    """Live corridor congestion, with recorder freshness."""
    return readers.traffic()


@app.get("/api/forecast", response_model=schemas.ForecastResponse, tags=["forecast"])
def forecast():
    """Trained models, the published comparison and checkpoint verification."""
    return readers.forecast()


@app.get("/api/routing", response_model=schemas.RoutingResponse, tags=["routing"])
def routing():
    """Routing arms on paired seeds and the ACT / NO_ACTION decision."""
    return readers.routing()


@app.get("/api/simulation", response_model=schemas.SimulationResponse, tags=["simulation"])
def simulation():
    """SUMO before / after and the network-wide decision guard."""
    return readers.simulation()


@app.get("/api/network", response_model=schemas.NetworkResponse, tags=["network"])
def network():
    """V2X delivery ratio, latency and loss from the MOSAIC sweep."""
    return readers.network()


@app.get("/api/evidence", response_model=schemas.EvidenceResponse, tags=["evidence"])
def evidence():
    """The phase gate and the evidence index."""
    return readers.evidence()


# ---------------------------------------------------------------------------
# LIVE DHAKA MODE
#
# These endpoints call the Google Routes API from the SERVER. The browser never sees a key and
# never talks to Google directly. Every response carries source / retrieved_at / is_live /
# request_status, and a failed call is reported as unavailable — recorded data is never
# substituted behind a "live" label.
# ---------------------------------------------------------------------------

@app.get("/api/live/corridors", tags=["live"])
def live_corridors(force: bool = False):
    """Every monitored Dhaka corridor, live. `force=true` bypasses the short in-memory cache."""
    return live_service.service.corridors(force=force)


@app.get("/api/live/corridor/{corridor_id}", tags=["live"])
def live_corridor(corridor_id: str, force: bool = False):
    """One corridor: traffic-aware ETA, static ETA, penalty, geometry and speed intervals."""
    return live_service.service.corridor(corridor_id, force=force)


@app.get("/api/live/routes", tags=["live"])
def live_routes(origin_lat: float, origin_lng: float, dest_lat: float, dest_lng: float):
    """Alternative routes between two points, traffic-aware, from the live API."""
    return live_service.service.routes((origin_lat, origin_lng), (dest_lat, dest_lng))


@app.get("/api/live/health", tags=["live"])
def live_health():
    """API health and credential presence. Reports a key fingerprint, never a key."""
    return {"live": live_service.service.health(), "credentials": key_store.status()}


@app.get("/api/predict/{corridor_id}", tags=["predict"])
def predict(corridor_id: str, force: bool = False):
    """Live state, then 5 / 15 / 30 / 60 min ahead.

    The response separates LIVE DHAKA INPUT from MODEL VALIDATED ON REAL BENCHMARK DATA and sets
    `dhaka_accuracy_claimed: false` — there is not yet enough lawful Dhaka ground truth to state
    an accuracy figure, so none is given.
    """
    cur = live_service.service.corridor(corridor_id, force=force)
    pred = predict_live.predictor.predict(
        corridor_id,
        current_state=cur.get("category", "UNKNOWN"),
        duration_s=cur.get("duration_s"),
        static_s=cur.get("static_duration_s"))
    return {"live": cur, "prediction": pred,
            "source": "google_routes + this project's recorded verdicts",
            "retrieved_at": cur.get("retrieved_at"),
            "is_live": cur.get("is_live", False),
            "request_status": cur.get("request_status", "UNKNOWN")}


@app.post("/api/simulate", tags=["simulate"])
def simulate_start(payload: dict):
    """Start a SUMO counterfactual from the selected live state. Returns a job to poll.

    Results are a SIMULATED COUNTERFACTUAL on the calibrated twin, never a live-road outcome.
    """
    return simulate.runner.start(
        corridor_id=payload.get("corridor_id", ""),
        category=payload.get("category", "UNKNOWN"),
        seeds=payload.get("seeds") or [11, 12, 13],
        horizon=int(payload.get("horizon", 1800)),
        compliance=float(payload.get("compliance", 0.3)))


@app.get("/api/simulate/{job_id}", tags=["simulate"])
def simulate_status(job_id: str):
    return simulate.runner.status(job_id)


@app.get("/api/corridors", tags=["live"])
def corridor_list():
    """The monitored corridors and which of them a counterfactual can honestly be run on."""
    return {"corridors": [corridor_registry.describe(c) for c in corridor_registry.CORRIDORS],
            "total": len(corridor_registry.CORRIDORS),
            "sumo_mapped": sum(1 for c in corridor_registry.CORRIDORS if c["sumo_mapped"])}


# ---------------------------------------------------------------------------
# CITY LAYER — arbitrary cities, created at runtime. No city is hard-coded here.
# Instantiating a city is NOT a forecasting claim: capability is gated separately.
# ---------------------------------------------------------------------------

def _city_bits():
    """Imported lazily so the dashboard still starts if the research deps are absent."""
    import sys
    sys.path.insert(0, str(config.REPO))
    from pipeline.city.datasets import catalog
    from pipeline.city.registry import registry
    return registry, catalog


@app.get("/api/cities", tags=["city"])
def cities():
    """Every city known to the system, with what each is ALLOWED to claim."""
    reg, catalog = _city_bits()
    cat = catalog()
    return {"cities": [reg.describe(cid, cat) for cid in reg.list_ids()],
            "capability_order": ["LIVE_ONLY", "SIMULATION_ONLY", "ZERO_SHOT",
                                 "FINE_TUNED", "FULL_FORECAST"]}


@app.get("/api/city/{city_id}", tags=["city"])
def city(city_id: str):
    reg, catalog = _city_bits()
    return reg.describe(city_id, catalog())


@app.post("/api/city", tags=["city"])
def create_city(payload: dict):
    """Create a city from a NAME (geocoded via OSM) or a BBOX drawn on the map.

    This is what makes the system city-agnostic in practice rather than in prose: the user names a
    place and the system finds it, instead of an engineer adding a constant.
    """
    reg, catalog = _city_bits()
    name = (payload.get("name") or "").strip()
    bbox = payload.get("bbox")
    if not name:
        return {"error": "name_required"}
    try:
        spec = (reg.create_from_bbox(name, tuple(bbox)) if bbox
                else reg.create_from_name(name))
    except Exception as exc:                       # noqa: BLE001 - surfaced to the user
        return {"error": "create_failed", "detail": f"{type(exc).__name__}: {exc}"}
    return reg.describe(spec.city_id, catalog())


@app.post("/api/city/{city_id}/graph", tags=["city"])
def build_city_graph(city_id: str, payload: dict | None = None):
    """Build the road graph and select STABLE OBSERVATION NODES (major road edges)."""
    reg, catalog = _city_bits()
    try:
        summary = reg.build_graph(city_id, max_nodes=int((payload or {}).get("max_nodes", 250)))
    except Exception as exc:                       # noqa: BLE001
        return {"error": "graph_failed", "detail": f"{type(exc).__name__}: {exc}"}
    return {"city_id": city_id, "graph": summary,
            "capability": reg.describe(city_id, catalog())["forecast_capability"]}


@app.get("/api/city/{city_id}/nodes", tags=["city"])
def city_nodes(city_id: str):
    reg, _ = _city_bits()
    nodes = reg.nodes(city_id)
    return {"city_id": city_id, "count": len(nodes), "nodes": nodes}


@app.get("/api/datasets", tags=["research"])
def datasets():
    """The research datasets, their scale and what each licenses us to claim.

    Arrays stay on Drive/S3 and are never vendored into git; their existence and scale are visible
    here so a reader can see the evidence base rather than infer it.
    """
    _, catalog = _city_bits()
    cat = catalog()
    return {"datasets": cat, "count": len(cat),
            "storage_note": ("arrays live on Google Drive / S3 / HuggingFace and are deliberately "
                             "not committed; this endpoint exposes their existence and scale"),
            "protocol_warning": ("OpenCity metrics use a 288-step horizon on the authors' split; "
                                 "city-specific models use 15-minute DCRNN horizons. Never "
                                 "compare them directly.")}


@app.get("/api/models", tags=["research"])
def models(city_id: str = "dhaka"):
    """Every forecasting model and whether it can honestly serve this city right now."""
    import sys
    sys.path.insert(0, str(config.REPO))
    from pipeline.forecasting.adapters.registry import available_for
    cd = observatory_mod.observatory.city_data(city_id)
    return {"city_id": city_id, "input": cd.describe(),
            "models": available_for(cd)}


# ---------------------------------------------------------------------------
# OBSERVATORY — the rolling window lives in the SERVER, not in a CLI invocation
# ---------------------------------------------------------------------------

@app.get("/api/observatory", tags=["live"])
def observatory_status(city_id: str = "dhaka"):
    return {"status": observatory_mod.observatory.status(),
            "readiness": observatory_mod.observatory.readiness(city_id)}


@app.post("/api/observatory/start", tags=["live"])
def observatory_start(payload: dict | None = None):
    cid = (payload or {}).get("city_id", "dhaka")
    return observatory_mod.observatory.start(cid)


@app.post("/api/observatory/sample", tags=["live"])
def observatory_sample(payload: dict | None = None):
    cid = (payload or {}).get("city_id", "dhaka")
    return observatory_mod.observatory.sample(cid)


def _recorded_len(city_id: str) -> int:
    """How many 5-minute bins the recorder's on-disk series holds for this city (0 if none)."""
    if city_id != "dhaka":
        return 0
    import sys
    sys.path.insert(0, str(config.REPO))
    from pipeline.forecasting import live_state
    if not live_state.SRC.exists():
        return 0
    rows = live_state.load_rows(live_state.SRC)
    return int(live_state.build(rows)[0].shape[0]) if rows else 0


def _recorded_is_longer(city_id: str, cd) -> bool:
    """The model is given whichever real history is LONGER — the in-memory buffer or the recorded
    series on disk — never a short buffer just because it is newer."""
    return _recorded_len(city_id) > int(cd.shape[0])


@app.get("/api/forecast/{city_id}", tags=["predict"])
def city_forecast(city_id: str, horizons: str = "5,15,30,60", source: str = "auto",
                  model: str | None = None):
    """The real forecast path: whichever model can honestly serve this city, or a LABELLED baseline.

    `source` says which observations the model is given. `observatory` is the rolling in-memory
    buffer (derived speeds; empty after a restart). `recorded` is the REAL_LIVE series the
    recorder wrote to disk over days (derived congestion classes). `auto` uses the buffer when it
    holds enough steps for a model to serve and the recorded window otherwise — and the response
    says which, so a click after a restart gets a real model over real history, never a floor
    dressed as the system's forecast.
    """
    import sys
    sys.path.insert(0, str(config.REPO))
    from pipeline.forecasting.adapters.registry import forecast as run_forecast
    hs = [int(h) for h in horizons.split(",") if h.strip().isdigit()]
    cd = observatory_mod.observatory.city_data(city_id)
    use_recorded = source == "recorded" or (source == "auto" and _recorded_is_longer(city_id, cd))
    if use_recorded:
        from pipeline.routing.forecast_to_costs import recorded_forecast
        out = recorded_forecast(city_id, hs, model, "latest")
        out["source"] = "recorded"
    else:
        out = run_forecast(cd, hs, model)
        out["input"] = cd.describe()
        out["source"] = "observatory"
    out["readiness"] = observatory_mod.observatory.readiness(city_id)
    try:
        out["logged_rows"] = forecast_log.log(out, city_id, source=out["source"])
    except Exception as exc:                        # noqa: BLE001 - the ledger must not break a forecast
        out["logged_rows"] = f"not logged: {type(exc).__name__}: {exc}"
    return out


@app.get("/api/forecast/{city_id}/scoreboard", tags=["predict"])
def city_forecast_scoreboard(city_id: str):
    """The system's own track record: forecasts it issued, graded against what was recorded next.

    Unlike the backtest (a replay), these were written down BEFORE their target time and cannot
    be revised. The scheduler issues one every five minutes while the server runs.
    """
    return forecast_log.score(city_id)


@app.get("/api/opencity/{city_id}", tags=["predict"])
def opencity_status(city_id: str):
    """Where the foundation model stands for this city, in the model's own terms.

    OpenCity runs through the authors' harness as a batch job. This reports how much of the
    history it needs has accumulated (the persisted observatory window), whether the CPU path has
    been verified, and the result once the run exists — never a fabricated number in between.
    """
    import sys
    sys.path.insert(0, str(config.REPO))
    from pipeline.forecasting import opencity_city_eval as oce
    return oce.readiness(city_id)


@app.get("/api/forecast/{city_id}/accuracy", tags=["predict"])
def city_forecast_accuracy(city_id: str):
    """How accurate the forecast is on THIS city's own recorded data — a rolling-origin backtest.

    Every model is cut at each origin bin, forecasts from that history only, and is scored on
    what the recorder later wrote. Read from the evidence file; the command regenerates it.
    """
    f = config.REPO / "results/forecasting/live_backtest.json"
    if city_id != "dhaka" or not f.exists():
        return {"available": False, "city_id": city_id,
                "missing": "results/forecasting/live_backtest.json",
                "command": "python pipeline/forecasting/live_backtest.py"}
    return {"available": True, **json.loads(f.read_text())}


# ---------------------------------------------------------------------------
# MISSION CONTROL feeds. Each returns REAL recorded data; none synthesises values.
# ---------------------------------------------------------------------------

@app.get("/api/history/{city_id}", tags=["predict"])
def history(city_id: str, horizons: str = "5,15,30,60"):
    """Observed history AND the forecast, in one payload, so a chart can draw both.

    The history is what the observatory actually recorded; the forecast is the same call the rest
    of the system uses. Nothing here is generated to make a curve look continuous — a gap in the
    record stays a gap.
    """
    import sys
    sys.path.insert(0, str(config.REPO))
    from pipeline.forecasting.adapters.registry import forecast as run_forecast
    rows, nodes = observatory_mod.observatory.series(city_id)
    hs = [int(h) for h in horizons.split(",") if h.strip().isdigit()]
    cd = observatory_mod.observatory.city_data(city_id)
    if _recorded_is_longer(city_id, cd):
        # the recorded REAL_LIVE series on disk is the longer history: draw that day and forecast
        # from it — the same window E1 was measured on, so its accuracy can be quoted
        from pipeline.routing.forecast_to_costs import recorded_city_data
        rcd, observed = recorded_city_data(city_id, "latest")
        out = run_forecast(rcd, hs)
        window = 288
        v = rcd.values[-window:]
        ts = rcd.timestamps[-window:]
        acc = config.REPO / "results/forecasting/live_backtest.json"
        accuracy = None
        if acc.exists():
            bt = json.loads(acc.read_text())
            m = (out.get("forecast") or {}).get("model")
            accuracy = {"rows": [r for r in bt["rows"] if r["model"] in (m, "persistence")],
                        "origins": bt["origins_evaluated"], "bins": bt["bins"]}
        return {
            "city_id": city_id, "nodes": rcd.node_ids,
            "history": [{"utc": t, "values": [None if x != x else round(float(x), 3) for x in row]}
                        for t, row in zip(ts, v)],
            "interval_s": rcd.interval_s, "unit": rcd.unit,
            "forecast": out.get("forecast"), "decision": out.get("decision"),
            "observed": observed, "accuracy": accuracy,
            "readiness": observatory_mod.observatory.readiness(city_id),
            "source": ("recorded REAL_LIVE series on disk (derived congestion classes), last 24 h, "
                       "+ the common forecast interface"),
        }
    out = run_forecast(cd, hs) if cd.shape[0] else {"forecast": None, "decision": None}
    return {
        "city_id": city_id,
        "nodes": nodes,
        "history": [{"utc": r["utc"], "values": [None if v != v else round(v, 3) for v in r["v"]]}
                    for r in rows],
        "interval_s": observatory_mod.observatory.interval_s,
        "unit": "m/s",
        "forecast": out.get("forecast"),
        "decision": out.get("decision"),
        "readiness": observatory_mod.observatory.readiness(city_id),
        "source": "observatory rolling buffer (derived speeds) + the common forecast interface",
    }


@app.get("/api/experiment/sweep", tags=["experiment"])
def experiment_sweep(grid: str = "compliance"):
    """E4: the penetration curve, every point a full three-arm paired-seed run."""
    f = config.REPO / f"results/routing/sweep_{grid}.json"
    if not f.exists():
        return {"available": False, "missing": str(f.relative_to(config.REPO)),
                "command": f"make sweep" if grid == "compliance" else "make sweep-v2x"}
    return {"available": True, **json.loads(f.read_text())}


@app.get("/api/experiment/ablation", tags=["experiment"])
def experiment_ablation():
    """E3: oracle / model / persistence / random through the same chain."""
    f = config.REPO / "results/routing/ablation_forecast_quality.json"
    if not f.exists():
        return {"available": False, "missing": str(f.relative_to(config.REPO)), "command": "make ablation"}
    return {"available": True, **json.loads(f.read_text())}


@app.get("/api/experiment/chain", tags=["experiment"])
def experiment_chain(tag: str = "_ideal", run_id: str | None = None):
    """A chain experiment that HAS run — the newest of `tag`, or the run you name.

    This endpoint only reads; POST /api/experiment/chain/run executes a new one.
    """
    ic = _chain_module()
    f = (ic.RUNS / run_id / "run.json") if run_id else \
        (config.REPO / f"results/routing/integrated_chain{tag}.json")
    if not f.exists():
        return {"available": False,
                "missing": str(f.relative_to(config.REPO)),
                "run_it": "POST /api/experiment/chain/run",
                "command": "python pipeline/routing/integrated_chain.py --seeds 11,12,13,14,15"}
    return {"available": True, **json.loads(f.read_text())}


# ---------------------------------------------------------------------------
# RUNNING the chain, not reading a past one. POST starts a real execution in a worker thread and
# returns its run id immediately; the GET below reports what that execution has actually produced
# so far. Nothing in this section synthesises a metric.
# ---------------------------------------------------------------------------

_CHAIN_LOCK = threading.Lock()
_CHAIN_ACTIVE: dict[str, dict] = {}


def _chain_module():
    import sys
    sys.path.insert(0, str(config.REPO))
    from pipeline.routing import integrated_chain
    return integrated_chain


@app.post("/api/experiment/chain/run", tags=["experiment"])
def experiment_chain_run(payload: dict | None = None):
    """Execute the whole chain now: forecast -> future edge costs -> routing -> SUMO -> metrics.

    Body (all optional): seeds, horizon, horizon_min, compliance, v2x, source, as_of, levels, tag.
    Returns a run_id straight away — SUMO takes minutes, so the run is done on a worker thread and
    polled through /api/experiment/chain/run/{run_id}.
    """
    ic = _chain_module()
    opts = {k: v for k, v in (payload or {}).items()
            if k in ic.DEFAULTS or k in ("run_id",)}
    run_id = ic.new_run_id(str(opts.get("tag") or ""))
    opts["run_id"] = run_id

    with _CHAIN_LOCK:
        busy = [r for r, st in _CHAIN_ACTIVE.items() if st.get("status") == "running"]
        if busy:
            return {"started": False, "reason": "a chain run is already in flight on this server",
                    "running": busy}
        _CHAIN_ACTIVE[run_id] = {"run_id": run_id, "status": "running", "stage": "starting"}

    def _work():
        try:
            rec = ic.run_chain(**opts)
            with _CHAIN_LOCK:
                _CHAIN_ACTIVE[run_id] = {"run_id": run_id, "status": "done",
                                         "summary": rec["summary"]}
        except BaseException as exc:                    # noqa: BLE001 - reported, never swallowed
            with _CHAIN_LOCK:
                _CHAIN_ACTIVE[run_id] = {"run_id": run_id, "status": "failed",
                                         "error": f"{type(exc).__name__}: {exc}"}
            (ic.RUNS / run_id).mkdir(parents=True, exist_ok=True)
            (ic.RUNS / run_id / "status.json").write_text(json.dumps(
                {"run_id": run_id, "status": "failed",
                 "error": f"{type(exc).__name__}: {exc}"}, indent=1))

    threading.Thread(target=_work, name=f"chain-{run_id}", daemon=True).start()
    return {"started": True, "run_id": run_id, "config": opts,
            "poll": f"/api/experiment/chain/run/{run_id}",
            "note": ("this is a real execution: a model forecast, a duarouter re-route on its "
                     "output and three SUMO runs. Metrics appear only when they are measured.")}


@app.get("/api/experiment/chain/runs", tags=["experiment"])
def experiment_chain_runs(limit: int = 20):
    """Every chain execution this repository holds, newest first."""
    ic = _chain_module()
    out = []
    if ic.RUNS.exists():
        for d in sorted((x for x in ic.RUNS.iterdir() if x.is_dir()), reverse=True)[:limit]:
            st = d / "status.json"
            rec = json.loads(st.read_text()) if st.exists() else {"run_id": d.name,
                                                                  "status": "unknown"}
            out.append({"run_id": d.name, "status": rec.get("status"),
                        "stage": rec.get("stage"), "started_utc": rec.get("started_utc"),
                        "arms_done": rec.get("arms_done"), "arms_total": rec.get("arms_total"),
                        "finished": (d / "run.json").exists()})
    return {"runs": out, "dir": (str(ic.RUNS.relative_to(config.REPO))
                                 if ic.RUNS.is_relative_to(config.REPO) else str(ic.RUNS))}


@app.get("/api/experiment/chain/run/{run_id}", tags=["experiment"])
def experiment_chain_status(run_id: str):
    """What THIS execution measured. While it runs, the stage and the arms already finished."""
    ic = _chain_module()
    d = ic.RUNS / run_id
    if ".." in run_id or "/" in run_id or not d.is_dir():
        return {"found": False, "run_id": run_id}
    st = json.loads((d / "status.json").read_text()) if (d / "status.json").exists() else {}
    done = d / "run.json"
    with _CHAIN_LOCK:
        live = _CHAIN_ACTIVE.get(run_id, {})
    return {"found": True, "run_id": run_id, "status": live.get("status", st.get("status")),
            "stage": st.get("stage"), "arms_done": st.get("arms_done"),
            "arms_total": st.get("arms_total"), "error": live.get("error") or st.get("error"),
            "config": st.get("config"), "command": st.get("command"),
            "result": json.loads(done.read_text()) if done.exists() else None}


# ---------------------------------------------------------------------------
# THE LIVE TWIN: SUMO stepped under the viewer's eye, and an agent that drives it.
# ---------------------------------------------------------------------------

@app.post("/api/sim/live/start", tags=["twin"])
def sim_live_start(payload: dict | None = None):
    """Start a live SUMO run: scale, duration_s, seed, compliance, arm, step_delay_ms."""
    return live_sim_mod.live_sim.start(payload or {})


@app.post("/api/sim/live/pause", tags=["twin"])
def sim_live_pause():
    return live_sim_mod.live_sim.pause()


@app.post("/api/sim/live/resume", tags=["twin"])
def sim_live_resume():
    return live_sim_mod.live_sim.resume()


@app.post("/api/sim/live/stop", tags=["twin"])
def sim_live_stop():
    return live_sim_mod.live_sim.stop()


@app.get("/api/sim/live/state", tags=["twin"])
def sim_live_state(vehicles: bool = True):
    """KPIs and every vehicle's position, as SUMO computed them this step."""
    return live_sim_mod.live_sim.state(with_vehicles=vehicles)


@app.get("/api/sim/live/history", tags=["twin"])
def sim_live_history():
    return {"runs": live_sim_mod.live_sim.history()}


@app.post("/api/sim/agent", tags=["twin"])
def sim_agent_chat(payload: dict):
    """Natural language -> the same start/pause/resume/stop the buttons call."""
    return sim_agent.chat(str(payload.get("message", "")), payload.get("history") or [])


@app.get("/api/config/map", tags=["meta"])
def map_config():
    """Which basemap the browser should use. A Mapbox public token is meant for the browser;
    without one the Esri street tiles are used. Never a secret key."""
    tok = key_store.mapbox_token()
    if tok:
        return {"provider": "mapbox",
                "tiles": f"https://api.mapbox.com/styles/v1/mapbox/streets-v12/tiles/256/{{z}}/{{x}}/{{y}}?access_token={tok}",
                "attribution": "© Mapbox © OpenStreetMap | Traffic © Google Routes API"}
    return {"provider": "esri",
            "tiles": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
            "attribution": "Tiles © Esri | Traffic © Google Routes API"}


@app.get("/api/networking/conditions", tags=["network"])
def networking_conditions():
    """Measured V2X delivery per (latency, loss), beside the federated forecast error.

    Both halves are read from evidence files. The delivery table comes from the Eclipse MOSAIC
    ITS-G5 sweep; the forecast errors come from the federated runs on AWS. They are SIMULATED
    communication events, not radio-hardware measurements, and the payload says so.
    """
    import csv as _csv
    lat = config.REPO / "results/networking/latency.csv"
    fed = config.REPO / "results/forecasting/federated.json"
    conditions = []
    if lat.exists():
        for r in _csv.DictReader(lat.open()):
            conditions.append({
                "added_latency_ms": int(r["added_latency_ms"]),
                "loss_pct": int(float(r["loss_pct"])),
                "delivery_single": float(r["frac_delivered_single_shot"]),
                "delivery_repeat": float(r["frac_delivered_1hz_repeat"]),
                "effective_latency_ms": float(r["effective_latency_mean_ms"]),
                "n_vehicles": int(r["n_vehicles"]),
            })
    federated = json.loads(fed.read_text()) if fed.exists() else {}
    return {
        "conditions": conditions,
        "federated": federated,
        "nature": ("SIMULATED — Eclipse MOSAIC ITS-G5 model, not radio hardware"),
        "source": {"delivery": "results/networking/latency.csv",
                   "federated": "results/forecasting/federated.json"},
    }


@app.get("/api/health", tags=["meta"])
def health():
    """Liveness plus data freshness — a dashboard must say when its data is stale."""
    h = readers.recorder_health()
    return {"status": "ok", "recorder_healthy": h.healthy, "last_tick_utc": h.last_tick_utc,
            "age_minutes": h.age_minutes}


def _pulse() -> dict:
    """A diff-sized payload: the browser already holds the tables, so only freshness and the
    latest level per corridor travel on the wire."""
    t, e = readers.traffic(), readers.evidence()
    return {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "recorder": t.recorder.model_dump() if t.recorder else None,
            "corridors": [{"id": c.id, "level": c.level, "state": c.state} for c in t.corridors],
            "bins": t.bins, "span_hours": t.span_hours, "gate_passed": e.gate_passed}


@app.get("/api/stream", tags=["realtime"])
async def stream(request: Request):
    """SSE. Emits on change, heartbeats otherwise, and tells the client how long to back off."""
    async def events():
        yield f"retry: {config.SSE_INTERVAL_S * 1000}\n\n"
        last = None
        while not await request.is_disconnected():
            payload = json.dumps(_pulse(), default=str)
            if payload != last:
                yield f"event: update\ndata: {payload}\n\n"
                last = payload
            else:
                yield ": heartbeat\n\n"
            await asyncio.sleep(config.SSE_INTERVAL_S)

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.on_event("startup")
def _start_observatory() -> None:
    """Begin accumulating the rolling window as soon as the server is up.

    The buffer only means anything if it is filling, and the audit's finding was that it never
    could. Starting it here is what makes readiness a real countdown: leave the server running and
    the 288-step window fills in about a day. Sampling is off by default in tests, where a live
    API call per tick would be both slow and pointless.
    """
    import os
    if os.environ.get("DHAKAFLOW_NO_OBSERVATORY"):
        return
    try:
        forecast_log.start_scheduler("dhaka")
        observatory_mod.observatory.start("dhaka")
    except Exception:                              # noqa: BLE001 - never block startup
        pass


FRONTEND = config.REPO / "dashboard/frontend"
if FRONTEND.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND), name="static")
    if (config.REPO / "docs/media").exists():
        app.mount("/media", StaticFiles(directory=config.REPO / "docs/media"), name="media")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(FRONTEND / "index.html")


if __name__ == "__main__":
    import uvicorn
    print("DhakaFlow -> http://127.0.0.1:8000    docs -> /api/docs")
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
