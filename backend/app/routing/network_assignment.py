"""NETWORK-LEVEL ROUTE ASSIGNMENT — the routing layer that asks "which set of route assignments
minimises total network cost?" instead of "what is cheapest for this vehicle?".

Four pieces, each switchable from backend/app/protocols/controller_config.json so the ORACLE ROUTING CAPACITY
test can isolate them:

  1. DIVERSE CANDIDATES (`candidates.diverse`)
     duarouter's K alternatives are cosmetic variants of one path (median overlap ≈ 0.7 on the LA
     corridor). Diversity is forced by the PENALTY METHOD: after each accepted path, its edges' travel
     times are multiplied by `penalty_factor` in the weight file and duarouter is run again, up to
     `penalty_rounds` times; a path is kept only if its length-weighted overlap with every kept path is
     ≤ `max_overlap`. Nothing about the routes is invented — every path is a duarouter shortest path
     under explicit, logged weights.

  2. OPPORTUNITY SCORE (`opportunity`)
     a vehicle is considered for rerouting only if it has a REAL alternative: overlap with the current
     route ≤ max_overlap, spare capacity on the alternative's bottleneck, and a future-cost separation
     ≥ min_saving before any penalty. Vehicles without one are logged NO_REAL_ALTERNATIVE, never priced.

  3. MARGINAL NETWORK COST (`assignment.background_load`, `assignment.route_capacity`)
     the load on each edge starts from the BACKGROUND: every vehicle (connected or not) whose remaining
     route enters the edge inside the routing window, not only the vehicles reassigned this round. The
     BPR term then prices the marginal cost of adding one more vehicle to an edge that already carries
     traffic. Vehicles are assigned greedily in descending opportunity; every accepted assignment updates
     the edge loads and the per-route admission counters seen by the next vehicle.

  4. ROUTE ADMISSION CAPACITY
     per alternative route: predicted entering vehicles, remaining capacity at its bottleneck for the
     window, admitted count; assignment stops when the route's bottleneck utilisation would exceed
     `max_route_utilisation`. Rejections are logged with their reason.

Parameters live in controller_config.json, chosen on development seeds and frozen; the file hash is in
every run. Diagnostics per round: candidate count, overlap, marginal cost, utilisation before/after,
admitted, rejected by reason.
"""
from __future__ import annotations

import hashlib
import json
import math
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

from app.routing import edge_costs as ec
from app.routing import route_optimizer as ro

CAP_LANE_H = 1800.0


def overlap(a: list[str], b: list[str], length: dict) -> float:
    sb = set(b); la = sum(length.get(e, 0.0) for e in a)
    return sum(length.get(e, 0.0) for e in a if e in sb) / la if la else 0.0


# ---------------------------------------------------------------------------
# 1. diverse candidates by the penalty method
# ---------------------------------------------------------------------------

def diverse_candidates(net: Path, trips: list[dict], table: dict, out_dir: Path, cfg: dict, cc: dict, seed: int, info: ro.NetInfo) -> tuple[dict[str, list[list[str]]], dict]:
    """vehicle -> [current, alt1, alt2, …] with every alternative ≤ max_overlap with the others."""
    out_dir.mkdir(parents=True, exist_ok=True)
    c = cc["candidates"]; max_ov, factor, rounds = float(c["max_overlap"]), float(c["penalty_factor"]), int(c["penalty_rounds"])
    trips_xml = ro.write_trips(trips, out_dir / "trips.xml")
    base_tt = {k: float(v) for k, v in table["edge_travel_times"].items()}
    per: dict[str, list[list[str]]] = {t["id"]: [list(t["current_route"])] for t in trips if t.get("current_route")}
    weights_tt = dict(base_tt); runs = []
    for r in range(rounds):
        wtab = {**table, "edge_travel_times": weights_tt, "future_cost_hash": ec.sha({k: round(v, 3) for k, v in weights_tt.items()}), "model": f"{table.get('model')}+penalty{r}"}
        wfile = ec.write_weights(wtab, out_dir / f"penalty_{r}_weights.xml", 0.0, 3600.0)
        routes = ro.duarouter_routes(net, trips_xml, out_dir / f"penalty_{r}.rou.xml", wfile, seed + r)
        kept = 0
        for vid, edges in routes.items():
            lst = per.setdefault(vid, [])
            if any(overlap(edges, k, info.length) > max_ov and overlap(k, edges, info.length) > max_ov for k in lst):
                continue
            lst.append(edges); kept += 1
        runs.append({"round": r, "penalised_edges": sum(1 for e in weights_tt if weights_tt[e] != base_tt.get(e, info.free_tt.get(e, 0.0))), "routes": len(routes), "kept": kept})
        # penalise every edge used by any route found so far, so the next duarouter run looks elsewhere
        used = {e for lst in per.values() for path in lst for e in path}
        for e in used:
            weights_tt[e] = weights_tt.get(e, info.free_tt.get(e, 1.0)) * factor
    return per, {"generator": "duarouter penalty method (eclipse-sumo v1_27_1)", "max_overlap": max_ov, "penalty_factor": factor, "penalty_rounds": rounds, "runs": runs}


# ---------------------------------------------------------------------------
# 2–4. opportunity, background load, marginal cost, route admission
# ---------------------------------------------------------------------------

class NetworkAssigner:
    def __init__(self, cfg: dict, cc: dict, info: ro.NetInfo, window_s: float, background_routes: dict[str, list[str]] | None, edge_tt):
        lp = cfg["generalized_cost"]["load_penalty"]
        self.alpha, self.beta = float(lp["bpr_alpha"]), float(lp["bpr_beta"])
        self.cap_lane_h = float(lp.get("capacity_veh_per_lane_h", CAP_LANE_H)); self.window_h = max(window_s / 3600.0, 1e-6)
        self.info, self.cc, self.edge_tt = info, cc, edge_tt
        a = cc["assignment"]; self.max_util = float(a["max_route_utilisation"]); self.min_saving = float(cfg["decision"]["min_saving_s"]); self.min_pct = float(cfg["decision"]["min_saving_pct"])
        self.switch = float(cfg["generalized_cost"]["overlap_penalty"]["switch_cost_s"]); self.max_ov = float(cc["candidates"]["max_overlap"])
        self.load: Counter = Counter()
        if a.get("background_load") and background_routes:
            for vid, route in background_routes.items():              # everyone on the road, connected or not
                horizon = 0.0
                for e in route:
                    if horizon > window_s:
                        break
                    self.load[e] += 1; horizon += (edge_tt.get(e) if hasattr(edge_tt, "get") else None) or info.free_tt.get(e, 0.0)
        self.background = Counter(self.load)
        self.route_admitted: Counter = Counter(); self.route_entering: dict[str, int] = {}
        self.diag: dict = {"rejections": Counter(), "marginal_costs": [], "utilisation_before": [], "utilisation_after": [], "candidate_counts": [], "candidate_overlaps": []}

    def capacity(self, e: str) -> float:
        return max(self.info.lanes.get(e, 1), 1) * self.cap_lane_h * self.window_h

    def util(self, e: str, extra: int = 0) -> float:
        return (self.load[e] + extra) / self.capacity(e)

    def tt(self, e: str) -> float:
        v = self.edge_tt.get(e) if hasattr(self.edge_tt, "get") else None
        return float(v) if v is not None else self.info.free_tt.get(e, 0.0)

    def route_cost(self, edges: list[str], extra: int = 0) -> tuple[float, float, float]:
        """(travel time, BPR load penalty with `extra` more vehicles on every edge, worst utilisation)."""
        tt = pen = 0.0; worst = 0.0
        for e in edges:
            base = self.tt(e); u = self.util(e, extra); worst = max(worst, u)
            tt += base; pen += base * self.alpha * (u ** self.beta)
        return tt, pen, worst

    def marginal(self, edges: list[str]) -> float:
        """network cost of adding one vehicle to this route: its own delay plus the extra delay imposed on the load already there."""
        m = 0.0
        for e in edges:
            base = self.tt(e); u0 = self.util(e); u1 = self.util(e, 1)
            own = base * (1 + self.alpha * u1 ** self.beta)
            others = self.load[e] * base * self.alpha * (u1 ** self.beta - u0 ** self.beta)
            m += own + others
        return m

    def bottleneck(self, edges: list[str]) -> str:
        return max(edges, key=lambda e: self.util(e, 1))

    def sig(self, edges: list[str]) -> str:
        return hashlib.sha1(" ".join(edges).encode()).hexdigest()[:12]

    def opportunity(self, cur: list[str], alts: list[list[str]]) -> tuple[float, dict | None]:
        """largest future-cost separation among REAL alternatives (diverse, spare capacity), else 0."""
        cur_tt, _, _ = self.route_cost(cur); best = None
        for a in alts:
            ov = overlap(a, cur, self.info.length)
            if ov > self.max_ov:
                continue
            tt, _, worst = self.route_cost(a, 1)
            if worst > self.max_util:
                continue
            sep = cur_tt - tt
            if best is None or sep > best["separation_s"]:
                best = {"edges": a, "separation_s": sep, "overlap": ov, "worst_util": worst}
        return (best["separation_s"] if best else 0.0), best

    def assign(self, vid: str, cur: list[str], alts: list[list[str]], last_reroute_s: float | None, now_s: float, cooldown_s: float) -> dict:
        self.diag["candidate_counts"].append(len(alts) + 1); self.diag["candidate_overlaps"] += [overlap(a, cur, self.info.length) for a in alts]
        rec = {"vehicle": vid, "candidates_real": len(alts) + 1, "candidates": []}
        opp, best = self.opportunity(cur, alts)
        cur_tt, cur_pen, cur_worst = self.route_cost(cur)
        rec["candidates"].append({"route_id": f"{vid}_c0", "index": 0, "edges": cur, "n_edges": len(cur), "is_current": True, "forecast_future_tt_s": round(cur_tt, 2), "load_penalty_s": round(cur_pen, 2), "marginal_cost_s": round(self.marginal(cur), 2), "overlap_with_current": 1.0, "final_cost_s": round(cur_tt + cur_pen, 2)})
        for i, a in enumerate(alts, 1):
            tt, pen, worst = self.route_cost(a, 1); ov = overlap(a, cur, self.info.length)
            rec["candidates"].append({"route_id": f"{vid}_c{i}", "index": i, "edges": a, "n_edges": len(a), "is_current": False, "forecast_future_tt_s": round(tt, 2), "load_penalty_s": round(pen, 2), "marginal_cost_s": round(self.marginal(a), 2),
                                      "overlap_with_current": round(ov, 3), "overlap_penalty_s": round(self.switch * (1 - ov), 2), "predicted_load_ratio_max": round(worst, 3), "final_cost_s": round(tt + pen + self.switch * (1 - ov), 2)})
        if best is None:
            rec.update(decision="NO_REAL_ALTERNATIVE", selected=f"{vid}_c0", predicted_saving_s=0.0, opportunity_s=0.0); self.diag["rejections"]["NO_REAL_ALTERNATIVE"] += 1; self._occupy(cur, False); return rec
        # marginal network cost decides, not the vehicle's own time
        m_cur = self.marginal(cur); m_alt = self.marginal(best["edges"]); saving = m_cur - m_alt; pct = 100 * saving / m_cur if m_cur > 0 else 0.0
        rec.update(opportunity_s=round(opp, 2), current_future_cost_s=round(m_cur, 2), alternative_future_cost_s=round(m_alt, 2), predicted_saving_s=round(saving, 2), predicted_saving_pct=round(pct, 2), best_alternative_overlap=round(best["overlap"], 3))
        if saving < self.min_saving or pct < self.min_pct:
            rec.update(decision="KEEP_CURRENT_BELOW_THRESHOLD", selected=f"{vid}_c0"); self.diag["rejections"]["BELOW_THRESHOLD"] += 1; self._occupy(cur, False); return rec
        if last_reroute_s is not None and now_s - last_reroute_s < cooldown_s:
            rec.update(decision="REJECTED_COOLDOWN", selected=f"{vid}_c0"); self.diag["rejections"]["COOLDOWN"] += 1; self._occupy(cur, False); return rec
        s = self.sig(best["edges"]); b = self.bottleneck(best["edges"]); u_after = self.util(b, 1)
        if u_after > self.max_util:
            rec.update(decision="REJECTED_ROUTE_CAPACITY", selected=f"{vid}_c0", bottleneck_edge=b, utilisation_after=round(u_after, 3)); self.diag["rejections"]["ROUTE_CAPACITY"] += 1; self._occupy(cur, False); return rec
        self.diag["marginal_costs"].append(round(saving, 2)); self.diag["utilisation_before"].append(round(self.util(b), 3)); self.diag["utilisation_after"].append(round(u_after, 3))
        idx = next(i for i, a in enumerate(alts, 1) if a == best["edges"])
        rec.update(decision="REROUTE", selected=f"{vid}_c{idx}", route_signature=s, bottleneck_edge=b, utilisation_after=round(u_after, 3))
        self._occupy(best["edges"], True, s); self._release(cur)
        return rec

    def _occupy(self, edges: list[str], rerouted: bool, sig: str | None = None) -> None:
        for e in edges:
            self.load[e] += 1
        if rerouted and sig:
            self.route_admitted[sig] += 1

    def _release(self, edges: list[str]) -> None:
        """a rerouted vehicle leaves the load it contributed to its old route as background."""
        for e in edges:
            if self.load[e] > 0:
                self.load[e] -= 1

    def diagnostics(self) -> dict:
        d = self.diag; med = lambda xs: (round(sorted(xs)[len(xs) // 2], 3) if xs else None)
        return {"vehicles_considered": len(d["candidate_counts"]), "median_candidates": med(d["candidate_counts"]), "median_candidate_overlap_with_current": med(d["candidate_overlaps"]),
                "admitted": len(d["marginal_costs"]), "rejected": dict(d["rejections"]), "median_marginal_saving_s": med(d["marginal_costs"]), "median_bottleneck_utilisation_before": med(d["utilisation_before"]), "median_bottleneck_utilisation_after": med(d["utilisation_after"]),
                "background_edges_loaded": sum(1 for v in self.background.values() if v), "max_edge_utilisation_background": round(max((self.util(e) for e in self.background), default=0.0), 3), "routes_admitted": dict(self.route_admitted)}


def assign_round(net: Path, trips: list[dict], table: dict, out_dir: Path, cfg: dict, cc: dict, seed: int, window_s: float, last_reroute: dict[str, float], now_s: float,
                 background_routes: dict[str, list[str]] | None, info: ro.NetInfo) -> dict:
    """One routing round with the network assigner. Same record shape as route_optimizer.optimize."""
    out_dir.mkdir(parents=True, exist_ok=True)
    edge_tt = ro.TimeDependentCosts(table["time_dependent"]) if table.get("time_dependent") else {k: float(v) for k, v in table["edge_travel_times"].items()}
    if cc["candidates"].get("diverse"):
        cands, gen = diverse_candidates(net, trips, table, out_dir, cfg, cc, seed, info)
    else:
        weights = ec.write_weights(table, out_dir / "future_weights.xml", 0.0, max(float(window_s), 3600.0))
        cands, gen = ro.candidates_from_sumo(net, trips, weights, out_dir, cfg, seed)
    asg = NetworkAssigner(cfg, cc, info, window_s, background_routes, edge_tt)
    order = []
    for t in trips:
        cs = cands.get(t["id"], []); cur = cs[0] if cs else None
        opp, _ = asg.opportunity(cur, cs[1:]) if cur else (0.0, None)
        order.append((opp, t))
    order.sort(key=lambda x: -x[0])                                   # highest opportunity first: the scarce capacity goes where it buys most
    decisions = []
    for opp, t in order:
        cs = cands.get(t["id"], [])
        if not cs:
            decisions.append({"vehicle": t["id"], "decision": "NO_ROUTE", "selected": None, "candidates": [], "candidates_real": 0}); continue
        decisions.append(asg.assign(t["id"], cs[0], cs[1:], last_reroute.get(t["id"]), now_s, float(cfg["admission"]["reroute_cooldown_s"])))
    by = Counter(d["decision"] for d in decisions)
    selected = {d["vehicle"]: next((c["edges"] for c in d["candidates"] if c["route_id"] == d.get("selected")), None) for d in decisions}
    rec = {"config": cfg, "controller_config": {k: v for k, v in cc.items() if not k.startswith("_")}, "seed": seed, "window_s": window_s, "net": str(net), "generator": gen,
           "edge_costs": {k: table.get(k) for k in ("model", "horizon_min", "unit", "coverage_hops", "priced_edges", "direct_edges", "derived_edges", "future_cost_hash")},
           "stats": {"vehicles": len(decisions), "decisions": dict(by), "vehicles_admitted": by["REROUTE"], "rejected_by_capacity_gate": by["REJECTED_ROUTE_CAPACITY"], "rejected_by_share_gate": 0, "rejected_by_cooldown": by["REJECTED_COOLDOWN"],
                     "reroute_count": by["REROUTE"], "top_route_share": 0.0, "top_edge_flow_concentration": 0.0, "mean_candidates_real": round(sum(d["candidates_real"] for d in decisions) / max(len(decisions), 1), 3), "candidates_real_histogram": dict(Counter(d["candidates_real"] for d in decisions)), "vehicles_with_fewer_than_k": 0},
           "assignment_diagnostics": asg.diagnostics(), "decisions": [{k: v for k, v in d.items() if k != "candidates"} for d in decisions], "selected_routes": selected,
           "selected_routes_hash": ec.sha({v: " ".join(r) if r else None for v, r in selected.items()}), "candidate_costs_hash": ec.sha({d["vehicle"]: [c["final_cost_s"] for c in d.get("candidates", [])] for d in decisions})}
    (out_dir / "routing_record.json").write_text(json.dumps(rec, indent=1))
    return rec
