"""The system's own track record: every forecast it issues, scored against what happened next.

A dashboard that shows a forecast curve is a picture. A system that writes down each forecast
the moment it is made, then grades it when the real reading arrives, has a track record — and
that record cannot be edited after the fact. This module is that ledger.

    log(res, city)        append every (corridor, horizon) value of one forecast response
    score(city)           join the ledger with the recorder's file: MAE, class accuracy, skill,
                          per model and horizon, plus the recent pairs for a chart
    start_scheduler()     issue a forecast every 5 minutes so the ledger fills without clicks

Storage is SQLite under results/forecasting/. Only OUR derived numbers are stored (a predicted
congestion level and, later, the recorded class) — never provider route content.
"""
from __future__ import annotations

import json
import sqlite3
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import config

DB = config.REPO / "results/forecasting/forecast_log.sqlite"
TICK_S = 300
HORIZONS = [15, 30, 60]
MODELS = ["Chronos-Bolt", "persistence"]          # the system's model and the floor it must beat
_lock = threading.Lock()
_thread: threading.Thread | None = None
_state = {"ticks": 0, "failures": 0, "last_tick_utc": None, "last_error": None}


def _conn() -> sqlite3.Connection:
    DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB, timeout=10)
    c.execute("""CREATE TABLE IF NOT EXISTS forecasts (
        issued_utc TEXT NOT NULL, target_utc TEXT NOT NULL, city TEXT NOT NULL,
        corridor TEXT NOT NULL, horizon_min INTEGER NOT NULL, model TEXT NOT NULL,
        is_baseline INTEGER NOT NULL, predicted REAL, unit TEXT, source TEXT,
        PRIMARY KEY (issued_utc, city, corridor, horizon_min, model))""")
    return c


def log(res: dict, city: str, source: str = "api") -> int:
    """Write one forecast response to the ledger. Returns rows written."""
    f = res.get("forecast")
    if not f:
        return 0
    issued = datetime.fromisoformat(f["inference_utc"]).astimezone(timezone.utc)
    rows = []
    for h in f["horizons_min"]:
        vals = f["values"].get(h) if h in f["values"] else f["values"].get(str(h))
        if vals is None:
            continue
        target = (issued + timedelta(minutes=int(h))).isoformat()
        for node, v in zip(f["node_ids"], vals):
            rows.append((issued.isoformat(), target, city, node, int(h), f["model"],
                         int(bool(f.get("is_baseline"))),
                         None if v is None or v != v else float(v), f.get("unit"), source))
    with _lock, _conn() as c:
        c.executemany("INSERT OR IGNORE INTO forecasts VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
    return len(rows)


def _actuals(city: str):
    """(bins epoch[], corridors[], values[T,N], mask[T,N]) from the recorder's file, or None."""
    sys.path.insert(0, str(config.REPO))
    from pipeline.forecasting import live_state
    if city != "dhaka" or not live_state.SRC.exists():
        return None
    rows = live_state.load_rows(live_state.SRC)
    if not rows:
        return None
    vals, mask, corridors, bins = live_state.build(rows)
    return bins, list(corridors), vals, mask


def score(city: str = "dhaka", recent: int = 200) -> dict:
    """Grade every logged forecast whose target time the recorder has already reached."""
    import numpy as np
    with _lock, _conn() as c:
        rows = c.execute("SELECT issued_utc, target_utc, corridor, horizon_min, model, is_baseline, "
                         "predicted, unit FROM forecasts WHERE city=? AND predicted IS NOT NULL "
                         "ORDER BY issued_utc", (city,)).fetchall()
    total = len(rows)
    act = _actuals(city)
    if not rows or act is None:
        return {"city": city, "logged": total, "scored": 0, "rows": [], "recent": [],
                "note": "no forecast has reached its target time yet, or no recorder file"}
    bins, corridors, vals, mask = act
    idx = {c: i for i, c in enumerate(corridors)}
    t0, bin_s = float(bins[0]), 300.0
    T = vals.shape[0]
    scored, by = [], {}
    for issued, target, corr, h, model, is_b, pred, unit in rows:
        n = idx.get(corr)
        if n is None or not str(unit or "").startswith("congestion_level"):
            continue
        b = int((datetime.fromisoformat(target).timestamp() - t0) // bin_s)
        if b < 0 or b >= T or not mask[b, n]:
            continue
        actual = float(vals[b, n])
        err = pred - actual
        scored.append({"issued_utc": issued, "target_utc": target, "corridor": corr,
                       "horizon_min": h, "model": model, "predicted": round(pred, 3),
                       "actual": actual})
        by.setdefault((model, h, bool(is_b)), []).append(
            (abs(err), err * err, float(np.clip(np.rint(pred), 0, 3) == actual)))
    table = []
    for (model, h, is_b), e in sorted(by.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        a = np.array(e)
        table.append({"model": model, "horizon_min": h, "is_baseline": is_b, "n": len(e),
                      "mae": round(float(a[:, 0].mean()), 4),
                      "rmse": round(float(np.sqrt(a[:, 1].mean())), 4),
                      "class_accuracy": round(float(a[:, 2].mean()), 4)})
    floor = {r["horizon_min"]: r["mae"] for r in table if r["model"] == "persistence"}
    for r in table:
        f = floor.get(r["horizon_min"])
        r["skill_vs_persistence"] = round(1 - r["mae"] / f, 4) if f else None
    return {"city": city, "logged": total, "scored": len(scored), "rows": table,
            "recent": scored[-recent:], "unit": "congestion_level_0_3",
            "protocol": ("each forecast was written to the ledger when issued and graded only "
                         "when the recorder later wrote the class for its target bin"),
            "db": str(DB.relative_to(config.REPO)) if DB.is_relative_to(config.REPO) else str(DB),
            "scheduler": dict(_state)}


def tick(city: str = "dhaka") -> dict:
    """Issue and log one forecast per model. Called by the scheduler and by tests."""
    sys.path.insert(0, str(config.REPO))
    from pipeline.routing.forecast_to_costs import recorded_forecast
    written = {}
    for m in MODELS:
        res = recorded_forecast(city, HORIZONS, m, "latest")
        written[m] = log(res, city, source="scheduler")
    _state.update(ticks=_state["ticks"] + 1, last_tick_utc=datetime.now(timezone.utc).isoformat())
    return written


def _loop(city: str) -> None:
    while True:
        try:
            tick(city)
        except Exception as exc:                        # noqa: BLE001 - recorded, never fatal
            _state.update(failures=_state["failures"] + 1, last_error=f"{type(exc).__name__}: {exc}")
        time.sleep(TICK_S)


def start_scheduler(city: str = "dhaka") -> None:
    global _thread
    if _thread and _thread.is_alive():
        return
    _thread = threading.Thread(target=_loop, args=(city,), name="forecast-log", daemon=True)
    _thread.start()
