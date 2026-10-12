"""ONLINE STATE CORRECTION for the predictive controller — two explicit, separately testable parts:

  1. IncidentDetector   a STATISTICAL (not ML) anomaly detector on received VEHICLE_STATUS messages:
                        an edge is flagged when, within a sliding window, at least `min_vehicles`
                        distinct vehicles in at least `min_messages` messages report speeds below
                        `ratio` × the expected speed. Output: edge, detection time, evidence
                        (vehicles, messages), severity = 1 − observed/expected, and the detection
                        delay when the true onset is known (synthetic incidents).

  2. residual_correction   a hybrid forecast: the offline base forecast (Graph WaveNet → edge costs,
                        one table per horizon) is corrected online by the residual between what the
                        V2X status messages observe NOW and what the base forecast expected NOW:

                            residual(e)        = observed_speed_now(e) − expected_speed_now(e)
                            corrected(e, h)    = base_speed(e, h) + w(h) · residual(e)
                            w(h)               = exp(−h / tau_min)          (decays with horizon)

                        and the residual spills UPSTREAM only (against traffic direction — a queue
                        grows backwards from the slow edge), through the road graph's incoming edges,
                        decayed by `hop_decay` per hop for up to `upstream_hops` hops. Downstream edges
                        are NOT corrected (a blocked edge starves, not floods, its successors).
                        Only residuals that make an edge SLOWER than expected are applied: a faster
                        observation never speeds a forecast up (the forecast may know about congestion
                        that has not arrived yet). Every corrected row keeps its provenance:
                        OBSERVED (the edge itself) or RESIDUAL_UPSTREAM (propagated), with the residual
                        and weight that produced it.

SCOPE (learned the hard way): residuals are only formed on edges the base forecast PRICES (DIRECT or DERIVED),
because only there does an expected speed exist. On an unpriced urban edge the only "expectation" would be
the speed limit, and a queue at a red light is then indistinguishable from an incident — the first version
corrected 1,500 edges per round for that reason and over-reacted. Upstream propagation may still reach
unpriced edges (a spillback queue is real wherever it forms).

Assumptions written down: (a) the observation window is short (60 s) so "now" means the last minute;
(b) tau_min and hop_decay are controller parameters chosen on DEVELOPMENT seeds and frozen — they are
not fitted to evaluation outcomes; (c) edges without observations keep the base forecast.
"""
from __future__ import annotations

import math
import statistics
from collections import defaultdict, deque

from core.simulation.routing import edge_costs as ec


class IncidentDetector:
    def __init__(self, window_s: float = 60.0, min_vehicles: int = 3, min_messages: int = 5, ratio: float = 0.5):
        self.window_s, self.min_vehicles, self.min_messages, self.ratio = float(window_s), int(min_vehicles), int(min_messages), float(ratio)
        self.obs: dict[str, deque] = defaultdict(deque)          # edge -> (t, vehicle, speed, expected)
        self.active: dict[str, dict] = {}                        # edge -> incident record
        self.history: list[dict] = []

    def ingest(self, t: float, edge: str, vehicle: str, speed: float, expected: float) -> None:
        q = self.obs[edge]; q.append((float(t), vehicle, float(speed), float(expected)))
        while q and t - q[0][0] > self.window_s:
            q.popleft()

    def detect(self, t: float, true_onsets: dict[str, float] | None = None) -> list[dict]:
        """Incidents newly detected at time t (also refreshes evidence of active ones, closes cleared ones)."""
        new = []
        for edge, q in list(self.obs.items()):
            if not q or t - q[-1][0] > self.window_s:
                if edge in self.active:
                    self.active[edge]["cleared_at_s"] = t; del self.active[edge]
                if not q or t - q[-1][0] > 5 * self.window_s:
                    self.obs.pop(edge, None)                        # forget idle edges: keeps the scan proportional to active traffic
                continue
            recent = [o for o in q if t - o[0] <= self.window_s]
            slow = [o for o in recent if o[3] > 0 and o[2] < self.ratio * o[3]]
            vehicles = {o[1] for o in slow}
            if len(vehicles) >= self.min_vehicles and len(slow) >= self.min_messages:
                sev = 1.0 - (statistics.fmean(o[2] for o in slow) / statistics.fmean(o[3] for o in slow))
                if edge not in self.active:
                    rec = {"edge": edge, "detected_at_s": t, "first_evidence_s": min(o[0] for o in slow), "vehicles": len(vehicles), "messages": len(slow), "severity": round(sev, 3),
                           "confidence": round(min(1.0, len(vehicles) / (2 * self.min_vehicles)), 3), "observed_speed_mps": round(statistics.fmean(o[2] for o in slow), 2), "expected_speed_mps": round(statistics.fmean(o[3] for o in slow), 2)}
                    if true_onsets and edge in true_onsets:
                        rec["true_onset_s"] = true_onsets[edge]; rec["detection_delay_s"] = round(t - true_onsets[edge], 1)
                    self.active[edge] = rec; self.history.append(rec); new.append(rec)
                else:
                    self.active[edge].update(vehicles=len(vehicles), messages=len(slow), severity=round(sev, 3), last_seen_s=t)
            elif edge in self.active and not slow:
                self.active[edge]["cleared_at_s"] = t; del self.active[edge]
        return new


def residual_correction(base: dict[int, dict], observed_now: dict[str, float], net, cfg: dict, tau_min: float = 30.0, upstream_hops: int = 2, hop_decay: float = 0.5,
                        min_rel_residual: float = 0.15, only_priced: bool = True) -> tuple[dict[int, dict], dict]:
    """base: {horizon_min: edge-cost table}; observed_now: edge -> mean observed speed (m/s) in the last
    minute. Returns ({horizon_min: corrected table}, diagnostics)."""
    v_min = float(cfg["edge_costs"]["speed_lower_bound_mps"])
    horizons = sorted(base)
    h0 = horizons[0]
    def speed_of(table: dict, e) -> float:
        row = table["edges"].get(e.getID())
        return float(row["bounded_speed_mps"]) if row and row.get("bounded_speed_mps") else float(e.getSpeed())
    residuals: dict[str, float] = {}
    for eid, v_obs in observed_now.items():
        if only_priced and eid not in base[h0]["edges"]:
            continue                                                  # no expectation for this edge: a queue at a signal is not an anomaly we can name
        try:
            e = net.getEdge(eid)
        except KeyError:
            continue
        expected = speed_of(base[h0], e)
        r = float(v_obs) - expected
        if expected > 0 and -r / expected >= min_rel_residual:          # only materially SLOWER than expected
            residuals[eid] = r
    # upstream propagation along incoming edges, decayed per hop; the strongest (most negative) wins
    prop: dict[str, tuple[float, int, str]] = {eid: (r, 0, eid) for eid, r in residuals.items()}
    frontier = dict(residuals)
    for hop in range(1, upstream_hops + 1):
        nxt = {}
        for eid, r in frontier.items():
            try:
                e = net.getEdge(eid)
            except KeyError:
                continue
            for inc in e.getIncoming():
                if not inc.allows("passenger"):
                    continue
                iid = inc.getID(); r_h = r * (hop_decay ** hop)
                if iid not in prop or r_h < prop[iid][0]:
                    prop[iid] = (r_h, hop, eid); nxt[iid] = r_h
        frontier = nxt
    out, n_by_kind = {}, {"OBSERVED": 0, "RESIDUAL_UPSTREAM": 0}
    for h in horizons:
        t = base[h]; w = math.exp(-h / tau_min) if tau_min > 0 else 1.0
        tt = dict(t["edge_travel_times"]); rows = dict(t["edges"]); changed = 0
        for eid, (r, hop, src) in prop.items():
            try:
                e = net.getEdge(eid)
            except KeyError:
                continue
            base_speed = speed_of(t, e)
            v_new = max(v_min, min(e.getSpeed(), base_speed + w * r))
            if v_new >= base_speed - 1e-6:
                continue
            new_tt = e.getLength() / v_new; tt[eid] = round(new_tt, 3); changed += 1
            rows[eid] = {**rows.get(eid, {"edge": eid, "length_m": round(e.getLength(), 2), "speed_limit_mps": round(e.getSpeed(), 3), "corridor": None, "forecast_value": None, "graph_distance": None, "decay_weight": None}),
                         "source": "OBSERVED" if hop == 0 else "RESIDUAL_UPSTREAM", "residual_mps": round(r, 3), "horizon_weight": round(w, 4), "upstream_hop": hop, "residual_source_edge": src,
                         "base_speed_mps": round(base_speed, 3), "bounded_speed_mps": round(v_new, 3), "future_tt_s": round(new_tt, 3)}
            if h == h0:
                n_by_kind["OBSERVED" if hop == 0 else "RESIDUAL_UPSTREAM"] += 1
        out[h] = {**t, "edge_travel_times": tt, "edges": rows, "priced_edges": len(rows), "corrected_edges": changed, "future_cost_hash": ec.sha({k: round(v, 3) for k, v in tt.items()}),
                  "forecast_only_cost_hash": t["future_cost_hash"], "correction": {"tau_min": tau_min, "upstream_hops": upstream_hops, "hop_decay": hop_decay, "horizon_weight": round(w, 4), "residual_edges": len(residuals)}}
    diag = {"residual_edges": len(residuals), "propagated_edges": len(prop) - len(residuals), "by_kind_at_h0": n_by_kind, "tau_min": tau_min, "upstream_hops": upstream_hops, "hop_decay": hop_decay,
            "largest_residuals": sorted(((round(r, 2), e) for e, r in residuals.items()))[:5]}
    return out, diag
