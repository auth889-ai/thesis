#!/usr/bin/env python3
"""FORECAST EDGE COSTS -> MULTIPLE SUMO ROUTE CANDIDATES -> CAPACITY-AWARE ADMISSION.

TrafficTwin does not search paths. For every trip it asks the pinned SUMO `duarouter` for
alternatives on the forecast weight file (run 0: exact weights = the best path; runs 1..K-1:
`--weights.random-factor` with distinct seeds, SUMO's documented diversification mechanism), keeps
the distinct edge sequences, adds the vehicle's current route as candidate 0, and then only
EVALUATES and ADMITS among those routes:

    final_cost_s = forecast_future_tt_s + load_penalty_s + overlap_penalty_s

    forecast_future_tt_s  sum of the priced future edge travel times (unpriced edges: free flow)
    load_penalty_s        BPR volume-delay on the vehicles this optimizer has already admitted
    overlap_penalty_s     switch cost x (1 - length fraction shared with the current route)

A vehicle is advised to change only when the predicted saving clears the configured thresholds,
and it is admitted only when the alternative's edges stay under the load ratio and the alternative
has not already absorbed the configured share of this round. Every term, every threshold and every
decision is in the returned record. All coefficients: src/traffictwin/optimization/routing_config.json.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

from traffictwin.paths import REPO

from traffictwin.optimization.edge_costs import load_config, sha

VEH_RE = re.compile(r'<vehicle id="([^"]+)"[^>]*>\s*<route[^>]*edges="([^"]+)"', re.S)


# ---------------------------------------------------------------------------
# network geometry needed for costing (read once per network)
# ---------------------------------------------------------------------------

class NetInfo:
    def __init__(self, net_path: Path):
        import sumolib
        self.path = Path(net_path)
        self.net = sumolib.net.readNet(str(net_path))
        self.length, self.free_tt, self.lanes = {}, {}, {}
        for e in self.net.getEdges():
            self.length[e.getID()] = float(e.getLength())
            self.free_tt[e.getID()] = float(e.getLength()) / max(float(e.getSpeed() or 13.9), 0.1)
            self.lanes[e.getID()] = int(e.getLaneNumber())


# ---------------------------------------------------------------------------
# candidates from SUMO
# ---------------------------------------------------------------------------

def duarouter_routes(net: Path, trips_xml: Path, out: Path, weights: Path | None, seed: int,
                     random_factor: float | None = None) -> dict[str, list[str]]:
    """One official duarouter call for all trips -> vehicle id -> edge list."""
    cmd = ["duarouter", "--net-file", str(net), "--route-files", str(trips_xml), "--output-file", str(out),
           "--ignore-errors", "--no-warnings", "--no-step-log", "--seed", str(seed), "--routing-threads", "4"]
    if weights is not None:
        cmd += ["--weight-files", str(weights), "--weight-attribute", "traveltime", "--weights.expand", "true"]
    if random_factor and random_factor > 1.0:
        cmd += ["--weights.random-factor", str(random_factor)]
    subprocess.run(cmd, check=True, capture_output=True)
    return {v: r.split() for v, r in VEH_RE.findall(out.read_text())} if out.exists() else {}


def write_trips(trips: list[dict], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("<routes>\n" + "".join(
        f'  <trip id="{t["id"]}" depart="{float(t.get("depart", 0))}" from="{t["from"]}" to="{t["to"]}"/>\n' for t in trips)
        + "</routes>\n")
    return path


def candidates_from_sumo(net: Path, trips: list[dict], weights: Path | None, out_dir: Path, cfg: dict, seed: int) -> tuple[dict[str, list[list[str]]], dict]:
    """vehicle id -> distinct candidate edge lists from duarouter. Candidate 0 is the current route
    (the trip's own, or the free-flow shortest path from duarouter when the trip has none)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    k = int(cfg["candidates"]["k_alternatives"])
    rf = float(cfg["candidates"]["weights_random_factor"])
    trips_xml = write_trips(trips, out_dir / "trips.xml")
    runs = []
    need_static = [t for t in trips if not t.get("current_route")]
    static = duarouter_routes(net, trips_xml, out_dir / "static.rou.xml", None, seed) if need_static else {}
    runs.append({"run": "static", "weights": None, "random_factor": None, "seed": seed, "routes": len(static)})
    per: dict[str, list[list[str]]] = {}
    for t in trips:
        cur = list(t["current_route"]) if t.get("current_route") else static.get(t["id"])
        per[t["id"]] = [cur] if cur else []
    for i in range(k):
        r = duarouter_routes(net, trips_xml, out_dir / f"alt_{i}.rou.xml", weights, seed + i, None if i == 0 else rf)
        runs.append({"run": f"alt_{i}", "weights": str(weights) if weights else None, "random_factor": None if i == 0 else rf, "seed": seed + i, "routes": len(r)})
        for vid, edges in r.items():
            lst = per.setdefault(vid, [])
            if edges not in lst:
                lst.append(edges)
    return per, {"generator": "duarouter (eclipse-sumo v1_27_1): run 0 exact forecast weights, runs 1..K-1 --weights.random-factor",
                 "k_requested": k, "random_factor": rf, "runs": runs}


# ---------------------------------------------------------------------------
# costing and decision
# ---------------------------------------------------------------------------

class TimeDependentCosts:
    """Edge travel times that depend on WHEN the vehicle reaches the edge: one table per forecast
    horizon (minutes ahead of now), linearly interpolated at the edge's expected entry time. Behaves
    like a plain {edge: tt} mapping at horizon 0 for code that only knows one table."""

    def __init__(self, tables: dict[int, dict[str, float]]):
        self.h = sorted(int(k) for k in tables)
        self.t = {int(k): {e: float(v) for e, v in tables[k].items()} for k in tables}
        if not self.h:
            raise ValueError("no horizon tables")

    def at(self, edge: str, minutes_ahead: float, free_tt: float) -> float | None:
        """travel time of `edge` when entered `minutes_ahead` minutes from now, or None if unpriced."""
        m = max(self.h[0], min(self.h[-1], float(minutes_ahead)))
        lo = max(k for k in self.h if k <= m); hi = min(k for k in self.h if k >= m)
        a, b = self.t[lo].get(edge), self.t[hi].get(edge)
        if a is None and b is None:
            return None
        a = free_tt if a is None else a; b = free_tt if b is None else b
        return a if hi == lo else a + (b - a) * (m - lo) / (hi - lo)

    # ---- mapping-like access at "now" (horizon 0 table), used by the load penalty and callers that expect a dict
    def get(self, edge, default=None):
        return self.t[self.h[0]].get(edge, default)

    def __contains__(self, edge):
        return any(edge in self.t[k] for k in self.h)

    def __getitem__(self, edge):
        return self.t[self.h[0]][edge]

    def items(self):
        return self.t[self.h[0]].items()

    def __len__(self):
        return len(self.t[self.h[0]])


def route_terms(edges: list[str], edge_tt, info: NetInfo, depart_offset_s: float = 0.0) -> dict:
    """Route cost. With a plain table every edge is priced at one horizon. With TimeDependentCosts
    the walk accumulates travel time, so each edge is priced at the horizon the vehicle is expected
    to reach it (offset + time spent on the edges before it); one refinement pass corrects the entry
    times with the priced times of the previous pass."""
    td = isinstance(edge_tt, TimeDependentCosts)
    passes = 2 if td else 1
    entry_tts = None
    for _ in range(passes):
        fut = base = dist = priced_len = 0.0; clock = float(depart_offset_s); this_pass = []
        for i, e in enumerate(edges):
            ft = info.free_tt.get(e, 0.0)
            base += ft
            dist += info.length.get(e, 0.0)
            if td:
                minutes = (clock if entry_tts is None else entry_tts[i]) / 60.0
                v = edge_tt.at(e, minutes, ft)
                tt = ft if v is None else v
                priced = v is not None
            else:
                priced = e in edge_tt
                tt = edge_tt[e] if priced else ft
            this_pass.append(clock)
            fut += tt; clock += tt
            if priced:
                priced_len += info.length.get(e, 0.0)
        entry_tts = this_pass
    return {"base_tt_s": round(base, 2), "forecast_future_tt_s": round(fut, 2), "distance_m": round(dist, 1),
            "priced_length_fraction": round(priced_len / dist, 4) if dist else 0.0, "time_dependent": td}


def overlap_fraction(edges: list[str], current: list[str], info: NetInfo) -> float:
    if not current:
        return 0.0
    cur = set(current)
    shared = sum(info.length.get(e, 0.0) for e in edges if e in cur)
    tot = sum(info.length.get(e, 0.0) for e in current)
    return round(shared / tot, 4) if tot else 0.0


class Admission:
    """Loads and shares accumulated over one decision round (the thin TrafficTwin layer)."""

    def __init__(self, cfg: dict, info: NetInfo, window_s: float, n_round: int):
        lp = cfg["generalized_cost"]["load_penalty"]
        self.alpha, self.beta = float(lp["bpr_alpha"]), float(lp["bpr_beta"])
        self.cap_lane_h = float(lp["capacity_veh_per_lane_h"])
        self.window_h = max(float(window_s) / 3600.0, 1e-6)
        self.max_ratio = float(cfg["admission"]["max_edge_load_ratio"])
        self.max_share = float(cfg["admission"]["max_share_per_alternative"])
        self.share_min_n = int(cfg["admission"].get("share_gate_min_vehicles", 1))
        self.cooldown = float(cfg["admission"]["reroute_cooldown_s"])
        self.info, self.n_round = info, max(int(n_round), 1)
        self.load: Counter = Counter()          # edge -> vehicles assigned this round
        self.route_share: Counter = Counter()   # route signature -> vehicles admitted to it
        self.edge_flow_rerouted: Counter = Counter()

    def capacity(self, e: str) -> float:
        return max(self.info.lanes.get(e, 1), 1) * self.cap_lane_h * self.window_h

    def load_ratio(self, e: str, extra: int = 0) -> float:
        return (self.load[e] + extra) / self.capacity(e)

    def penalty(self, edges: list[str], edge_tt: dict[str, float]) -> tuple[float, float]:
        pen, worst = 0.0, 0.0
        for e in edges:
            r = self.load_ratio(e)
            worst = max(worst, r)
            tt = edge_tt.get(e, self.info.free_tt.get(e, 0.0))
            pen += tt * self.alpha * (r ** self.beta)
        return round(pen, 3), round(worst, 4)

    def capacity_ok(self, edges: list[str]) -> bool:
        return all(self.load_ratio(e, 1) <= self.max_ratio for e in edges)

    def share_ok(self, sig: str) -> bool:
        if self.n_round < self.share_min_n:            # one analysed trip is not a herd
            return True
        return (self.route_share[sig] + 1) / self.n_round <= self.max_share

    def occupy(self, edges: list[str], rerouted: bool, sig: str | None = None):
        for e in edges:
            self.load[e] += 1
            if rerouted:
                self.edge_flow_rerouted[e] += 1
        if rerouted and sig:
            self.route_share[sig] += 1


def decide_vehicle(vid: str, cands: list[list[str]], edge_tt: dict[str, float], info: NetInfo, cfg: dict,
                   adm: Admission, last_reroute_s: float | None = None, now_s: float = 0.0) -> dict:
    gc, dc = cfg["generalized_cost"], cfg["decision"]
    switch = float(gc["overlap_penalty"]["switch_cost_s"])
    current = cands[0] if cands else []
    table = []
    for i, edges in enumerate(cands):
        t = route_terms(edges, edge_tt, info)
        ov = 1.0 if i == 0 else overlap_fraction(edges, current, info)
        lp, worst = adm.penalty(edges, edge_tt)
        op = 0.0 if i == 0 else round(switch * (1.0 - ov), 3)
        t.update(route_id=f"{vid}_c{i}", index=i, edges=edges, n_edges=len(edges), overlap_with_current=ov,
                 predicted_load_ratio_max=worst, load_penalty_s=lp, overlap_penalty_s=op,
                 final_cost_s=round(t["forecast_future_tt_s"] + lp + op, 3), is_current=(i == 0))
        table.append(t)
    rec = {"vehicle": vid, "candidates_requested": int(cfg["candidates"]["k_alternatives"]), "candidates_real": len(table),
           "candidates": table, "threshold_s": float(dc["min_saving_s"]), "threshold_pct": float(dc["min_saving_pct"])}
    if not table:
        rec.update(decision="NO_ROUTE", selected=None)
        return rec
    cur = table[0]
    alts = [c for c in table[1:]]
    if not alts:
        rec.update(decision="NO_ALTERNATIVE", selected=cur["route_id"], current_future_cost_s=cur["final_cost_s"],
                   alternative_future_cost_s=None, predicted_saving_s=0.0, predicted_saving_pct=0.0)
        adm.occupy(cur["edges"], False)
        return rec
    best = min(alts, key=lambda c: c["final_cost_s"])
    saving = cur["final_cost_s"] - best["final_cost_s"]
    pct = 100.0 * saving / cur["final_cost_s"] if cur["final_cost_s"] > 0 else 0.0
    rec.update(current_future_cost_s=cur["final_cost_s"], alternative_future_cost_s=best["final_cost_s"], best_alternative=best["route_id"],
               predicted_saving_s=round(saving, 2), predicted_saving_pct=round(pct, 2))
    if saving < rec["threshold_s"] or pct < rec["threshold_pct"]:
        rec.update(decision="KEEP_CURRENT_BELOW_THRESHOLD", selected=cur["route_id"])
        adm.occupy(cur["edges"], False)
        return rec
    if last_reroute_s is not None and now_s - last_reroute_s < adm.cooldown:
        rec.update(decision="REJECTED_COOLDOWN", selected=cur["route_id"])
        adm.occupy(cur["edges"], False)
        return rec
    sig = hashlib.sha1(" ".join(best["edges"]).encode()).hexdigest()[:12]
    if not adm.capacity_ok(best["edges"]):
        rec.update(decision="REJECTED_CAPACITY", selected=cur["route_id"], rejected_alternative=best["route_id"])
        adm.occupy(cur["edges"], False)
        return rec
    if not adm.share_ok(sig):
        rec.update(decision="REJECTED_SHARE", selected=cur["route_id"], rejected_alternative=best["route_id"])
        adm.occupy(cur["edges"], False)
        return rec
    rec.update(decision="REROUTE", selected=best["route_id"], route_signature=sig)
    adm.occupy(best["edges"], True, sig)
    return rec


# ---------------------------------------------------------------------------
# one optimisation round
# ---------------------------------------------------------------------------

def optimize(net_path: Path, trips: list[dict], table: dict, out_dir: Path, seed: int, window_s: float,
             cfg: dict | None = None, last_reroute: dict[str, float] | None = None, now_s: float = 0.0,
             keep_candidates: bool = True) -> dict:
    """trips: [{id, from, to, depart, current_route?}]; table: an edge_costs table (or oracle table).
    Returns the routing record: candidates, every decision, admission statistics, hashes."""
    cfg = cfg or load_config()
    info = NetInfo(net_path)
    edge_tt = {k: float(v) for k, v in table["edge_travel_times"].items()}
    if table.get("time_dependent"):                     # {horizon_min: {edge: tt}} — priced at each edge's expected entry time
        edge_tt = TimeDependentCosts(table["time_dependent"])
    from traffictwin.optimization.edge_costs import write_weights
    weights = write_weights(table, out_dir / "future_weights.xml", 0.0, max(float(window_s), 3600.0)) if len(edge_tt) or table.get("time_dependent") else None
    cands, gen = candidates_from_sumo(net_path, trips, weights, out_dir, cfg, seed)
    adm = Admission(cfg, info, window_s, len(trips))
    decisions = []
    for t in sorted(trips, key=lambda x: float(x.get("depart", 0))):
        d = decide_vehicle(t["id"], cands.get(t["id"], []), edge_tt, info, cfg, adm,
                           (last_reroute or {}).get(t["id"]), now_s)
        decisions.append(d)
    n = len(decisions)
    by = Counter(d["decision"] for d in decisions)
    rerouted = [d for d in decisions if d["decision"] == "REROUTE"]
    top_share = (max(adm.route_share.values()) / n) if adm.route_share and n else 0.0
    top_edge = (max(adm.edge_flow_rerouted.values()) / len(rerouted)) if rerouted else 0.0
    selected = {d["vehicle"]: next((c["edges"] for c in d["candidates"] if c["route_id"] == d["selected"]), None) for d in decisions}
    stats = {"vehicles": n, "decisions": dict(by), "advised_above_threshold": sum(by[k] for k in by if k.startswith("REROUTE") or k.startswith("REJECTED")),
             "vehicles_admitted": by["REROUTE"], "rejected_by_capacity_gate": by["REJECTED_CAPACITY"], "rejected_by_share_gate": by["REJECTED_SHARE"],
             "rejected_by_cooldown": by["REJECTED_COOLDOWN"], "reroute_count": by["REROUTE"],
             "top_route_share": round(top_share, 4), "top_edge_flow_concentration": round(top_edge, 4),
             "mean_candidates_real": round(sum(d["candidates_real"] for d in decisions) / n, 3) if n else 0.0,
             "candidates_real_histogram": dict(Counter(d["candidates_real"] for d in decisions)),
             "vehicles_with_fewer_than_k": sum(1 for d in decisions if d["candidates_real"] < int(cfg["candidates"]["k_alternatives"]) + 1)}
    rec = {"config": cfg, "seed": seed, "window_s": window_s, "net": str(net_path), "generator": gen,
           "edge_costs": {k: table.get(k) for k in ("analysis_run_id", "model", "horizon_min", "unit", "coverage_hops", "priced_edges",
                                                     "direct_edges", "derived_edges", "network_edges", "future_cost_hash", "raw_forecast_hash")},
           "stats": stats, "decisions": decisions if keep_candidates else [{k: v for k, v in d.items() if k != "candidates"} for d in decisions],
           "selected_routes": selected,
           "selected_routes_hash": sha({v: " ".join(r) if r else None for v, r in selected.items()}),
           "candidate_sets_hash": sha({v: sorted(" ".join(c) for c in cs) for v, cs in cands.items()}),
           "candidate_costs_hash": sha({d["vehicle"]: [round(c["final_cost_s"], 2) for c in d["candidates"]] for d in decisions})}
    (out_dir / "routing_record.json").write_text(json.dumps(rec, indent=1))
    return rec
