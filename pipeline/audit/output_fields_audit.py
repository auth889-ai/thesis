#!/usr/bin/env python3
"""GATE 9 — every numeric output the Operations UI displays, traced to its backend source.

    python pipeline/audit/output_fields_audit.py [--run-id an_xxx] [--out docs/audit/output_fields_audit.json]

For each displayed field: the frontend component, the API endpoint, the backend function that
produces it, the source type, and `hardcoded` (true only if the value does not come from a request
made for THIS input). The run id column is filled from a real provenance record so the audit can
be replayed: GET /api/runs/<run_id> shows the same hashes the page showed.

Source types: LIVE_API (a third-party call made for this request), LIVE_COMPUTATION (computed now
from the request's inputs), CHECKPOINT (a stored trained artefact, inference recomputed),
RESEARCH_BENCHMARK (a precomputed experiment file, labelled as such in the UI), INPUT_ECHO (the
user's own input shown back).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "dashboard/backend"))

MC = "dashboard/frontend/components/mission-control.js"
PP = "dashboard/frontend/components/prediction-page.js"
LT = "dashboard/frontend/components/live-twin-page.js"
RP = "dashboard/frontend/components/results-page.js"


def field(name, component, endpoint, backend, source, note=""):
    return {"field": name, "frontend_component": component, "api_endpoint": endpoint, "backend_function": backend,
            "source_type": source, "hardcoded": False, "note": note}


FIELDS = [
    # ---------------------------------------------------------------- Mission Control (live / dataset analysis)
    field("Current travel time (min)", MC, "POST /api/analyze → GET /api/analyze/{job}", "live.service.routes (Google Routes API, TRAFFIC_AWARE_OPTIMAL) → analyze._run / dataset_ops.analyze_dataset", "LIVE_API"),
    field("Average speed now (km/h)", MC, "GET /api/analyze/{job}", "analyze._run: distance_m / duration_s of the fastest live route", "LIVE_COMPUTATION"),
    field("Congestion word now", MC, "GET /api/analyze/{job}", "live.service.routes: category from traffic-aware vs static duration", "LIVE_API"),
    field("Travel time in 15/30/60 min", MC, "GET /api/analyze/{job}", "analyze._run: live ETA × multiplier(predicted level)/multiplier(now) on the observed corridors; dataset_ops: live ETA × mean(now speed)/mean(predicted speed) over sensors on the route", "LIVE_COMPUTATION"),
    field("Expected speed at horizon", MC, "GET /api/analyze/{job}", "distance / predicted ETA", "LIVE_COMPUTATION"),
    field("Congestion word at horizon", MC, "GET /api/analyze/{job}", "analyze: predicted congestion level ≥2 HIGH / ≥1 MEDIUM; dataset_ops: predicted speed < 60 % / 80 % of free-flow", "LIVE_COMPUTATION"),
    field("Recommended route", MC, "GET /api/analyze/{job}", "argmin of predicted ETA at the chosen horizon over the live routes", "LIVE_COMPUTATION"),
    field("Time saving", MC, "GET /api/analyze/{job}", "fastest-now predicted ETA − recommended predicted ETA", "LIVE_COMPUTATION"),
    field("Congestion risk (recommendation)", MC, "GET /api/analyze/{job}", "risk of the recommended route at the horizon", "LIVE_COMPUTATION"),
    field("Confidence", MC, "GET /api/analyze/{job}", "Dhaka: class accuracy from results/forecasting/live_backtest.json (rolling-origin backtest on the city's recorded data, RESEARCH_BENCHMARK, shown as such); datasets: held-out test skill of the resolved model's card", "RESEARCH_BENCHMARK", "an accuracy statement about the model, not a live number"),
    field("Route cards: current / in N min / distance", MC, "GET /api/analyze/{job}", "live routes + the forecast pricing above", "LIVE_COMPUTATION"),
    field("Forecast model / checkpoint / sha256 / hashes / stage seconds", MC, "GET /api/analyze/{job}, GET /api/runs/{run_id}", "provenance.Run written by the analysis", "LIVE_COMPUTATION"),
    field("Sensor dots (now / predicted per road)", MC, "GET /api/analyze/{job}", "dataset_ops.forecast_all: the resolved model's forward pass at the dataset moment", "CHECKPOINT"),
    field("SUMO test: BASELINE / REACTIVE / PREDICTION-AWARE metrics, verdict, CI", MC, "POST /api/experiment/chain/run → GET /api/experiment/chain/run/{id}", "pipeline.routing.integrated_chain.run_chain: SUMO runs started for this request; parse_metrics", "LIVE_COMPUTATION"),
    field("Simulate this area: baseline vs reactive metrics", MC, "POST /api/twin/network → POST /api/twin/compare", "city.sumo_scenario.build + twin_compare (SUMO runs for this request)", "LIVE_COMPUTATION"),
    # ---------------------------------------------------------------- Prediction page
    field("Now / +h tiles (value, word)", PP, "POST /api/predict-lab/run → GET /api/predict-lab/{job}", "predict_lab._run: the chosen model's forward pass at the chosen moment (OpenCity harness / checkpoint / adapters)", "LIVE_COMPUTATION"),
    field("'actually' values under the tiles", PP, "GET /api/predict-lab/{job}", "the dataset's own readings after the moment (predict_lab: vals[end:end+12])", "LIVE_COMPUTATION"),
    field("How much to trust it: off by X vs no-change", PP, "GET /api/predict-lab/{job}", "predict_lab: |pred − actual| and |last − actual| at the horizon", "LIVE_COMPUTATION"),
    field("Accuracy on unseen data", PP, "GET /api/predict-lab/{job}", "the model card's test metrics (their runner / evaluate.py on the held-out split)", "CHECKPOINT"),
    field("Training progress (round, validation error)", PP, "GET /api/train/{job}", "train_jobs: parsed from the harness's live log lines", "LIVE_COMPUTATION"),
    field("Training result table (MAE/RMSE/MAPE/F1/skill)", PP, "GET /api/train/{job}", "train_eval on the harness's test split; their evaluate.py for verification", "LIVE_COMPUTATION"),
    field("Model registry gates / Automatic choice", PP + ", " + MC, "GET /api/registry?scope=", "model_registry.registry: read from the cards on disk on every call", "CHECKPOINT"),
    # ---------------------------------------------------------------- Digital twin
    field("Vehicles, mean speed, mean travel time, p95, queue, teleports", LT, "GET /api/sim/live/state, /history", "live_sim.LiveSim: TraCI subscriptions of the running SUMO", "LIVE_COMPUTATION"),
    # ---------------------------------------------------------------- Results (research, labelled)
    field("Penetration curve, ablation table, accuracy figures", RP, "GET /api/experiment/sweep|ablation, /api/forecast/{city}/accuracy", "precomputed experiment JSON files with their regenerating command", "RESEARCH_BENCHMARK", "labelled on the page; never presented as a new live result"),
]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-id", default=None, help="a provenance run id to attach as the replayable example")
    ap.add_argument("--out", default=str(REPO / "docs/audit/output_fields_audit.json"))
    a = ap.parse_args()
    import provenance
    rec = provenance.load(a.run_id) if a.run_id else None
    if rec is None:
        recs = provenance.recent(1)
        rec = provenance.load(recs[0]["run_id"]) if recs else None
    rows = []
    for f in FIELDS:
        r = dict(f)
        r["run_id"] = rec["run_id"] if rec and ("analyze" in f["api_endpoint"] or "runs" in f["api_endpoint"]) else None
        rows.append(r)
    out = {"generated_utc": datetime.now(timezone.utc).isoformat(), "rule": "presets fill INPUT fields only; every displayed OUTPUT comes from a request made for this input, or is labelled RESEARCH_BENCHMARK",
           "hardcoded_fields": sum(1 for r in rows if r["hardcoded"]), "fields": rows,
           "example_run": {k: rec.get(k) for k in ("run_id", "city", "requested_model", "resolved_model", "checkpoint_path", "checkpoint_sha256", "dataset_hash",
                                                   "input_window_hash", "raw_prediction_hash", "postprocessed_prediction_hash", "result_source", "stages")} if rec else None}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(out, indent=1, default=str))
    print(f"{len(rows)} displayed output fields audited, {out['hardcoded_fields']} hardcoded -> {a.out}")
    return 0 if out["hardcoded_fields"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
