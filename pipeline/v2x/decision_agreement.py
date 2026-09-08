#!/usr/bin/env python3
"""DECISION-LEVEL FORECAST METRICS — does forecast error matter to routing?

Offline replay on the BASELINE arm of an identical-state fork run: at every routing round the baseline
recorded the connected vehicles' positions and remaining routes (nobody had rerouted, so the state is
the same whatever the information source). For each round the production optimizer is run on exactly
those vehicles under each information source:

    persistence   current detector readings carried forward
    gwnet         the 207-node Graph WaveNet forecast (time-dependent tables)
    corrected     gwnet + online residual correction, with the OBSERVED speeds approximated by the
                  measured last-interval edge speeds of the baseline run (what V2X status messages report)
    oracle        the measured future of the same baseline run (edge_costs.oracle_table)

and compared decision by decision with the oracle:

    top-1 route agreement       same selected route as the oracle
    pairwise ranking accuracy   fraction of candidate pairs ordered like the oracle's costs
    predicted saving error      source saving − oracle saving (s)
    false-positive reroute      source says REROUTE, oracle says keep
    false-negative reroute      oracle says REROUTE, source keeps
    decisive-edge provenance    of the edges that differ between the current route and the source's
                                best alternative, how many are DIRECT, DERIVED, or unpriced

plus forecast MAE against the oracle on the edges the candidates actually use, split DIRECT / DERIVED,
by horizon table.

    python pipeline/v2x/decision_agreement.py --run results/v2x/closed_loop/<fork run dir>
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from itertools import combinations
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "dashboard/backend"))

from pipeline.routing import edge_costs as ec              # noqa: E402
from pipeline.routing import predictive_routing as pr     # noqa: E402
from pipeline.routing import route_optimizer as ro        # noqa: E402
from pipeline.v2x import closed_loop as cl                # noqa: E402
from pipeline.v2x.state_correction import residual_correction   # noqa: E402

SOURCES = ("persistence", "gwnet", "corrected")


def measured_last_interval(edgedata: Path, net, t: float) -> dict[str, float]:
    """edge -> measured mean speed (m/s) over the interval ending at t (what the uplink messages would carry)."""
    rows = pr.load_weights(edgedata)
    out = {}
    for b, e, eid, tt in rows:
        if e <= t < e + 1e-6 or (b < t <= e):
            try:
                out[eid] = net.getEdge(eid).getLength() / tt if tt > 0 else None
            except KeyError:
                pass
    return {k: v for k, v in out.items() if v}


def replay(run_dir: Path, seed: int) -> dict:
    import sumolib
    P = json.loads((run_dir / "PROTOCOL.json").read_text()); cfg = ec.load_config(); cc = cl.controller_config()
    sdir = run_dir / f"s{seed}"; base = sdir / "baseline"
    snaps = json.loads((base / "round_snapshots.json").read_text())
    net_path = REPO / P["network"]; net = sumolib.net.readNet(str(net_path))
    fc = cl.Forecaster(P, seed)
    out = sdir / "decision_replay"; out.mkdir(exist_ok=True)
    agg = {s: defaultdict(list) for s in SOURCES}; edge_err = {s: defaultdict(list) for s in SOURCES}; decisive = {s: defaultdict(int) for s in SOURCES}
    rounds = []
    for snap in snaps["snapshots"]:
        k, t, veh = snap["round"], snap["sim_time_s"], snap["vehicles"]
        trips = [{"id": v, "from": cur, "to": rem[-1], "depart": t, "current_route": rem} for v, (cur, rem) in veh.items() if len(rem) >= 2]
        if not trips:
            continue
        F = fc.predict(t)
        tables = {}
        oracle = ec.oracle_table(base / "edgedata.xml", net_path, cfg, float(t), float(t + P["round_s"]))
        tables["oracle"] = oracle
        base_tabs = fc.tables(F, cfg, net_path, tuple(cc["horizons_min"]))
        tables["gwnet"] = {**base_tabs[15], "time_dependent": {h: base_tabs[h]["edge_travel_times"] for h in base_tabs}}
        pers = fc.tables({**F, "pred": np.repeat(F["now"][None, :], 12, axis=0)}, cfg, net_path, (0, 15))
        tables["persistence"] = pers[15]
        obs = measured_last_interval(base / "edgedata.xml", net, t)
        c = cc["correction"]; corr, diag = residual_correction(base_tabs, obs, net, cfg, c["tau_min"], c["upstream_hops"], c["hop_decay"], c["min_rel_residual"])
        tables["corrected"] = {**corr[15], "time_dependent": {h: corr[h]["edge_travel_times"] for h in corr}}
        decisions = {}
        for name, table in tables.items():
            rec = ro.optimize(net_path, trips, table, out / f"r{k}_{name}", seed, float(P["round_s"]), cfg, None, t, keep_candidates=True)
            decisions[name] = {d["vehicle"]: d for d in rec["decisions"]}
        O = decisions["oracle"]; rr = {"round": k, "sim_time_s": t, "vehicles": len(trips), "observed_edges_for_correction": len(obs), "correction": diag}
        for s in SOURCES:
            D = decisions[s]; top1 = fp = fn = 0; rank = []; sav = []
            for v, d in D.items():
                o = O.get(v)
                if not o or not d.get("candidates") or not o.get("candidates"):
                    continue
                same = d.get("selected") == o.get("selected") or (d["decision"] != "REROUTE" and o["decision"] != "REROUTE")
                top1 += int(same)
                fp += int(d["decision"] == "REROUTE" and o["decision"] != "REROUTE"); fn += int(o["decision"] == "REROUTE" and d["decision"] != "REROUTE")
                oc = {c["route_id"]: c["final_cost_s"] for c in o["candidates"]}; sc = {c["route_id"]: c["final_cost_s"] for c in d["candidates"]}
                pairs = [(a, b) for a, b in combinations(sorted(set(oc) & set(sc)), 2)]
                if pairs:
                    rank.append(sum(1 for a, b in pairs if (oc[a] < oc[b]) == (sc[a] < sc[b])) / len(pairs))
                if d.get("predicted_saving_s") is not None and o.get("predicted_saving_s") is not None:
                    sav.append(d["predicted_saving_s"] - o["predicted_saving_s"])
                if d["decision"] == "REROUTE":
                    best = next((c for c in d["candidates"] if c["route_id"] == d["selected"]), None); cur = d["candidates"][0]
                    if best:
                        for e in set(best["edges"]) ^ set(cur["edges"]):
                            row = tables[s]["edges"].get(e); decisive[s][row["source"] if row else "UNPRICED"] += 1
            n = len(D); a = agg[s]
            a["top1"].append(top1 / n if n else None); a["rank"].append(statistics.fmean(rank) if rank else None); a["fp"].append(fp); a["fn"].append(fn); a["n"].append(n)
            a["oracle_reroutes"].append(sum(1 for o in O.values() if o["decision"] == "REROUTE")); a["source_reroutes"].append(sum(1 for d in D.values() if d["decision"] == "REROUTE"))
            a["saving_err"].extend(sav)
            # forecast error against the oracle on the edges the candidates use
            used = {e for d in D.values() for c in (d.get("candidates") or []) for e in c["edges"]}
            for e in used:
                o_tt = oracle["edge_travel_times"].get(e); row = tables[s]["edges"].get(e)
                if o_tt is None:
                    continue
                s_tt = tables[s]["edge_travel_times"].get(e)
                kind = row["source"] if row else "UNPRICED"
                edge_err[s][kind].append(abs((s_tt if s_tt is not None else o_tt) - o_tt) if s_tt is not None else None)
        rounds.append(rr)
    def m(xs):
        xs = [x for x in xs if x is not None]; return round(statistics.fmean(xs), 4) if xs else None
    summary = {s: {"rounds": len(agg[s]["n"]), "decisions": sum(agg[s]["n"]), "top1_agreement_with_oracle": m(agg[s]["top1"]), "pairwise_ranking_accuracy": m(agg[s]["rank"]),
                   "false_positive_reroutes": sum(agg[s]["fp"]), "false_negative_reroutes": sum(agg[s]["fn"]), "source_reroutes": sum(agg[s]["source_reroutes"]), "oracle_reroutes": sum(agg[s]["oracle_reroutes"]),
                   "predicted_saving_error_mean_s": m(agg[s]["saving_err"]), "predicted_saving_abs_error_mean_s": m([abs(x) for x in agg[s]["saving_err"]]),
                   "edge_tt_MAE_vs_oracle_s": {kind: m([x for x in v if x is not None]) for kind, v in edge_err[s].items()}, "edges_compared": {kind: len(v) for kind, v in edge_err[s].items()},
                   "decisive_edge_provenance": dict(decisive[s])} for s in SOURCES}
    rep = {"run": str(run_dir.relative_to(REPO)), "seed": seed, "controller_config_hash": cc["_hash"], "sources": summary, "rounds": rounds, "note": "offline replay on the baseline's per-round snapshots; the same vehicles and state under every information source"}
    (out / "decision_agreement.json").write_text(json.dumps(rep, indent=1, default=str))
    return rep


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--run", required=True); p.add_argument("--seeds", default=None)
    a = p.parse_args(); run_dir = REPO / a.run
    seeds = [int(x) for x in a.seeds.split(",")] if a.seeds else sorted(int(d.name[1:]) for d in run_dir.glob("s*") if (d / "baseline/round_snapshots.json").exists())
    reps = [replay(run_dir, s) for s in seeds]
    combined = {"run": a.run, "seeds": seeds, "sources": {}}
    for s in SOURCES:
        rows = [r["sources"][s] for r in reps]
        combined["sources"][s] = {k: (round(statistics.fmean(x[k] for x in rows if x[k] is not None), 4) if any(x[k] is not None for x in rows) else None) if isinstance(rows[0][k], (int, float, type(None))) else rows[0][k]
                                  for k in ("top1_agreement_with_oracle", "pairwise_ranking_accuracy", "predicted_saving_abs_error_mean_s", "predicted_saving_error_mean_s")}
        combined["sources"][s].update({k: sum(x[k] for x in rows) for k in ("decisions", "false_positive_reroutes", "false_negative_reroutes", "source_reroutes", "oracle_reroutes")})
        combined["sources"][s]["decisive_edge_provenance"] = {kk: sum(x["decisive_edge_provenance"].get(kk, 0) for x in rows) for kk in {kk for x in rows for kk in x["decisive_edge_provenance"]}}
        combined["sources"][s]["edge_tt_MAE_vs_oracle_s"] = {kk: round(statistics.fmean(v for v in (x["edge_tt_MAE_vs_oracle_s"].get(kk) for x in rows) if v is not None), 3) for kk in {kk for x in rows for kk in x["edge_tt_MAE_vs_oracle_s"]} if any(x["edge_tt_MAE_vs_oracle_s"].get(kk) is not None for x in rows)}
    (run_dir / "decision_agreement.json").write_text(json.dumps(combined, indent=1, default=str))
    for s, v in combined["sources"].items():
        print(f"{s:<12} top1={v['top1_agreement_with_oracle']} rank={v['pairwise_ranking_accuracy']} FP={v['false_positive_reroutes']} FN={v['false_negative_reroutes']} reroutes={v['source_reroutes']} (oracle {v['oracle_reroutes']}) "
              f"saving|err|={v['predicted_saving_abs_error_mean_s']} s edgeMAE={v['edge_tt_MAE_vs_oracle_s']} decisive={v['decisive_edge_provenance']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
