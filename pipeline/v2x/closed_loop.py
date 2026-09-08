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
    predictive_v2x  the loop above, under a named network profile (pipeline/v2x/channel.PROFILES)

    python pipeline/v2x/closed_loop.py --city la_c4_central_wide --seeds 101 --arms baseline,predictive_v2x --profile ideal
    python pipeline/v2x/closed_loop.py --city la_c4_central_wide --seeds 101,102,103 --profile lat500 --penetration 0.3

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

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "dashboard/backend"))

from pipeline.city.sumo_scenario import scenario_dir, sumo_tools_dir      # noqa: E402
from pipeline.routing import edge_costs as ec                              # noqa: E402
from pipeline.routing import predictive_routing as pr                      # noqa: E402
from pipeline.routing import route_optimizer as ro                         # noqa: E402
from pipeline.routing.oracle_gate import never_inserted_charge, paired, sha_file, sumo_version   # noqa: E402
from pipeline.v2x.channel import PROFILES, Channel, connected              # noqa: E402

OUT = REPO / "results/v2x/closed_loop"
CONTROLLER_CFG = REPO / "pipeline/v2x/controller_config.json"


def controller_config() -> dict:
    c = json.loads(CONTROLLER_CFG.read_text())
    c["_hash"] = hashlib.sha256(json.dumps({k: v for k, v in c.items() if not k.startswith("_") and k != "status"}, sort_keys=True).encode()).hexdigest()[:12]
    return c
CK207 = REPO / "results/forecasting/checkpoints/GraphWaveNet/METR-LA_50_12_12/d1ffd3d52d3caacf60ebf59214673f7c/GraphWaveNet_best_val_MAE.pt"
CK207_SHA = "548e399bd53c"
MPH = 0.44704
ARMS = ("baseline", "reactive", "persistence_v2x", "predictive_v2x", "predictive_corrected_v2x", "oracle_v2x", "random_v2x")
INFO = {"persistence_v2x": "persistence", "predictive_v2x": "gwnet", "predictive_corrected_v2x": "gwnet+correction", "oracle_v2x": "oracle", "random_v2x": "random"}
ARM_WORDS = {"baseline": "nobody reroutes", "reactive": "SUMO rerouteTraveltime on current travel times (connected vehicles)", "persistence_v2x": "the production router fed by 'no change' (current detector speeds), via V2X",
             "predictive_v2x": "the production router fed by the 207-node Graph WaveNet forecast, via V2X", "predictive_corrected_v2x": "Graph WaveNet + online residual correction from V2X status messages",
             "oracle_v2x": "the production router fed by the MEASURED future edge travel times of the paired baseline run (experimental upper bound, never a product arm)",
             "random_v2x": "negative control: the Graph WaveNet forecast with sensors shuffled (same magnitude, wrong places)"}


def protocol(a, cfg: dict) -> dict:
    mapping_file = REPO / "results/routing/coverage_rescue" / a.city / "sensor_to_edge_207.json"
    if not mapping_file.exists():
        raise SystemExit(f"no 207-detector mapping for {a.city}; run pipeline/city/coverage_rescue.py --city {a.city}")
    mapping = json.loads(mapping_file.read_text())
    man = json.loads((scenario_dir(a.city) / "MANIFEST.json").read_text())
    from pipeline.forecasting import basicts_train as bt
    from pipeline.forecasting import train_eval as te
    if te.sha256_file(CK207, 12) != CK207_SHA:
        raise SystemExit("the verified 207-node checkpoint is not the frozen one")
    lat, jit, loss, ttl = PROFILES[a.profile]
    return {"protocol_id": "V2X_CLOSED_LOOP_v1", "city_id": a.city, "network": man["files"]["net"], "network_hash": sha_file(REPO / man["files"]["net"]),
            "mapping_file": str(mapping_file.relative_to(REPO)), "mapping_hash": sha_file(mapping_file), "mapped_detectors": mapping["mapped_GOOD"], "detectors_total": mapping["detectors_total"],
            "model": "GWNet", "model_label": "Graph WaveNet (207-node METR-LA, verified)", "checkpoint_path": str(CK207), "checkpoint_sha256": CK207_SHA,
            "dataset": "METR-LA", "dataset_hash": te.sha256_file(bt.BTS / "datasets/METR-LA/data.dat"), "graph_hash": te.sha256_file(bt.BTS / "datasets/METR-LA/adj_mx.pkl", 8),
            "routing_config_hash": cfg["_config_hash"], "coverage_hops": cfg["edge_costs"]["coverage_hops"], "min_saving_s": cfg["decision"]["min_saving_s"], "min_saving_pct": cfg["decision"]["min_saving_pct"], "admission": cfg["admission"],
            "demand": "SYNTHETIC_WHAT_IF randomTrips on the real OSM network, one draw per seed, departures 0-1800 s", "observations": "REAL METR-LA detector speeds (mph), replayed as lane speed caps on mapped edges in every arm",
            "communication": "SIMULATED V2X (pipeline/v2x/channel.py) — not radio hardware", "profile": a.profile, "profile_params": {"latency_ms": lat, "jitter_ms": jit, "loss": loss, "ttl_s": ttl},
            "penetration": a.penetration, "round_s": a.round_s, "horizon_min": a.horizon_min, "status_period_s": a.status_period_s, "reactive_period_s": 60, "simulation_duration_s": a.duration_s, "time_to_teleport_s": 300,
            "incident": [{"edge": e, "t_start_s": t, "cap_mps": c} for e, t, c in a.incident] if getattr(a, "incident", None) else [], "fuse_observed": bool(getattr(a, "fuse_observed", False)),
            "fork_t0_s": getattr(a, "fork_t0", None), "fork": "every arm is started from ONE SUMO state saved at fork_t0_s by a baseline prefix run (vehicles, positions, speeds, routes, signals, RNG); lane caps and incidents are re-applied identically after loading" if getattr(a, "fork_t0", None) else "arms start from departure (no state fork)",
            "controller": {k: v for k, v in controller_config().items() if not k.startswith("_doc")}, "controller_config_hash": controller_config()["_hash"],
            "oracle": "oracle_v2x prices every edge with the sampledSeconds-weighted measured travel time of the paired BASELINE run over the routing window (edge_costs.oracle_table) — an experimental upper bound on future information, never leaked into the baseline",
            "moment": a.moment, "moment_rule": {"rule": "as_of = test_start + 12 + (seed*97) mod (test_len-24)", "peak": "weekday 17:30 of the seed-th held-out weekday (evening rush hour)", "prepeak": "weekday 16:15 of the seed-th held-out weekday: the measured speeds fall over the next 45 min (forecastable build-up, no incident)"}[a.moment] + "; advances one dataset step per 300 s of simulation", "sumo_version": sumo_version(), "seeds": a.seeds}


# ---------------------------------------------------------------------------
# demand, observations, forecast
# ---------------------------------------------------------------------------

def demand_for_seed(P: dict, seed: int, out: Path) -> tuple[Path, dict]:
    import subprocess
    out.mkdir(parents=True, exist_ok=True)
    trips, routes = out / f"trips_s{seed}.xml", out / f"demand_s{seed}.rou.xml"
    if not routes.exists():
        man = json.loads((scenario_dir(P["city_id"]) / "MANIFEST.json").read_text())
        raw, cleaned, skip = man["process"]["randomtrips_options"], [], False
        for o in raw:
            if o in ("-n", "-o", "-r", "-b", "-e", "-p", "--seed"):
                skip = True; continue
            if skip:
                skip = False; continue
            cleaned.append(o)
        opts = ["-n", str(REPO / P["network"]), "-o", str(trips), "-r", str(routes), "-b", "0", "-e", "1800", "-p", "2.0", "--seed", str(seed)] + cleaned
        r = subprocess.run([sys.executable, str(sumo_tools_dir() / "randomTrips.py")] + opts, check=False, capture_output=True, text=True, cwd=out)
        if r.returncode != 0 or not routes.exists():
            raise RuntimeError(f"randomTrips failed: {(r.stderr or r.stdout)[-300:]}")
    return routes, {"demand_file": str(routes.relative_to(REPO)), "demand_hash": sha_file(routes), "vehicles": len(re.findall(r"<vehicle ", routes.read_text()))}


def moment_for(rule: str, seed: int, T: int, test_lo: int) -> int:
    """The dataset moment the run starts from — a SCENARIO choice declared in the protocol, never read
    from outcomes. `rule`: the v1 hash rule (a random held-out moment, mostly off-peak); `peak`: the
    weekday 17:30 (METR-LA clock, 2012-03-01 00:00 = index 0) of the seed-th weekday inside the
    held-out split — the evening rush hour that the detectors actually record as congested."""
    if rule == "rule":
        return int(test_lo + 12 + (seed * 97) % ((T - test_lo) - 24))
    from datetime import datetime, timedelta
    t0 = datetime(2012, 3, 1)
    hour, minute = {"peak": (17, 30), "prepeak": (16, 15)}[rule]      # prepeak: the evening build-up is still ahead — a FORECASTABLE deterioration, no incident
    days = []
    for i in range(test_lo + 12, T - 24):
        d = t0 + timedelta(minutes=5 * i)
        if d.weekday() < 5 and d.hour == hour and d.minute == minute:
            days.append(i)
    if not days:
        raise SystemExit("no weekday 17:30 inside the held-out split")
    return days[seed % len(days)]


class Forecaster:
    """The verified 207-node Graph WaveNet on the real METR-LA series; only mapped detectors are used."""

    def __init__(self, P: dict, seed: int):
        from pipeline.forecasting import basicts_train as bt
        from pipeline.forecasting import train_eval as te
        raw, _ = bt._prepared("METR-LA")
        self.raw, self.vals = raw, np.asarray(raw[:, :, 0], dtype="float64")
        T = raw.shape[0]; lo = te.splits(T)["test"][0]
        self.as_of0 = moment_for(P["moment"], seed, T, lo)
        self.card = {"arch": "GWNet", "arch_class": "GraphWaveNet", "bts_name": "METR-LA", "checkpoint": P["checkpoint_path"]}
        mapping = json.loads((REPO / P["mapping_file"]).read_text())
        self.good = [r for r in mapping["records"] if r["quality"] == "GOOD"]
        self.cmap = {f"S{r['node_index']}": {"edges": [r["edge"]], "sensor_id": r["sensor_id"], "quality": "GOOD"} for r in self.good}
        self.free = {f"S{r['node_index']}": float(r["speed_limit_mps"]) for r in self.good}
        self.bt = bt

    def moment(self, sim_t: float) -> int:
        return min(self.raw.shape[0] - 12, self.as_of0 + int(sim_t // 300))

    def predict(self, sim_t: float) -> dict:
        import provenance as pv
        as_of = self.moment(sim_t)
        t0 = time.perf_counter(); pred = self.bt.predict(self.card, as_of); secs = time.perf_counter() - t0
        pred = np.where(np.isfinite(pred), pred, self.vals[as_of - 1][None, :])
        return {"as_of": as_of, "pred": pred, "now": self.vals[as_of - 1], "inference_seconds": round(secs, 3), "raw_prediction_hash": pv.sha_array(pred), "input_window_hash": pv.sha_array(self.raw[as_of - 12:as_of])}

    def table(self, F: dict, horizon_min: int, cfg: dict, net_path: Path, observed: dict | None = None) -> dict:
        k = max(0, min(11, horizon_min // 5 - 1))
        values = {node: float(F["pred"][k, int(node[1:])]) * MPH for node in self.cmap}
        t = ec.build(values, "speed_mps", self.cmap, net_path, horizon_min, cfg, None, "GWNet-207", None, corridor_free_speed=self.free)
        if observed:
            t = fuse_observed(t, observed, net_path, cfg)
        return t

    def tables(self, F: dict, cfg: dict, net_path: Path, horizons=(0, 15, 30, 60)) -> dict[int, dict]:
        """One production edge-cost table per horizon; horizon 0 = the detectors' current readings."""
        out = {}
        for h in horizons:
            src = F["now"] if h == 0 else F["pred"][max(0, min(11, h // 5 - 1))]
            values = {node: float(src[int(node[1:])]) * MPH for node in self.cmap}
            out[h] = ec.build(values, "speed_mps", self.cmap, net_path, h or 15, cfg, None, "GWNet-207" if h else "now", None, corridor_free_speed=self.free)
        return out

    def caps(self, duration_s: int) -> dict:
        """edge -> [(t_from_s, cap_mps)]: the measured detector speeds after the moment, every 300 s."""
        sched = {}
        for r in self.good:
            j = r["node_index"]; limit = float(r["speed_limit_mps"]); steps = []
            for k in range(int(math.ceil(duration_s / 300))):
                v = self.vals[min(self.as_of0 + k, self.vals.shape[0] - 1), j]
                steps.append((k * 300, round(max(1.0, min(limit, v * MPH)), 3) if v > 0 else limit))
            sched[r["edge"]] = steps
        return sched


# ---------------------------------------------------------------------------
# the traffic-management server
# ---------------------------------------------------------------------------

_NET_CACHE: dict = {}


def net_for(path) -> "sumolib.net.Net":
    """The parsed SUMO network, read once per process (a 15k-edge network takes seconds to parse)."""
    key = str(path)
    if key not in _NET_CACHE:
        import sumolib
        _NET_CACHE[key] = sumolib.net.readNet(key)
    return _NET_CACHE[key]


def fuse_observed(table: dict, observed: dict[str, float], net_path: Path, cfg: dict) -> dict:
    """OBSERVED current state (mean speed of the VEHICLE_STATUS messages received on an edge in the
    last minute) fused into the forecast table: an edge whose observed speed is below what the table
    assumes gets travel time = length / observed speed (bounded below by the routing config's speed
    floor). Forecast rows keep their provenance; fused rows are tagged OBSERVED so the reroute log can
    say which information moved a vehicle. Never applied in the baseline or reactive arms."""
    import sumolib
    net = net_for(net_path)
    v_min = float(cfg["edge_costs"]["speed_lower_bound_mps"])
    tt = dict(table["edge_travel_times"]); rows = dict(table["edges"]); fused = 0
    for eid, v in observed.items():
        try:
            e = net.getEdge(eid)
        except KeyError:
            continue
        v_eff = max(v_min, min(float(v), e.getSpeed()))
        cur = tt.get(eid, e.getLength() / max(e.getSpeed(), 0.1))
        new = e.getLength() / v_eff
        if new > cur * 1.05:                                        # only when observation says slower than assumed
            tt[eid] = round(new, 3); fused += 1
            rows[eid] = {**rows.get(eid, {"edge": eid, "length_m": round(e.getLength(), 2), "speed_limit_mps": round(e.getSpeed(), 3), "corridor": None, "forecast_value": None, "graph_distance": None, "decay_weight": None}),
                         "source": "OBSERVED", "observed_speed_mps": round(float(v), 3), "future_tt_s": round(new, 3), "bounded_speed_mps": round(v_eff, 3)}
    out = {**table, "edge_travel_times": tt, "edges": rows, "observed_edges": fused, "priced_edges": len(rows), "future_cost_hash": ec.sha({k: round(v, 3) for k, v in tt.items()}), "forecast_only_cost_hash": table["future_cost_hash"]}
    return out


class Server:
    """Receives VEHICLE_STATUS messages, keeps the current per-edge speed picture, runs the forecast and
    the optimizer each round, and emits ROUTE_RECOMMENDATION messages."""

    def __init__(self, P: dict, seed: int, cfg: dict, fc: Forecaster, net_path: Path, out: Path, sim_id: str, mode: str = "gwnet", oracle_edgedata: Path | None = None):
        self.P, self.seed, self.cfg, self.fc, self.net_path, self.out, self.sim_id = P, seed, cfg, fc, net_path, out, sim_id
        self.mode, self.oracle_edgedata = mode, oracle_edgedata
        from pipeline.v2x.state_correction import IncidentDetector
        self.cc = controller_config(); d = self.cc["detector"]
        self.detector = IncidentDetector(d["window_s"], d["min_vehicles"], d["min_messages"], d["ratio"])
        self.incidents: list[dict] = []
        F0 = fc.predict(0.0); t0 = fc.tables(F0, cfg, net_path, (0,))[0]
        self.expected: dict[str, float] = {e: r["bounded_speed_mps"] for e, r in t0["edges"].items() if r.get("bounded_speed_mps")}
        self.status: dict[str, dict] = {}                 # vehicle -> last received status
        self.edge_obs: dict[str, list] = defaultdict(list)
        self.last_reroute: dict[str, float] = {}
        self.rounds: list[dict] = []
        self.routing_run_ids: list[str] = []

    def receive(self, env: dict, t: float) -> None:
        m = env["payload"]; self.status[m["vehicle_id"]] = {**m, "received_s": t, "latency_ms": env["latency_ms"]}
        self.edge_obs[m["edge"]].append((t, m["speed_mps"]))
        exp = self.expected.get(m["edge"])                # an expectation exists only where the base forecast prices the edge (DIRECT / DERIVED)
        if exp:
            self.detector.ingest(t, m["edge"], m["vehicle_id"], m["speed_mps"], exp); self._dirty = True

    def detect(self, t: float) -> None:
        """Run the detector once per simulation step (not once per message)."""
        if not getattr(self, "_dirty", False):
            return
        self._dirty = False
        true_onsets = {i["edge"]: float(i["t_start_s"]) for i in (self.P.get("incident") or [])}
        for inc in self.detector.detect(t, true_onsets):
            inc["sim_time_s"] = t; self.incidents.append(inc)

    def current_edge_speeds(self, t: float, window_s: float = 60.0) -> dict:
        return {e: statistics.fmean(s for ts, s in obs if t - ts <= window_s) for e, obs in self.edge_obs.items() if any(t - ts <= window_s for ts, _ in obs)}

    def plan_round(self, k: int, t: float, vehicles: dict[str, tuple[str, list[str]]]) -> tuple[list[dict], dict]:
        """vehicles: connected vehicles now on the road -> (current_edge, remaining_route). Returns
        ROUTE_RECOMMENDATION payloads for REROUTE decisions and the round record."""
        import provenance as pv
        F = self.fc.predict(t)
        observed = self.current_edge_speeds(t) if (self.P.get("fuse_observed") or self.mode == "gwnet+correction") else None
        if self.mode == "oracle":
            table = ec.oracle_table(self.oracle_edgedata, self.net_path, self.cfg, float(t), float(t + self.P["round_s"]))
            table.setdefault("future_cost_hash", ec.sha({k: round(v, 3) for k, v in table["edge_travel_times"].items()}))
        elif self.mode == "persistence":
            table = self.fc.table({**F, "pred": np.repeat(F["now"][None, :], 12, axis=0)}, self.P["horizon_min"], self.cfg, self.net_path, None)
        elif self.mode == "random":
            rng = np.random.RandomState(self.seed * 1000 + k); cols = [int(n[1:]) for n in self.fc.cmap]; perm = rng.permutation(len(cols))
            pred = F["pred"].copy(); pred[:, cols] = F["pred"][:, [cols[i] for i in perm]]
            table = self.fc.table({**F, "pred": pred}, self.P["horizon_min"], self.cfg, self.net_path, None)
        elif self.mode == "gwnet+correction":
            from pipeline.v2x.state_correction import residual_correction
            net = net_for(self.net_path)
            base = self.fc.tables(F, self.cfg, self.net_path, tuple(self.cc["horizons_min"]))
            self.expected = {e: r["bounded_speed_mps"] for e, r in base[0]["edges"].items() if r.get("bounded_speed_mps")}
            cc = self.cc["correction"]
            corrected, diag = residual_correction(base, observed or {}, net, self.cfg, cc["tau_min"], cc["upstream_hops"], cc["hop_decay"], cc["min_rel_residual"], cc.get("only_priced", True))
            table = {**corrected[self.P["horizon_min"]], "time_dependent": {h: corrected[h]["edge_travel_times"] for h in corrected} if self.cc["time_dependent_costing"] else None, "correction_diag": diag}
        else:
            if self.cc["time_dependent_costing"]:
                base = self.fc.tables(F, self.cfg, self.net_path, tuple(self.cc["horizons_min"]))
                table = {**base[self.P["horizon_min"]], "time_dependent": {h: base[h]["edge_travel_times"] for h in base}}
            else:
                table = self.fc.table(F, self.P["horizon_min"], self.cfg, self.net_path, observed)
        trips = [{"id": v, "from": cur, "to": rem[-1], "depart": t, "current_route": rem} for v, (cur, rem) in vehicles.items() if len(rem) >= 2]
        rid = f"rt_v2x_{self.sim_id[4:]}_r{k}"
        rec = {"decisions": [], "selected_routes": {}, "stats": {"vehicles": 0, "decisions": {}}}
        if trips:
            rec = ro.optimize(self.net_path, trips, table, self.out / f"routing_round_{k}", self.seed, float(self.P["round_s"]), self.cfg, self.last_reroute, t, keep_candidates=False)
        msgs = []
        adm = self.cc["admission"]
        budget = max(int(adm["min_reroutes_per_round"]), int(math.ceil(adm["max_reroute_fraction_per_round"] * len(trips))))
        reroutes = sorted([d for d in rec["decisions"] if d["decision"] == "REROUTE"], key=lambda d: -(d.get("predicted_saving_s") or 0))
        deferred = reroutes[budget:]; reroutes = reroutes[:budget]
        for d in deferred:
            d["decision"] = "DEFERRED_BUDGET"; self.last_reroute.pop(d["vehicle"], None)
        for i, d in enumerate(reroutes):
            new = rec["selected_routes"].get(d["vehicle"]); cur, rem = vehicles[d["vehicle"]]
            if not new or new == rem:
                continue
            self.last_reroute[d["vehicle"]] = t
            msgs.append({"type": "ROUTE_RECOMMENDATION", "from": "TMS", "to": d["vehicle"], "vehicle_id": d["vehicle"], "created_s": t, "send_at_s": t + i * float(adm["stagger_s"]), "route": new, "old_route": rem,
                         "reason": d.get("decision_reason") or "predicted saving above threshold", "validity_s": PROFILES[self.P["profile"]][3], "routing_run_id": rid,
                         "horizon_min": self.P["horizon_min"], "old_predicted_cost_s": d.get("current_future_cost_s"), "new_predicted_cost_s": d.get("alternative_future_cost_s"),
                         "predicted_saving_s": d.get("predicted_saving_s"), "model": self.mode, "forecast_hash": F["raw_prediction_hash"], "edge_cost_hash": table["future_cost_hash"]})
        run = pv.Run(rid, kind="v2x_routing", simulation_run_id=self.sim_id, seed=self.seed, round=k, sim_time_s=t, as_of_index=F["as_of"], model=self.mode, checkpoint_sha256=self.P["checkpoint_sha256"],
                     raw_prediction_hash=F["raw_prediction_hash"], input_window_hash=F["input_window_hash"], inference_seconds=F["inference_seconds"], future_cost_hash=table["future_cost_hash"],
                     priced_edges=table["priced_edges"], direct_edges=table.get("direct_edges"), derived_edges=table.get("derived_edges"), config_hash=self.cfg["_config_hash"],
                     vehicles_considered=len(trips), decisions=rec["stats"].get("decisions"), recommendations_sent=len(msgs), result_source="LIVE_COMPUTATION")
        run.finish("done"); self.routing_run_ids.append(rid)
        by = defaultdict(int)
        for d in rec["decisions"]:
            by[d["decision"]] += 1
        r = {"routing_run_id": rid, "round": k, "sim_time_s": t, "as_of_index": F["as_of"], "raw_prediction_hash": F["raw_prediction_hash"], "future_cost_hash": table["future_cost_hash"], "priced_edges": table["priced_edges"],
             "reroute_budget": budget, "deferred_by_budget": len(deferred), "decisions_after_budget": dict(by), "correction": table.get("correction_diag"), "incidents_detected_so_far": len(self.incidents), "time_dependent": bool(table.get("time_dependent")),
             "direct_edges": table.get("direct_edges"), "derived_edges": table.get("derived_edges"), "observed_edges_fused": table.get("observed_edges", 0), "information": self.mode, "inference_seconds": F["inference_seconds"], "vehicles_considered": len(trips), "decisions": rec["stats"].get("decisions"),
             "recommendations_sent": len(msgs), "statuses_known": len(self.status), "edges_with_current_speed": len(self.current_edge_speeds(t))}
        self.rounds.append(r)
        return msgs, r


# ---------------------------------------------------------------------------
# applying a delivered recommendation to a SUMO vehicle
# ---------------------------------------------------------------------------

def apply_recommendation(traci, env: dict, t: float) -> dict:
    """A ROUTE_RECOMMENDATION has just ARRIVED at the vehicle (after the channel's latency). Apply it
    only if the vehicle still exists and is still on an edge of the recommended route; otherwise it
    is logged as inapplicable. Nothing is applied for dropped messages because they never arrive."""
    m = env["payload"]; vid = m["vehicle_id"]
    entry = {"vehicle_id": vid, "sim_time_s": t, "message_id": env["msg_id"], "created_s": m["created_s"], "latency_ms": env["latency_ms"],
             "routing_run_id": m.get("routing_run_id"), "forecast_hash": m.get("forecast_hash"), "edge_cost_hash": m.get("edge_cost_hash"), "model": m.get("model"), "horizon_min": m.get("horizon_min"),
             "reason": m.get("reason"), "old_predicted_cost_s": m.get("old_predicted_cost_s"), "new_predicted_cost_s": m.get("new_predicted_cost_s"), "predicted_saving_s": m.get("predicted_saving_s")}
    try:
        if vid not in traci.vehicle.getIDList():
            entry["outcome"] = "VEHICLE_GONE"; return entry
        cur = traci.vehicle.getRoadID(vid)
        if cur.startswith(":"):
            entry.update(outcome="DEFERRED_ON_JUNCTION", current_edge=cur); return entry      # SUMO refuses route changes mid-junction: retry next step
        new = list(m["route"])
        if cur not in new:
            entry.update(outcome="INAPPLICABLE_PAST_FORK", current_edge=cur); return entry
        tail = new[new.index(cur):]
        old = list(traci.vehicle.getRoute(vid))[traci.vehicle.getRouteIndex(vid):]
        traci.vehicle.setRoute(vid, tail)
        entry.update(outcome="APPLIED", current_edge=cur, old_route=old, new_route=tail, affected_edges=sorted(set(tail) ^ set(old)))
    except traci.TraCIException as ex:
        entry["outcome"] = f"TRACI_ERROR: {ex}"
    return entry


# ---------------------------------------------------------------------------
# one SUMO execution
# ---------------------------------------------------------------------------

def state_content_hash(path: Path) -> str:
    """SHA-256 of a SUMO state file's CONTENT: the <!-- generated on … --> header and the
    <configuration> block (file paths, timestamps) are skipped, so two identical simulation states
    saved at different times or under different directories hash the same."""
    txt = path.read_text()
    i = txt.find("<snapshot")                       # everything before it is SUMO's commented-out configuration echo (paths, port, timestamp)
    body = txt[i:] if i >= 0 else txt
    return hashlib.sha256(body.encode()).hexdigest()[:12]


def save_fork_state(seed: int, routes: Path, out: Path, P: dict, caps: dict) -> tuple[Path, str]:
    """The baseline prefix: run from departure to fork_t0_s with the caps (and any incident already
    started) applied, save ONE SUMO state including pending vehicles and the RNG, hash it."""
    import traci
    out.mkdir(parents=True, exist_ok=True)
    t_fork = int(P["fork_t0_s"]); state = out / f"fork_state_s{seed}_t{t_fork}.xml"
    if state.exists():
        return state, state_content_hash(state)
    ns = argparse.Namespace(net=str(REPO / P["network"]), routes=str(routes), seed=seed, scale=1.0, horizon=P["simulation_duration_s"], edgedata_period=300, time_to_teleport=P["time_to_teleport_s"], sumo_binary="sumo")
    cmd = pr.base_cmd(ns, out) + ["--route-steps", "0", "--save-state.rng", "true"]
    traci.start(cmd, port=pr.free_port(), label=f"prefix-{seed}-{time.time()}")
    lanes = {e: [f"{e}_{i}" for i in range(traci.edge.getLaneNumber(e))] for e in caps if e in traci.edge.getIDList()}
    def apply(t_now):
        for edge, steps in caps.items():
            cap = next((c for tf, c in reversed(steps) if tf <= t_now), steps[0][1])
            for inc in (P.get("incident") or []):
                if inc["edge"] == edge and t_now >= inc["t_start_s"]:
                    cap = min(cap, float(inc["cap_mps"]))
            for lid in lanes.get(edge, []):
                traci.lane.setMaxSpeed(lid, cap)
        for inc in (P.get("incident") or []):
            if t_now >= inc["t_start_s"] and inc["edge"] not in caps:
                for lid in [f"{inc['edge']}_{i}" for i in range(traci.edge.getLaneNumber(inc["edge"]))]:
                    traci.lane.setMaxSpeed(lid, float(inc["cap_mps"]))
    apply(0); t = 0
    while t < t_fork:
        traci.simulationStep(); t = int(traci.simulation.getTime())
        if t % 300 == 0 or any(t == int(i["t_start_s"]) for i in (P.get("incident") or [])):
            apply(t)
    traci.simulation.saveState(str(state))
    traci.close()
    return state, state_content_hash(state)


def run_sumo(arm: str, seed: int, routes: Path, out: Path, P: dict, cfg: dict, fc: Forecaster, caps: dict, fork: tuple[Path, str] | None = None, oracle_edgedata: Path | None = None) -> dict:
    import traci
    out.mkdir(parents=True, exist_ok=True)
    net_path = REPO / P["network"]
    ns = argparse.Namespace(net=str(net_path), routes=str(routes), seed=seed, scale=1.0, horizon=P["simulation_duration_s"], edgedata_period=300, time_to_teleport=P["time_to_teleport_s"], sumo_binary="sumo")
    cmd = pr.base_cmd(ns, out) + ["--vehroute-output", str(out / "vehroutes.xml"), "--route-steps", "0"]
    t_begin = 0
    if fork:
        state, state_sha = fork; t_begin = int(P["fork_t0_s"])
        i = cmd.index("--route-files"); cmd = cmd[:i] + cmd[i + 2:]                     # the state carries every vehicle, pending ones included
        cmd += ["--load-state", str(state), "--begin", str(t_begin)]
    sim_id = f"sim_v2x_s{seed}_{arm}_{P['profile']}_p{int(P['penetration'] * 100)}"
    t0 = time.time()
    traci.start(cmd, port=pr.free_port(), label=f"{sim_id}-{t0}")
    lanes = {}
    for edge in caps:
        try:
            lanes[edge] = [f"{edge}_{i}" for i in range(traci.edge.getLaneNumber(edge))]
        except traci.TraCIException:
            lanes[edge] = []
    def apply_caps(t_now):
        for edge, steps in caps.items():
            cap = next((c for tf, c in reversed(steps) if tf <= t_now), steps[0][1])
            for inc in (P.get("incident") or []):
                if inc["edge"] == edge and t_now >= inc["t_start_s"]:
                    cap = min(cap, float(inc["cap_mps"]))
            for lid in lanes.get(edge, []):
                try:
                    traci.lane.setMaxSpeed(lid, cap)
                except traci.TraCIException:
                    pass
    incidents = [dict(i) for i in (P.get("incident") or [])]; incident_log = []
    def apply_incidents(t_now):
        for inc in incidents:
            if inc.get("applied") or t_now < inc["t_start_s"]:
                continue
            n_l = 0
            for lid in [f"{inc['edge']}_{i}" for i in range(traci.edge.getLaneNumber(inc["edge"]))]:
                try:
                    traci.lane.setMaxSpeed(lid, float(inc["cap_mps"])); n_l += 1
                except traci.TraCIException:
                    pass
            inc["applied"] = True; incident_log.append({"edge": inc["edge"], "t_start_s": t_now, "cap_mps": inc["cap_mps"], "lanes": n_l})
    apply_caps(t_begin); apply_incidents(t_begin)                                      # after a state load the lane caps are NOT in the state: re-applied identically in every arm
    up = Channel.from_profile("uplink", P["profile"], seed); down = Channel.from_profile("downlink", P["profile"], seed)
    server = Server(P, seed, cfg, fc, net_path, out, sim_id, INFO[arm], oracle_edgedata) if arm in INFO else None
    reroute_log, teleports, applied, inapplicable, reactive_calls = [], [], 0, 0, 0
    pending_msgs: list[dict] = []; snapshots: list[dict] = []
    conn_cache: dict[str, bool] = {}
    is_conn = lambda v: conn_cache.setdefault(v, connected(v, P["penetration"], seed))
    H, t, k = P["simulation_duration_s"], t_begin, 0
    next_round = (t_begin // P["round_s"] + 1) * P["round_s"]
    while t < H and traci.simulation.getMinExpectedNumber() > 0:
        traci.simulationStep(); t = int(traci.simulation.getTime())
        if t % 300 == 0:
            apply_caps(t)
        if incidents:
            apply_incidents(t)
        for vid in traci.simulation.getStartingTeleportIDList():
            teleports.append({"vehicle_id": vid, "sim_time_s": t, "connected": is_conn(vid)})
        if arm == "baseline":
            if t >= next_round:                                   # snapshot of the connected vehicles for the offline decision replay
                snap = {}
                for vid in traci.vehicle.getIDList():
                    if not is_conn(vid):
                        continue
                    try:
                        edge = traci.vehicle.getRoadID(vid)
                        if edge.startswith(":"):
                            continue
                        route = list(traci.vehicle.getRoute(vid)); idx = traci.vehicle.getRouteIndex(vid)
                        if 0 <= idx < len(route) - 2:
                            snap[vid] = [route[idx], route[idx:]]
                    except traci.TraCIException:
                        pass
                snapshots.append({"round": k, "sim_time_s": t, "vehicles": snap}); k += 1; next_round += P["round_s"]
            continue
        if arm == "oracle_v2x" and oracle_edgedata is None:
            raise RuntimeError("oracle_v2x needs the paired baseline run's edgedata.xml")
        ids = [v for v in traci.vehicle.getIDList() if is_conn(v)]
        if arm == "reactive":
            for vid in ids:
                if (int(hashlib.md5(vid.encode()).hexdigest()[8:12], 16) + t) % P["reactive_period_s"] == 0:
                    try:
                        traci.vehicle.rerouteTraveltime(vid, currentTravelTimes=True); reactive_calls += 1
                    except traci.TraCIException:
                        pass
            continue
        # ---- predictive_v2x: uplink status messages
        for vid in ids:
            if (int(hashlib.md5(vid.encode()).hexdigest()[8:12], 16) + t) % P["status_period_s"] == 0:
                try:
                    edge = traci.vehicle.getRoadID(vid)
                    if edge.startswith(":"):
                        continue
                    up.send(t, {"type": "VEHICLE_STATUS", "from": vid, "to": "TMS", "vehicle_id": vid, "t": t, "edge": edge, "lane_pos_m": round(traci.vehicle.getLanePosition(vid), 1),
                                "speed_mps": round(traci.vehicle.getSpeed(vid), 2), "angle_deg": round(traci.vehicle.getAngle(vid), 1), "route_index": traci.vehicle.getRouteIndex(vid)})
                except traci.TraCIException:
                    pass
        for env in up.deliver(t):
            server.receive(env, t)
        server.detect(t)
        # ---- the round: forecast -> costs -> optimizer -> recommendations
        if t >= next_round:
            vehicles = {}
            for vid in ids:
                try:
                    edge = traci.vehicle.getRoadID(vid)
                    if edge.startswith(":"):
                        continue
                    route = list(traci.vehicle.getRoute(vid)); idx = traci.vehicle.getRouteIndex(vid)
                    if idx < 0 or idx >= len(route) - 2:
                        continue
                    vehicles[vid] = (route[idx], route[idx:])
                except traci.TraCIException:
                    pass
            msgs, rrec = server.plan_round(k, t, vehicles)
            pending_msgs.extend(msgs)
            print(f"      round {k} t={t}s as_of={rrec['as_of_index']} priced={rrec['priced_edges']} considered={rrec['vehicles_considered']} decisions={rrec['decisions']} sent={len(msgs)} statuses={rrec['statuses_known']}", flush=True)
            k += 1; next_round += P["round_s"]
        # ---- staggered sending: a recommendation leaves the server at its send_at_s, not all at once
        due_now = [m for m in pending_msgs if m.get("send_at_s", m["created_s"]) <= t]
        for m in due_now:
            down.send(t, m); pending_msgs.remove(m)
        # ---- downlink delivery: the reroute happens when the message arrives
        for env in down.deliver(t):
            entry = apply_recommendation(traci, env, t)
            if entry["outcome"] == "DEFERRED_ON_JUNCTION":                    # the message stays with the vehicle; applied at the next step off the junction
                env["deliver_at_s"] = t + 1; env["status"] = "QUEUED"; down.queue.append(env); continue
            if entry["outcome"] == "APPLIED":
                applied += 1
            else:
                inapplicable += 1
            reroute_log.append(entry)
    up.expire_all(t); down.expire_all(t)
    traci.close()
    m = pr.parse_metrics(out, horizon=H)
    m.update(never_inserted_charge(routes, out / "tripinfo.xml", H))
    m["total_vehicle_hours_incl_never_inserted"] = round(m["total_vehicle_hours"] + m["never_inserted_vehicle_hours"], 4)
    m["teleports"] = len(teleports); m["teleport_events"] = teleports
    m["reactive_reroute_calls"] = reactive_calls
    m["incidents_applied"] = incident_log
    m["wall_s"] = round(time.time() - t0, 1)
    first_applied = next((e["sim_time_s"] for e in reroute_log if e["outcome"] == "APPLIED"), None)
    inc_t = min((float(i["t_start_s"]) for i in (P.get("incident") or [])), default=None)
    net_metrics = {"uplink": up.metrics(H), "downlink": down.metrics(H), "connected_vehicles": sum(1 for v in conn_cache.values() if v), "vehicles_seen": len(conn_cache), "penetration_configured": P["penetration"],
                   "recommendations_delivered": sum(1 for e in reroute_log), "reroutes_applied": applied, "recommendations_inapplicable": inapplicable,
                   "incidents_detected": (server.incidents if server else []), "incident_detection_delay_s": (server.incidents[0].get("detection_delay_s") if server and server.incidents else None),
                   "lead_time": {"incident_onset_s": inc_t, "first_reroute_applied_s": first_applied, "first_reroute_after_onset_s": (first_applied - inc_t) if (inc_t is not None and first_applied is not None and first_applied >= inc_t) else None,
                                 "reroutes_before_onset": sum(1 for e in reroute_log if e["outcome"] == "APPLIED" and inc_t is not None and e["sim_time_s"] < inc_t)}}
    if snapshots:
        (out / "round_snapshots.json").write_text(json.dumps({"seed": seed, "as_of0": fc.as_of0, "round_s": P["round_s"], "snapshots": snapshots}, indent=0))
    (out / "reroute_log.jsonl").write_text("".join(json.dumps(e) + "\n" for e in reroute_log))
    (out / "messages_downlink.jsonl").write_text("".join(json.dumps({k: v for k, v in e.items() if k != "payload"} | {"vehicle_id": e["payload"].get("vehicle_id")}) + "\n" for e in down.log))
    (out / "network_metrics.json").write_text(json.dumps(net_metrics, indent=1))
    res = {"simulation_run_id": sim_id, "arm": arm, "seed": seed, "profile": P["profile"], "penetration": P["penetration"], "moment": P["moment"], "config_hash": P["routing_config_hash"], "network_hash": P["network_hash"],
           "fork": {"t0_s": P.get("fork_t0_s"), "state_file": str(fork[0].relative_to(REPO)), "state_sha256": fork[1]} if fork else None, "information": INFO.get(arm, arm),
           "metrics": m, "network": net_metrics, "rounds": server.rounds if server else [], "routing_run_ids": server.routing_run_ids if server else [], "reroute_log_file": str((out / "reroute_log.jsonl").relative_to(REPO)),
           "reroutes_applied": applied, "out_dir": str(out.relative_to(REPO))}
    (out / "arm_result.json").write_text(json.dumps(res, indent=1, default=str))
    return res


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
    import provenance as pv
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
        if r is not None:
            rec["arms"][arm] = r
            print(f"[v2x] s{seed} {arm:<15} reused {r['reused_from']}", flush=True); continue
        base_ed = (sdir / "baseline" / "edgedata.xml") if arm == "oracle_v2x" else None
        if arm == "oracle_v2x" and not (base_ed and base_ed.exists()):
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
              round_s: int = 300, horizon_min: int = 15, status_period_s: int = 10, duration_s: int = 2700, incident: list | None = None, fuse_observed: bool = False, fork_t0: int | None = None) -> dict:
    """One (profile, penetration) point of the closed loop — what the sweep calls."""
    a = argparse.Namespace(city=city, seeds=list(seeds), profile=profile, penetration=penetration, moment=moment, round_s=round_s, horizon_min=horizon_min, status_period_s=status_period_s, duration_s=duration_s, tag=tag,
                           incident=incident or [], fuse_observed=fuse_observed, fork_t0=fork_t0)
    cfg = ec.load_config(); P = protocol(a, cfg)
    if incident or fuse_observed or fork_t0:
        reuse = False                                               # an incident, fusion or a fork changes the scenario / the information: nothing is comparable across points
        tag = "_".join(x for x in [tag, "inc" if incident else "", "fused" if fuse_observed else "", f"fork{fork_t0}" if fork_t0 else ""] if x)
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
    p.add_argument("--no-reuse", action="store_true", help="re-run baseline/reactive even if an identical arm exists")
    a = p.parse_args(); seeds = [int(x) for x in a.seeds.split(",")]; arms = tuple(x for x in a.arms.split(",") if x in ARMS)
    inc = [(x.split(":")[0], float(x.split(":")[1]), float(x.split(":")[2])) for x in a.incident]
    rep = run_point(a.city, seeds, a.profile, a.penetration, a.moment, arms, a.tag, not a.no_reuse, a.round_s, a.horizon_min, a.status_period_s, a.duration_s, incident=inc, fuse_observed=a.fuse_observed, fork_t0=a.fork_t0)
    print(markdown(rep))
    return 0


if __name__ == "__main__":
    sys.exit(main())
