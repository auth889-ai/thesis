#!/usr/bin/env python3
"""BLOCKER #6 — THE FINAL LEARNED-MODEL OUTCOME EXPERIMENT (FINAL_LEARNED_PROTOCOL_v1).

Does prediction-aware routing with the trained, validated Graph WaveNet checkpoint improve actual
SUMO outcomes against no rerouting, reactive rerouting, and the same router fed by persistence?

Scenario (frozen): the downtown Los Angeles network built from OpenStreetMap around eight genuine
METR-LA detectors (src/pipeline/city/sensor_map.py). Background demand is SUMO's randomTrips with the
scenario's own wizard options, drawn once per seed. What makes the forecast MEAN something in the
simulation: the detectors' measured speeds at the analysed moment and the 45 minutes after it are
replayed as speed caps on the eight mapped edges, every 5 minutes, identically in every arm. A good
forecast anticipates those caps; persistence assumes the current one persists.

Four arms on identical paired scenarios, only the information/policy differs:

    A  baseline               static routes, no rerouting
    B  reactive               traci.vehicle.rerouteTraveltime on current travel times (equipped share)
    C  persistence_predictive the production router (edge_costs -> route_optimizer) fed by persistence
    D  learned_predictive     the production router fed by a FRESH Graph WaveNet forward pass
    (research only) oracle    measured future of the paired baseline, never in the headline

Every learned run: load the verified checkpoint, run inference at this seed's dataset moment,
hash the raw prediction, build the edge-cost table, write RoutingRuns, run SUMO. Provenance
records (an_/rt_/sim_) go to the same store the product uses.

    python -m traffictwin.protocols.learned_gate --seeds dev
    python -m traffictwin.protocols.learned_gate --seeds final
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import statistics
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from traffictwin.paths import REPO
sys.path.insert(0, str(REPO))
from traffictwin.optimization import edge_costs as ec              # noqa: E402
from traffictwin.digital_twin import runtime as pr     # noqa: E402
from traffictwin.optimization import route_optimizer as ro        # noqa: E402
from traffictwin.protocols.oracle_gate import TCRIT, concentration, never_inserted_charge, paired, probe_tripinfo, sha_file, sumo_version  # noqa: E402
from traffictwin.digital_twin import sensor_map                      # noqa: E402
from traffictwin.digital_twin.scenario_builder import scenario_dir, sumo_tools_dir  # noqa: E402

OUT = REPO / "results/routing/learned_gate"
FROZEN_JOB, FROZEN_SHA = "train_7bf79d6c81", "566b97d97943"     # Graph WaveNet, 120 epochs, AWS g5.xlarge, validated 2026-09-05
FROZEN_CARD = OUT / f"FROZEN_CARD_GWNet_{FROZEN_SHA}.json"


def frozen_card(ident: dict) -> dict:
    """The model card of the frozen checkpoint. The product keeps one card per dataset and model,
    so a later training job overwrites it; the gate therefore keeps its own copy, rebuilt from the
    frozen job's identity (paths, hashes, epochs) and the shared architecture/data fields."""
    from traffictwin.forecasting.training import basicts_train as bt
    if FROZEN_CARD.exists():
        c = json.loads(FROZEN_CARD.read_text())
        if c.get("checkpoint") == ident["checkpoint_path"]:
            return c
    base = bt.card_for(ident["dataset"], "GWNet") or {}
    j = json.loads((REPO / "results/forecasting/train_jobs" / f"{ident['training_job_id']}.json").read_text())
    c = {**base, "epochs": ident["epochs"], "checkpoint": ident["checkpoint_path"], "run_dir": str(Path(ident["checkpoint_path"]).parent), "cache_key": j.get("cache_key"),
         "config_hash": ident.get("config_hash"), "best_val_MAE": j.get("validation_MAE"), "trained_utc": j.get("updated_utc"), "training_job_id": ident["training_job_id"],
         "test_metrics": j.get("test"), "verification": j.get("verification"), "trust": j.get("trust"), "checkpoint_sha256": ident["checkpoint_sha256"],
         "note": "frozen copy for FINAL_LEARNED_PROTOCOL_v1; the product card file was later overwritten by another training job"}
    for k in ("curve", "evaluation", "persistence_test"):
        c.pop(k, None)                                     # those belong to whichever job wrote the product card
    OUT.mkdir(parents=True, exist_ok=True)
    FROZEN_CARD.write_text(json.dumps(c, indent=1, default=str))
    return c
ARMS = ("baseline", "reactive", "persistence_predictive", "learned_predictive")
PRED_ARMS = {"persistence_predictive": "persistence", "learned_predictive": "GWNet"}


# ---------------------------------------------------------------------------
# the frozen protocol
# ---------------------------------------------------------------------------

def protocol(cfg: dict | None = None, with_oracle: bool = False) -> dict:
    from traffictwin.forecasting.operations import model_registry as model_registry
    cfg = cfg or ec.load_config()
    city_id, dataset = "los_angeles_metr", "user:los_angeles"
    man = json.loads((scenario_dir(city_id) / "MANIFEST.json").read_text())
    mapping = sensor_map.find_for_dataset(dataset)
    if not mapping:
        raise SystemExit(f"no detector -> edge mapping for {dataset}")
    from traffictwin.forecasting.operations import training_jobs as train_jobs
    ident = train_jobs.identity_for(FROZEN_JOB)
    if not ident or not ident.get("checkpoint_path"):
        raise SystemExit(f"the frozen training job {FROZEN_JOB} has no checkpoint identity")
    ck = Path(ident["checkpoint_path"])
    from traffictwin.forecasting.training import basicts_train as bt
    from traffictwin.forecasting.training import train_eval as te
    if not ck.exists() or te.sha256_file(ck, 12) != FROZEN_SHA:
        raise SystemExit(f"the frozen checkpoint {FROZEN_SHA} is not on disk at {ck}")
    if not ident.get("routing_eligible"):
        raise SystemExit("the frozen checkpoint is not routing-eligible")
    card = frozen_card(ident)
    today = model_registry.resolve(dataset, None)
    name = bt.bts_name(dataset)
    rt_opts = list(man["process"]["randomtrips_options"])
    return {
        "protocol_id": "FINAL_LEARNED_PROTOCOL_v1",
        "city_id": city_id, "network": man["files"]["net"], "network_hash": sha_file(REPO / man["files"]["net"]),
        "dataset": dataset, "dataset_hash": te.sha256_file(bt.BTS / "datasets" / name / "data.dat"), "graph_hash": te.sha256_file(bt.BTS / "datasets" / name / "adj_mx.pkl", 8),
        "mapping_file": mapping["file"], "mapping_hash": mapping["file_hash"], "mapping_counts": mapping["counts"], "mapping_upstream": mapping["source"],
        "model": "GWNet", "model_label": "Graph WaveNet", "training_job_id": FROZEN_JOB, "checkpoint": ck.name, "checkpoint_path": str(ck), "checkpoint_sha256": FROZEN_SHA, "checkpoint_cache_key": card.get("cache_key"),
        "checkpoint_epochs": ident.get("epochs"), "checkpoint_config_hash": ident.get("config_hash"), "frozen_card": str(FROZEN_CARD.relative_to(REPO)),
        "model_selection_rule": {"frozen_choice": "GWNet", "frozen_on": "2026-09-05", "why": "the registry's automatic rule chose this Graph WaveNet checkpoint (validation MAE 3.79 vs STID 3.94) when the protocol was frozen",
                                 "registry_choice_today": {"model": today.get("model"), "checkpoint_sha256": te.sha256_file(Path(today["checkpoint_path"]), 12) if today.get("checkpoint_path") else None},
                                 "note": "the checkpoint is pinned by training job id and SHA; a later training job cannot change what this protocol evaluates"},
        "held_out_MAE": ident.get("held_out_MAE"), "persistence_MAE": ident.get("persistence_MAE"), "held_out_skill": ident.get("skill_vs_persistence"), "held_out_horizon": ident.get("held_out_horizon"),
        "routing_config_file": cfg["_config_file"], "routing_config_hash": cfg["_config_hash"], "coverage_hops": cfg["edge_costs"]["coverage_hops"],
        "min_saving_s": cfg["decision"]["min_saving_s"], "min_saving_pct": cfg["decision"]["min_saving_pct"], "admission": cfg["admission"], "candidates": cfg["candidates"], "generalized_cost": cfg["generalized_cost"],
        "demand_method": "SUMO randomTrips.py with the scenario's osmWebWizard passenger options, one draw per seed (--seed <seed>), departures 0-1800 s; SUMO --scale 1",
        "randomtrips_options": [o for o in rt_opts if not o.startswith("/")],
        "calibration_method": "the eight mapped detectors' MEASURED speeds from the dataset moment onward are replayed every 300 s as lane speed caps (min(limit, measured)) on their mapped edges, identically in every arm",
        "od_population": "randomTrips origins/destinations per seed, identical in every arm; equipped share by the deterministic id hash",
        "simulation_duration_s": 2700, "routing_round_s": 900, "edgedata_period_s": 300, "compliance": 0.3, "reactive_period_s": 60, "time_to_teleport_s": 300,
        "forecast_moments": "dataset index as_of = test_start + 12 + (seed * 97) mod (test_len - 24): one held-out moment per seed; the model sees only the 12 steps before it",
        "round_horizons_min": [10, 25, 40],
        "sumo_version": sumo_version(), "with_oracle": with_oracle,
        "dev_seeds": [101, 102, 103], "final_seeds": list(range(301, 321)),
        "probe": {"from": "-161702903#3", "to": "382269888#0", "depart_s": 600, "note": "the Blocker #5 trip, reported separately, never the system conclusion"},
        "primary_metric": "total vehicle-hours of every vehicle loaded before the horizon (never-inserted vehicles charged from departure to the horizon), as in the oracle gate",
        "primary_metric_key": "total_vehicle_hours_incl_never_inserted", "lower_is_better": True,
    }


# ---------------------------------------------------------------------------
# per-seed inputs: demand, forecast, measured caps
# ---------------------------------------------------------------------------

def demand_for_seed(P: dict, seed: int, out: Path) -> tuple[Path, dict]:
    """randomTrips with the scenario's own options, this seed's draw."""
    out.mkdir(parents=True, exist_ok=True)
    trips, routes = out / f"trips_s{seed}.xml", out / f"demand_s{seed}.rou.xml"
    if not routes.exists():
        net = str(REPO / P["network"])
        cleaned, skip = [], False            # the scenario's options minus the file/seed/timing ones we set per seed
        for o in P["randomtrips_options"]:
            if o in ("-n", "-o", "-r", "-b", "-e", "-p", "--seed"):
                skip = True; continue
            if skip:
                skip = False; continue
            cleaned.append(o)
        opts = ["-n", net, "-o", str(trips), "-r", str(routes), "-b", "0", "-e", "1800", "-p", "2.0", "--seed", str(seed)] + cleaned
        r = subprocess.run([sys.executable, str(sumo_tools_dir() / "randomTrips.py")] + opts, check=False, capture_output=True, text=True, cwd=out)
        if r.returncode != 0 or not routes.exists():
            raise RuntimeError(f"randomTrips failed for seed {seed}: {(r.stderr or r.stdout)[-400:]}")
    n = len(re.findall(r"<vehicle ", routes.read_text()))
    return routes, {"demand_file": str(routes.relative_to(REPO)), "demand_hash": sha_file(routes), "vehicles": n}


def moment_for_seed(P: dict, seed: int, T: int) -> int:
    from traffictwin.forecasting.training import train_eval as te
    sp = te.splits(T)
    test_lo = sp["test"][0]
    test_len = T - test_lo
    return int(test_lo + 12 + (seed * 97) % (test_len - 24))


def forecast_for_seed(P: dict, seed: int, mapping: dict) -> dict:
    """A FRESH forward pass of the frozen checkpoint at this seed's moment, plus persistence and
    the measured future, all on the dataset's own arrays. Returns everything the arms need."""
    from traffictwin.data import provenance as pv
    from traffictwin.forecasting.training import basicts_train as bt
    from traffictwin.forecasting.training import train_eval as te
    dataset = P["dataset"]
    name = bt.bts_name(dataset)
    raw, _ = bt._prepared(name)
    vals = np.asarray(raw[:, :, 0], dtype="float64")
    meta = json.loads((REPO / "results/live/user_datasets" / dataset[5:] / "meta.json").read_text())
    nodes = meta["nodes"]
    as_of = moment_for_seed(P, seed, vals.shape[0])
    # the FROZEN checkpoint, by path and SHA — never whatever the registry resolves to today
    if te.sha256_file(Path(P["checkpoint_path"]), 12) != P["checkpoint_sha256"]:
        raise RuntimeError("the frozen checkpoint on disk has changed; refusing to run")
    card = json.loads((REPO / P["frozen_card"]).read_text())
    assert card["checkpoint"] == P["checkpoint_path"]
    an_id = f"an_lg_s{seed}"
    run = pv.Run(an_id, kind="learned_gate_analysis", city=dataset, dataset_scope=dataset, requested_model="GWNet", horizon_min=P["round_horizons_min"][0], seed=seed, protocol_id=P["protocol_id"])
    run.stage("Loading checkpoint")
    run.set(resolved_model="GWNet", checkpoint_path=P["checkpoint_path"], checkpoint_sha256=P["checkpoint_sha256"], training_job_id=P["training_job_id"], dataset_hash=P["dataset_hash"], graph_hash=P["graph_hash"],
            as_of_index=as_of, input_window_hash=pv.sha_array(raw[as_of - 12:as_of]), cache_hit_training=True, result_source="LIVE_COMPUTATION")
    run.stage("Running inference")
    t0 = time.perf_counter()
    pred = bt.predict(card, as_of)                          # the product's own inference path, on the frozen card
    now = vals[as_of - 1].copy()
    pred = np.where(np.isfinite(pred), pred, now[None, :])
    info = {"inference_seconds": round(time.perf_counter() - t0, 3), "checkpoint_sha256": te.sha256_file(Path(card["checkpoint"]), 12)}
    if info["checkpoint_sha256"] != P["checkpoint_sha256"]:
        raise RuntimeError("inference did not run on the frozen checkpoint")
    pers = np.repeat(now[None, :], 12, axis=0)
    actual = vals[as_of:as_of + 12]                                             # the measured future, 12 x 5 min
    actual = np.where(actual > 0, actual, np.nan)
    step_min = int(meta["interval_s"]) // 60
    hz = {str(h): {nodes[j]: round(float(pred[max(0, min(11, h // step_min - 1)), j]), 4) for j in range(len(nodes))} for h in (15, 30, 60)}
    run.set(raw_prediction_hash=pv.sha_array(pred), raw_prediction=hz, forecast_unit=meta.get("quantity"), inference_recomputed=True, inference_seconds=info.get("inference_seconds"),
            persistence_prediction_hash=pv.sha_array(pers))
    run.finish("done")
    # forecast quality at this moment: over the mapped detectors, for the steps the simulation covers (45 min = 9 steps)
    mapped = [nodes.index(n) for n in sensor_map.corridor_map(mapping)[0]]
    ks = list(range(min(9, actual.shape[0])))
    def mae(p):
        e = [abs(p[k, j] - actual[k, j]) for k in ks for j in mapped if np.isfinite(actual[k, j])]
        return float(np.mean(e)) if e else None
    m_model, m_pers = mae(pred), mae(pers)
    from datetime import timedelta
    as_of_time = (datetime.fromisoformat(meta["first_utc"]) + timedelta(seconds=int(meta["interval_s"]) * as_of)).isoformat() if meta.get("first_utc") else None
    quality = {"as_of_index": as_of, "as_of_time": as_of_time, "mapped_sensors": len(mapped), "steps": len(ks),
               "forecast_MAE_kmh": None if m_model is None else round(m_model, 3), "persistence_MAE_kmh": None if m_pers is None else round(m_pers, 3),
               "skill_vs_persistence": None if not m_model or not m_pers else round(1 - m_model / m_pers, 4)}
    return {"analysis_run_id": an_id, "as_of": as_of, "nodes": nodes, "now": now, "pred": pred, "pers": pers, "actual": actual, "unit": meta.get("quantity"), "quality": quality,
            "raw_prediction_hash": run.rec["raw_prediction_hash"], "persistence_prediction_hash": run.rec["persistence_prediction_hash"], "input_window_hash": run.rec["input_window_hash"], "inference_seconds": info.get("inference_seconds")}


def speed_schedule(F: dict, mapping: dict, P: dict) -> dict:
    """edge -> [(t_from_s, cap_mps)]: the measured detector speeds after the moment, every 300 s."""
    cmap, free, facts = sensor_map.corridor_map(mapping)
    k_ms = 1 / 3.6 if "km/h" in (F["unit"] or "") else 0.44704 if "mph" in (F["unit"] or "") else 1.0
    sched = {}
    for node, rec in cmap.items():
        j = F["nodes"].index(node); edge = rec["edges"][0]; limit = free[node]
        steps = []
        for k in range(int(math.ceil(P["simulation_duration_s"] / 300))):
            v = F["actual"][min(k, F["actual"].shape[0] - 1), j]
            cap = min(limit, float(v) * k_ms) if np.isfinite(v) and v > 0 else limit
            steps.append((k * 300, round(max(cap, 1.0), 3)))
        sched[edge] = steps
    return sched


# ---------------------------------------------------------------------------
# the predictive arms: production router on this seed's forecast
# ---------------------------------------------------------------------------

def predictive_routes(arm: str, seed: int, demand: Path, F: dict, mapping: dict, out: Path, P: dict, cfg: dict) -> tuple[Path, list[str] | None, dict]:
    from traffictwin.data import provenance as pv
    from traffictwin.digital_twin.live.trip_comparison import read_any_routes, rewrite_routes
    cmap, free, facts = sensor_map.corridor_map(mapping)
    k_ms = 1 / 3.6 if "km/h" in (F["unit"] or "") else 0.44704 if "mph" in (F["unit"] or "") else 1.0
    veh = read_any_routes(demand)
    R, H = P["routing_round_s"], P["simulation_duration_s"]
    model = PRED_ARMS[arm]
    new_routes, rounds, probe_route, advised = {}, [], None, []
    net = REPO / P["network"]
    decisions_all = {}
    for k in range(int(math.ceil(H / R))):
        b, e = k * R, min((k + 1) * R, H)
        trips = [{"id": v, "from": r[0], "to": r[-1], "depart": d, "current_route": r} for v, d, r in veh if pr.equipped(v, P["compliance"]) and b <= d < e]
        if b <= P["probe"]["depart_s"] < e:
            trips.append({"id": "probe", "from": P["probe"]["from"], "to": P["probe"]["to"], "depart": float(P["probe"]["depart_s"])})
        if not trips:
            continue
        h_min = P["round_horizons_min"][min(k, len(P["round_horizons_min"]) - 1)]
        step = max(0, min(11, h_min // 5 - 1))
        src = F["pers"] if model == "persistence" else F["pred"]
        values = {node: float(src[step, F["nodes"].index(node)]) * k_ms for node in cmap}
        table = ec.build(values, "speed_mps", cmap, net, h_min, cfg, None, model, F["analysis_run_id"], corridor_free_speed=free)
        rdir = out / f"{arm}_round_{k}"
        rec = ro.optimize(net, trips, table, rdir, seed, float(R), cfg, keep_candidates=False)
        rid = f"rt_lg_s{seed}_{'pers' if model == 'persistence' else 'gwnet'}_r{k}"
        run = pv.Run(rid, kind="learned_gate_routing", analysis_run_id=F["analysis_run_id"], seed=seed, arm=arm, round=k, window_s=[b, e], protocol_id=P["protocol_id"],
                     resolved_model=model, checkpoint_sha256=P["checkpoint_sha256"] if model == "GWNet" else None, raw_prediction_hash=F["raw_prediction_hash"] if model == "GWNet" else F["persistence_prediction_hash"],
                     future_cost_hash=table["future_cost_hash"], priced_edges=table["priced_edges"], direct_edges=table["direct_edges"], derived_edges=table["derived_edges"], horizon_min=h_min,
                     config_hash=cfg["_config_hash"], mapping_hash=P["mapping_hash"], admission=rec["stats"], selected_routes_hash=rec["selected_routes_hash"], candidate_costs_hash=rec["candidate_costs_hash"])
        run.finish("done")
        for d in rec["decisions"]:
            sel = rec["selected_routes"].get(d["vehicle"])
            decisions_all[d["vehicle"]] = {"decision": d["decision"], "selected": sel, "saving": d.get("predicted_saving_s")}
            if d["vehicle"] == "probe":
                probe_route = sel
            elif d["decision"] == "REROUTE" and sel:
                new_routes[d["vehicle"]] = sel; advised.append(d["vehicle"])
        s = rec["stats"]
        rounds.append({"routing_run_id": rid, "round": k, "window_s": [b, e], "horizon_min": h_min, "future_cost_hash": table["future_cost_hash"], "priced_edges": table["priced_edges"],
                       "vehicles": s["vehicles"], "admitted": s["vehicles_admitted"], "rejected_capacity": s["rejected_by_capacity_gate"], "rejected_share": s["rejected_by_share_gate"], "decisions": s["decisions"]})
    merged = rewrite_routes(demand, out / f"demand_s{seed}_{arm}.rou.xml", new_routes)
    savings = [d["saving"] for d in decisions_all.values() if d["decision"] == "REROUTE" and d["saving"] is not None]
    info = {"routing_run_ids": [r["routing_run_id"] for r in rounds], "rounds": rounds, "routes_changed": len(new_routes), "advised_ids": advised, "routes_file": str(merged), "routes_hash": sha_file(merged),
            "mean_predicted_saving_s": round(float(np.mean(savings)), 2) if savings else 0.0, "decisions": decisions_all}
    return merged, probe_route, info


# ---------------------------------------------------------------------------
# one SUMO execution with the measured caps and teleport tracing
# ---------------------------------------------------------------------------

def run_sumo(arm: str, seed: int, routes: Path, out: Path, P: dict, probe_route: list[str] | None, schedule: dict) -> dict:
    import traci
    out.mkdir(parents=True, exist_ok=True)
    ns = argparse.Namespace(net=str(REPO / P["network"]), routes=str(routes), seed=seed, scale=1.0, horizon=P["simulation_duration_s"],
                            edgedata_period=P["edgedata_period_s"], time_to_teleport=P["time_to_teleport_s"], sumo_binary="sumo")
    cmd = pr.base_cmd(ns, out) + ["--vehroute-output", str(out / "vehroutes.xml"), "--vehroute-output.exit-times", "false"]
    t0 = time.time()
    traci.start(cmd, port=pr.free_port(), label=f"lg-{arm}-{seed}-{t0}")
    probe = P["probe"]; pid = "probe"; inserted_probe = False
    reroutes, t, applied = 0, 0, 0
    lanes = {}
    for edge in schedule:
        try:
            lanes[edge] = [f"{edge}_{i}" for i in range(traci.edge.getLaneNumber(edge))]
        except traci.TraCIException:
            lanes[edge] = []
    def apply_caps(t_now):
        nonlocal applied
        for edge, steps in schedule.items():
            cap = next((c for tf, c in reversed(steps) if tf <= t_now), steps[0][1])
            for lid in lanes.get(edge, []):
                try:
                    traci.lane.setMaxSpeed(lid, cap); applied += 1
                except traci.TraCIException:
                    pass
    apply_caps(0)
    teleports = []
    H = P["simulation_duration_s"]
    while t < H and (traci.simulation.getMinExpectedNumber() > 0 or not inserted_probe):
        traci.simulationStep()
        t = int(traci.simulation.getTime())
        if t % 300 == 0:
            apply_caps(t)
        if not inserted_probe and t >= probe["depart_s"]:
            edges = probe_route or list(traci.simulation.findRoute(probe["from"], probe["to"]).edges)
            traci.route.add("route_probe", edges)
            traci.vehicle.add(pid, "route_probe", depart="now", departLane="best", departSpeed="max")
            inserted_probe = True
        for vid in traci.simulation.getStartingTeleportIDList():
            try:
                edge = traci.vehicle.getRoadID(vid)
            except traci.TraCIException:
                edge = None
            teleports.append({"vehicle_id": vid, "sim_time_s": t, "edge": edge, "is_probe": vid == pid, "equipped": pr.equipped(vid, P["compliance"])})
        if arm != "reactive":
            continue
        for vid in traci.vehicle.getIDList():
            if not (pr.equipped(vid, P["compliance"]) or vid == pid):
                continue
            if (int(hashlib.md5(vid.encode()).hexdigest()[8:12], 16) + t) % P["reactive_period_s"] == 0:
                try:
                    traci.vehicle.rerouteTraveltime(vid, currentTravelTimes=True); reroutes += 1
                except traci.TraCIException:
                    pass
    traci.close()
    m = pr.parse_metrics(out, horizon=H)
    m.update(never_inserted_charge(routes, out / "tripinfo.xml", H))
    m["total_vehicle_hours_incl_never_inserted"] = round(m["total_vehicle_hours"] + m["never_inserted_vehicle_hours"], 4)
    m.update(concentration(out / "vehroutes.xml"))
    m["probe"] = probe_tripinfo(out / "tripinfo.xml", pid)
    m["probe"]["teleported"] = any(x["is_probe"] for x in teleports)
    m["in_simulation_reroute_calls"] = reroutes
    m["speed_caps_applied"] = applied
    m["teleport_events"] = teleports
    m["teleport_rate_per_1000_inserted"] = round(1000 * len(teleports) / m["inserted"], 3) if m.get("inserted") else None
    m["teleport_edges"] = dict(Counter(x["edge"] for x in teleports if x["edge"]))
    m["wall_s"] = round(time.time() - t0, 1)
    return m


# ---------------------------------------------------------------------------
# driver
# ---------------------------------------------------------------------------

def run_seed(seed: int, P: dict, cfg: dict, mapping: dict, root: Path) -> dict:
    from traffictwin.data import provenance as pv
    sdir = root / f"s{seed}"; sdir.mkdir(parents=True, exist_ok=True)
    demand, dinfo = demand_for_seed(P, seed, sdir)
    F = forecast_for_seed(P, seed, mapping)
    sched = speed_schedule(F, mapping, P)
    (sdir / "speed_schedule.json").write_text(json.dumps({"analysis_run_id": F["analysis_run_id"], "as_of": F["as_of"], "schedule": sched}, indent=1))
    rec = {"seed": seed, "demand": dinfo, "analysis_run_id": F["analysis_run_id"], "forecast_quality": F["quality"], "raw_prediction_hash": F["raw_prediction_hash"],
           "persistence_prediction_hash": F["persistence_prediction_hash"], "input_window_hash": F["input_window_hash"], "inference_seconds": F["inference_seconds"], "arms": {}}
    arms = list(ARMS) + (["oracle"] if P.get("with_oracle") else [])
    base_out = sdir / "baseline"
    for arm in arms:
        out = sdir / arm
        routes, probe_route, routing = demand, None, None
        if arm in PRED_ARMS:
            routes, probe_route, routing = predictive_routes(arm, seed, demand, F, mapping, sdir / "routing", P, cfg)
        elif arm == "oracle":
            from traffictwin.digital_twin.live.trip_comparison import oracle_debug_routes      # research-only arm: measured future of the paired baseline
            routes, probe_route, routing = oracle_debug_routes(f"sim_lg_s{seed}_oracle", str(REPO / P["network"]), demand, base_out, sdir / "oracle_routing", seed, P["simulation_duration_s"], P["compliance"],
                                                                {"id": "probe", "from_edge": P["probe"]["from"], "to_edge": P["probe"]["to"], "depart_s": P["probe"]["depart_s"]})
        m = run_sumo(arm, seed, routes, out, P, probe_route, sched)
        sim_id = f"sim_lg_s{seed}_{arm}"
        prov = pv.Run(sim_id, kind="learned_gate_simulation", protocol_id=P["protocol_id"], seed=seed, arm=arm, analysis_run_id=F["analysis_run_id"],
                      routing_run_ids=routing["routing_run_ids"] if routing and "routing_run_ids" in routing else ([r["routing_run_id"] for r in routing["rounds"]] if routing else []),
                      model=PRED_ARMS.get(arm), checkpoint_sha256=P["checkpoint_sha256"] if arm == "learned_predictive" else None,
                      raw_prediction_hash=F["raw_prediction_hash"] if arm == "learned_predictive" else (F["persistence_prediction_hash"] if arm == "persistence_predictive" else None),
                      dataset_hash=P["dataset_hash"], network_hash=P["network_hash"], mapping_hash=P["mapping_hash"], routing_config_hash=cfg["_config_hash"], demand_hash=dinfo["demand_hash"],
                      sumo_version=P["sumo_version"], metrics={k: v for k, v in m.items() if k not in ("teleport_events",)}, teleports=len(m["teleport_events"]), result_source="SYNTHETIC_WHAT_IF")
        prov.finish("done")
        rec["arms"][arm] = {"arm": arm, "seed": seed, "simulation_run_id": sim_id, "routing_run_ids": prov.rec["routing_run_ids"], "analysis_run_id": F["analysis_run_id"],
                            "checkpoint_sha256": prov.rec["checkpoint_sha256"], "raw_prediction_hash": prov.rec["raw_prediction_hash"],
                            "edge_cost_hashes": [r["future_cost_hash"] for r in routing["rounds"]] if routing else [], "routing": {k: v for k, v in (routing or {}).items() if k not in ("advised_ids", "decisions")} if routing else None,
                            "decisions": (routing or {}).get("decisions"), "routes_file": str(routes.relative_to(REPO)), "routes_file_hash": sha_file(routes), "demand_hash": dinfo["demand_hash"], "metrics": m, "out_dir": str(out.relative_to(REPO))}
        print(f"[lg] s{seed} {arm:<23} veh-h={m['total_vehicle_hours_incl_never_inserted']:.1f} tt={m['mean_travel_time_all']:.0f}s p95={m['p95_travel_time_s']:.0f}s arr={m['arrived']} "
              f"tel={len(m['teleport_events'])} q={m['mean_queue_veh']:.1f} {'changed=' + str(routing['routes_changed']) if routing else ''} probe={m['probe'].get('travel_time_s')} caps={m['speed_caps_applied']} ({m['wall_s']}s)", flush=True)
    # forecast quality -> routing quality, per seed
    lp, pp = rec["arms"]["learned_predictive"], rec["arms"]["persistence_predictive"]
    dl, dp = lp["decisions"] or {}, pp["decisions"] or {}
    common = [v for v in dl if v in dp and v != "probe"]
    diff = sum(1 for v in common if (dl[v]["selected"] or []) != (dp[v]["selected"] or []))
    b = rec["arms"]["baseline"]["metrics"]["total_vehicle_hours_incl_never_inserted"]
    rec["quality_vs_outcome"] = {**F["quality"], "pct_route_decisions_differ_from_persistence": round(100 * diff / len(common), 2) if common else None,
                                 "mean_predicted_saving_s_learned": lp["routing"]["mean_predicted_saving_s"], "mean_predicted_saving_s_persistence": pp["routing"]["mean_predicted_saving_s"],
                                 "reroutes_learned": lp["routing"]["routes_changed"], "reroutes_persistence": pp["routing"]["routes_changed"],
                                 "realized_saving_pct_learned_vs_baseline": round(100 * (b - lp["metrics"]["total_vehicle_hours_incl_never_inserted"]) / b, 3) if b else None,
                                 "realized_saving_pct_persistence_vs_baseline": round(100 * (b - pp["metrics"]["total_vehicle_hours_incl_never_inserted"]) / b, 3) if b else None}
    from traffictwin.digital_twin.live.trip_comparison import read_any_routes
    pops = {a: hashlib.sha256(json.dumps([(v, d) for v, d, _ in read_any_routes(REPO / x["routes_file"])]).encode()).hexdigest()[:12] for a, x in rec["arms"].items()}
    rec["population_hash_by_arm"] = pops
    rec["same_population"] = len(set(pops.values())) == 1          # identical vehicles and departures in every arm; only routes differ
    (sdir / "seed_record.json").write_text(json.dumps({k: v for k, v in rec.items()}, indent=1, default=str))
    return rec


def spearman(x: list[float], y: list[float]) -> float | None:
    if len(x) < 3:
        return None
    rx = np.argsort(np.argsort(x)); ry = np.argsort(np.argsort(y))
    d = rx - ry
    n = len(x)
    return round(float(1 - 6 * float(np.sum(d * d)) / (n * (n * n - 1))), 3)


METRICS = [("total_vehicle_hours_incl_never_inserted", True), ("total_vehicle_hours", True), ("mean_travel_time_all", True), ("mean_travel_time_s", True), ("p95_travel_time_s", True),
           ("total_waiting_s", True), ("mean_queue_veh", True), ("max_queue_veh", True), ("arrived", False), ("teleports", True), ("top_route_share", True), ("top_edge_flow_concentration", True)]
PAIRS = [("learned_predictive", "baseline"), ("learned_predictive", "reactive"), ("learned_predictive", "persistence_predictive"), ("persistence_predictive", "baseline"), ("reactive", "baseline")]


def report(P: dict, recs: list[dict], label: str) -> dict:
    per_seed = {r["seed"]: {a: {"metrics": x["metrics"]} for a, x in r["arms"].items()} for r in recs}
    pairs = {f"{a}_vs_{b}": {m: paired(per_seed, a, b, m, lib) for m, lib in METRICS} for a, b in PAIRS + ([("oracle", "baseline")] if P.get("with_oracle") else [])}
    key = P["primary_metric_key"]
    primary = pairs["learned_predictive_vs_baseline"][key]; vs_pers = pairs["learned_predictive_vs_persistence_predictive"][key]; pers_base = pairs["persistence_predictive_vs_baseline"][key]
    outcome = ("A: learned beats baseline and persistence (CI excludes zero)" if primary["label"] == "HELPED" and vs_pers["label"] == "HELPED" else
               "B: routing helps vs baseline, but the learned model shows no added value over persistence" if primary["label"] == "HELPED" else
               "D: learned routing is worse than baseline" if primary["label"] == "HURT" else "C: forecast/control benefit not established")
    tele = {a: {"count_total": sum(len(r["arms"][a]["metrics"]["teleport_events"]) for r in recs), "rate_per_1000_inserted_mean": round(float(np.mean([r["arms"][a]["metrics"]["teleport_rate_per_1000_inserted"] or 0 for r in recs])), 3),
               "probe_affected_seeds": [r["seed"] for r in recs if r["arms"][a]["metrics"]["probe"].get("teleported")],
               "equipped_share": round(float(np.mean([np.mean([e["equipped"] for e in r["arms"][a]["metrics"]["teleport_events"]]) if r["arms"][a]["metrics"]["teleport_events"] else 0 for r in recs])), 3),
               "top_edges": dict(Counter(e for r in recs for e in r["arms"][a]["metrics"]["teleport_edges"]).most_common(8))} for a in recs[0]["arms"]}
    q = [r["quality_vs_outcome"] for r in recs]
    sk = [x["skill_vs_persistence"] for x in q]; rs = [x["realized_saving_pct_learned_vs_baseline"] for x in q]; rsp = [x["realized_saving_pct_learned_vs_baseline"] - x["realized_saving_pct_persistence_vs_baseline"] for x in q]
    ok = [i for i in range(len(q)) if sk[i] is not None and rs[i] is not None]
    quality = {"per_seed": [{"seed": r["seed"], **r["quality_vs_outcome"]} for r in recs],
               "spearman_skill_vs_realized_saving_over_baseline": spearman([sk[i] for i in ok], [rs[i] for i in ok]),
               "spearman_skill_vs_realized_saving_over_persistence_arm": spearman([sk[i] for i in ok], [rsp[i] for i in ok]), "n": len(ok),
               "reading": "with n seeds this is a correlation across moments of one dataset, not a causal estimate"}
    slim = [{**r, "arms": {a: {k: v for k, v in x.items() if k != "decisions"} for a, x in r["arms"].items()}} for r in recs]   # per-vehicle decisions stay in each seed_record.json
    return {"protocol": P, "seed_set": label, "seeds": [r["seed"] for r in recs], "same_population_all_seeds": all(r["same_population"] for r in recs), "per_seed": slim, "paired": pairs,
            "primary": primary, "learned_vs_persistence": vs_pers, "persistence_vs_baseline": pers_base, "verdict": primary["label"], "outcome": outcome, "teleports": tele, "forecast_quality": quality,
            "generated_utc": datetime.now(timezone.utc).isoformat()}


def markdown(rep: dict) -> str:
    P = rep["protocol"]; pct = lambda v: "—" if v is None else f"{v:+.2f} %"
    L = [f"# Learned-model outcome gate — {P['protocol_id']} ({rep['seed_set']} seeds, n = {len(rep['seeds'])})", "",
         f"**Verdict (Graph WaveNet vs baseline, total vehicle-hours): {rep['verdict']}** — mean {pct(rep['primary'].get('mean_pct'))}, median {pct(rep['primary'].get('median_pct'))}, 95 % CI {rep['primary'].get('ci95')}, "
         f"wins/losses/ties {rep['primary'].get('wins')}/{rep['primary'].get('losses')}/{rep['primary'].get('ties')}.", "",
         f"**Outcome class:** {rep['outcome']}", "",
         f"Graph WaveNet vs persistence-predictive: {pct(rep['learned_vs_persistence'].get('mean_pct'))}, CI {rep['learned_vs_persistence'].get('ci95')}, {rep['learned_vs_persistence'].get('wins')}/{rep['learned_vs_persistence'].get('losses')}/{rep['learned_vs_persistence'].get('ties')}, **{rep['learned_vs_persistence'].get('label')}**. "
         f"Persistence-predictive vs baseline: {pct(rep['persistence_vs_baseline'].get('mean_pct'))}, CI {rep['persistence_vs_baseline'].get('ci95')}, **{rep['persistence_vs_baseline'].get('label')}**.", "",
         "## Frozen protocol", ""]
    for k in ("city_id", "network_hash", "dataset", "dataset_hash", "mapping_hash", "mapping_counts", "model", "checkpoint", "checkpoint_sha256", "held_out_skill", "routing_config_hash", "coverage_hops", "min_saving_s", "min_saving_pct",
              "demand_method", "calibration_method", "simulation_duration_s", "routing_round_s", "round_horizons_min", "compliance", "forecast_moments", "sumo_version", "dev_seeds", "final_seeds"):
        L.append(f"- {k}: `{P[k]}`")
    L += ["", "## Paired statistics (first arm relative to second; negative = fewer vehicle-hours / less time)", "", "| pair | metric | n | mean % | median % | 95 % CI | wins/losses/ties | label |", "|---|---|---|---|---|---|---|---|"]
    for pk, ms in rep["paired"].items():
        for m, st in ms.items():
            if st.get("seeds") and m in ("total_vehicle_hours_incl_never_inserted", "mean_travel_time_all", "p95_travel_time_s", "total_waiting_s", "mean_queue_veh", "arrived", "teleports", "top_edge_flow_concentration"):
                L.append(f"| {st['pair']} | {m} | {st['seeds']} | {st['mean_pct']} | {st['median_pct']} | {st['ci95']} | {st['wins']}/{st['losses']}/{st['ties']} | **{st['label']}** |")
    L += ["", "## Teleports (never hidden)", "", "| arm | total | rate / 1000 inserted | probe affected (seeds) | share equipped | top edges |", "|---|---|---|---|---|---|"]
    for a, t in rep["teleports"].items():
        L.append(f"| {a} | {t['count_total']} | {t['rate_per_1000_inserted_mean']} | {t['probe_affected_seeds'] or '—'} | {t['equipped_share']} | {', '.join(f'{e} ({n})' for e, n in list(t['top_edges'].items())[:4]) or '—'} |")
    q = rep["forecast_quality"]
    L += ["", "## Forecast quality → routing outcome, per seed", "", "| seed | moment | GWNet MAE (km/h) | persistence MAE | skill | % decisions ≠ persistence | mean predicted saving GWNet / pers (s) | reroutes GWNet / pers | realized saving vs baseline GWNet / pers (%) |", "|---|---|---|---|---|---|---|---|---|"]
    for x in q["per_seed"]:
        g = lambda k: x.get(k, "—")
        L.append(f"| {g('seed')} | {str(x.get('as_of_time') or g('as_of_index'))[:16]} | {g('forecast_MAE_kmh')} | {g('persistence_MAE_kmh')} | {g('skill_vs_persistence')} | {g('pct_route_decisions_differ_from_persistence')} | {g('mean_predicted_saving_s_learned')} / {g('mean_predicted_saving_s_persistence')} | {g('reroutes_learned')} / {g('reroutes_persistence')} | {g('realized_saving_pct_learned_vs_baseline')} / {g('realized_saving_pct_persistence_vs_baseline')} |")
    L += ["", f"Spearman(skill, realized saving vs baseline) = {q['spearman_skill_vs_realized_saving_over_baseline']}; Spearman(skill, learned − persistence realized saving) = {q['spearman_skill_vs_realized_saving_over_persistence_arm']} (n = {q['n']}). {q['reading']}.", ""]
    L += [f"Per-seed table: see report.json. Probe trip (one user trip, never the conclusion): " + json.dumps({a: [r['arms'][a]['metrics']['probe'].get('travel_time_s') for r in rep['per_seed']] for a in rep['per_seed'][0]['arms']}), ""]
    return "\n".join(L) + "\n"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--seeds", default="dev", help="'dev', 'final', or a comma list")
    p.add_argument("--with-oracle", action="store_true", help="research-only fifth arm, never in the headline")
    p.add_argument("--resume", action="store_true", help="reuse seeds whose seed_record.json already exists under the same protocol/config/checkpoint directory")
    a = p.parse_args()
    cfg = ec.load_config()
    P = protocol(cfg, a.with_oracle)
    mapping = sensor_map.find_for_dataset(P["dataset"])
    seeds = P["dev_seeds"] if a.seeds == "dev" else P["final_seeds"] if a.seeds == "final" else [int(x) for x in a.seeds.split(",")]
    label = a.seeds if a.seeds in ("dev", "final") else "custom"
    root = OUT / f"{P['protocol_id']}_{label}_cfg{cfg['_config_hash']}_ck{P['checkpoint_sha256']}"
    root.mkdir(parents=True, exist_ok=True)
    (root / "PROTOCOL.json").write_text(json.dumps(P, indent=1))
    recs = []
    for s in seeds:
        done = root / f"s{s}" / "seed_record.json"
        if a.resume and done.exists():
            recs.append(json.loads(done.read_text())); print(f"[lg] s{s} resumed from {done.relative_to(REPO)}", flush=True)
        else:
            recs.append(run_seed(s, P, cfg, mapping, root))
    rep = report(P, recs, label)
    (root / "report.json").write_text(json.dumps(rep, indent=1, default=str))
    (root / "report.md").write_text(markdown(rep))
    print(markdown(rep))
    return 0


if __name__ == "__main__":
    sys.exit(main())
