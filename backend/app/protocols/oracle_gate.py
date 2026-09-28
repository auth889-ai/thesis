#!/usr/bin/env python3
"""BLOCKER #3 — THE ORACLE OUTCOME GATE.

Can the routing/control system improve traffic when it is given PERFECT future information?
Three arms on identical paired scenarios, the ONLY difference being information / policy:

    A  BASELINE            static routes, no rerouting
    B  REACTIVE            traci.vehicle.rerouteTraveltime on CURRENT travel times (equipped share)
    C  ORACLE-PREDICTIVE   the MEASURED future edge travel times of the paired baseline run, per
                           routing round, pushed through the production path:
                           edge_costs.oracle_table -> route_optimizer.optimize (duarouter candidates,
                           generalized cost, threshold, capacity/share admission) -> SUMO

The oracle gets better information only. Same router, same gates, same thresholds, same demand,
same compliance, same candidate mechanism. It never assigns an optimal path directly.

Everything that defines the experiment is frozen in PROTOCOL and hashed into the report. Metrics
come from SUMO's own tripinfo / statistic / summary / vehroute outputs of THIS execution.

    python -m app.protocols.oracle_gate --seeds dev      # tuning seeds
    python -m app.protocols.oracle_gate --seeds final    # held-out gate
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import re
import statistics
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

from app.paths import REPO
sys.path.insert(0, str(REPO))

from app.routing import edge_costs as ec              # noqa: E402
from app.twin import runtime as pr     # noqa: E402
from app.routing import route_optimizer as ro        # noqa: E402
from app.protocols.chains.predeparture_arm import read_routes  # noqa: E402

OUT = REPO / "results/routing/oracle_gate"
ARMS = ("baseline", "reactive", "oracle")


def sha_file(p: Path, n: int = 12) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()[:n]


def sumo_version() -> str:
    try:
        return subprocess.run(["sumo", "--version"], capture_output=True, text=True).stdout.splitlines()[0].strip()
    except Exception as exc:                        # noqa: BLE001
        return f"unknown ({exc})"


def protocol(cfg: dict | None = None) -> dict:
    cfg = cfg or ec.load_config()
    sc = REPO / "results/routing/SCALE_CHOICE.json"
    frac = json.loads(sc.read_text()).get("scale", 0.25) if sc.exists() else 0.25
    return {
        "protocol_id": "FINAL_PROTOCOL_v1",
        "network": str(pr.DEFAULT_NET.relative_to(REPO)), "network_hash": sha_file(pr.DEFAULT_NET),
        "demand_source": str(Path(pr.DEFAULT_ROUTES).relative_to(REPO)), "demand_source_hash": sha_file(pr.DEFAULT_ROUTES),
        "demand_sample_fraction": frac,
        "demand_sampling": "each seed keeps a deterministic random subset (fraction above) of the calibrated hourly demand, identical in all three arms; SUMO --scale 1",
        "od_population": "every kept vehicle keeps its calibrated O/D, departure time and static route",
        "simulation_duration_s": 3600, "routing_round_s": 900, "edgedata_period_s": 300,
        "routing_horizon": "one routing round = 900 s of departures; the oracle table for a round is the measured edge travel time of the paired baseline over that round",
        "compliance": 0.3, "equipped_rule": "src/pipeline/routing/predictive_routing.equipped(vid, compliance): deterministic hash of the vehicle id",
        "reactive_period_s": 60, "time_to_teleport_s": 300,
        "coverage_mode": "oracle: MEASURED per-edge travel time (sampledSeconds-weighted over the round), unmeasured edges free flow; no DERIVED propagation",
        "routing_config_file": cfg["_config_file"], "routing_config_hash": cfg["_config_hash"],
        "min_saving_s": cfg["decision"]["min_saving_s"], "min_saving_pct": cfg["decision"]["min_saving_pct"],
        "admission": cfg["admission"], "candidates": cfg["candidates"], "generalized_cost": cfg["generalized_cost"],
        "sumo_version": sumo_version(),
        "dev_seeds": [101, 102, 103], "final_seeds": [201, 202, 203, 204, 205, 206, 207, 208, 209, 210],
        "probe": {"from": "33783822#0", "to": "188458229#3", "depart_s": 600, "note": "one user trip, reported separately, never the system conclusion"},
        "primary_metric": "total vehicle-hours of every vehicle loaded before the horizon: inserted vehicles to arrival or the horizon, never-inserted vehicles from their departure to the horizon",
        "primary_metric_key": "total_vehicle_hours_incl_never_inserted", "lower_is_better": True,
    }


# ---------------------------------------------------------------------------
# demand
# ---------------------------------------------------------------------------

def sample_demand(seed: int, frac: float, out: Path) -> tuple[Path, dict]:
    veh = read_routes(Path(pr.DEFAULT_ROUTES))
    rng = random.Random(seed)
    kept = [(v, d, r) for v, d, r in veh if rng.random() < frac]
    f = out / f"demand_s{seed}.rou.xml"
    _write_routes(f, kept)
    return f, {"vehicles_total": len(veh), "vehicles_kept": len(kept), "demand_hash": sha_file(f)}


def _write_routes(f: Path, veh: list[tuple[str, str, str]]) -> None:
    with open(f, "w") as fh:
        fh.write('<routes xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/routes_file.xsd">\n')
        for v, d, r in veh:
            fh.write(f'    <vehicle id="{v}" depart="{d}">\n        <route edges="{r}" />\n    </vehicle>\n')
        fh.write("</routes>\n")


# ---------------------------------------------------------------------------
# one SUMO execution
# ---------------------------------------------------------------------------

def run_sumo(arm: str, seed: int, routes: Path, out: Path, P: dict, probe_route: list[str] | None) -> dict:
    import traci
    out.mkdir(parents=True, exist_ok=True)
    ns = argparse.Namespace(net=str(pr.DEFAULT_NET), routes=str(routes), seed=seed, scale=1.0, horizon=P["simulation_duration_s"],
                            edgedata_period=P["edgedata_period_s"], time_to_teleport=P["time_to_teleport_s"], sumo_binary="sumo")
    cmd = pr.base_cmd(ns, out) + ["--vehroute-output", str(out / "vehroutes.xml"), "--vehroute-output.exit-times", "false"]
    t0 = time.time()
    traci.start(cmd, port=pr.free_port(), label=f"gate-{arm}-{seed}-{t0}")
    probe = P["probe"]; pid = "probe"; inserted_probe = False
    reroutes, t = 0, 0
    H = P["simulation_duration_s"]
    while t < H and (traci.simulation.getMinExpectedNumber() > 0 or not inserted_probe):
        traci.simulationStep()
        t = int(traci.simulation.getTime())
        if not inserted_probe and t >= probe["depart_s"]:
            edges = probe_route or list(traci.simulation.findRoute(probe["from"], probe["to"]).edges)
            traci.route.add("route_probe", edges)
            traci.vehicle.add(pid, "route_probe", depart="now", departLane="best", departSpeed="max")
            inserted_probe = True
        if arm != "reactive":
            continue
        for vid in traci.vehicle.getIDList():
            if not (pr.equipped(vid, P["compliance"]) or vid == pid):
                continue
            if (int(hashlib.md5(vid.encode()).hexdigest()[8:12], 16) + t) % P["reactive_period_s"] == 0:
                try:
                    traci.vehicle.rerouteTraveltime(vid, currentTravelTimes=True)
                    reroutes += 1
                except traci.TraCIException:
                    pass
    traci.close()
    m = pr.parse_metrics(out, horizon=H)
    m.update(never_inserted_charge(routes, out / "tripinfo.xml", H))
    m["total_vehicle_hours_incl_never_inserted"] = round(m["total_vehicle_hours"] + m["never_inserted_vehicle_hours"], 4)
    m.update(concentration(out / "vehroutes.xml"))
    m["probe"] = probe_tripinfo(out / "tripinfo.xml", pid)
    m["in_simulation_reroute_calls"] = reroutes
    m["wall_s"] = round(time.time() - t0, 1)
    return m


def never_inserted_charge(routes: Path, tripinfo: Path, H: float) -> dict:
    """Vehicles loaded with depart < H that SUMO never managed to insert (blocked origins) are not
    in tripinfo; an arm must not look better by leaving them outside. They are charged H - depart."""
    import xml.etree.ElementTree as ET
    seen = {el.get("id") for el in ET.parse(tripinfo).getroot().iter("tripinfo")}
    hours, n = 0.0, 0
    for v, d, _r in read_routes(routes):
        if float(d) < H and v not in seen:
            n += 1; hours += (H - float(d)) / 3600.0
    return {"never_inserted": n, "never_inserted_vehicle_hours": round(hours, 4)}


def probe_tripinfo(tripinfo: Path, pid: str) -> dict:
    import xml.etree.ElementTree as ET
    for el in ET.parse(tripinfo).getroot().iter("tripinfo"):
        if el.get("id") == pid:
            return {"travel_time_s": float(el.get("duration")), "route_length_m": float(el.get("routeLength")),
                    "waiting_time_s": float(el.get("waitingTime")), "finished": float(el.get("arrival", -1)) >= 0}
    return {"travel_time_s": None, "finished": False}


ROUTE_RE = re.compile(r'<vehicle id="([^"]+)"[^>]*>(.*?)</vehicle>', re.S)
EDGES_RE = re.compile(r'<route[^>]*edges="([^"]+)"')


def concentration(vehroutes: Path) -> dict:
    """Top-route share and top-edge flow concentration from the routes vehicles ACTUALLY drove
    (the last <route> of each vehicle in vehroute-output)."""
    if not vehroutes.exists():
        return {"top_route_share": None, "top_edge_flow_concentration": None}
    routes, edge_flow = Counter(), Counter()
    n = 0
    for _vid, body in ROUTE_RE.findall(vehroutes.read_text()):
        es = EDGES_RE.findall(body)
        if not es:
            continue
        n += 1
        routes[es[-1]] += 1
        for e in set(es[-1].split()):
            edge_flow[e] += 1
    return {"top_route_share": round(max(routes.values()) / n, 4) if n else None,
            "top_edge_flow_concentration": round(max(edge_flow.values()) / n, 4) if n else None,
            "vehicles_in_vehroutes": n}


# ---------------------------------------------------------------------------
# the oracle arm: measured future -> production optimizer -> routes
# ---------------------------------------------------------------------------

def oracle_routes(seed: int, demand: Path, baseline_out: Path, out: Path, P: dict, cfg: dict) -> tuple[Path, list[str] | None, dict]:
    veh = read_routes(demand)
    R, H = P["routing_round_s"], P["simulation_duration_s"]
    edgedata = baseline_out / "edgedata.xml"
    new_routes: dict[str, str] = {}
    rounds = []
    probe_route = None
    for k in range(int(math.ceil(H / R))):
        b, e = k * R, min((k + 1) * R, H)
        trips = [{"id": v, "from": r.split()[0], "to": r.split()[-1], "depart": float(d), "current_route": r.split()}
                 for v, d, r in veh if pr.equipped(v, P["compliance"]) and b <= float(d) < e]
        if b <= P["probe"]["depart_s"] < e:
            trips.append({"id": "probe", "from": P["probe"]["from"], "to": P["probe"]["to"], "depart": float(P["probe"]["depart_s"])})
        table = ec.oracle_table(edgedata, pr.DEFAULT_NET, cfg, b, e)
        rdir = out / f"round_{k}"
        rec = ro.optimize(pr.DEFAULT_NET, trips, table, rdir, seed, float(R), cfg, keep_candidates=False)
        rid = f"rt_gate_s{seed}_r{k}"
        (rdir / "routing_run.json").write_text(json.dumps({"routing_run_id": rid, "seed": seed, "round": k, "window_s": [b, e],
                                                            "future_cost_hash": table["future_cost_hash"], "priced_edges": table["priced_edges"],
                                                            "stats": rec["stats"], "config_hash": cfg["_config_hash"]}, indent=1))
        for d in rec["decisions"]:
            sel = rec["selected_routes"].get(d["vehicle"])
            if d["vehicle"] == "probe":
                probe_route = sel
            elif d["decision"] == "REROUTE" and sel:
                new_routes[d["vehicle"]] = " ".join(sel)
        s = rec["stats"]
        rounds.append({"routing_run_id": rid, "round": k, "window_s": [b, e], "future_cost_hash": table["future_cost_hash"],
                       "priced_edges": table["priced_edges"], "vehicles": s["vehicles"], "admitted": s["vehicles_admitted"],
                       "rejected_capacity": s["rejected_by_capacity_gate"], "rejected_share": s["rejected_by_share_gate"],
                       "decisions": s["decisions"], "mean_candidates_real": s["mean_candidates_real"],
                       "top_route_share_admitted": s["top_route_share"], "top_edge_flow_concentration_admitted": s["top_edge_flow_concentration"]})
    merged = out / f"demand_s{seed}_oracle.rou.xml"
    _write_routes(merged, [(v, d, new_routes.get(v, r)) for v, d, r in veh])
    return merged, probe_route, {"rounds": rounds, "routes_changed": len(new_routes), "routes_hash": sha_file(merged)}


# ---------------------------------------------------------------------------
# statistics
# ---------------------------------------------------------------------------

TCRIT = {2: 12.706, 3: 4.303, 4: 3.182, 5: 2.776, 6: 2.571, 7: 2.447, 8: 2.365, 9: 2.306, 10: 2.262, 11: 2.228, 12: 2.201, 13: 2.179}


def paired(per_seed: dict[int, dict[str, dict]], a: str, b: str, metric: str, lower_is_better: bool = True) -> dict:
    """a vs b: paired percentage change per seed ((a - b) / b * 100)."""
    per = []
    for s, arms in sorted(per_seed.items()):
        if a in arms and b in arms and arms[a]["metrics"].get(metric) is not None and arms[b]["metrics"].get(metric):
            x, y = arms[a]["metrics"][metric], arms[b]["metrics"][metric]
            per.append(round((x - y) / y * 100, 3))
    n = len(per)
    if n == 0:
        return {"pair": f"{a} vs {b}", "metric": metric, "seeds": 0, "label": "INCONCLUSIVE"}
    mean = sum(per) / n
    med = statistics.median(per)
    sd = statistics.stdev(per) if n > 1 else None
    half = TCRIT.get(n, 1.96) * sd / math.sqrt(n) if sd is not None else None
    lo, hi = (mean - half, mean + half) if half is not None else (None, None)
    better = (lambda v: v < 0) if lower_is_better else (lambda v: v > 0)
    wins = sum(1 for v in per if better(v)); ties = sum(1 for v in per if abs(v) < 1e-9); losses = n - wins - ties
    label = "INCONCLUSIVE" if half is None else ("HELPED" if (hi < 0 if lower_is_better else lo > 0) else
                                                 "HURT" if (lo > 0 if lower_is_better else hi < 0) else "INCONCLUSIVE")
    return {"pair": f"{a} vs {b}", "metric": metric, "seeds": n, "per_seed_pct": per, "mean_pct": round(mean, 2), "median_pct": round(med, 2),
            "ci95": [None if lo is None else round(lo, 2), None if hi is None else round(hi, 2)], "wins": wins, "losses": losses, "ties": ties,
            "label": label, "lower_is_better": lower_is_better}


METRICS = [("total_vehicle_hours_incl_never_inserted", True), ("total_vehicle_hours", True), ("mean_travel_time_all", True), ("mean_travel_time_s", True), ("p95_travel_time_s", True),
           ("total_waiting_s", True), ("mean_queue_veh", True), ("max_queue_veh", True), ("arrived", False), ("teleports", True)]


# ---------------------------------------------------------------------------
# driver
# ---------------------------------------------------------------------------

def run_seed(seed: int, P: dict, cfg: dict, root: Path) -> dict:
    sdir = root / f"s{seed}"; sdir.mkdir(parents=True, exist_ok=True)
    demand, dinfo = sample_demand(seed, P["demand_sample_fraction"], sdir)
    rec = {"seed": seed, "demand": dinfo, "arms": {}}
    base_out = sdir / "baseline"
    for arm in ARMS:
        out = sdir / arm
        routes, probe_route, routing = demand, None, None
        if arm == "oracle":
            routes, probe_route, routing = oracle_routes(seed, demand, base_out, sdir / "oracle_routing", P, cfg)
        m = run_sumo(arm, seed, routes, out, P, probe_route)
        rec["arms"][arm] = {"arm": arm, "seed": seed, "run_id": f"gate_{P['protocol_id']}_s{seed}_{arm}", "simulation_run_id": f"sim_gate_s{seed}_{arm}",
                            "routing_run_ids": [r["routing_run_id"] for r in routing["rounds"]] if routing else [],
                            "routing": routing, "routes_file_hash": sha_file(routes), "network_hash": P["network_hash"],
                            "demand_hash": dinfo["demand_hash"], "routing_config_hash": cfg["_config_hash"], "metrics": m, "out_dir": str(out.relative_to(REPO))}
        print(f"[gate] s{seed} {arm:<9} veh-h={m['total_vehicle_hours_incl_never_inserted']:.1f} (inserted-only {m['total_vehicle_hours']:.1f}, never inserted {m['never_inserted']}) tt={m['mean_travel_time_all']:.0f}s p95={m['p95_travel_time_s']:.0f}s "
              f"arr={m['arrived']} tel={m['teleports']} q={m['mean_queue_veh']:.1f} topedge={m['top_edge_flow_concentration']} "
              f"{'changed=' + str(routing['routes_changed']) if routing else ''} probe={m['probe'].get('travel_time_s')} ({m['wall_s']}s)", flush=True)
    # same population in every arm: the set of inserted vehicle ids from tripinfo
    loaded = {arm: [(v, d) for v, d, _r in read_routes(demand if arm != "oracle" else sdir / "oracle_routing" / f"demand_s{seed}_oracle.rou.xml")] for arm in ARMS}
    rec["same_population"] = loaded["baseline"] == loaded["reactive"] == loaded["oracle"]      # same vehicles, same departures
    rec["population_size"] = len(loaded["baseline"])
    rec["inserted_by_arm"] = {arm: rec["arms"][arm]["metrics"]["inserted"] for arm in ARMS}
    rec["never_inserted_by_arm"] = {arm: rec["arms"][arm]["metrics"]["never_inserted"] for arm in ARMS}
    (sdir / "seed_record.json").write_text(json.dumps(rec, indent=1))
    return rec


def report(P: dict, seeds_rec: list[dict], label: str) -> dict:
    per_seed = {r["seed"]: r["arms"] for r in seeds_rec}
    pairs = {}
    for a, b in (("oracle", "baseline"), ("oracle", "reactive"), ("reactive", "baseline")):
        pairs[f"{a}_vs_{b}"] = {m: paired(per_seed, a, b, m, lib) for m, lib in METRICS}
    primary = pairs["oracle_vs_baseline"][P["primary_metric_key"]]
    verdict = primary["label"]
    probe = {arm: [r["arms"][arm]["metrics"]["probe"].get("travel_time_s") for r in seeds_rec] for arm in ARMS}
    return {"protocol": P, "seed_set": label, "seeds": [r["seed"] for r in seeds_rec], "same_population_all_seeds": all(r["same_population"] for r in seeds_rec),
            "per_seed": seeds_rec, "paired": pairs, "primary": primary, "verdict": verdict, "probe_travel_time_s": probe,
            "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}


def markdown(rep: dict) -> str:
    P = rep["protocol"]
    L = [f"# Oracle outcome gate — {P['protocol_id']} ({rep['seed_set']} seeds {rep['seeds']})", "",
         f"**Verdict on the primary metric ({P['primary_metric']}; ORACLE vs BASELINE): {rep['verdict']}** — mean {rep['primary'].get('mean_pct')} %, "
         f"median {rep['primary'].get('median_pct')} %, 95 % CI {rep['primary'].get('ci95')}, wins/losses/ties {rep['primary'].get('wins')}/{rep['primary'].get('losses')}/{rep['primary'].get('ties')}.", "",
         "## Frozen protocol", ""]
    for k in ("network", "network_hash", "demand_source", "demand_source_hash", "demand_sample_fraction", "simulation_duration_s", "routing_round_s", "compliance",
              "coverage_mode", "routing_config_hash", "min_saving_s", "min_saving_pct", "sumo_version", "dev_seeds", "final_seeds"):
        L.append(f"- {k}: `{P[k]}`")
    L += [f"- admission: `{json.dumps(P['admission'])}`", f"- identical inserted population in all arms, every seed: **{rep['same_population_all_seeds']}**", "",
          "## Per seed", "", "| seed | arm | veh-h (all loaded) | veh-h (inserted) | never inserted | mean TT (all) | p95 TT | waiting s | mean/max queue | arrived | reroutes | teleports | top-route share | top-edge conc. | probe TT |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rep["per_seed"]:
        for arm in ARMS:
            m = r["arms"][arm]["metrics"]; rr = r["arms"][arm].get("routing")
            rer = rr["routes_changed"] if rr else m["in_simulation_reroute_calls"]
            L.append(f"| {r['seed']} | {arm} | {m['total_vehicle_hours_incl_never_inserted']:.1f} | {m['total_vehicle_hours']:.1f} | {m['never_inserted']} | {m['mean_travel_time_all']:.0f} | {m['p95_travel_time_s']:.0f} | {m['total_waiting_s']:.0f} | "
                     f"{m['mean_queue_veh']:.1f}/{m['max_queue_veh']:.0f} | {m['arrived']} | {rer} | {m['teleports']} | {m['top_route_share']} | {m['top_edge_flow_concentration']} | {m['probe'].get('travel_time_s')} |")
    L += ["", "## Paired statistics (percentage change per seed, first arm relative to second)", "",
          "| pair | metric | n | mean % | median % | 95 % CI | wins/losses/ties | label |", "|---|---|---|---|---|---|---|---|"]
    for pk, ms in rep["paired"].items():
        for m, st in ms.items():
            if st.get("seeds"):
                L.append(f"| {st['pair']} | {m} | {st['seeds']} | {st['mean_pct']} | {st['median_pct']} | {st['ci95']} | {st['wins']}/{st['losses']}/{st['ties']} | **{st['label']}** |")
    L += ["", "Probe trip travel time per arm (seconds, per seed; one user trip, not the system conclusion): " + json.dumps(rep["probe_travel_time_s"]), ""]
    return "\n".join(L) + "\n"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--seeds", default="dev", help="'dev', 'final', or a comma list")
    p.add_argument("--tag", default="")
    a = p.parse_args()
    cfg = ec.load_config()
    P = protocol(cfg)
    seeds = P["dev_seeds"] if a.seeds == "dev" else P["final_seeds"] if a.seeds == "final" else [int(x) for x in a.seeds.split(",")]
    label = a.seeds if a.seeds in ("dev", "final") else "custom"
    root = OUT / f"{P['protocol_id']}_{label}{('_' + a.tag) if a.tag else ''}_cfg{cfg['_config_hash']}"
    root.mkdir(parents=True, exist_ok=True)
    (root / "PROTOCOL.json").write_text(json.dumps(P, indent=1))
    recs = [run_seed(s, P, cfg, root) for s in seeds]
    rep = report(P, recs, label)
    (root / "report.json").write_text(json.dumps(rep, indent=1))
    (root / "report.md").write_text(markdown(rep))
    print(markdown(rep))
    return 0


if __name__ == "__main__":
    sys.exit(main())
