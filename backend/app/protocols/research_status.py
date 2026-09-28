"""Computed research-status gates.

No UI or document is allowed to declare a gate.  This module derives every status from frozen
configuration and generated evidence, and preserves unavailable/negative states as results.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from app.paths import REPO
def _read(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError, json.JSONDecodeError):
        return None


def compute_research_status() -> dict:
    verify_path = REPO / "results/forecasting/verify_GWNet_METR-LA_207.json"
    verify = _read(verify_path) or {}
    skills = {h: v.get("skill") for h, v in (verify.get("held_out") or {}).items()}
    forecast_ok = bool(skills) and all(isinstance(v, (int, float)) and v > 0 for v in skills.values())

    cfg_path = REPO / "backend/app/protocols/controller_config.json"
    cfg = _read(cfg_path) or {}
    stress = ((cfg.get("stress_scenario") or {}).get("la_c4_central_wide:uniform:arterial") or {})
    stress_ok = stress.get("gate") == "VALID_TRAFFIC_STRESS_CASE"

    oracle_path = REPO / "results/v2x/stress/la_c4_central_wide/scenarioA_oracle_gate_eval.json"

    controller_path = REPO / "results/v2x/controller_status.json"
    controller = (_read(controller_path) or {}).get("current") or {}
    predictive = controller.get("PREDICTIVE_TRAFFIC_BENEFIT", "UNAVAILABLE")

    network_run = REPO / "results/v2x/closed_loop/la_c4_central_wide_prepeak_ideal_p30_cfgea08dddedc14_stressA_eval_fork1200_x8_peak_arterial/report.json"
    report = _read(network_run) or {}
    from app.protocols.oracle_gate import paired
    rows = {r["seed"]: r["arms"] for r in report.get("per_seed", [])}
    key = "total_vehicle_hours_incl_never_inserted"
    def comparison(a, b):
        expected_seeds = {201, 202, 203, 204, 205}
        values = [r.get(arm, {}).get("metrics", {}).get(key) for r in rows.values() for arm in (a, b)]
        if set(rows) != expected_seeds or len(report.get("per_seed", [])) != len(expected_seeds) or not all(
            isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and v > 0 for v in values
        ):
            return {"status": "NOT_ESTABLISHED", "reason": "requires complete finite paired evidence for all five frozen evaluation seeds"}
        stat = paired(rows, a, b, key, True)
        hi = (stat.get("ci95") or [None, None])[1]
        ok = report.get("fork_state_identical_across_arms") is True and isinstance(hi, (int, float)) and hi < 0 and stat.get("mean_pct", 0) < 0
        return {"status": "ESTABLISHED" if ok else "NOT_ESTABLISHED", "scope": "frozen Scenario A, evaluation seeds", "paired": stat}
    network = report.get("network_summary") or {}
    down = network.get("downlink") or {}
    networking_ok = bool(report.get("fork_state_identical_across_arms")) and (down.get("messages_tx") or 0) > 0 and (down.get("messages_rx") or 0) > 0

    dhaka_path = REPO / "results/final_validation/metrics.json"
    dhaka = _read(dhaka_path) or {}
    dhaka_checks = dhaka.get("checks") or {}
    dhaka_ok = bool(dhaka_checks) and all(dhaka_checks.values())

    return {
        "generated_from": {"forecast": str(verify_path.relative_to(REPO)), "stress": str(cfg_path.relative_to(REPO)),
                           "oracle": str(oracle_path.relative_to(REPO)), "controller": str(controller_path.relative_to(REPO)),
                           "networking": str(network_run.relative_to(REPO)), "dhaka": str(dhaka_path.relative_to(REPO))},
        "gates": {
            "FORECAST_VALIDATED": {"status": "PASSED" if forecast_ok else "FAILED", "scope": "METR-LA only", "skill_vs_persistence": skills},
            "NETWORKING_VALIDATED": {"status": "PASSED" if networking_ok else "FAILED", "scope": "SIMULATED V2X EMULATOR", "downlink": down},
            "VALID_TRAFFIC_STRESS_CASE": {"status": "PASSED" if stress_ok else "FAILED", "scenario": stress},
            "FUTURE_INFORMATION_VALUE": comparison("oracle_v2x", "reactive"),
            "PREDICTIVE_CONTROL_VS_REACTIVE": comparison("predictive_v2x", "reactive"),
            "LEARNED_FORECAST_ADVANTAGE_VS_PERSISTENCE": comparison("predictive_v2x", "persistence_v2x"),
            "PREDICTIVE_TRAFFIC_BENEFIT": {"status": predictive, "controller": controller},
            "DHAKA_DEPLOYMENT_READY": {"status": "PASSED" if dhaka_ok else "NOT_READY", "checks": dhaka_checks,
                                         "reason": "requires local held-out forecast validation and twin validation"},
        },
    }
