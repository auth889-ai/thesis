#!/usr/bin/env python3
"""FULL METR-LA COVERAGE RESCUE — feasibility only (no final seeds, no tuning).

For a candidate OSM->SUMO scenario: map ALL 207 genuine METR-LA detectors onto it with the strict
gates of `sensor_map` (GOOD only: within 60 m of a passenger motorway/trunk/primary/secondary edge),
run the 207-node Graph WaveNet at a development moment, keep only the mapped sensors, build the
DIRECT + DERIVED edge-cost table with the production builder, run ONE baseline SUMO execution on
development demand, and measure what actually matters:

    MODEL COVERAGE     mapped sensors, DIRECT / DERIVED / UNFORECASTED edges
    NETWORK COVERAGE   % drivable edge length DIRECT, DIRECT+DERIVED
    TRAFFIC EXPOSURE   % vehicles touching DIRECT, DIRECT+DERIVED; % vehicle-km and % vehicle-time on covered edges
    ROUTING EXPOSURE   equipped decisions whose candidate set contains a priced edge; % candidate routes priced

    python src/pipeline/city/coverage_rescue.py --city la_c1_glendale_110_2 [--city ...] --out results/routing/coverage_rescue
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from traffictwin.paths import REPO
sys.path.insert(0, str(REPO))
from traffictwin.digital_twin import sensor_map as sm                       # noqa: E402
from traffictwin.digital_twin.scenario_builder import scenario_dir             # noqa: E402
from pipeline.routing import edge_costs as ec                    # noqa: E402
from pipeline.routing import predictive_routing as pr            # noqa: E402
from pipeline.routing import route_optimizer as ro               # noqa: E402

CK207 = REPO / "results/forecasting/checkpoints/GraphWaveNet/METR-LA_50_12_12/d1ffd3d52d3caacf60ebf59214673f7c/GraphWaveNet_best_val_MAE.pt"
DEV_SEED, DEV_MOMENT_RULE = 101, "test_start + 12 + (101*97) mod (test_len-24)"
DURATION_S, COMPLIANCE, ROUND_S = 2700, 0.3, 900
MPH = 0.44704


def sha_file(p: Path, n: int = 12) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:n]


# ---------------------------------------------------------------------------
# 1. all 207 detectors -> this scenario (strict gates, genuine coordinates only)
# ---------------------------------------------------------------------------

def map_207(city_id: str) -> dict:
    import sumolib
    man = json.loads((scenario_dir(city_id) / "MANIFEST.json").read_text())
    net_path = REPO / man["files"]["net"]
    net = sumolib.net.readNet(str(net_path))
    s, w, n, e_ = man["bbox"]
    rows = sm.genuine_rows()
    recs = []
    for i, r in enumerate(rows):
        lat, lon = float(r["latitude"]), float(r["longitude"])
        rec = {"node_index": i, "sensor_id": r["sensor_id"], "lat": lat, "lon": lon, "edge": None, "snap_m": None, "edge_type": None, "speed_limit_mps": None, "edge_length_m": None, "quality": "REJECTED", "reason": None}
        if not (s <= lat <= n and w <= lon <= e_):
            rec["reason"] = "outside the scenario bbox"
        else:
            e, d, cands = sm.snap(net, lat, lon)
            if e is None:
                rec["reason"] = f"no drivable edge within {sm.MAX_M:.0f} m"
            else:
                t = e.getType() or ""
                rec.update(edge=e.getID(), snap_m=round(d, 1), edge_type=t, speed_limit_mps=round(e.getSpeed(), 3), edge_length_m=round(e.getLength(), 1))
                if d <= sm.GOOD_M and t in sm.MAJOR:
                    rec["quality"] = "GOOD"
                else:
                    rec["quality"] = "REJECTED"; rec["reason"] = f"snap {d:.0f} m > {sm.GOOD_M:.0f} m" if d > sm.GOOD_M else f"nearest edge is {t or 'untyped'}, not a major road"
        recs.append(rec)
    good = [r for r in recs if r["quality"] == "GOOD"]
    # two detectors on one edge (opposite carriageways snap to the same edge occasionally): the edge is priced once
    inside = [r for r in recs if r["reason"] != "outside the scenario bbox"]
    snaps = [r["snap_m"] for r in good]
    drivable = [e for e in net.getEdges() if not e.getID().startswith(":") and e.allows("passenger")]
    length_km = sum(e.getLength() for e in drivable) / 1000
    area_km2 = (n - s) * 111.0 * (e_ - w) * 92.0
    return {"city_id": city_id, "bbox": man["bbox"], "network": str(net_path.relative_to(REPO)), "network_hash": sha_file(net_path), "source": sm.upstream_pin(),
            "detectors_total": len(recs), "inside_bbox": len(inside), "mapped_GOOD": len(good), "distinct_direct_edges": len({r["edge"] for r in good}),
            "rejected_inside": {k: sum(1 for r in inside if r["quality"] == "REJECTED" and (r["reason"] or "").startswith(k)) for k in ("snap", "nearest", "no drivable")},
            "snap_median_m": round(float(np.median(snaps)), 1) if snaps else None, "snap_max_m": round(max(snaps), 1) if snaps else None,
            "sumo_edges": len(net.getEdges()), "drivable_edges": len(drivable), "drivable_km": round(length_km, 1), "area_km2": round(area_km2, 1),
            "detector_density_per_km2": round(len(good) / area_km2, 3) if area_km2 else None, "records": recs}


# ---------------------------------------------------------------------------
# 2. the 207-node forecast at a development moment -> only mapped sensors -> edge-cost table
# ---------------------------------------------------------------------------

def forecast_207(as_of: int | None = None) -> dict:
    from traffictwin.forecasting.training import basicts_train as bt
    from traffictwin.forecasting.training import train_eval as te
    import torch
    raw, _ = bt._prepared("METR-LA")
    T = raw.shape[0]; sp = te.splits(T); lo = sp["test"][0]
    as_of = int(lo + 12 + (DEV_SEED * 97) % ((T - lo) - 24)) if as_of is None else as_of
    card = {"arch": "GWNet", "arch_class": "GraphWaveNet", "bts_name": "METR-LA", "checkpoint": str(CK207)}
    t0 = time.perf_counter()
    pred = bt.predict(card, as_of)                                # (12, 207), mph — the product's own inference path
    secs = time.perf_counter() - t0
    now = np.asarray(raw[as_of - 1, :, 0], dtype="float64")
    from traffictwin.data import provenance as pv
    return {"as_of": as_of, "now": now, "pred": pred, "inference_seconds": round(secs, 3), "checkpoint_sha256": sha_file(CK207), "raw_prediction_hash": pv.sha_array(pred), "nodes": raw.shape[1]}


def cost_tables(mapping: dict, F: dict, net_path: Path, cfg: dict) -> dict:
    good = [r for r in mapping["records"] if r["quality"] == "GOOD"]
    cmap, free = {}, {}
    for r in good:
        node = f"S{r['node_index']}"
        cmap[node] = {"edges": [r["edge"]], "sensor_id": r["sensor_id"], "quality": "GOOD"}; free[node] = float(r["speed_limit_mps"])
    tables = {}
    for h in (15, 30):
        k = max(0, min(11, h // 5 - 1))
        values = {node: float(F["pred"][k, int(node[1:])]) * MPH for node in cmap}
        tables[h] = ec.build(values, "speed_mps", cmap, net_path, h, cfg, None, "GWNet-207", None, corridor_free_speed=free)
    return tables


# ---------------------------------------------------------------------------
# 3. one baseline SUMO execution on development demand -> exposure
# ---------------------------------------------------------------------------

def baseline_run(city_id: str, out: Path) -> tuple[Path, Path]:
    import traci
    man = json.loads((scenario_dir(city_id) / "MANIFEST.json").read_text())
    net, routes = REPO / man["files"]["net"], REPO / man["files"]["routes"]
    out.mkdir(parents=True, exist_ok=True)
    ns = argparse.Namespace(net=str(net), routes=str(routes), seed=DEV_SEED, scale=1.0, horizon=DURATION_S, edgedata_period=300, time_to_teleport=300, sumo_binary="sumo")
    cmd = pr.base_cmd(ns, out) + ["--vehroute-output", str(out / "vehroutes.xml"), "--vehroute-output.exit-times", "true"]
    traci.start(cmd, port=pr.free_port(), label=f"cov-{city_id}-{time.time()}")
    t = 0
    while t < DURATION_S and traci.simulation.getMinExpectedNumber() > 0:
        traci.simulationStep(); t = int(traci.simulation.getTime())
    traci.close()
    return out / "vehroutes.xml", routes


def exposure(vehroutes: Path, net_path: Path, direct: set[str], derived: set[str]) -> dict:
    import sumolib
    net = sumolib.net.readNet(str(net_path))
    L = {e.getID(): e.getLength() for e in net.getEdges()}
    txt = vehroutes.read_text()
    veh = re.findall(r'<vehicle id="([^"]+)"[^>]*depart="([^"]+)"[^>]*?(?:arrival="([^"]+)")?[^>]*>.*?<route[^>]*edges="([^"]+)"(?:\s+exitTimes="([^"]+)")?', txt, flags=re.S)
    n = len(veh); touch_d = touch_dd = 0; km = km_d = km_dd = 0.0; tt = tt_d = tt_dd = 0.0
    for vid, dep, arr, edges, exits in veh:
        E = edges.split(); Ls = [L.get(e, 0.0) for e in E]
        km += sum(Ls) / 1000; kd = sum(l for e, l in zip(E, Ls) if e in direct) / 1000; kdd = sum(l for e, l in zip(E, Ls) if e in direct or e in derived) / 1000
        km_d += kd; km_dd += kdd
        if any(e in direct for e in E): touch_d += 1
        if any(e in direct or e in derived for e in E): touch_dd += 1
        if exits:
            xs = [float(x) for x in exits.split()]; t_prev = float(dep)
            for e, x in zip(E, xs):
                d = max(0.0, x - t_prev); t_prev = x; tt += d
                if e in direct: tt_d += d
                if e in direct or e in derived: tt_dd += d
    pct = lambda a, b: round(100 * a / b, 2) if b else None
    return {"vehicles_in_output": n, "pct_vehicles_touching_DIRECT": pct(touch_d, n), "pct_vehicles_touching_DIRECT_or_DERIVED": pct(touch_dd, n),
            "vehicle_km_total": round(km, 1), "pct_vehicle_km_DIRECT": pct(km_d, km), "pct_vehicle_km_DIRECT_or_DERIVED": pct(km_dd, km),
            "vehicle_hours_total": round(tt / 3600, 2), "pct_vehicle_time_DIRECT": pct(tt_d, tt), "pct_vehicle_time_DIRECT_or_DERIVED": pct(tt_dd, tt),
            "note": "vehicle-time from vehroute exitTimes of the baseline development run; distance from edge lengths"}


def routing_exposure(city_id: str, routes: Path, table: dict, out: Path, cfg: dict) -> dict:
    from backend.app.simulation.trip_comparison import read_any_routes
    man = json.loads((scenario_dir(city_id) / "MANIFEST.json").read_text())
    net = REPO / man["files"]["net"]
    veh = read_any_routes(routes)
    priced = set(table["edges"].keys())
    exposed = total = cand_total = cand_priced = 0; by = defaultdict(int)
    for k in range(2):                                            # departures 0-1800 s: two 900 s rounds
        b, e = k * ROUND_S, (k + 1) * ROUND_S
        trips = [{"id": v, "from": r[0], "to": r[-1], "depart": d, "current_route": r} for v, d, r in veh if pr.equipped(v, COMPLIANCE) and b <= d < e]
        if not trips:
            continue
        rec = ro.optimize(net, trips, table, out / f"round_{k}", DEV_SEED, float(ROUND_S), cfg, keep_candidates=True)
        for d in rec["decisions"]:
            total += 1; by[d["decision"]] += 1
            cs = d.get("candidates") or []; cand_total += len(cs)
            hit = [c for c in cs if any(x in priced for x in c["edges"])]; cand_priced += len(hit)
            if hit:
                exposed += 1
    return {"equipped_decisions": total, "decisions_with_a_priced_edge_in_candidates": exposed, "pct_decisions_exposed": round(100 * exposed / total, 2) if total else None,
            "candidate_routes": cand_total, "pct_candidate_routes_priced": round(100 * cand_priced / cand_total, 2) if cand_total else None, "decisions_by_outcome": dict(by),
            "note": "development demand and moment only; the routing config, thresholds and admission are the frozen production ones"}


# ---------------------------------------------------------------------------

def evaluate(city_id: str, out_root: Path, F: dict, cfg: dict) -> dict:
    out = out_root / city_id; out.mkdir(parents=True, exist_ok=True)
    mapping = map_207(city_id)
    (out / "sensor_to_edge_207.json").write_text(json.dumps(mapping, indent=1))
    net_path = REPO / mapping["network"]
    good = [r for r in mapping["records"] if r["quality"] == "GOOD"]
    res = {"city_id": city_id, "bbox": mapping["bbox"], "network_hash": mapping["network_hash"], "sumo_edges": mapping["sumo_edges"], "drivable_edges": mapping["drivable_edges"], "drivable_km": mapping["drivable_km"], "area_km2": mapping["area_km2"],
           "detectors_inside_bbox": mapping["inside_bbox"], "mapped_GOOD": mapping["mapped_GOOD"], "distinct_direct_edges": mapping["distinct_direct_edges"], "rejected_inside": mapping["rejected_inside"],
           "snap_median_m": mapping["snap_median_m"], "snap_max_m": mapping["snap_max_m"], "detector_density_per_km2": mapping["detector_density_per_km2"]}
    if not good:
        res["verdict"] = "no GOOD detector inside"; return res
    tables = cost_tables(mapping, F, net_path, cfg)
    t15 = tables[15]
    direct = {e for e, r in t15["edges"].items() if r["source"] == "DIRECT"}; derived = {e for e, r in t15["edges"].items() if r["source"] == "DERIVED"}
    import sumolib
    net = sumolib.net.readNet(str(net_path))
    L = {e.getID(): e.getLength() for e in net.getEdges() if not e.getID().startswith(":") and e.allows("passenger")}
    tot = sum(L.values())
    res["model_coverage"] = {"mapped_sensors": len(good), "DIRECT_edges": len(direct), "DERIVED_edges": len(derived), "UNFORECASTED_edges": len(L) - len(direct) - len(derived), "coverage_hops": t15["coverage_hops"], "future_cost_hash_15": t15["future_cost_hash"]}
    res["network_coverage"] = {"pct_drivable_length_DIRECT": round(100 * sum(L.get(e, 0) for e in direct) / tot, 2), "pct_drivable_length_DIRECT_or_DERIVED": round(100 * sum(L.get(e, 0) for e in direct | derived) / tot, 2)}
    t0 = time.time()
    vehroutes, routes = baseline_run(city_id, out / "baseline_dev")
    res["traffic_exposure"] = exposure(vehroutes, net_path, direct, derived); res["traffic_exposure"]["sumo_wall_s"] = round(time.time() - t0, 1)
    res["routing_exposure"] = routing_exposure(city_id, routes, t15, out / "routing_dev", cfg)
    res["demand"] = {"file": str(routes.relative_to(REPO)), "hash": sha_file(routes), "vehicles": len(re.findall(r"<vehicle ", routes.read_text())), "reality": "SYNTHETIC_WHAT_IF randomTrips on the real OSM network (development seed 101)"}
    res["forecast"] = {"model": "Graph WaveNet, 207-node METR-LA checkpoint", "checkpoint_sha256": F["checkpoint_sha256"], "as_of_index": F["as_of"], "raw_prediction_hash": F["raw_prediction_hash"], "inference_seconds": F["inference_seconds"], "sensors_used": len(good), "sensors_ignored": F["nodes"] - len(good)}
    (out / "coverage.json").write_text(json.dumps(res, indent=1))
    return res


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--city", action="append", required=True)
    p.add_argument("--out", default="results/routing/coverage_rescue")
    a = p.parse_args()
    cfg = ec.load_config()
    F = forecast_207()
    print(f"[cov] 207-node forecast at index {F['as_of']}: {F['inference_seconds']} s, raw hash {F['raw_prediction_hash']}, ckpt {F['checkpoint_sha256']}", flush=True)
    out_root = REPO / a.out; out_root.mkdir(parents=True, exist_ok=True)
    rows = []
    for cid in a.city:
        t = time.time()
        try:
            r = evaluate(cid, out_root, F, cfg)
        except Exception as ex:                                     # noqa: BLE001
            r = {"city_id": cid, "error": f"{type(ex).__name__}: {ex}"}
        rows.append(r)
        te_ = r.get("traffic_exposure", {}); rx = r.get("routing_exposure", {}); mc = r.get("model_coverage", {}); nc = r.get("network_coverage", {})
        print(f"[cov] {cid:<28} in={r.get('detectors_inside_bbox')} GOOD={r.get('mapped_GOOD')} DIRECT={mc.get('DIRECT_edges')} DERIVED={mc.get('DERIVED_edges')} edges={r.get('sumo_edges')} "
              f"len%={nc.get('pct_drivable_length_DIRECT')}/{nc.get('pct_drivable_length_DIRECT_or_DERIVED')} veh%={te_.get('pct_vehicles_touching_DIRECT')}/{te_.get('pct_vehicles_touching_DIRECT_or_DERIVED')} "
              f"km%={te_.get('pct_vehicle_km_DIRECT')}/{te_.get('pct_vehicle_km_DIRECT_or_DERIVED')} time%={te_.get('pct_vehicle_time_DIRECT')}/{te_.get('pct_vehicle_time_DIRECT_or_DERIVED')} "
              f"dec%={rx.get('pct_decisions_exposed')} cand%={rx.get('pct_candidate_routes_priced')} {r.get('error', '')} ({time.time()-t:.0f}s)", flush=True)
    (out_root / "summary.json").write_text(json.dumps({"generated_utc": datetime.now(timezone.utc).isoformat(), "forecast": {k: v for k, v in F.items() if k not in ("now", "pred")}, "candidates": rows}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
