"""Server-side route decisions from forecasts and received V2X observations."""
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path
import numpy as np
from traffictwin.forecasting.routing_forecast import Forecaster
from traffictwin.digital_twin.network import net_for
from traffictwin.optimization import edge_costs as ec, route_optimizer as ro

class RoutingController:
    """Receives VEHICLE_STATUS messages, keeps the current per-edge speed picture, runs the forecast and
    the optimizer each round, and emits ROUTE_RECOMMENDATION messages."""

    def __init__(self, P: dict, seed: int, cfg: dict, fc: Forecaster, net_path: Path, out: Path, sim_id: str, mode: str = "gwnet", oracle_edgedata: Path | None = None, optimizer: str = "vehicle", *, controller_settings: dict):
        self.P, self.seed, self.cfg, self.fc, self.net_path, self.out, self.sim_id = P, seed, cfg, fc, net_path, out, sim_id
        self.mode, self.oracle_edgedata, self.optimizer = mode, oracle_edgedata, optimizer
        self.info = ro.NetInfo(net_path) if optimizer != "vehicle" else None
        from traffictwin.networking.state_correction import IncidentDetector
        self.cc = controller_settings; d = self.cc["detector"]
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

    def plan_round(self, k: int, t: float, vehicles: dict[str, tuple[str, list[str]]], background: dict[str, list[str]] | None = None) -> tuple[list[dict], dict]:
        """vehicles: connected vehicles now on the road -> (current_edge, remaining_route). Returns
        ROUTE_RECOMMENDATION payloads for REROUTE decisions and the round record."""
        from traffictwin.data import provenance as pv
        F = self.fc.predict(t)
        if self.P.get("strict_fresh"):
            round_dir = self.out / f"routing_round_{k}"
            round_dir.mkdir(exist_ok=False)
            np.savez_compressed(round_dir / "fresh_forecast.npz", prediction=F["pred"], observation=F["now"])
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
            from traffictwin.networking.state_correction import residual_correction
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
        if self.mode in ("gwnet_direct", "oracle_coverage_limited"):
            from traffictwin.optimization.coverage import intervene
            oracle = ec.oracle_table(self.oracle_edgedata, self.net_path, self.cfg, float(t), float(t + self.P["round_s"])) if self.mode == "oracle_coverage_limited" else None
            table = intervene(table, self.mode, oracle)
        trips = [{"id": v, "from": cur, "to": rem[-1], "depart": t, "current_route": rem} for v, (cur, rem) in vehicles.items() if len(rem) >= 2]
        rid = f"rt_v2x_{self.sim_id[4:]}_r{k}"
        rec = {"decisions": [], "selected_routes": {}, "stats": {"vehicles": 0, "decisions": {}}}
        if trips and self.optimizer == "vehicle":
            rec = ro.optimize(self.net_path, trips, table, self.out / f"routing_round_{k}", self.seed, float(self.P["round_s"]), self.cfg, self.last_reroute, t, keep_candidates=True)
        elif trips:
            from traffictwin.optimization.network_assignment import assign_round
            cc = json.loads(json.dumps(self.cc)); v = self.optimizer
            cc["candidates"]["diverse"] = v in ("div", "net"); cc["assignment"]["background_load"] = v in ("cap", "net"); cc["assignment"]["route_capacity"] = v in ("cap", "net")
            if v == "div":
                cc["assignment"]["max_route_utilisation"] = 1e9
            rec = assign_round(self.net_path, trips, table, self.out / f"routing_round_{k}", self.cfg, cc, self.seed, float(self.P["round_s"]), self.last_reroute, t, background if cc["assignment"]["background_load"] else None, self.info)
        msgs = []
        adm = self.cc["admission"]
        frac = 1.0 if getattr(self, "full_budget", False) else adm["max_reroute_fraction_per_round"]
        budget = max(int(adm["min_reroutes_per_round"]), int(math.ceil(frac * len(trips))))
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
                         "reason": d.get("decision_reason") or "predicted saving above threshold", "validity_s": self.P["profile_params"]["ttl_s"], "routing_run_id": rid,
                         "horizon_min": self.P["horizon_min"], "old_predicted_cost_s": d.get("current_future_cost_s"), "new_predicted_cost_s": d.get("alternative_future_cost_s"),
                         "predicted_saving_s": d.get("predicted_saving_s"), "model": self.mode, "forecast_hash": F["raw_prediction_hash"], "edge_cost_hash": table["future_cost_hash"]})
        if trips:
            round_dir = self.out / f"routing_round_{k}"
            rec["round"] = k
            rec["sim_time_s"] = t
            rec["admission_after_budget"] = {d["vehicle"]: d["decision"] for d in rec["decisions"]}
            rec["recommendation_vehicle_ids"] = [m["vehicle_id"] for m in msgs]
            rec["forecast_provenance"] = {"checkpoint_sha256": self.P["checkpoint_sha256"], "input_window_hash": F["input_window_hash"], "forecast_hash": F["raw_prediction_hash"], "inference_seconds": F["inference_seconds"]}
            (round_dir / "routing_record.json").write_text(json.dumps(rec, indent=1))
            (round_dir / "edge_cost_table.json").write_text(json.dumps(table, default=str))
        run = pv.Run(rid, kind="v2x_routing", simulation_run_id=self.sim_id, seed=self.seed, round=k, sim_time_s=t, as_of_index=F["as_of"], model=self.mode, checkpoint_sha256=self.P["checkpoint_sha256"],
                     raw_prediction_hash=F["raw_prediction_hash"], input_window_hash=F["input_window_hash"], inference_seconds=F["inference_seconds"], future_cost_hash=table["future_cost_hash"],
                     priced_edges=table["priced_edges"], direct_edges=table.get("direct_edges"), derived_edges=table.get("derived_edges"), config_hash=self.cfg["_config_hash"],
                     vehicles_considered=len(trips), decisions=rec["stats"].get("decisions"), recommendations_sent=len(msgs), result_source="LIVE_COMPUTATION")
        run.finish("done"); self.routing_run_ids.append(rid)
        by = defaultdict(int)
        for d in rec["decisions"]:
            by[d["decision"]] += 1
        r = {"routing_run_id": rid, "round": k, "sim_time_s": t, "as_of_index": F["as_of"], "checkpoint_sha256": self.P["checkpoint_sha256"], "input_window_hash": F["input_window_hash"], "raw_prediction_hash": F["raw_prediction_hash"], "future_cost_hash": table["future_cost_hash"], "priced_edges": table["priced_edges"],
             "reroute_budget": budget, "deferred_by_budget": len(deferred), "decisions_after_budget": dict(by), "correction": table.get("correction_diag"), "incidents_detected_so_far": len(self.incidents), "time_dependent": bool(table.get("time_dependent")),
             "optimizer": self.optimizer, "assignment_diagnostics": rec.get("assignment_diagnostics"), "candidate_generator": (rec.get("generator") or {}).get("generator"),
             "direct_edges": table.get("direct_edges"), "derived_edges": table.get("derived_edges"), "observed_edges_fused": table.get("observed_edges", 0), "information": self.mode, "inference_seconds": F["inference_seconds"], "vehicles_considered": len(trips), "decisions": rec["stats"].get("decisions"),
             "recommendations_sent": len(msgs), "statuses_known": len(self.status), "edges_with_current_speed": len(self.current_edge_speeds(t))}
        self.rounds.append(r)
        if self.P.get("strict_fresh"):
            r.update(input_tensor_sha256=F["input_tensor_sha256"], inference_recomputed=True, prediction_cache_hit=False)
        return msgs, r

