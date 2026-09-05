"""MISSION CONTROL on an UPLOADED CITY DATASET — the selected checkpoint actually runs.

When the operator picks a data source that is an uploaded dataset with road coordinates (for
example the 14-day Los Angeles sample), the trip is routed live in that city and the traffic
forecast along the route comes from the model chosen in the registry — the exact checkpoint,
loaded and run at the dataset moment that matches the departure (same weekday and slot of the
day, in the last week of the data).

    origin / destination  -> geocoded inside the dataset's city, routed live (Google Routes)
    model                 -> model_registry.resolve(scope, requested): trained checkpoint, research
                             estimator, Chronos-Bolt, persistence or historical average
    sensors on the route  -> every road of the dataset within NEAR_M of the route polyline
    ETA at +h             -> the current live ETA scaled by mean(now speed) / mean(predicted speed)
                             over the sensors on the route (speed data), clamped to [0.7, 3]
    risk                  -> predicted speed below 60 % of a road's free-flow = congested

Every number in the result names its source: the checkpoint file, the dataset moment, the
sensors used. Nothing here reads a saved answer.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import numpy as np

import config
import user_datasets

NEAR_M = 500                                            # freeway detectors sit beside the carriageway; the routed polyline may be the other side
HORIZONS = [15, 30, 60]


def scope_for(city_text: str) -> str | None:
    """'user:<id>' when the typed city is an uploaded dataset (by id or by its name)."""
    t = (city_text or "").strip()
    if t.startswith("user:"):
        return t if user_datasets.load_meta(t[5:]) else None
    key = "".join(ch for ch in t.lower() if ch.isalnum())
    for d in user_datasets.datasets():
        m = user_datasets.load_meta(d["id"][5:]) or {}
        if m.get("coords") and key in {"".join(ch for ch in (m.get("name") or "").lower() if ch.isalnum()), d["id"][5:].replace("_", "")}:
            return d["id"]
    return None


def _dist_m(lat1, lng1, lat2, lng2) -> float:
    dy = (lat1 - lat2) * 111_000
    dx = (lng1 - lng2) * 111_000 * math.cos(math.radians((lat1 + lat2) / 2))
    return math.hypot(dx, dy)


def _near_route(pt, poly, near_m=NEAR_M) -> bool:
    lat, lng = pt
    step = max(1, len(poly) // 400)
    return any(_dist_m(lat, lng, a, b) <= near_m for a, b in poly[::step])


def moment_for(meta: dict, departure_iso: str | None) -> tuple[int, str]:
    """The dataset index with the same weekday and slot of day as the departure, in the last
    week of the data (or the last matching slot of day when the data is shorter)."""
    T, step = meta["steps"], int(meta["interval_s"])
    first = datetime.fromisoformat(meta["first_utc"])
    # the dataset's clock is the city's own wall clock (its timestamps carry no zone), so the
    # departure is matched by ITS wall clock too — 08:00 in Los Angeles means 08:00 in the data
    dep = datetime.fromisoformat(departure_iso) if departure_iso else datetime.now().astimezone()
    dep = dep.replace(tzinfo=timezone.utc)
    last = first + timedelta(seconds=step * (T - 13))
    # walk back from the end of the data to the latest instant with the same weekday + time of day
    target = last.replace(hour=dep.hour, minute=dep.minute, second=0, microsecond=0)
    while target.weekday() != dep.weekday() or target > last:
        target -= timedelta(days=1)
    if target < first + timedelta(seconds=step * 12):          # data shorter than a week: same time of day only
        target = last.replace(hour=dep.hour, minute=dep.minute, second=0, microsecond=0)
        if target > last:
            target -= timedelta(days=1)
    idx = int((target - first).total_seconds() // step)
    idx = max(12, min(T - 13, idx))
    return idx, (first + timedelta(seconds=step * idx)).isoformat()


def research_predict(card: dict, as_of: int) -> np.ndarray:
    """Run a fitted XGBoost / Random Forest in a child process and read back its (12, N)."""
    import json as _json
    import subprocess
    import sys as _sys
    code = ("import sys, json; sys.path.insert(0, %r); sys.path.insert(0, %r)\n"
            "from pipeline.forecasting import research_baselines as rb\n"
            "card = json.load(open(%r)); print(json.dumps(rb.predict(card, %d).tolist()))") % (
        str(config.REPO), str(config.REPO / "dashboard/backend"), _card_path(card), int(as_of))
    r = subprocess.run([_sys.executable, "-c", code], capture_output=True, text=True, timeout=300, cwd=config.REPO)
    if r.returncode != 0:
        raise RuntimeError("research model failed: " + (r.stderr or r.stdout)[-400:])
    return np.asarray(_json.loads(r.stdout.strip().splitlines()[-1]), dtype="float64")


def _card_path(card: dict) -> str:
    from pipeline.forecasting import basicts_train as bt
    return str(bt.CARDS / f"{card['bts_name']}__{card['arch']}.json")


def forecast_all(scope: str, entry: dict, as_of: int) -> tuple[np.ndarray, np.ndarray, dict]:
    """(now[N], pred[12, N], info) from the resolved registry entry, at dataset index `as_of`."""
    from pipeline.forecasting import basicts_train as bt
    from pipeline.forecasting import train_eval as te
    model = entry["model"]
    card = None
    if entry.get("checkpoint_path"):
        card = next((c for c in bt.cards() if c["checkpoint"] == entry["checkpoint_path"]), None)
    name = bt.bts_name(scope)
    if not (bt.BTS / "datasets" / name / "desc.json").exists():
        bt.prepare(scope)                                 # their data preparation, once per upload
    raw, _ = bt._prepared(name)
    vals = np.asarray(raw[:, :, 0], dtype="float64")
    now = vals[as_of - 1].copy()
    info = {"model": model, "checkpoint": entry.get("checkpoint"), "as_of_index": as_of}
    if card and card.get("family") == "research":
        pred = research_predict(card, as_of)              # separate process: xgboost/sklearn OpenMP vs torch's
    elif card:
        pred = bt.predict(card, as_of)
        info["checkpoint_sha256"] = te.sha256_file(__import__("pathlib").Path(card["checkpoint"]), 12)
    elif model == "persistence":
        pred = np.repeat(now[None, :], 12, axis=0)
    elif model == "historical_average":
        spd = int(round(86400 / int(user_datasets.load_meta(scope[5:])["interval_s"])))
        ha = te.historical_average(vals, te.splits(vals.shape[0])["train"][1], spd)
        pred = te.predict_ha(ha, np.array([as_of]), spd)[0]
    elif model == "Chronos-Bolt":
        meta = user_datasets.load_meta(scope[5:])
        p, _ = te.predict_chronos(vals, np.array([as_of]), int(meta["interval_s"]), meta["quantity"], meta["nodes"], max_windows=1)
        pred = p[0]
    else:
        raise RuntimeError(f"{model} cannot run on this dataset here")
    pred = np.where(np.isfinite(pred), pred, now[None, :])
    return now, pred, info


def analyze_dataset(p: dict, scope: str, emit, run_id: str = "") -> dict:
    import model_registry
    import provenance as pv
    from live import service
    from analyze import resolve_place
    from pipeline.forecasting import basicts_train as bt
    from pipeline.forecasting import train_eval as te
    did = scope[5:]
    run = pv.Run(run_id or f"an_{did}", city=scope, origin=p.get("origin"), destination=p.get("destination"),
                 requested_model=p.get("model") or "auto", horizon_min=int(p.get("horizon_min") or 30), request=p)
    run.stage("Resolving city", emit)
    meta = user_datasets.load_meta(did)
    if not meta or not meta.get("coords"):
        run.finish("failed", "no road coordinates")
        raise RuntimeError("this dataset has no road coordinates; upload it again with a road, lat, lon file")
    h = int(p.get("horizon_min") or 30)
    step_min = int(meta["interval_s"]) // 60
    o = resolve_place(p.get("origin") or meta["name"], meta["name"])
    d = resolve_place(p.get("destination") or meta["name"], meta["name"])
    run.set(origin_resolved=o, destination_resolved=d)
    run.stage("Loading graph", emit)
    name = bt.bts_name(scope)
    if not (bt.BTS / "datasets" / name / "desc.json").exists():
        bt.prepare(scope)
    raw, _ = bt._prepared(name)
    vals = np.asarray(raw[:, :, 0], dtype="float64")
    run.set(dataset_hash=te.sha256_file(bt.BTS / "datasets" / name / "data.dat"), graph_hash=te.sha256_file(bt.BTS / "datasets" / name / "adj_mx.pkl", 8),
            roads=len(meta["nodes"]), steps=int(vals.shape[0]))
    run.stage("Validating traffic data", emit)
    routes = service.routes((o["lat"], o["lng"]), (d["lat"], d["lng"]))
    if not routes.get("is_live") or not routes.get("routes"):
        run.finish("failed", f"live routing unavailable: {routes.get('request_status')}")
        raise RuntimeError(f"live routing unavailable: {routes.get('request_status')}")
    quality = te.data_quality(np.where(vals == 0, np.nan, vals), int(meta["interval_s"]))
    run.set(routes_retrieved_at=routes.get("retrieved_at"), routes_n=len(routes.get("routes") or []), data_quality=te.to_jsonable(quality))
    run.set(routing_provider=routes.get("source"), routing_preference=routes.get("routing_preference"), routing_request_status=routes.get("request_status"),
            routing_backend_function="dashboard/backend/live.py: LiveService.routes -> Google Routes API computeRoutes", routing_latency_ms=routes.get("request_latency_ms"),
            route_geometry_hash=pv.sha_json([[pt for s in (r.get("segments") or []) for pt in (s.get("coordinates") or [])] for r in routes["routes"]]),
            routes_summary=[{"key": "ABC"[i], "distance_m": r.get("distance_m"), "duration_s": r.get("duration_s"), "static_duration_s": r.get("static_duration_s"),
                             "points": sum(len(s.get("coordinates") or []) for s in (r.get("segments") or []))} for i, r in enumerate(routes["routes"][:3])])

    run.stage("Loading checkpoint", emit)
    entry = model_registry.resolve(scope, p.get("model"))
    if not entry.get("can_forecast") and not entry.get("checkpoint_path") and entry["model"] not in ("persistence", "historical_average", "Chronos-Bolt"):
        run.finish("failed", f"{entry['model']} unavailable")
        raise RuntimeError(f"UNAVAILABLE: {entry.get('label', entry['model'])} cannot serve this data — {entry.get('reason') or 'failed a gate'}")
    as_of, as_of_time = moment_for(meta, p.get("departure_local") or p.get("departure"))
    run.set(resolved_model=entry["model"], checkpoint_path=entry.get("checkpoint_path") or entry.get("checkpoint"),
            checkpoint_sha256=pv.sha_file(entry.get("checkpoint_path")), cache_hit_training=bool(entry.get("checkpoint_path")),
            as_of_index=as_of, as_of_dataset_time=as_of_time, input_window_hash=pv.sha_array(raw[as_of - 12:as_of]))
    run.stage("Running inference", emit)
    now, pred, info = forecast_all(scope, entry, as_of)
    run.set(raw_prediction_hash=pv.sha_array(pred), raw_prediction_first10=[round(float(x), 3) for x in np.asarray(pred).ravel()[:10]],
            inference_recomputed=True)
    speed_like = any(k in (meta.get("quantity") or "").lower() for k in ("speed", "km/h", "mph"))
    ff = te.freeflow_from_train(vals, te.splits(vals.shape[0])["train"][1]) if speed_like else None
    run.stage("Evaluating routes", emit)
    coords = meta["coords"]; names = meta["nodes"]
    cards = []
    for i, r in enumerate(routes["routes"][:3]):
        poly = [tuple(pt) for s in (r.get("segments") or []) for pt in (s.get("coordinates") or [])]
        on = [j for j, pt in enumerate(coords) if _near_route(pt, poly)]
        per_h = {}
        for hh in HORIZONS:
            k = max(0, min(11, hh // step_min - 1))
            if on and speed_like:
                n_s = float(np.mean([now[j] for j in on if now[j] > 0] or [0])); p_s = float(np.mean([pred[k, j] for j in on if pred[k, j] > 0] or [0]))
                factor = max(0.7, min(3.0, n_s / p_s)) if n_s > 0 and p_s > 0 else 1.0
                cong = [pred[k, j] < 0.6 * ff[j] for j in on] if ff is not None else []
                slow = [pred[k, j] < 0.8 * ff[j] for j in on] if ff is not None else []
                risk = "HIGH" if any(cong) else "MEDIUM" if any(slow) else "LOW"
                per_h[hh] = {"eta_s": round(float(r["duration_s"]) * factor), "risk": risk, "covered": True,
                             "level": round(float(np.mean(cong)) * 3, 2) if cong else 0.0, "speed_now": round(n_s, 1), "speed_pred": round(p_s, 1)}
            else:
                per_h[hh] = {"eta_s": round(float(r["duration_s"])), "risk": "—", "covered": False, "level": None}
        cards.append({"key": "ABC"[i], "index": i, "eta_now_s": r["duration_s"], "static_s": r.get("static_duration_s"),
                      "distance_m": r.get("distance_m"), "category_now": r.get("category"),
                      "corridors": [names[j] for j in on], "sensors": on, "forecast": per_h, "segments": r.get("segments") or []})
    best_now = min(cards, key=lambda c: c["eta_now_s"])
    best_pred = min(cards, key=lambda c: c["forecast"][h]["eta_s"])
    saving = best_now["forecast"][h]["eta_s"] - best_pred["forecast"][h]["eta_s"]
    for c in cards:
        c["recommended"] = c["key"] == best_pred["key"]
        c["status"] = "RECOMMENDED" if c["recommended"] else "AVOID" if c["forecast"][h]["risk"] == "HIGH" else "ACCEPTABLE"
    covered_any = any(c["forecast"][h]["covered"] for c in cards)
    if not covered_any:
        reason = "no dataset road lies within 300 m of these routes; the fastest live route stands"
    elif best_pred["key"] == best_now["key"]:
        reason = f"{entry['label']} keeps route {best_pred['key']} fastest at +{h} min ({best_pred['forecast'][h]['risk'].lower()} congestion risk)"
    else:
        reason = (f"route {best_now['key']} is fastest now but {entry['label']} predicts {best_now['forecast'][h]['risk']} risk on its roads at +{h} min; "
                  f"route {best_pred['key']} saves about {round(saving / 60)} min")
    skill = entry.get("test_skill")
    conf = (f"{skill * 100:.0f} % better than 'no change' on this dataset's held-out test" if skill is not None
            else "no held-out test for this choice")
    cur = {"eta_s": best_now["eta_now_s"], "route": best_now["key"], "distance_m": best_now.get("distance_m"),
           "speed_kmh": round(best_now["distance_m"] / best_now["eta_now_s"] * 3.6, 1) if best_now.get("distance_m") else None,
           "congestion": best_now.get("category_now") or "UNKNOWN"}
    lats = [pt[0] for c in cards for s in c["segments"] for pt in (s.get("coordinates") or [])]
    lngs = [pt[1] for c in cards for s in c["segments"] for pt in (s.get("coordinates") or [])]
    run.stage("Preparing result", emit)
    run.set(postprocessed_prediction_hash=pv.sha_json([c["forecast"] for c in cards]), recommended=best_pred["key"])
    sensors = [{"id": names[j], "lat": coords[j][0], "lng": coords[j][1], "now": round(float(now[j]), 1),
                "pred": {str(hh): round(float(pred[max(0, min(11, hh // step_min - 1)), j]), 1) for hh in HORIZONS},
                "freeflow": round(float(ff[j]), 1) if ff is not None else None} for j in range(len(names))]
    rec = run.finish("done")
    return {"run_id": rec["run_id"], "result_source": "LIVE_COMPUTATION", "cache_hit_training": rec["cache_hit_training"], "inference_recomputed": True,
            "provenance": run.summary(), "stages": rec["stages"],
            "forecast_decision": {**(entry.get("forecast_decision") or {}), "model_used": entry["model"], "model_used_status": entry.get("status"),
                                  "model_used_trust": entry.get("trust")},
            "routing_policy": entry.get("routing"),
            "city": meta["name"], "scope": scope, "is_dhaka": False, "forecastable": True, "dataset": True,
            "origin": {**o}, "destination": {**d}, "horizon_min": h, "retrieved_at": routes.get("retrieved_at"),
            "current": cur,
            "forecast": {"eta_s": best_now["forecast"][h]["eta_s"], "risk": best_now["forecast"][h]["risk"], "covered": best_now["forecast"][h]["covered"],
                         "confidence": conf, "model": entry["label"], "checkpoint": info.get("checkpoint"), "checkpoint_sha256": info.get("checkpoint_sha256"),
                         "requested": entry.get("requested"), "automatic": entry.get("automatic"), "trust": entry.get("trust"),
                         "input_steps": 12, "as_of_index": as_of, "as_of_dataset_time": as_of_time, "quantity": meta["quantity"]},
            "decision": {"recommended": best_pred["key"], "saving_s": max(0, saving), "reason": reason,
                         "basis": f"{entry['label']} ({info.get('checkpoint') or 'no checkpoint'}) on {len(names)} roads at {as_of_time[:16].replace('T', ' ')} in the dataset"},
            "routes": cards, "sensors": sensors, "layers": {"now": []},
            "bbox": [min(lats) - 0.006, min(lngs) - 0.006, max(lats) + 0.006, max(lngs) + 0.006] if lats else meta.get("bbox"),
            "observe": {"city_id": None, "watched": False, "steps_have": meta["steps"]}}
