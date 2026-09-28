"""Congested-scenario evidence for the Results page — every number is read from run files under
results/v2x/stress/ and the closed-loop report they point to. Nothing is typed in."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter

from app import evidence_paths as config

router = APIRouter()
KEY = "total_vehicle_hours_incl_never_inserted"
ARMS = ["reactive", "persistence_v2x", "predictive_v2x", "predictive_corrected_v2x", "random_v2x", "oracle_v2x"]
WORDS = {"baseline": "no advice", "reactive": "reactive routing (current travel times)", "persistence_v2x": "persistence forecast + V2X", "predictive_v2x": "Graph WaveNet forecast + V2X",
         "predictive_corrected_v2x": "Graph WaveNet + online correction + V2X", "random_v2x": "shuffled forecast (negative control)", "oracle_v2x": "perfect future information (upper bound)"}


def _read(p: Path):
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return None


def _arm_table(rep: dict) -> list[dict]:
    rows = []
    for a in ARMS:
        vb = ((rep.get("paired") or {}).get(f"{a}_vs_baseline") or {}).get(KEY) or {}
        vr = ((rep.get("paired") or {}).get(f"{a}_vs_reactive") or {}).get(KEY) or {}
        if not vb and not vr:
            continue
        rows.append({"arm": a, "label": WORDS.get(a, a), "reroutes": (rep.get("reroutes_by_arm") or {}).get(a),
                     "vs_baseline": {k: vb.get(k) for k in ("mean_pct", "ci95", "wins", "losses", "ties", "label")},
                     "vs_reactive": {k: vr.get(k) for k in ("mean_pct", "ci95", "wins", "losses", "ties", "label")} if a != "reactive" else None})
    return rows


@router.get("/api/experiment/stress", tags=["experiment"])
def experiment_stress(city: str = "la_c4_central_wide"):
    """Calibration sweep, scenario-quality gate, oracle-headroom gates and the 7-arm comparison on the
    development and the evaluation seeds, for both research scenarios."""
    root = config.REPO / "results/v2x/stress" / city
    if not root.is_dir():
        return {"available": False, "city": city}
    cc = _read(config.REPO / "backend/app/protocols/controller_config.json") or {}
    stress = cc.get("stress_scenario") or {}
    sweeps = {}
    for sj in sorted(root.glob("summary_*.json")):
        s = _read(sj) or {}
        sweeps[sj.stem] = {"od_rule": s.get("od_rule"), "gate": s.get("gate"), "chosen_scale": s.get("chosen_scale"), "rule": s.get("rule"),
                           "points": [{"scale": pt["scale"], "STABLE": pt["STABLE"], "CONGESTED": pt["CONGESTED"], **{k: pt["mean"].get(k) for k in ("vehicles_loaded", "arrival_share", "teleport_rate", "jam_teleports", "tti", "mean_travel_time_s", "p95_travel_time_s", "loaded_mean_speed_mps", "util_p90")}} for pt in s.get("points", [])]}
    scenarios = {}
    for sc, text in (("A", "forecastable peak — demand rises to the calibrated level, no incident"), ("B", "unexpected incident — lane-speed cap on the busiest detector road")):
        entry = {"text": text}
        for ss in ("dev", "eval"):
            g = _read(root / f"scenario{sc}_oracle_gate_{ss}.json") or {}
            ptr = _read(root / f"scenario{sc}_learned_{ss}_report_pointer.json") or _read(root / f"scenario{sc}_oracle_{ss}_report_pointer.json") or {}
            rep = _read(config.REPO / ptr["run_dir"] / "report.json") if ptr.get("run_dir") else None
            entry[ss] = {"oracle_gate": {k: g.get(k) for k in ("status", "rule", "oracle_vs_reactive", "oracle_vs_baseline", "reactive_vs_baseline", "seeds", "fork_state_identical_across_arms", "computed_utc")} if g else None,
                         "arms": _arm_table(rep) if rep else [], "seeds": (rep or {}).get("seeds"), "fork_identical": (rep or {}).get("fork_state_identical_across_arms"),
                         "run_dir": ptr.get("run_dir"), "stress_level": g.get("stress_level") if g else None}
        scenarios[sc] = entry
    status = (_read(config.REPO / "results/v2x/controller_status.json") or {}).get("current") or {}
    low_load = config.REPO / "results/v2x/ORACLE_FORK_REPORT.md"
    return {"available": True, "city": city, "result_source": "RESEARCH_BENCHMARK", "demand": "SYNTHETIC_WHAT_IF scaled randomTrips on the real OSM network; METR-LA is speed-only so no flow calibration was possible",
            "stress_levels": stress, "sweeps": sweeps, "scenarios": scenarios, "controller_status": {k: status.get(k) for k in ("status", "FUTURE_INFORMATION_VALUE", "PREDICTIVE_TRAFFIC_BENEFIT", "arm", "seeds", "computed_utc", "rule")},
            "low_load_negative_result": str(low_load.relative_to(config.REPO)) if low_load.exists() else None, "report": "results/v2x/STRESS_REPORT.md"}
