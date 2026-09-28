#!/usr/bin/env python3
"""THE VERTICAL SLICE — real traffic state → validated forecast → SUMO edge costs → route optimizer
→ V2X recommendation message → simulated latency / loss → SUMO vehicle receives it → the vehicle
actually reroutes → every reroute logged → baseline vs optimized metrics.

One SUMO execution, driven step by step through TraCI:

    every step        connected vehicles (deterministic share = penetration) send VEHICLE_STATUS
                      through the SIMULATED uplink; the traffic-management server (this process)
                      receives them after the channel's latency and keeps a per-edge current speed
    every round_s     the server runs the VALIDATED Graph WaveNet checkpoint on the real METR-LA
                      observations up to the round's moment (a fresh forward pass), keeps only the
                      detectors genuinely mapped into this scenario, builds DIRECT/DERIVED edge costs
                      with the production builder, runs the production optimizer for the connected
                      vehicles now on the road, and sends a ROUTE_RECOMMENDATION through the downlink
    on delivery       if the vehicle still exists and is still on the recommended route's start, the
                      new route is set with traci.vehicle.setRoute — the reroute happens when the
                      message ARRIVES, not when it was decided; dropped messages never reroute; late
                      ones may find the vehicle past the fork and are logged as INAPPLICABLE
    all the while     the detectors' MEASURED speeds after the moment are replayed as lane speed
                      caps on their edges, identically in every arm, so the forecast has a real future

Arms on identical demand, network, seed and caps:
    baseline        nobody reroutes, no messages
    reactive        connected vehicles reroute on the travel times observed right now (SUMO's own
                    rerouteTraveltime) every reactive_period_s — no forecast, no server
    predictive_v2x  the loop above, under a named network profile (src/pipeline/v2x/channel.PROFILES)

    python src/pipeline/v2x/closed_loop.py --city la_c4_central_wide --seeds 101 --arms baseline,predictive_v2x --profile ideal
    python src/pipeline/v2x/closed_loop.py --city la_c4_central_wide --seeds 101,102,103 --profile lat500 --penetration 0.3

Demand is SYNTHETIC WHAT-IF randomTrips on the real OSM network; the observations are real METR-LA
detector speeds; the communication is SIMULATED. Every output record says so.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import statistics
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from traffictwin.paths import REPO

from traffictwin.digital_twin.scenario_builder import scenario_dir, sumo_tools_dir      # noqa: E402
from traffictwin.optimization import edge_costs as ec
from traffictwin.digital_twin import runtime as pr
from traffictwin.optimization import route_optimizer as ro
from traffictwin.protocols.oracle_gate import never_inserted_charge, paired, sha_file, sumo_version   # noqa: E402
from traffictwin.networking.channel import PROFILES, Channel, connected

OUT = REPO / "results/v2x/closed_loop"
CONTROLLER_CFG = REPO / "src/pipeline/v2x/controller_config.json"


def controller_config() -> dict:
    c = json.loads(CONTROLLER_CFG.read_text())
    c["_hash"] = hashlib.sha256(json.dumps({k: v for k, v in c.items() if not k.startswith("_") and k != "status"}, sort_keys=True).encode()).hexdigest()[:12]
    return c
CK207 = REPO / "results/forecasting/checkpoints/GraphWaveNet/METR-LA_50_12_12/d1ffd3d52d3caacf60ebf59214673f7c/GraphWaveNet_best_val_MAE.pt"
CK207_SHA = "548e399bd53c"
MPH = 0.44704
ARMS = ("baseline", "reactive", "persistence_v2x", "predictive_v2x", "predictive_corrected_v2x", "oracle_v2x", "random_v2x",
        "oracle_div_v2x", "oracle_cap_v2x", "oracle_net_v2x", "predictive_net_v2x", "persistence_net_v2x", "random_net_v2x",
        "oracle_netfull_v2x", "oracle_full_v2x", "predictive_netfull_v2x")                    # *_full: the per-round reroute budget lifted (diagnostic)
INFO = {"persistence_v2x": "persistence", "predictive_v2x": "gwnet", "predictive_corrected_v2x": "gwnet+correction", "oracle_v2x": "oracle", "random_v2x": "random",
        "gwnet_direct_v2x": "gwnet_direct", "oracle_coverage_limited_v2x": "oracle_coverage_limited",
        "oracle_div_v2x": "oracle", "oracle_cap_v2x": "oracle", "oracle_net_v2x": "oracle", "predictive_net_v2x": "gwnet", "persistence_net_v2x": "persistence", "random_net_v2x": "random",
        "oracle_netfull_v2x": "oracle", "oracle_full_v2x": "oracle", "predictive_netfull_v2x": "gwnet"}
OPTIMIZER = {a: ("div" if "_div_" in a else "cap" if "_cap_" in a else "net" if ("_net_" in a or "_netfull_" in a) else "vehicle") for a in ARMS}   # which routing layer an arm uses
FULL_BUDGET = {a for a in ARMS if "full" in a}
ARM_WORDS = {"baseline": "nobody reroutes", "reactive": "SUMO rerouteTraveltime on current travel times (connected vehicles)", "persistence_v2x": "the production router fed by 'no change' (current detector speeds), via V2X",
             "predictive_v2x": "the production router fed by the 207-node Graph WaveNet forecast, via V2X", "predictive_corrected_v2x": "Graph WaveNet + online residual correction from V2X status messages",
             "oracle_v2x": "the production router fed by the MEASURED future edge travel times of the paired baseline run (experimental upper bound, never a product arm)",
             "random_v2x": "negative control: the Graph WaveNet forecast with sensors shuffled (same magnitude, wrong places)",
             "oracle_div_v2x": "oracle information + diverse candidates (penalty method) only", "oracle_cap_v2x": "oracle information + background load & route-capacity admission (duarouter candidates)",
             "oracle_net_v2x": "oracle information + NETWORK optimizer (diverse candidates, background load, marginal cost, route capacity)",
             "predictive_net_v2x": "Graph WaveNet + NETWORK optimizer", "persistence_net_v2x": "persistence + NETWORK optimizer", "random_net_v2x": "shuffled forecast + NETWORK optimizer (control)",
             "oracle_netfull_v2x": "oracle + NETWORK optimizer, reroute budget lifted (diagnostic)", "oracle_full_v2x": "oracle + production optimizer, reroute budget lifted (diagnostic)", "predictive_netfull_v2x": "Graph WaveNet + NETWORK optimizer, budget lifted (diagnostic)"}


def protocol(a, cfg: dict) -> dict:
    mapping_file = REPO / "results/routing/coverage_rescue" / a.city / "sensor_to_edge_207.json"
    if not mapping_file.exists():
        raise SystemExit(f"no 207-detector mapping for {a.city}; run src/pipeline/city/coverage_rescue.py --city {a.city}")
    mapping = json.loads(mapping_file.read_text())
    man = json.loads((scenario_dir(a.city) / "MANIFEST.json").read_text())
    from pipeline.forecasting import basicts_train as bt
    from pipeline.forecasting import train_eval as te
    from traffictwin.forecasting import ModelRegistry
    forecast_contract = ModelRegistry.metr_la_gwnet().public()
    if te.sha256_file(CK207, 12) != CK207_SHA:
        raise SystemExit("the verified 207-node checkpoint is not the frozen one")
    lat, jit, loss, ttl = PROFILES[a.profile]
    return {"protocol_id": "V2X_CLOSED_LOOP_v1", "city_id": a.city, "network": man["files"]["net"], "network_hash": sha_file(REPO / man["files"]["net"]),
            "mapping_file": str(mapping_file.relative_to(REPO)), "mapping_hash": sha_file(mapping_file), "mapped_detectors": mapping["mapped_GOOD"], "detectors_total": mapping["detectors_total"],
            "model": "GWNet", "model_label": "Graph WaveNet (207-node METR-LA, verified)", "checkpoint_path": str(CK207), "checkpoint_sha256": CK207_SHA,
            "forecast_contract": forecast_contract,
            "dataset": "METR-LA", "dataset_hash": te.sha256_file(bt.BTS / "datasets/METR-LA/data.dat"), "graph_hash": te.sha256_file(bt.BTS / "datasets/METR-LA/adj_mx.pkl", 8),
            "routing_config_hash": cfg["_config_hash"], "coverage_hops": cfg["edge_costs"]["coverage_hops"], "min_saving_s": cfg["decision"]["min_saving_s"], "min_saving_pct": cfg["decision"]["min_saving_pct"], "admission": cfg["admission"],
            "demand": f"SYNTHETIC_WHAT_IF randomTrips on the real OSM network, one draw per seed, scale {getattr(a, 'demand_scale', 1.0)}x, profile {getattr(a, 'demand_profile', 'uniform')} {PROFILES_DEMAND[getattr(a, 'demand_profile', 'uniform')]}",
            "demand_scale": float(getattr(a, "demand_scale", 1.0)), "demand_profile": getattr(a, "demand_profile", "uniform"), "od_rule": getattr(a, "od_rule", "any"), "od_rule_text": OD_RULES[getattr(a, "od_rule", "any")], "observations": "REAL METR-LA detector speeds (mph), replayed as lane speed caps on mapped edges in every arm",
            "communication": "SIMULATED V2X (src/pipeline/v2x/channel.py) — not radio hardware", "profile": a.profile, "profile_params": {"latency_ms": lat, "jitter_ms": jit, "loss": loss, "ttl_s": ttl},
            "penetration": a.penetration, "round_s": a.round_s, "horizon_min": a.horizon_min, "status_period_s": a.status_period_s, "reactive_period_s": 60, "simulation_duration_s": a.duration_s, "time_to_teleport_s": 300,
            "incident": [({"edge": str(x["edge"]), "t_start_s": float(x["t_start_s"]), "cap_mps": float(x["cap_mps"])} if isinstance(x, dict) else {"edge": str(x[0]), "t_start_s": float(x[1]), "cap_mps": float(x[2])}) for x in a.incident] if getattr(a, "incident", None) else [], "fuse_observed": bool(getattr(a, "fuse_observed", False)),
            "fork_t0_s": getattr(a, "fork_t0", None), "fork": "every arm is started from ONE SUMO state saved at fork_t0_s by a baseline prefix run (vehicles, positions, speeds, routes, signals, RNG); lane caps and incidents are re-applied identically after loading" if getattr(a, "fork_t0", None) else "arms start from departure (no state fork)",
            "controller": {k: v for k, v in controller_config().items() if not k.startswith("_doc")}, "controller_config_hash": controller_config()["_hash"],
            "oracle": "oracle_v2x prices every edge with the sampledSeconds-weighted measured travel time of the paired BASELINE run over the routing window (edge_costs.oracle_table) — an experimental upper bound on future information, never leaked into the baseline",
            "moment": a.moment, "moment_rule": {"rule": "as_of = test_start + 12 + (seed*97) mod (test_len-24)", "peak": "weekday 17:30 of the seed-th held-out weekday (evening rush hour)", "prepeak": "weekday 16:15 of the seed-th held-out weekday: the measured speeds fall over the next 45 min (forecastable build-up, no incident)"}[a.moment] + "; advances one dataset step per 300 s of simulation", "sumo_version": sumo_version(), "seeds": a.seeds}


# ---------------------------------------------------------------------------
# demand, observations, forecast
# ---------------------------------------------------------------------------

PROFILES_DEMAND = {                                     # (t_from_s, t_to_s, relative rate) — SYNTHETIC what-if demand shapes, always labelled
    "uniform": [(0, 1800, 1.0)],
    "peak": [(0, 600, 0.5), (600, 1500, 0.8), (1500, 2400, 1.0), (2400, 3600, 1.0)],   # normal → rising → bottleneck develops → peak: the rate reaches the CALIBRATED level (demand_scale) in phase 3; deterioration comes from demand dynamics, not from an incident
}


OD_RULES = {                                            # automatic OD screening rules — fixed here, never hand-picked pairs
    "any": "scenario default: randomTrips samples origins/destinations from every passenger edge, lane-weighted, fringe factor 5",
    "arterial": "origins and destinations restricted to MAJOR roads (OSM motorway/trunk/primary/secondary incl. links), weight = lanes × length, minimum trip distance 2000 m — demand concentrates on the corridor's arterials instead of the 12k-edge residential grid",
}


def od_weights(P: dict, out: Path) -> Path:
    """randomTrips --weights-prefix files for the `arterial` rule (edgeData format): weight = lanes × length on MAJOR edges, 0 elsewhere."""
    from traffictwin.digital_twin.sensor_map import MAJOR
    net = net_for(REPO / P["network"]); prefix = out / "od_arterial"
    rows = "\n".join(f'    <edge id="{e.getID()}" value="{e.getLaneNumber() * e.getLength():.1f}"/>' for e in net.getEdges() if (e.getType() or "") in MAJOR and e.allows("passenger"))
    body = f'<edgedata>\n  <interval begin="0" end="100000">\n{rows}\n  </interval>\n</edgedata>\n'
    for suffix in (".src.xml", ".dst.xml"):
        Path(str(prefix) + suffix).write_text(body)
    return prefix


def demand_for_seed(P: dict, seed: int, out: Path) -> tuple[Path, dict]:
    """randomTrips with the scenario's own options; `demand_scale` multiplies the base rate (period 2.0 s
    per vehicle), `demand_profile` shapes it over time by generating one randomTrips segment per phase."""
    import subprocess
    out.mkdir(parents=True, exist_ok=True)
    scale, profile, od_rule = float(P.get("demand_scale", 1.0)), P.get("demand_profile", "uniform"), P.get("od_rule", "any")
    routes = out / f"demand_s{seed}.rou.xml"
    if P.get("strict_fresh") and routes.exists():
        raise RuntimeError("Fresh execution refuses an existing demand file")
    if not routes.exists():
        man = json.loads((scenario_dir(P["city_id"]) / "MANIFEST.json").read_text())
        raw, cleaned, skip = man["process"]["randomtrips_options"], [], False
        for o in raw:
            if o in ("-n", "-o", "-r", "-b", "-e", "-p", "--seed", "--prefix") or (od_rule == "arterial" and o in ("--min-distance", "--fringe-factor", "--min-distance.fringe", "--allow-fringe.min-length")):
                skip = True; continue
            if skip:
                skip = False; continue
            cleaned.append(o)
        if od_rule == "arterial":
            cleaned += ["--weights-prefix", str(od_weights(P, out)), "--min-distance", "2000", "--fringe-factor", "1"]
        segments = []
        for i, (b, e, rate) in enumerate(PROFILES_DEMAND[profile]):
            period = 2.0 / (scale * rate)
            trips, seg = out / f"trips_s{seed}_{i}.xml", out / f"seg_s{seed}_{i}.rou.xml"
            opts = ["-n", str(REPO / P["network"]), "-o", str(trips), "-r", str(seg), "-b", str(b), "-e", str(e), "-p", f"{period:.4f}", "--seed", str(seed * 10 + i), "--prefix", f"veh{i}_"] + cleaned
            r = subprocess.run([sys.executable, str(sumo_tools_dir() / "randomTrips.py")] + opts, check=False, capture_output=True, text=True, cwd=out)
            if r.returncode != 0 or not seg.exists():
                raise RuntimeError(f"randomTrips failed: {(r.stderr or r.stdout)[-300:]}")
            segments.append(seg)
        # merge the segments into one route file, vehicles sorted by departure (SUMO requires it)
        vehs = []
        for seg in segments:
            vehs += re.findall(r"(<vehicle [^>]*depart=\"([0-9.]+)\"[^>]*>.*?</vehicle>)", seg.read_text(), flags=re.S)
        vehs.sort(key=lambda x: float(x[1]))
        head = re.search(r"<routes[^>]*>", segments[0].read_text()).group(0)
        vtypes = [vt for seg in segments for vt in re.findall(r"<vType [^>]*/>", seg.read_text())]      # randomTrips names the vType after the prefix: one per segment
        routes.write_text(head + "\n" + "\n".join(vtypes) + "\n" + "\n".join(v for v, _ in vehs) + "\n</routes>\n")
    return routes, {"demand_file": str(routes.relative_to(REPO)), "demand_hash": sha_file(routes), "vehicles": len(re.findall(r"<vehicle ", routes.read_text())), "demand_scale": scale, "demand_profile": profile, "profile_phases": PROFILES_DEMAND[profile], "od_rule": od_rule, "od_rule_text": OD_RULES[od_rule]}


from traffictwin.forecasting.routing_forecast import Forecaster, moment_for


# ---------------------------------------------------------------------------
# the traffic-management server
# ---------------------------------------------------------------------------

from traffictwin.digital_twin.network import net_for


from traffictwin.networking.observed_costs import fuse_observed


from traffictwin.optimization.controller import RoutingController


class Server(RoutingController):
    """Compatibility constructor using the frozen controller configuration."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, controller_settings=controller_config(), **kwargs)


from traffictwin.digital_twin.metrics import congestion_metrics


# ---------------------------------------------------------------------------
# applying a delivered recommendation to a SUMO vehicle
# ---------------------------------------------------------------------------

from traffictwin.digital_twin.route_application import apply_recommendation


# ---------------------------------------------------------------------------
# one SUMO execution
# ---------------------------------------------------------------------------

from traffictwin.digital_twin.state import state_content_hash, save_fork_state


def run_sumo(*args, **kwargs):
    """Compatibility entry point for the SUMO branch runner."""
    from traffictwin.digital_twin.runner import run_sumo as run
    return run(*args, controller_factory=Server, information=INFO, optimizers=OPTIMIZER, full_budget_arms=FULL_BUDGET, **kwargs)


# ---------------------------------------------------------------------------

METRICS = [("total_vehicle_hours_incl_never_inserted", True), ("mean_travel_time_all", True), ("p95_travel_time_s", True), ("total_waiting_s", True), ("mean_queue_veh", True), ("arrived", False), ("teleports", True)]


def find_reusable(arm: str, seed: int, P: dict) -> dict | None:
    """An identical arm already executed for this city, moment, seed, network, routing config and demand
    draw — baseline does not depend on the network profile or penetration, reactive only on penetration.
    The predictive arm is never reused across profiles or penetrations."""
    if not OUT.exists():
        return None
    pattern = f"{P['city_id']}_{P['moment']}_{P['profile']}_p{int(P['penetration'] * 100)}_cfg*" if arm == "predictive_v2x" else f"{P['city_id']}_{P['moment']}_*"
    for f in sorted(OUT.glob(f"{pattern}/s{seed}/{arm}/arm_result.json")):
        try:
            r = json.loads(f.read_text())
        except json.JSONDecodeError:
            continue
        if r.get("config_hash") != P["routing_config_hash"] or r.get("network_hash") != P["network_hash"] or r.get("moment") != P["moment"]:
            continue
        if arm in ("reactive", "predictive_v2x") and float(r.get("penetration", -1)) != float(P["penetration"]):
            continue
        if arm == "predictive_v2x" and r.get("profile") != P["profile"]:
            continue
        r["reused_from"] = str(f.relative_to(REPO))
        return r
    return None


def run_seed(seed: int, P: dict, cfg: dict, arms: list[str], root: Path, reuse: bool = True) -> dict:
    from traffictwin.data import provenance as pv
    sdir = root / f"s{seed}"; sdir.mkdir(parents=True, exist_ok=True)
    routes, dinfo = demand_for_seed(P, seed, sdir)
    fc = Forecaster(P, seed); caps = fc.caps(P["simulation_duration_s"])
    an_id = f"an_v2x_s{seed}"
    pv.Run(an_id, kind="v2x_analysis", protocol_id=P["protocol_id"], seed=seed, dataset="METR-LA", dataset_hash=P["dataset_hash"], graph_hash=P["graph_hash"], model="GWNet-207", checkpoint_sha256=P["checkpoint_sha256"],
           as_of_index=fc.as_of0, mapped_detectors=len(fc.good), result_source="LIVE_COMPUTATION").finish("done")
    fork = save_fork_state(seed, routes, sdir / "fork", P, caps) if P.get("fork_t0_s") else None
    rec = {"seed": seed, "analysis_run_id": an_id, "as_of_index": fc.as_of0, "demand": dinfo, "fork": {"t0_s": P.get("fork_t0_s"), "state_file": str(fork[0].relative_to(REPO)), "state_sha256": fork[1]} if fork else None, "arms": {}}
    if fork:
        print(f"[v2x] s{seed} fork state at {P['fork_t0_s']} s: {fork[1]}", flush=True)
    order = sorted(arms, key=lambda a: 0 if a == "baseline" else 1)                    # the oracle needs the baseline's measured future first
    for arm in order:
        r = find_reusable(arm, seed, P) if (reuse and not fork) else None
        done = sdir / arm / "arm_result.json"
        if r is None and reuse and fork and done.exists():                                  # a finished arm of THIS run (same fork state, same protocol): extend, don't re-simulate
            prev = json.loads(done.read_text())
            if (prev.get("fork") or {}).get("state_sha256") == fork[1]:
                r = prev; r["reused_from"] = str(done.parent.relative_to(REPO))
        if r is not None:
            rec["arms"][arm] = r
            print(f"[v2x] s{seed} {arm:<15} reused {r['reused_from']}", flush=True); continue
        base_ed = (sdir / "baseline" / "edgedata.xml") if INFO.get(arm) == "oracle" else None
        if INFO.get(arm) == "oracle" and not (base_ed and base_ed.exists()):
            raise RuntimeError("run the baseline arm in the same call so the oracle can read its measured future")
        r = run_sumo(arm, seed, routes, sdir / arm, P, cfg, fc, caps, fork, base_ed)
        pv.Run(r["simulation_run_id"], kind="v2x_simulation", protocol_id=P["protocol_id"], seed=seed, arm=arm, analysis_run_id=an_id, routing_run_ids=r["routing_run_ids"], network_hash=P["network_hash"], demand_hash=dinfo["demand_hash"],
               mapping_hash=P["mapping_hash"], profile=P["profile"], penetration=P["penetration"], sumo_version=P["sumo_version"], metrics={k: v for k, v in r["metrics"].items() if k != "teleport_events"}, network=r["network"],
               reroutes_applied=r["reroutes_applied"], result_source="SYNTHETIC_WHAT_IF").finish("done")
        rec["arms"][arm] = r
        m, n = r["metrics"], r["network"]
        print(f"[v2x] s{seed} {arm:<24} veh-h={m['total_vehicle_hours_incl_never_inserted']:.1f} tt={m['mean_travel_time_all']:.0f}s p95={m['p95_travel_time_s']:.0f}s arr={m['arrived']} tel={m['teleports']} "
              f"conn={n['connected_vehicles']}/{n['vehicles_seen']} tx={n['uplink']['messages_tx']}+{n['downlink']['messages_tx']} rx={n['uplink']['messages_rx']}+{n['downlink']['messages_rx']} PDR={n['downlink']['packet_delivery_ratio']} "
              f"lat_med={n['downlink']['latency_median_ms']} reroutes={r['reroutes_applied']} ({m['wall_s']}s)", flush=True)
    (sdir / "seed_record.json").write_text(json.dumps(rec, indent=1, default=str))
    return rec


def report(P: dict, recs: list[dict], arms: list[str]) -> dict:
    per_seed = {r["seed"]: {a: {"metrics": x["metrics"]} for a, x in r["arms"].items()} for r in recs}
    pairs = {}
    for a in arms:
        if a != "baseline" and "baseline" in arms:
            pairs[f"{a}_vs_baseline"] = {m: paired(per_seed, a, "baseline", m, lib) for m, lib in METRICS}
        if a not in ("baseline", "reactive") and "reactive" in arms:
            pairs[f"{a}_vs_reactive"] = {m: paired(per_seed, a, "reactive", m, lib) for m, lib in METRICS}
    if "predictive_v2x" in arms and "oracle_v2x" in arms:
        pairs["predictive_v2x_vs_oracle_v2x"] = {m: paired(per_seed, "predictive_v2x", "oracle_v2x", m, lib) for m, lib in METRICS}
    for a in arms:
        if a.startswith("oracle_") and a != "oracle_v2x" and "oracle_v2x" in arms:
            pairs[f"{a}_vs_oracle_v2x"] = {m: paired(per_seed, a, "oracle_v2x", m, lib) for m, lib in METRICS}
        if a.endswith("_net_v2x") and a.replace("_net", "") in arms:
            pairs[f"{a}_vs_{a.replace('_net', '')}"] = {m: paired(per_seed, a, a.replace("_net", ""), m, lib) for m, lib in METRICS}
    key = "total_vehicle_hours_incl_never_inserted"
    net = [r["arms"]["predictive_v2x"]["network"] for r in recs if "predictive_v2x" in r["arms"]]
    reroutes_by_arm = {a: sum(r["arms"][a].get("reroutes_applied", 0) for r in recs if a in r["arms"]) for a in arms}
    fork_hashes = {r["seed"]: (r.get("fork") or {}).get("state_sha256") for r in recs}
    fork_identical = all(all((x.get("fork") or {}).get("state_sha256") == fork_hashes[r["seed"]] for x in r["arms"].values()) for r in recs) if any(r.get("fork") for r in recs) else None
    agg = None
    if net:
        agg = {"connected_vehicles_mean": statistics.fmean(n["connected_vehicles"] for n in net), "reroutes_applied_total": sum(n["reroutes_applied"] for n in net),
               "recommendations_inapplicable_total": sum(n["recommendations_inapplicable"] for n in net),
               "downlink": {k: statistics.fmean(x for x in (n["downlink"][k] for n in net) if x is not None) if any(n["downlink"][k] is not None for n in net) else None
                            for k in ("messages_tx", "messages_rx", "messages_dropped", "messages_expired", "packet_delivery_ratio", "latency_median_ms", "latency_p95_ms", "latency_p99_ms")},
               "uplink": {k: statistics.fmean(x for x in (n["uplink"][k] for n in net) if x is not None) if any(n["uplink"][k] is not None for n in net) else None
                          for k in ("messages_tx", "messages_rx", "messages_dropped", "packet_delivery_ratio", "latency_median_ms", "latency_p95_ms")}}
    verdict = (pairs.get("predictive_v2x_vs_baseline") or {}).get(key, {}).get("label")
    return {"protocol": P, "seeds": [r["seed"] for r in recs], "arms": arms, "per_seed": [{**r, "arms": {a: {k: v for k, v in x.items() if k != "metrics"} | {"metrics": {k: v for k, v in x["metrics"].items() if k != "teleport_events"}} for a, x in r["arms"].items()}} for r in recs],
            "paired": pairs, "network_summary": agg, "reroutes_by_arm": reroutes_by_arm, "fork_state_identical_across_arms": fork_identical, "fork_state_hashes": fork_hashes,
            "verdict_predictive_v2x_vs_baseline": verdict, "generated_utc": datetime.now(timezone.utc).isoformat()}


def markdown(rep: dict) -> str:
    P = rep["protocol"]; L = [f"# V2X closed loop — {P['protocol_id']} · {P['city_id']} · profile `{P['profile']}` · penetration {P['penetration']} · seeds {rep['seeds']}", "",
                              f"Model {P['model_label']} (ckpt `{P['checkpoint_sha256']}`), {P['mapped_detectors']} of {P['detectors_total']} detectors mapped, routing config `{P['routing_config_hash']}`. "
                              f"{P['demand']}. {P['observations']}. {P['communication']}: latency {P['profile_params']['latency_ms']} ms ± {P['profile_params']['jitter_ms']}, loss {P['profile_params']['loss']}, TTL {P['profile_params']['ttl_s']} s.", ""]
    if rep.get("fork_state_hashes") and any(rep["fork_state_hashes"].values()):
        L += [f"Identical-state fork at {P.get('fork_t0_s')} s: state hashes {rep['fork_state_hashes']} — identical across arms: **{rep['fork_state_identical_across_arms']}**. Reroutes applied by arm: {rep['reroutes_by_arm']}.", ""]
    L += ["| pair | metric | n | mean % | median % | 95 % CI | W/L/T | label |", "|---|---|---|---|---|---|---|---|"]
    for pk, ms in rep["paired"].items():
        for m, st in ms.items():
            if st.get("seeds"):
                L.append(f"| {st['pair']} | {m} | {st['seeds']} | {st['mean_pct']} | {st['median_pct']} | {st['ci95']} | {st['wins']}/{st['losses']}/{st['ties']} | **{st['label']}** |")
    if rep["network_summary"]:
        n = rep["network_summary"]; d = n["downlink"]; u = n["uplink"]
        L += ["", f"Network (means over seeds): connected {n['connected_vehicles_mean']:.0f} vehicles · uplink TX {u['messages_tx']:.0f} RX {u['messages_rx']:.0f} PDR {u['packet_delivery_ratio']} lat med {u['latency_median_ms']} p95 {u['latency_p95_ms']} ms · "
              f"downlink TX {d['messages_tx']:.0f} RX {d['messages_rx']:.0f} dropped {d['messages_dropped']:.0f} expired {d['messages_expired']:.0f} PDR {d['packet_delivery_ratio']} lat med {d['latency_median_ms']} p95 {d['latency_p95_ms']} ms · "
              f"reroutes applied {n['reroutes_applied_total']} · inapplicable {n['recommendations_inapplicable_total']}", ""]
    for r in rep["per_seed"]:
        for a, x in r["arms"].items():
            m = x["metrics"]; L.append(f"- s{r['seed']} {a}: veh-h {m['total_vehicle_hours_incl_never_inserted']}, mean tt {m['mean_travel_time_all']:.0f} s, p95 {m['p95_travel_time_s']:.0f} s, arrived {m['arrived']}, teleports {m['teleports']}, reroutes applied {x.get('reroutes_applied', 0)}, sim `{x['simulation_run_id']}`")
    return "\n".join(L) + "\n"


def run_point(city: str, seeds: list[int], profile: str, penetration: float, moment: str = "peak", arms: tuple[str, ...] = ARMS, tag: str = "", reuse: bool = True,
              round_s: int = 300, horizon_min: int = 15, status_period_s: int = 10, duration_s: int = 2700, incident: list | None = None, fuse_observed: bool = False, fork_t0: int | None = None,
              demand_scale: float = 1.0, demand_profile: str = "uniform", od_rule: str = "any") -> dict:
    """One (profile, penetration) point of the closed loop — what the sweep calls."""
    a = argparse.Namespace(city=city, seeds=list(seeds), profile=profile, penetration=penetration, moment=moment, round_s=round_s, horizon_min=horizon_min, status_period_s=status_period_s, duration_s=duration_s, tag=tag,
                           incident=incident or [], fuse_observed=fuse_observed, fork_t0=fork_t0, demand_scale=demand_scale, demand_profile=demand_profile, od_rule=od_rule)
    cfg = ec.load_config(); P = protocol(a, cfg)
    if incident or fuse_observed or fork_t0 or demand_scale != 1.0 or demand_profile != "uniform" or od_rule != "any":
        reuse = False                                               # a different scenario or information: nothing is comparable across points
        tag = "_".join(x for x in [tag, "inc" if incident else "", "fused" if fuse_observed else "", f"fork{fork_t0}" if fork_t0 else "", f"x{demand_scale:g}" if demand_scale != 1.0 else "", demand_profile if demand_profile != "uniform" else "", od_rule if od_rule != "any" else ""] if x)
    root = OUT / f"{city}_{moment}_{profile}_p{int(penetration * 100)}_cfg{cfg['_config_hash']}{('_' + tag) if tag else ''}"; root.mkdir(parents=True, exist_ok=True)
    (root / "PROTOCOL.json").write_text(json.dumps(P, indent=1))
    recs = [run_seed(s, P, cfg, list(arms), root, reuse) for s in seeds]
    rep = report(P, recs, list(arms))
    rep["run_dir"] = str(root.relative_to(REPO))
    (root / "report.json").write_text(json.dumps(rep, indent=1, default=str)); (root / "report.md").write_text(markdown(rep))
    return rep


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--city", default="la_c4_central_wide"); p.add_argument("--seeds", default="101"); p.add_argument("--arms", default="baseline,reactive,predictive_v2x")
    p.add_argument("--profile", default="ideal", choices=sorted(PROFILES)); p.add_argument("--penetration", type=float, default=0.3)
    p.add_argument("--round-s", dest="round_s", type=int, default=300); p.add_argument("--horizon-min", dest="horizon_min", type=int, default=15); p.add_argument("--status-period-s", dest="status_period_s", type=int, default=10)
    p.add_argument("--duration-s", dest="duration_s", type=int, default=2700); p.add_argument("--tag", default="")
    p.add_argument("--moment", default="peak", choices=["rule", "peak", "prepeak"], help="scenario moment: 'peak' = held-out weekday 17:30, 'rule' = the v1 hash rule")
    p.add_argument("--incident", action="append", default=[], help="EDGE:T_START_S:CAP_MPS — a lane speed cut on that edge from t_start, identical in every arm (repeatable)")
    p.add_argument("--fuse-observed", dest="fuse_observed", action="store_true", help="predictive arm: fuse the OBSERVED status-message speeds into the forecast cost table")
    p.add_argument("--fork-t0", dest="fork_t0", type=int, default=None, help="save one SUMO state at this time from a baseline prefix and start EVERY arm from it")
    p.add_argument("--demand-scale", dest="demand_scale", type=float, default=1.0, help="multiplier on the base randomTrips rate (period 2.0 s)")
    p.add_argument("--demand-profile", dest="demand_profile", default="uniform", choices=sorted(PROFILES_DEMAND), help="time shape of the demand: uniform, or peak (normal → rising → bottleneck → peak)")
    p.add_argument("--od-rule", dest="od_rule", default="any", choices=sorted(OD_RULES), help="automatic OD screening rule (see OD_RULES)")
    p.add_argument("--no-reuse", action="store_true", help="re-run baseline/reactive even if an identical arm exists")
    a = p.parse_args(); seeds = [int(x) for x in a.seeds.split(",")]; arms = tuple(x for x in a.arms.split(",") if x in ARMS)
    inc = [(x.split(":")[0], float(x.split(":")[1]), float(x.split(":")[2])) for x in a.incident]
    rep = run_point(a.city, seeds, a.profile, a.penetration, a.moment, arms, a.tag, not a.no_reuse, a.round_s, a.horizon_min, a.status_period_s, a.duration_s, incident=inc, fuse_observed=a.fuse_observed, fork_t0=a.fork_t0,
                    demand_scale=a.demand_scale, demand_profile=a.demand_profile, od_rule=a.od_rule)
    print(markdown(rep))
    return 0


if __name__ == "__main__":
    sys.exit(main())
