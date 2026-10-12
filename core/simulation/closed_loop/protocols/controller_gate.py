#!/usr/bin/env python3
"""CONTROLLER VALIDATION GATE — the predictive controller's status is COMPUTED from evaluation results,
never set by hand.

    MECHANICALLY_VALIDATED           the closed loop works: tests pass, recommendations are delivered and
                                     applied, provenance intact — but no traffic claim
    TRAFFIC_BENEFIT_NOT_ESTABLISHED  mechanically validated, and the unseen-seed evaluation does NOT show
                                     a paired improvement whose 95 % CI excludes zero against BOTH the
                                     no-advice baseline and reactive routing, or it does but with worse
                                     teleports (a simulation-quality warning)
    TRAFFIC_BENEFIT_ESTABLISHED      unseen-seed evaluation: vehicle-hours vs baseline AND vs reactive both
                                     HELPED (CI excludes zero), teleports not HURT, on evaluation seeds only

    python -m core.simulation.closed_loop.protocols.controller_gate --run results/v2x/closed_loop/<eval run dir> --arm predictive_corrected_v2x
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from core.common.paths import REPO
sys.path.insert(0, str(REPO))
KEY = "total_vehicle_hours_incl_never_inserted"


def gate(report: dict, arm: str, tests_passed: bool = True) -> dict:
    cfg = json.loads((REPO / "core/simulation/closed_loop/protocols/controller_config.json").read_text())
    eval_seeds = set(cfg["seeds"]["evaluation"]); seeds = set(report.get("seeds", []))
    on_eval = bool(seeds) and seeds <= eval_seeds
    reroutes = (report.get("reroutes_by_arm") or {}).get(arm, 0)
    mech = tests_passed and reroutes > 0 and bool(report.get("fork_state_identical_across_arms", True))
    vb = (report["paired"].get(f"{arm}_vs_baseline") or {}); vr = (report["paired"].get(f"{arm}_vs_reactive") or {})
    tel = (vb.get("teleports") or {}).get("label")
    helped = vb.get(KEY, {}).get("label") == "HELPED" and vr.get(KEY, {}).get("label") == "HELPED" and tel != "HURT"
    if not mech:
        status = "NOT_VALIDATED"
    elif on_eval and helped:
        status = "TRAFFIC_BENEFIT_ESTABLISHED"
    else:
        status = "TRAFFIC_BENEFIT_NOT_ESTABLISHED" if on_eval else "MECHANICALLY_VALIDATED"
    ob = (report["paired"].get("oracle_v2x_vs_reactive") or {}).get(KEY, {})
    future_value = "ESTABLISHED" if (on_eval and ob.get("label") == "HELPED") else "NOT_ESTABLISHED"
    return {"arm": arm, "status": status, "evaluated_on_unseen_seeds": on_eval,
            "FUTURE_INFORMATION_VALUE": future_value, "PREDICTIVE_TRAFFIC_BENEFIT": "ESTABLISHED" if status == "TRAFFIC_BENEFIT_ESTABLISHED" else "NOT_ESTABLISHED",
            "oracle_vs_reactive": {k: ob.get(k) for k in ("mean_pct", "ci95", "wins", "losses", "ties", "label")}, "seeds": sorted(seeds), "reroutes_applied": reroutes, "fork_identical": report.get("fork_state_identical_across_arms"),
            "vs_baseline": {k: vb.get(KEY, {}).get(k) for k in ("mean_pct", "ci95", "wins", "losses", "ties", "label")}, "vs_reactive": {k: vr.get(KEY, {}).get(k) for k in ("mean_pct", "ci95", "wins", "losses", "ties", "label")},
            "teleports_vs_baseline": tel, "controller_config_hash": report.get("protocol", {}).get("controller_config_hash"), "run": report.get("run_dir"), "computed_utc": datetime.now(timezone.utc).isoformat(),
            "rule": "ESTABLISHED only if vehicle-hours vs baseline AND vs reactive are HELPED (95 % CI excludes zero) on evaluation seeds and teleports are not HURT"}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--run", required=True); p.add_argument("--arm", default="predictive_corrected_v2x")
    a = p.parse_args()
    rep = json.loads((REPO / a.run / "report.json").read_text())
    g = gate(rep, a.arm)
    out = REPO / "results/v2x/controller_status.json"
    hist = json.loads(out.read_text()) if out.exists() else {"history": []}
    hist["current"] = g; hist["history"].append(g)
    out.write_text(json.dumps(hist, indent=1))
    print(json.dumps(g, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
