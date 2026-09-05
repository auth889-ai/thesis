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

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from pathlib import Path
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
import analyze
import twin_compare
import predict_lab
import city_corridors

app = FastAPI(title="TrafficTwin", version="1.0.0", docs_url="/api/docs",
              description="Traffic prediction (ML/DL), route optimization, SUMO simulation and V2X networking — for any city.")


@app.middleware("http")
async def _no_stale_frontend(request: Request, call_next):
    """The interface is ES modules; a browser that caches them shows yesterday's app after every
    change. Static files are always revalidated, so a plain reload shows the current code."""
    resp = await call_next(request)
    if request.url.path.startswith("/static") or request.url.path in ("/", "/index.html"):
        resp.headers["Cache-Control"] = "no-store"
    return resp


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


def _opencity_predict(args: list[str]) -> dict:
    """Run the authors' stack in a subprocess (it chdirs and rewrites argv) and return its JSON."""
    import subprocess
    import sys as _sys
    import tempfile
    out = Path(tempfile.mkdtemp(prefix="opencity_")) / "prediction.json"
    cmd = [_sys.executable, str(config.REPO / "pipeline/forecasting/opencity_predict.py"), *args,
           "--out", str(out)]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=900, cwd=config.REPO)
    if proc.returncode != 0 or not out.exists():
        tail = (proc.stderr or proc.stdout or "")[-1200:]
        return {"ok": False, "error": tail.strip().splitlines()[-1] if tail.strip() else "no output",
                "log_tail": tail}
    return {"ok": True, **json.loads(out.read_text())}


@app.post("/api/opencity/{city_id}/predict", tags=["predict"])
def opencity_predict_city(city_id: str, payload: dict | None = None):
    """OpenCity-plus forward pass on this city's own window (persisted observatory speeds by
    default, or the recorded classes), through the authors' unmodified stack. Refuses, with the
    model's own reason, when the window is too short or the graph too small."""
    p = payload or {}
    args = ["--source", str(p.get("source", "observatory")), "--city", city_id,
            "--horizons", str(p.get("horizons", "15,30,60"))]
    if p.get("as_of") is not None:
        args += ["--as-of", str(int(p["as_of"]))]
    return _opencity_predict(args)


@app.post("/api/opencity/upload", tags=["predict"])
async def opencity_predict_upload(csv: UploadFile = File(...), adj: UploadFile = File(...),
                                  horizons: str = Form("15,30,60"), as_of: str = Form("")):
    """Their demo's contract: a CSV (`time` + one column per region) and an `_rn_adj.npy`."""
    import tempfile
    d = Path(tempfile.mkdtemp(prefix="opencity_upload_"))
    csv_path, adj_path = d / "city.csv", d / "city_rn_adj.npy"
    csv_path.write_bytes(await csv.read()); adj_path.write_bytes(await adj.read())
    args = ["--source", "csv", "--csv", str(csv_path), "--adj", str(adj_path), "--horizons", horizons]
    if as_of.strip():
        args += ["--as-of", as_of.strip()]
    return _opencity_predict(args)


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
    return {"available": True, "result_source": "RESEARCH_BENCHMARK", **json.loads(f.read_text())}


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
    return {"available": True, "result_source": "RESEARCH_BENCHMARK", **json.loads(f.read_text())}


@app.get("/api/experiment/ablation", tags=["experiment"])
def experiment_ablation():
    """E3: oracle / model / persistence / random through the same chain."""
    f = config.REPO / "results/routing/ablation_forecast_quality.json"
    if not f.exists():
        return {"available": False, "missing": str(f.relative_to(config.REPO)), "command": "make ablation"}
    return {"available": True, "result_source": "RESEARCH_BENCHMARK", **json.loads(f.read_text())}


@app.get("/api/experiment/oracle_gate", tags=["experiment"])
def experiment_oracle_gate(seed_set: str = "final"):
    """The frozen oracle outcome gate (Blocker #3): the newest report of the named seed set, read as-is."""
    root = config.REPO / "results/routing/oracle_gate"
    cands = sorted(root.glob(f"FINAL_PROTOCOL_v1_{seed_set}_cfg*/report.json"), key=lambda f: f.stat().st_mtime) if root.exists() else []
    if not cands:
        return {"available": False, "command": f"python pipeline/routing/oracle_gate.py --seeds {seed_set}"}
    rep = json.loads(cands[-1].read_text())
    P = rep.get("protocol", {})
    return {"available": True, "result_source": "RESEARCH_BENCHMARK", "report": str(cands[-1].relative_to(config.REPO)), "seed_set": rep.get("seed_set"),
            "seeds": rep.get("seeds"), "verdict": rep.get("verdict"), "primary": rep.get("primary"), "paired": rep.get("paired"),
            "same_population_all_seeds": rep.get("same_population_all_seeds"), "generated_utc": rep.get("generated_utc"),
            "protocol": {k: P.get(k) for k in ("protocol_id", "network", "network_hash", "demand_source", "demand_sample_fraction", "simulation_duration_s", "routing_round_s",
                                               "compliance", "routing_config_hash", "min_saving_s", "min_saving_pct", "sumo_version", "dev_seeds", "final_seeds", "primary_metric", "coverage_mode")},
            "learned_model_final_outcome": {"status": "SEE_LEARNED_GATE", "endpoint": "/api/experiment/learned_gate", "note": "the learned-model outcome runs under its own frozen protocol (FINAL_LEARNED_PROTOCOL_v1) and is reported separately"}}


@app.get("/api/forecast-map/{dataset}", tags=["predict"])
def forecast_map_network(dataset: str, as_of: str | None = None, model: str | None = None):
    """The future state of the road network at one dataset moment: every sensor's prediction, the
    DIRECT/DERIVED edges the router prices, the unforecast backdrop, and the coverage counts."""
    import forecast_map
    try:
        return forecast_map.network(dataset, as_of, model)
    except KeyError as ex:
        raise HTTPException(404, str(ex))


@app.get("/api/forecast-map/{dataset}/road", tags=["predict"])
def forecast_map_road(dataset: str, node: str, as_of: str | None = None, models: str = "GWNet,persistence"):
    """One sensor: history, each model's prediction, the measured future when inside the data."""
    import forecast_map
    try:
        return forecast_map.road(dataset, node, as_of, tuple(m for m in models.split(",") if m))
    except (KeyError, ValueError) as ex:
        raise HTTPException(404, str(ex))


@app.get("/api/experiment/learned_gate", tags=["experiment"])
def experiment_learned_gate(seed_set: str = "final"):
    """The frozen learned-model outcome gate (Blocker #6): the newest report of the named seed set, read as-is.
    Headline pairs: Graph WaveNet vs baseline, vs reactive, vs persistence-predictive; persistence vs baseline.
    The oracle arm, when present, is research-only and never the headline."""
    root = config.REPO / "results/routing/learned_gate"
    cands = sorted(root.glob(f"FINAL_LEARNED_PROTOCOL_v1_{seed_set}_cfg*/report.json"), key=lambda f: f.stat().st_mtime) if root.exists() else []
    if not cands:
        return {"available": False, "command": f"python pipeline/routing/learned_gate.py --seeds {seed_set}"}
    rep = json.loads(cands[-1].read_text())
    P = rep.get("protocol", {})
    key = P.get("primary_metric_key", "total_vehicle_hours_incl_never_inserted")
    pairs = rep.get("paired", {})
    def head(pk):
        st = (pairs.get(pk) or {}).get(key) or {}
        return {k: st.get(k) for k in ("pair", "seeds", "mean_pct", "median_pct", "ci95", "wins", "losses", "ties", "label", "p_value", "mean_abs")}
    prov = {"protocol_id": P.get("protocol_id"), "model": P.get("model_label"), "checkpoint": P.get("checkpoint"), "checkpoint_sha256": P.get("checkpoint_sha256"), "dataset": P.get("dataset"),
            "dataset_hash": P.get("dataset_hash"), "graph_hash": P.get("graph_hash"), "mapping_hash": P.get("mapping_hash"), "network_hash": P.get("network_hash"), "routing_config_hash": P.get("routing_config_hash"),
            "sumo_version": P.get("sumo_version"), "seeds": rep.get("seeds"), "report": str(cands[-1].relative_to(config.REPO)), "generated_utc": rep.get("generated_utc"), "result_source": "RESEARCH_BENCHMARK"}
    per_seed = [{"seed": r["seed"], "analysis_run_id": r.get("analysis_run_id"), "raw_prediction_hash": r.get("raw_prediction_hash"), "as_of_time": (r.get("forecast_quality") or {}).get("as_of_time"),
                 "arms": {a: {"simulation_run_id": x.get("simulation_run_id"), "routing_run_ids": x.get("routing_run_ids"), "edge_cost_hashes": x.get("edge_cost_hashes"),
                              "vehicle_hours": (x.get("metrics") or {}).get(key), "teleports": len((x.get("metrics") or {}).get("teleport_events") or [])} for a, x in (r.get("arms") or {}).items()},
                 **{k: v for k, v in (r.get("quality_vs_outcome") or {}).items()}} for r in rep.get("per_seed", [])]
    return {"available": True, "result_source": "RESEARCH_BENCHMARK", "report": prov["report"], "seed_set": rep.get("seed_set"), "seeds": rep.get("seeds"), "verdict": rep.get("verdict"), "outcome": rep.get("outcome"),
            "primary_metric": P.get("primary_metric"), "learned_vs_baseline": head("learned_predictive_vs_baseline"), "learned_vs_reactive": head("learned_predictive_vs_reactive"),
            "learned_vs_persistence": head("learned_predictive_vs_persistence_predictive"), "persistence_vs_baseline": head("persistence_predictive_vs_baseline"), "reactive_vs_baseline": head("reactive_vs_baseline"),
            "oracle_research_only": head("oracle_vs_baseline") if "oracle_vs_baseline" in pairs else None, "paired": pairs, "teleports": rep.get("teleports"),
            "forecast_quality": {k: v for k, v in (rep.get("forecast_quality") or {}).items() if k != "per_seed"}, "per_seed": per_seed, "same_population_all_seeds": rep.get("same_population_all_seeds"),
            "provenance": prov, "protocol": {k: P.get(k) for k in ("protocol_id", "city_id", "dataset", "model", "model_label", "checkpoint", "checkpoint_sha256", "held_out_skill", "mapping_counts", "coverage_hops", "min_saving_s", "min_saving_pct",
                                                                  "demand_method", "calibration_method", "simulation_duration_s", "routing_round_s", "round_horizons_min", "compliance", "forecast_moments", "sumo_version", "dev_seeds", "final_seeds", "primary_metric", "model_selection_rule")},
            "generated_utc": rep.get("generated_utc")}


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
    rec = json.loads(f.read_text())
    kind = str(((rec.get("options") or rec.get("request") or {}).get("forecast_kind")) or rec.get("forecast_kind") or "").lower()
    src = "SYNTHETIC_WHAT_IF" if kind in ("random", "oracle") else "RESEARCH_BENCHMARK"
    return {"available": True, "result_source": src, **rec}


# ---------------------------------------------------------------------------
# RUNNING the chain, not reading a past one. POST starts a real execution in a worker thread and
# returns its run id immediately; the GET below reports what that execution has actually produced
# so far. Nothing in this section synthesises a metric.
# ---------------------------------------------------------------------------

_CHAIN_LOCK = threading.Lock()
_CHAIN_ACTIVE: dict[str, dict] = {}


def _read_json(path) -> dict | None:
    """A status file is rewritten after every arm; a reader may catch it half-written."""
    try:
        return json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError):
        return None


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
            rec = _read_json(d / "status.json") or {"run_id": d.name, "status": "unknown"}
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
    st = _read_json(d / "status.json") or {}
    done = d / "run.json"
    result = _read_json(done) if done.exists() else None
    with _CHAIN_LOCK:
        live = _CHAIN_ACTIVE.get(run_id, {})
    return {"found": True, "run_id": run_id, "status": live.get("status", st.get("status")),
            "stage": st.get("stage"), "arms_done": st.get("arms_done"),
            "arms_total": st.get("arms_total"), "error": live.get("error") or st.get("error"),
            "config": st.get("config"), "command": st.get("command"),
            "result": result}


# ---------------------------------------------------------------------------
# THE LIVE TWIN: SUMO stepped under the viewer's eye, and an agent that drives it.
# ---------------------------------------------------------------------------

@app.post("/api/sim/live/start", tags=["twin"])
def sim_live_start(payload: dict | None = None):
    """Start a live SUMO run: scale, duration_s, seed, compliance, arm, step_delay_ms."""
    return live_sim_mod.live_sim.start(payload or {})


@app.post("/api/sim/live/screenshot", tags=["twin"])
def sim_live_screenshot(payload: dict | None = None):
    """sumo-gui writes its own view to a PNG (TraCI gui.screenshot)."""
    return live_sim_mod.live_sim.screenshot((payload or {}).get("path"))


@app.post("/api/sim/live/follow", tags=["twin"])
def sim_live_follow(payload: dict | None = None):
    """Follow one simulated vehicle in the sumo-gui window."""
    return live_sim_mod.live_sim.follow((payload or {}).get("vehicle_id"))


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


_NET_JOBS: dict[str, dict] = {}


@app.post("/api/city/{city_id}/observe", tags=["city"])
def city_observe(city_id: str, payload: dict | None = None):
    """Start learning a city: derive its observation corridors from its road graph, sample them
    live every five minutes (persisted), and serve forecasts as soon as the history allows.
    Accepts a registered city id or a free city name (created and geocoded on the spot)."""
    reg, catalog = _city_bits()
    cid = analyze.city_id_for(city_id) or (city_id if reg.get(city_id) else None)
    if cid == "dhaka":
        observatory_mod.observatory.start("dhaka")
        return {"ok": True, "city_id": "dhaka", "corridors": [], "readiness": observatory_mod.observatory.readiness("dhaka")}
    if not cid:
        try:
            cid = reg.create_from_name(city_id).city_id
        except Exception as exc:                       # noqa: BLE001
            return {"ok": False, "error": f"cannot find city {city_id!r}: {type(exc).__name__}: {exc}"}
    try:
        cs = city_corridors.ensure(cid, int((payload or {}).get("corridors", city_corridors.DEFAULT_K)))
        if (payload or {}).get("routes"):
            cs = city_corridors.add_routes(cid, payload["routes"])
    except Exception as exc:                           # noqa: BLE001
        return {"ok": False, "city_id": cid, "error": f"could not derive corridors: {type(exc).__name__}: {exc}"}
    observatory_mod.observatory.start(cid)
    import time as _t
    _t.sleep(2.5)                                       # the wake-up sample is running; let it land
    return {"ok": True, "city_id": cid, "corridors": cs, "readiness": observatory_mod.observatory.readiness(cid),
            "next": {"persistence": "after the first sample", "Chronos-Bolt": "after 8 samples (~40 min)",
                     "OpenCity-plus": "after 288 samples (24 h) with >= 9 corridors"}}


@app.get("/api/city/{city_id}/observe", tags=["city"])
def city_observe_status(city_id: str):
    city_id = analyze.city_id_for(city_id) or city_id
    r = observatory_mod.observatory.readiness(city_id)
    return {"city_id": city_id, "corridors": city_corridors.load(city_id) if city_id != "dhaka" else None,
            "watched": city_id in observatory_mod.observatory.cities(), "readiness": r,
            "live": live_service.service.corridors_for(city_id) if city_corridors.load(city_id) or city_id == "dhaka" else None}


@app.get("/api/predict-lab/datasets", tags=["predict"])
def predict_lab_datasets():
    """Real datasets present locally and the models that can serve each."""
    return {"datasets": predict_lab.datasets()}


@app.post("/api/predict-lab/upload", tags=["predict"])
async def predict_lab_upload(csv: UploadFile = File(...), name: str = Form("my city"), quantity: str = Form("speed_kmh"),
                             adj: UploadFile | None = File(None), coords: UploadFile | None = File(None)):
    """Any city, your data: a CSV (wide `time,<road>...` or long `time,road,value`), optionally a
    coordinates CSV or an adjacency `.npy`, becomes a dataset every model on the page can serve."""
    import user_datasets
    try:
        meta = user_datasets.save(name, await csv.read(), quantity,
                                  adj_bytes=(await adj.read()) if adj and adj.filename else None,
                                  coords_bytes=(await coords.read()) if coords and coords.filename else None)
    except Exception as exc:                            # noqa: BLE001 - the page shows the reason
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    return {"ok": True, "dataset": f"user:{meta['id']}", "meta": meta, "models": user_datasets.models_for(meta)}


@app.post("/api/predict-lab/run", tags=["predict"])
def predict_lab_run(payload: dict):
    """A real forward pass: dataset, region, moment, model -> prediction, scored where possible."""
    return {"job": predict_lab.start(payload or {}), "poll": "/api/predict-lab/{job}"}


@app.post("/api/predict-lab/train", tags=["predict"])
def predict_lab_train(payload: dict):
    """Train an official BasicTS baseline (STID / GWNet) on THIS dataset — their data preparation,
    config, runner and metrics, on CPU. Returns a job to poll; the model then appears in the menu."""
    return {"job": predict_lab.train_start(payload or {}), "poll": "/api/predict-lab/train/{job}"}


@app.get("/api/predict-lab/train/{job}", tags=["predict"])
def predict_lab_train_status(job: str):
    return predict_lab.train_status(job)


# ---------------------------------------------------------------------------
# TRAINING DISPATCHER: one job id from the Train button to a trusted (or honestly untrusted) model.
# ---------------------------------------------------------------------------

@app.post("/api/train", tags=["train"])
def train_create(payload: dict):
    """Create a training job. Policy: small jobs run here, larger ones on an AWS single-GPU worker
    (unless `where` pins it). Returns the job id to poll."""
    import train_jobs
    try:
        return train_jobs.start(payload or {})
    except ValueError as exc:
        return {"error": str(exc)}


@app.get("/api/train", tags=["train"])
def train_list():
    import train_jobs
    return {"jobs": train_jobs.list_jobs()}


@app.get("/api/train/{job_id}", tags=["train"])
def train_status(job_id: str):
    """Stage (QUEUED … COMPLETE | FAILED), epoch and validation metrics while training, then the
    validation / test tables, checkpoint verification and the trust gate."""
    import train_jobs
    j = train_jobs.get(job_id)
    if j.get("status") == "done" and not j.get("identity"):
        j["identity"] = train_jobs.identity_for(job_id)          # the causal-chain record of a finished job
    return j


@app.post("/api/train/{job_id}/cancel", tags=["train"])
def train_cancel(job_id: str):
    """Stop a job; a cloud worker is terminated immediately."""
    import train_jobs
    return train_jobs.cancel(job_id)


@app.get("/api/predict-lab/cloud", tags=["predict"])
def predict_lab_cloud():
    """Whether the GPU path is configured (AWS keys on the server, aws CLI present). Never a key value."""
    return predict_lab.cloud()


@app.get("/api/predict-lab/trained", tags=["predict"])
def predict_lab_trained():
    """Models trained here, with their test metrics beside persistence on the same split."""
    return {"trained": predict_lab.trained()}


@app.get("/api/predict-lab/{job}", tags=["predict"])
def predict_lab_status(job: str):
    return predict_lab.status(job)


@app.get("/api/operate/cities", tags=["operate"])
def operate_cities():
    """Cities the operations screen offers: Dhaka (observed, forecastable) plus any registered
    city — and any other name typed in is geocoded on the spot."""
    reg, _ = _city_bits()
    out = [{"id": "dhaka", "label": "Dhaka", "forecast": True}]
    watched = set(observatory_mod.observatory.cities())
    for cid in reg.list_ids():
        sp = reg.get(cid)
        if sp and sp.display_name and not analyze.is_dhaka(sp.display_name) and cid in watched:   # only cities with history
            out.append({"id": cid, "label": sp.display_name, "forecast": cid in watched,
                        "steps": observatory_mod.observatory.readiness(cid)["steps_have"] if cid in watched else 0})
    import user_datasets
    for d in user_datasets.datasets():                  # uploaded datasets with road coordinates are operable cities
        if d.get("has_coords"):
            out.append({"id": d["id"], "label": f"{d['name'].split(' —')[0]} (your upload)", "forecast": True, "dataset": True, "steps": d["steps"]})
    return {"cities": out}


@app.get("/api/places", tags=["operate"])
def places_list(city: str = "dhaka", q: str = ""):
    """Place suggestions for the origin / destination inputs, INSIDE the named city (known Dhaka
    places, then OpenStreetMap bounded to the city). Free text and 'lat, lng' also work."""
    if not q and analyze.is_dhaka(city):
        return {"places": analyze.places()}
    return {"places": analyze.suggest(city, q)}


@app.get("/api/operate/models", tags=["operate"])
def operate_models(city: str = "dhaka"):
    """Forecast models that can serve this city right now, with the registry's reasons (flat)."""
    return {"city": city, "models": analyze.models_for_city(city)}


@app.get("/api/registry", tags=["operate"])
def models_registry(scope: str = "dhaka"):
    """THE MODEL REGISTRY for a scope (an uploaded dataset `user:<id>` or a city): grouped
    Recommended / Trained on your city / Pretrained / Research, every entry with the gates it
    passed, and what Automatic resolves to. Read fresh from disk — a finished training job
    appears without a restart."""
    import model_registry
    return model_registry.registry(scope)


@app.get("/api/runs", tags=["operate"])
def runs_recent(limit: int = 20):
    """The most recent prediction runs with their provenance (what computed each result)."""
    import provenance
    return {"runs": provenance.recent(limit)}


@app.get("/api/runs/{run_id}", tags=["operate"])
def run_provenance(run_id: str):
    """Technical details of one run: requested vs resolved model, checkpoint path + sha256, dataset /
    graph / input-window / raw-prediction / post-processed hashes, measured stage timings, result_source."""
    import provenance
    rec = provenance.load(run_id)
    return rec or {"run_id": run_id, "error": "UNAVAILABLE: no provenance record for this run id"}


@app.get("/api/analyze/{job}/provenance", tags=["operate"])
def analyze_provenance(job: str):
    import provenance
    rec = provenance.load(job)
    return rec or {"run_id": job, "error": "UNAVAILABLE: no provenance record (job still running, failed before inference, or unknown)"}


@app.post("/api/analyze", tags=["operate"])
def analyze_start(payload: dict):
    """ANALYZE TRAFFIC: origin, destination, departure, horizon -> current, forecast, decision.
    Runs in the background so the page can show each stage as it really happens."""
    return {"job": analyze.start(payload or {}), "poll": "/api/analyze/{job}"}


@app.get("/api/analyze/{job}", tags=["operate"])
def analyze_status(job: str):
    return analyze.status(job)


@app.post("/api/twin/test", tags=["twin"])
def twin_test_start(payload: dict | None = None):
    """TEST IN DIGITAL TWIN for one AnalysisRun: the run's own city, resolved O/D, model and
    forecast become the SUMO scenario (probe vehicle for that exact trip in every arm).
    404 ANALYSIS_RUN_NOT_FOUND when the run id is unknown; SUMO_OD_MAPPING_FAILED when the
    trip cannot be snapped to drivable edges — never a stored or fixed scenario."""
    import twin_test
    r = twin_test.start(payload or {})
    if not r.get("started") and r.get("http") == 404:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=404, content=r)
    return r


@app.get("/api/twin/test/{simulation_run_id}", tags=["twin"])
def twin_test_status(simulation_run_id: str):
    import twin_test
    return twin_test.status(simulation_run_id)


@app.post("/api/route/optimize", tags=["routing"])
def route_optimize(payload: dict | None = None):
    """ROUTE OPTIMIZATION for one AnalysisRun: its stored forecast -> continuous future edge costs ->
    duarouter candidates -> threshold + capacity admission. Returns the RoutingRun with every
    candidate's cost terms. 404 ANALYSIS_RUN_NOT_FOUND; 422 when the run holds no forecast."""
    import route_opt, twin_test
    from fastapi.responses import JSONResponse
    payload = payload or {}
    try:
        rec = twin_test.load_analysis(str(payload.get("analysis_run_id") or ""))
    except twin_test.AnalysisRunNotFound as exc:
        return JSONResponse(status_code=404, content={"error": f"ANALYSIS_RUN_NOT_FOUND: {exc}"})
    scen = twin_test.scenario_for(rec, lambda **k: None)
    if payload.get("origin_edge") and payload.get("destination_edge"):
        o_edge, d_edge = payload["origin_edge"], payload["destination_edge"]
    else:
        od = twin_test.map_od(scen["net"], rec["origin_resolved"], rec["destination_resolved"])
        o_edge, d_edge = od["origin"]["edge"], od["destination"]["edge"]
    seed = int(payload.get("seed") or twin_test.runtime_seed(rec["run_id"]))
    out = config.REPO / "results/routing/optimize" / rec["run_id"]
    try:
        rt = route_opt.optimize_for_analysis(rec, scen["net"], o_edge, d_edge, out, seed, float(payload.get("window_s") or 1800),
                                             hops=payload.get("hops"))
    except route_opt.NoStoredForecast as exc:
        return JSONResponse(status_code=422, content={"error": str(exc), "analysis_run_id": rec["run_id"]})
    return route_opt.public(rt)


@app.get("/api/route/optimize/{routing_run_id}", tags=["routing"])
def route_optimize_get(routing_run_id: str):
    import provenance as pv, route_opt
    from fastapi.responses import JSONResponse
    rec = pv.load(routing_run_id)
    if not rec:
        return JSONResponse(status_code=404, content={"error": f"ROUTING_RUN_NOT_FOUND: {routing_run_id}"})
    return route_opt.public(rec)


@app.post("/api/twin/compare", tags=["twin"])
def twin_compare_start(payload: dict):
    """Baseline vs reactive on any generated network, paired seeds, CI verdict. Background job."""
    if not payload.get("network"):
        return {"error": "network required"}
    return {"job": twin_compare.start(payload), "poll": "/api/twin/compare/{job}"}


@app.get("/api/twin/compare/{job}", tags=["twin"])
def twin_compare_status(job: str):
    return twin_compare.status(job)


@app.get("/api/twin/networks", tags=["twin"])
def twin_networks():
    """Every network the twin can run — the calibrated one, then cities generated from OSM."""
    return {"networks": live_sim_mod.networks()}


@app.post("/api/twin/network", tags=["twin"])
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


@app.get("/api/twin/network/{job}", tags=["twin"])
def twin_network_job(job: str):
    return _NET_JOBS.get(job) or {"job": job, "status": "unknown"}


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
    import train_jobs
    try:
        train_jobs.reattach_on_startup()
    except Exception as exc:                            # noqa: BLE001
        print(f"[train] could not re-attach jobs: {exc}")
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
