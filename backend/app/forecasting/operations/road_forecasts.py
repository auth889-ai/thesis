"""TRAFFIC FORECAST — the future state of a road network, from the genuine model outputs.

One dataset moment -> the trusted model's prediction for every sensor (a fresh forward pass through
the same `dataset_ops.forecast_all` the product uses) -> the detector-to-edge mapping and the
production edge-cost builder (`src/pipeline/routing/edge_costs.build`) -> coloured road segments with
their provenance:

    DIRECT    the edge a mapped detector sits on: the model's prediction for that detector
    DERIVED   a neighbouring edge within the routing coverage (1 hop), decayed from a DIRECT edge
    (none)    every other edge: no forecast — drawn as background only, never coloured as predicted

Nothing here changes a model; nothing here invents a value. Sensors that carry a prediction but are
not mapped into the SUMO scenario are still shown as points (MODEL SENSOR COVERAGE), distinct from
the edges the router can act on (SUMO CONTROL COVERAGE).
"""
from __future__ import annotations

import hashlib
import json
import sys
import threading
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

import numpy as np

from app import evidence_paths as config
from app.forecasting.operations import scientific_prediction

sys.path.insert(0, str(config.REPO))

HORIZONS = (15, 30, 60)
HISTORY_STEPS = 36                      # three hours of 5-minute readings before the moment
_LOCK = threading.Lock()


def _clock(first_utc: str | None, idx: int, step_s: int) -> str | None:
    if not first_utc:
        return None
    return (datetime.fromisoformat(first_utc) + timedelta(seconds=step_s * idx)).isoformat()


def _to_kmh(v: float | None, quantity: str) -> float | None:
    if v is None or not np.isfinite(v):
        return None
    q = (quantity or "").lower()
    return float(v) * (1.609 if "mph" in q else 3.6 if "m/s" in q else 1.0)


def _predict(dataset: str, as_of: int, model: str | None):
    """The product's inference path: a fresh forward pass on every request, never a stored answer."""
    if dataset in scientific_prediction.DATASETS:
        return scientific_prediction.forecast(as_of, model)
    from app.data import forecast_inputs as dataset_ops
    from app.forecasting.operations import model_registry
    entry = model_registry.resolve(dataset, model)
    now, pred, info = dataset_ops.forecast_all(dataset, entry, int(as_of))
    info = {**info, "resolved_model": entry.get("model"), "checkpoint_path": entry.get("checkpoint_path"), "trust": entry.get("trust"),
            "validation_MAE": entry.get("validation_MAE"), "test_skill": entry.get("test_skill"), "cache_key": entry.get("cache_key"),
            "prediction_cache_hit": False, "inference_recomputed": True, "result_source": "FRESH_INFERENCE"}
    return now, pred, info


@lru_cache(maxsize=4)
def _net(city_id: str):
    import sumolib
    from app.twin.scenario_builder import scenario_dir
    man = json.loads((scenario_dir(city_id) / "MANIFEST.json").read_text())
    net_path = config.REPO / man["files"]["net"]
    net = sumolib.net.readNet(str(net_path))
    return net, net_path, man


def _shape(net, e) -> list[list[float]]:
    return [[round(lon, 5), round(lat, 5)] for lon, lat in (net.convertXY2LonLat(x, y) for x, y in e.getShape())]


@lru_cache(maxsize=4)
def _background(city_id: str) -> dict:
    """Major roads of the scenario as plain geometry — the backdrop that is NOT forecast."""
    from app.twin.sensor_map import MAJOR
    net, net_path, man = _net(city_id)
    feats = []
    for e in net.getEdges():
        if e.getID().startswith(":") or not e.allows("passenger"):
            continue
        t = e.getType() or ""
        if t in MAJOR or t == "highway.secondary_link":
            feats.append({"id": e.getID(), "type": t.replace("highway.", ""), "shape": _shape(net, e)})
    return {"city_id": city_id, "network": str(net_path.relative_to(config.REPO)), "bbox": man["bbox"], "network_edges": len(net.getEdges()), "major_edges": len(feats), "edges": feats}


def _series(dataset: str):
    if dataset in scientific_prediction.DATASETS:
        return scientific_prediction.series()
    from app.forecasting.training import basicts_train as bt
    from app.data import uploads as user_datasets
    meta = user_datasets.load_meta(dataset.split(":", 1)[1])
    if not meta:
        raise KeyError(f"unknown dataset {dataset}")
    name = bt.bts_name(dataset)
    if not (bt.BTS / "datasets" / name / "desc.json").exists():
        bt.prepare(dataset)
    raw, _ = bt._prepared(name)
    vals = np.asarray(raw[:, :, 0], dtype="float64")
    return meta, vals


def _mapping(dataset):
    from app.twin import sensor_map
    return scientific_prediction.mapping() if dataset in scientific_prediction.DATASETS else sensor_map.find_for_dataset(dataset)


def _index(as_of, length):
    if as_of in (None, "", "latest"):
        return length
    if isinstance(as_of, bool) or (not isinstance(as_of, (int, str))) or not str(as_of).isdigit():
        raise ValueError("as_of must be an integer dataset index or latest")
    value = int(as_of)
    if not 12 <= value <= length:
        raise ValueError(f"as_of must be in [12, {length}]")
    return value


def held_out(T: int, meta: dict) -> dict:
    """The chronological held-out window (last 20 %) and a handful of moments inside it."""
    from app.forecasting.training import train_eval as te
    sp = te.splits(T)
    lo, hi = sp["test"][0] + 12, T - 12
    step_s = int(meta.get("interval_s", 300))
    n = 12
    picks = [int(lo + k * (hi - lo) / (n - 1)) for k in range(n)]
    return {"from_index": lo, "to_index": hi, "from_utc": _clock(meta.get("first_utc"), lo, step_s), "to_utc": _clock(meta.get("first_utc"), hi, step_s),
            "moments": [{"index": i, "utc": _clock(meta.get("first_utc"), i, step_s)} for i in picks], "rule": "chronological 70/10/20 split; the model never saw these steps"}


def network(dataset: str, as_of: int | str | None = None, model: str | None = None) -> dict:
    """The forecast state of the network at one moment: sensors, DIRECT/DERIVED edges, coverage."""
    from app.twin import sensor_map
    from app.routing import edge_costs as ec
    from app.routing import analysis_routing as route_opt
    meta, vals = _series(dataset)
    T, step_s = vals.shape[0], int(meta.get("interval_s", 300))
    step_min = step_s // 60
    latest = as_of in (None, "", "latest")
    idx = _index(as_of, T)
    now, pred, info = _predict(dataset, idx, model)
    quantity = meta.get("quantity") or ""
    nodes, coords = meta["nodes"], meta.get("coords") or []
    actual = vals[idx:idx + 12] if idx < T else None
    if actual is not None:
        actual = np.where(actual > 0, actual, np.nan)
    hstep = {h: max(0, min(11, h // step_min - 1)) for h in HORIZONS}
    mapping = _mapping(dataset)
    mrec = {r["node"]: r for r in (mapping or {}).get("records", [])}
    sensors = []
    for j, node in enumerate(nodes):
        c = coords[j] if j < len(coords) else None
        r = mrec.get(node, {})
        sensors.append({"node": node, "index": j, "sensor_id": r.get("sensor_id"), "lat": c[0] if c else None, "lon": c[1] if c else None,
                        "now": _to_kmh(now[j], quantity), "pred": {str(h): _to_kmh(pred[hstep[h], j], quantity) for h in HORIZONS},
                        "actual": {str(h): _to_kmh(actual[hstep[h], j], quantity) if hstep[h] < len(actual) else None for h in HORIZONS} if actual is not None else None,
                        "mapped_edge": r.get("edge"), "mapping_quality": r.get("quality"), "mapping_reason": r.get("reason")})
    edges, coverage, cfg_hash = [], {"direct_edges": 0, "derived_edges": 0, "network_edges": None, "control_sensors": 0}, None
    background = None
    if mapping:
        net, net_path, man = _net(mapping["city_id"])
        cmap, free, facts = sensor_map.corridor_map(mapping, include_weak=dataset not in scientific_prediction.DATASETS)
        cfg = ec.load_config(); cfg_hash = cfg["_config_hash"]
        tables = {}
        for label, src in [("now", now)] + [(str(h), pred[hstep[h]]) for h in HORIZONS]:
            values, unit = route_opt.to_mps({n: float(src[nodes.index(n)]) for n in cmap}, quantity)
            tables[label] = ec.build(values, unit, cmap, net_path, int(label) if label != "now" else 0, cfg, None, info.get("resolved_model"), None, corridor_free_speed=free)
        ids = sorted(set().union(*(t["edges"].keys() for t in tables.values())))
        for eid in ids:
            rows = {k: t["edges"].get(eid) for k, t in tables.items()}
            any_row = next(r for r in rows.values() if r)
            e = net.getEdge(eid)
            edges.append({"id": eid, "shape": _shape(net, e), "provenance": any_row["source"], "hop": any_row["graph_distance"], "corridor": any_row["corridor"],
                          "sensor_id": facts.get(any_row["corridor"], {}).get("sensor_id"), "type": (e.getType() or "").replace("highway.", ""), "length_m": any_row["length_m"],
                          "limit_kmh": round(any_row["speed_limit_mps"] * 3.6, 1),
                          "speed_kmh": {k: (round(r["bounded_speed_mps"] * 3.6, 1) if r else None) for k, r in rows.items()},
                          "ratio": {k: (r["ratio"] if r else None) for k, r in rows.items()}})
        coverage = {"direct_edges": tables["15"]["direct_edges"], "derived_edges": tables["15"]["derived_edges"], "network_edges": tables["15"]["network_edges"],
                    "coverage_hops": tables["15"]["coverage_hops"], "control_sensors": len(cmap), "future_cost_hash_15": tables["15"]["future_cost_hash"],
                    "mapping_file": mapping.get("file"), "mapping_hash": mapping.get("file_hash"), "city_id": mapping["city_id"]}
        background = _background(mapping["city_id"])
    from app.data import provenance as pv
    return {"dataset": dataset, "name": meta.get("name"), "quantity": quantity, "interval_s": step_s, "steps": T,
            "model": info.get("resolved_model"), "requested_model": model or "auto", "checkpoint": Path(info["checkpoint_path"]).name if info.get("checkpoint_path") else None,
            "checkpoint_sha256": info.get("checkpoint_sha256"), "trust": info.get("trust"), "validation_MAE": info.get("validation_MAE"), "test_skill": info.get("test_skill"),
            "as_of_index": idx, "as_of_utc": _clock(meta.get("first_utc"), idx, step_s), "mode": "LATEST" if latest else "HELD_OUT" if idx >= held_out(T, meta)["from_index"] else "HISTORICAL",
            "has_actual": actual is not None, "horizons": list(HORIZONS), "held_out": held_out(T, meta),
            "sensors": sensors, "edges": edges, "background": background,
            "coverage": {**coverage, "model_sensors": len(nodes), "sensors_with_coords": sum(1 for s in sensors if s["lat"] is not None),
                         "rejected_sensors": sum(1 for r in mrec.values() if r.get("quality") == "REJECTED"), "routing_config_hash": cfg_hash},
            "forecast_contract": info.get("forecast_contract"),
            "provenance": {"raw_prediction_hash": info.get("raw_prediction_hash") or pv.sha_array(pred),
                           "input_window_hash": info.get("input_window_hash") or pv.sha_array(vals[idx - 12:idx]),
                           "inference_seconds": info.get("inference_seconds"), "result_source": info.get("result_source"),
                           "prediction_cache_hit": info.get("prediction_cache_hit", False),
                           "inference_recomputed": info.get("inference_recomputed", True),
                           "nonfinite_values_replaced": info.get("nonfinite_values_replaced")}}


def road(dataset: str, node: str | int, as_of: int | str | None = None, models: tuple[str, ...] = ("GWNet", "persistence")) -> dict:
    """One sensor's history, each model's 12-step prediction, and the measured future when the
    moment is inside the data — the inspector chart and the validation replay."""
    meta, vals = _series(dataset)
    T, step_s = vals.shape[0], int(meta.get("interval_s", 300))
    nodes = meta["nodes"]
    j = int(node) if str(node).isdigit() and str(node) not in nodes else nodes.index(str(node))
    if not 0 <= j < len(nodes):
        raise ValueError("sensor index outside this dataset")
    latest = as_of in (None, "", "latest")
    idx = _index(as_of, T)
    quantity = meta.get("quantity") or ""
    hist = [_to_kmh(v, quantity) if v > 0 else None for v in vals[max(0, idx - HISTORY_STEPS):idx, j]]
    actual = [_to_kmh(v, quantity) if v > 0 else None for v in vals[idx:idx + 12, j]] if idx < T else None
    out_models, errs = {}, {}
    for m in models:
        try:
            now, pred, info = _predict(dataset, idx, m)
        except Exception as ex:                       # noqa: BLE001 — a model that cannot run here is reported, not faked
            errs[m] = str(ex); continue
        series = [_to_kmh(pred[k, j], quantity) for k in range(pred.shape[0])]
        rec = {"model": info.get("resolved_model"), "prediction": series, "checkpoint_sha256": info.get("checkpoint_sha256"), "inference_seconds": info.get("inference_seconds"),
               "provenance": info}
        if actual:
            pairs = [(p, a) for p, a in zip(series, actual) if p is not None and a is not None]
            rec["MAE_kmh"] = round(float(np.mean([abs(p - a) for p, a in pairs])), 3) if pairs else None
            rec["abs_error_by_h"] = {str(h): (round(abs(series[h // (step_s // 60) - 1] - actual[h // (step_s // 60) - 1]), 2) if actual[h // (step_s // 60) - 1] is not None and series[h // (step_s // 60) - 1] is not None else None) for h in HORIZONS if h // (step_s // 60) - 1 < min(len(series), len(actual))}
        out_models[m] = rec
    pm = out_models.get("persistence", {}).get("MAE_kmh")
    for m, rec in out_models.items():
        rec["skill_vs_persistence"] = round(1 - rec["MAE_kmh"] / pm, 4) if rec.get("MAE_kmh") is not None and pm else None
    from app.twin import sensor_map
    mapping = _mapping(dataset)
    r = next((x for x in (mapping or {}).get("records", []) if x["node"] == nodes[j]), {})
    return {"dataset": dataset, "node": nodes[j], "index": j, "sensor_id": r.get("sensor_id"), "mapped_edge": r.get("edge"), "mapping_quality": r.get("quality"), "edge_type": (r.get("edge_type") or "").replace("highway.", ""),
            "provenance": "DIRECT" if r.get("quality") in ("GOOD", "WEAK") else "SENSOR_ONLY", "quantity": quantity, "unit": "km/h", "interval_s": step_s,
            "as_of_index": idx, "as_of_utc": _clock(meta.get("first_utc"), idx, step_s), "history": hist, "history_from_utc": _clock(meta.get("first_utc"), max(0, idx - HISTORY_STEPS), step_s),
            "actual": actual, "models": out_models, "errors": errs, "mode": "LATEST" if latest else "HELD_OUT" if idx >= held_out(T, meta)["from_index"] else "HISTORICAL"}
