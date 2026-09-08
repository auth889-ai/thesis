#!/usr/bin/env python3
"""Assemble the oracle / identical-state-fork phase report from the run files — every table is read from
report.json, decision_agreement.json, controller_status.json and the sweep JSONs; nothing is typed in.

    python pipeline/v2x/phase_report.py
"""
from __future__ import annotations

import glob
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
KEY = "total_vehicle_hours_incl_never_inserted"
CL = REPO / "results/v2x/closed_loop"
WORDS = {"baseline": "no advice", "reactive": "reactive (current travel times)", "persistence_v2x": "persistence + V2X", "predictive_v2x": "Graph WaveNet + V2X", "predictive_corrected_v2x": "Graph WaveNet + online correction + V2X", "oracle_v2x": "ORACLE future state + V2X (upper bound)", "random_v2x": "shuffled forecast (negative control)"}


def find(pattern: str) -> Path | None:
    hits = sorted((Path(p) for p in glob.glob(str(CL / pattern))), key=lambda p: p.stat().st_mtime)
    return hits[-1] if hits else None


def arm_table(rep: dict, title: str) -> list[str]:
    L = [f"### {title}", "", f"Seeds {rep['seeds']} · fork {rep['protocol'].get('fork_t0_s')} s · state hashes {rep.get('fork_state_hashes')} · identical across arms: **{rep.get('fork_state_identical_across_arms')}** · reroutes by arm {rep.get('reroutes_by_arm')}", "",
         "| arm | vs baseline: mean % | 95 % CI | W/L/T | label | vs reactive: mean % | 95 % CI | W/L/T | label | p95 % | waiting % | queue % | arrived % | teleports (sum) |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    tel = {a: sum(r["arms"][a]["metrics"]["teleports"] for r in rep["per_seed"] if a in r["arms"]) for a in rep["arms"]}
    for a in rep["arms"]:
        if a == "baseline":
            L.append(f"| {WORDS.get(a, a)} | — | — | — | — | — | — | — | — | — | — | — | — | {tel[a]} |"); continue
        vb = (rep["paired"].get(f"{a}_vs_baseline") or {}); vr = (rep["paired"].get(f"{a}_vs_reactive") or {})
        b = vb.get(KEY, {}); r = vr.get(KEY, {}); g = lambda d, k: d.get(k, "—") if d else "—"
        L.append(f"| {WORDS.get(a, a)} | {g(b, 'mean_pct')} | {g(b, 'ci95')} | {g(b, 'wins')}/{g(b, 'losses')}/{g(b, 'ties')} | **{g(b, 'label')}** | {g(r, 'mean_pct')} | {g(r, 'ci95')} | {g(r, 'wins')}/{g(r, 'losses')}/{g(r, 'ties')} | **{g(r, 'label')}** | "
                 f"{g(vb.get('p95_travel_time_s'), 'mean_pct')} | {g(vb.get('total_waiting_s'), 'mean_pct')} | {g(vb.get('mean_queue_veh'), 'mean_pct')} | {g(vb.get('arrived'), 'mean_pct')} | {tel[a]} |")
    L += ["", "Per-seed vehicle-hours: " + "; ".join(f"s{r['seed']}: " + ", ".join(f"{a} {x['metrics'][KEY]:.1f}" for a, x in r["arms"].items()) for r in rep["per_seed"]), ""]
    det = []
    for r in rep["per_seed"]:
        for a in ("predictive_corrected_v2x", "predictive_v2x"):
            n = (r["arms"].get(a) or {}).get("network") or {}
            d = [i for i in n.get("incidents_detected", []) if i.get("detection_delay_s") is not None]
            if d:
                det.append(f"s{r['seed']} {a}: detected {d[0]['detection_delay_s']} s after onset by {d[0]['vehicles']} vehicles; first reroute applied at {n.get('lead_time', {}).get('first_reroute_applied_s')} s")
    if det:
        L += ["Incident detection (statistical detector, status messages, 30 % penetration): " + "; ".join(det), ""]
    return L


def main() -> int:
    dev = find("la_c4_central_wide_peak_ideal_p30_cfg*_inc_fork480/report.json")
    ev = find("la_c4_central_wide_peak_ideal_p30_cfg*_eval_inc_fork480/report.json")
    pre = find("la_c4_central_wide_prepeak_ideal_p30_cfg*_fork300/report.json")
    da = dev.parent / "decision_agreement.json" if dev else None
    status = REPO / "results/v2x/controller_status.json"
    L = ["# Oracle / identical-state fork phase — report", "", f"Generated {datetime.now(timezone.utc).isoformat()} from run files (no number typed in).", "",
         "## 1–2. Can genuine future information beat reactive routing? (development seeds, incident, identical fork)", ""]
    if dev:
        L += arm_table(json.loads(dev.read_text()), f"Incident response — `{dev.parent.name}`")
    if da and da.exists():
        d = json.loads(da.read_text()); L += ["## 9–10. Decision-level forecast metrics (offline replay of the baseline's rounds under every information source)", "",
                                             "| source | decisions | top-1 route agreement with oracle | pairwise ranking accuracy | reroutes (oracle) | false-positive reroutes | false-negative reroutes | predicted-saving |error| s | edge tt MAE vs oracle s | decisive edges by provenance |", "|---|---|---|---|---|---|---|---|---|---|"]
        for s, v in d["sources"].items():
            L.append(f"| {s} | {v['decisions']} | {v['top1_agreement_with_oracle']} | {v['pairwise_ranking_accuracy']} | {v['source_reroutes']} ({v['oracle_reroutes']}) | {v['false_positive_reroutes']} | {v['false_negative_reroutes']} | {v['predicted_saving_abs_error_mean_s']} | {v['edge_tt_MAE_vs_oracle_s']} | {v['decisive_edge_provenance']} |")
        L += ["", "Reading: the decisive edges (those that differ between the current route and the best alternative) are overwhelmingly UNPRICED — the forecast covers the detector roads, the oracle prices every edge. That, not forecast error on the priced edges, is why the forecast sources keep routes the oracle would switch (false negatives ≫ false positives).", ""]
    if ev:
        L += ["## 16. Evaluation seeds (unseen) — the gate", ""] + arm_table(json.loads(ev.read_text()), f"Incident response, evaluation seeds — `{ev.parent.name}`")
    if status.exists():
        st = json.loads(status.read_text())["current"]; L += [f"**Controller status (computed by pipeline/v2x/controller_gate.py): `{st['status']}`** — {st['rule']}", ""]
    if pre:
        L += ["## 13. Forecastable congestion (pre-peak build-up, no incident)", ""] + arm_table(json.loads(pre.read_text()), f"Pre-peak — `{pre.parent.name}`")
    sw = REPO / "results/v2x/sweep/la_c4_central_wide_peak"
    if sw.exists():
        L += ["## Network ablation (from departure, not forked; development seeds)", ""]
        for g in ("latency", "loss", "penetration"):
            f = sw / f"sweep_{g}.json"
            if f.exists():
                rows = json.loads(f.read_text())["rows"]
                L += [f"**{g}**: " + "; ".join(f"{r['profile']} p={r['penetration']}: PDR {r['downlink_pdr']}, reroutes {r['reroutes_applied']}, veh-h {r['vehicle_hours_pred_vs_base_pct']} % {r['vehicle_hours_pred_vs_base_ci']} {r['vehicle_hours_pred_vs_base_label']}" for r in rows), ""]
    out = REPO / "results/v2x/ORACLE_FORK_REPORT.md"; out.write_text("\n".join(L)); print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
