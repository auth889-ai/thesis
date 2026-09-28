"""Predictions HTTP endpoints."""
from __future__ import annotations

import json
import sys
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from backend.app import config
from backend.app.live import observatory as observatory_mod
from backend.app.evidence import forecast_ledger as forecast_log
from fastapi import APIRouter

router = APIRouter()


@router.get("/api/models", tags=["research"])
def models(city_id: str = "dhaka"):
    """Every forecasting model and whether it can honestly serve this city right now."""
    import sys
    sys.path.insert(0, str(config.REPO))
    from traffictwin.forecasting.adapters.registry import available_for
    cd = observatory_mod.observatory.city_data(city_id)
    return {"city_id": city_id, "input": cd.describe(),
            "models": available_for(cd)}


def _recorded_len(city_id: str) -> int:
    """How many 5-minute bins the recorder's on-disk series holds for this city (0 if none)."""
    if city_id != "dhaka":
        return 0
    import sys
    sys.path.insert(0, str(config.REPO))
    from traffictwin.forecasting.live import live_state
    if not live_state.SRC.exists():
        return 0
    rows = live_state.load_rows(live_state.SRC)
    return int(live_state.build(rows)[0].shape[0]) if rows else 0


def _recorded_is_longer(city_id: str, cd) -> bool:
    """The model is given whichever real history is LONGER — the in-memory buffer or the recorded
    series on disk — never a short buffer just because it is newer."""
    return _recorded_len(city_id) > int(cd.shape[0])


@router.get("/api/forecast/{city_id}", tags=["predict"])
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
    from traffictwin.forecasting.adapters.registry import forecast as run_forecast
    hs = [int(h) for h in horizons.split(",") if h.strip().isdigit()]
    cd = observatory_mod.observatory.city_data(city_id)
    use_recorded = source == "recorded" or (source == "auto" and _recorded_is_longer(city_id, cd))
    if use_recorded:
        from traffictwin.optimization.forecast_costs import recorded_forecast
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


@router.get("/api/forecast/{city_id}/scoreboard", tags=["predict"])
def city_forecast_scoreboard(city_id: str):
    """The system's own track record: forecasts it issued, graded against what was recorded next.

    Unlike the backtest (a replay), these were written down BEFORE their target time and cannot
    be revised. The scheduler issues one every five minutes while the server runs.
    """
    return forecast_log.score(city_id)


@router.get("/api/forecast/{city_id}/accuracy", tags=["predict"])
def city_forecast_accuracy(city_id: str):
    """How accurate the forecast is on THIS city's own recorded data — a rolling-origin backtest.

    Every model is cut at each origin bin, forecasts from that history only, and is scored on
    what the recorder later wrote. Read from the evidence file; the command regenerates it.
    """
    f = config.REPO / "results/forecasting/live_backtest.json"
    if city_id != "dhaka" or not f.exists():
        return {"available": False, "city_id": city_id,
                "missing": "results/forecasting/live_backtest.json",
                "command": "python src/pipeline/forecasting/live_backtest.py"}
    return {"available": True, "result_source": "RESEARCH_BENCHMARK", **json.loads(f.read_text())}


@router.get("/api/history/{city_id}", tags=["predict"])
def history(city_id: str, horizons: str = "5,15,30,60"):
    """Observed history AND the forecast, in one payload, so a chart can draw both.

    The history is what the observatory actually recorded; the forecast is the same call the rest
    of the system uses. Nothing here is generated to make a curve look continuous — a gap in the
    record stays a gap.
    """
    import sys
    sys.path.insert(0, str(config.REPO))
    from traffictwin.forecasting.adapters.registry import forecast as run_forecast
    rows, nodes = observatory_mod.observatory.series(city_id)
    hs = [int(h) for h in horizons.split(",") if h.strip().isdigit()]
    cd = observatory_mod.observatory.city_data(city_id)
    if _recorded_is_longer(city_id, cd):
        # the recorded REAL_LIVE series on disk is the longer history: draw that day and forecast
        # from it — the same window E1 was measured on, so its accuracy can be quoted
        from traffictwin.optimization.forecast_costs import recorded_city_data
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


@router.get("/api/forecast-map/{dataset}", tags=["predict"])
def forecast_map_network(dataset: str, as_of: str | None = None, model: str | None = None):
    """The future state of the road network at one dataset moment: every sensor's prediction, the
    DIRECT/DERIVED edges the router prices, the unforecast backdrop, and the coverage counts."""
    from backend.app.forecasting import road_forecasts as forecast_map
    try:
        return forecast_map.network(dataset, as_of, model)
    except KeyError as ex:
        raise HTTPException(404, str(ex))
    except ValueError as ex:
        raise HTTPException(422, str(ex))
    except (FileNotFoundError, RuntimeError) as ex:
        raise HTTPException(503, str(ex))


@router.get("/api/forecast-map/{dataset}/road", tags=["predict"])
def forecast_map_road(dataset: str, node: str, as_of: str | None = None, models: str = "GWNet,persistence"):
    """One sensor: history, each model's prediction, the measured future when inside the data."""
    from backend.app.forecasting import road_forecasts as forecast_map
    try:
        return forecast_map.road(dataset, node, as_of, tuple(m for m in models.split(",") if m))
    except (KeyError, ValueError) as ex:
        raise HTTPException(404, str(ex))
