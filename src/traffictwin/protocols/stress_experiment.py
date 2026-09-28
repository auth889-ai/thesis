#!/usr/bin/env python3
"""CONGESTED TRAFFIC EXPERIMENT — two research scenarios on the calibrated stress level, ORACLE SANITY FIRST.

    python src/pipeline/v2x/stress_experiment.py --scenario A --stage oracle          # baseline / reactive / oracle from one identical fork
    python src/pipeline/v2x/stress_experiment.py --scenario A --stage learned         # refused unless the oracle gate PASSED
    python src/pipeline/v2x/stress_experiment.py --scenario B --stage oracle          # incident in the stress scenario

Scenario A  FORECASTABLE CONGESTION: demand profile `peak` (0-600 s normal · 600-1500 s rising · 1500-2400 s
            the bottleneck develops · 2400-3600 s peak), every arm forked from ONE saved SUMO state at
            fork_t0 (in the rising phase, before the deterioration). Information sources compete on the same
            optimizer, channel and budget.
Scenario B  UNEXPECTED INCIDENT in the stress scenario: uniform demand at the calibrated level, a lane-speed
            cap on the corridor's busiest DIRECT detector edge at incident_t, fork before the incident.

Frozen protocol
    stress level      src/pipeline/v2x/controller_config.json → stress_scenario[<city>:uniform:<od_rule>] written by
                      stress_sweep.py on DEVELOPMENT seeds; the experiment refuses to run if its gate is not
                      VALID_TRAFFIC_STRESS_CASE (a rejected scenario is a result, not something to tune away)
    stage oracle      arms baseline, reactive, oracle_v2x. ORACLE_HEADROOM passes only when oracle_v2x beats
                      reactive on total vehicle-hours with a paired 95 % CI that excludes zero (label BETTER)
    stage learned     persistence_v2x, predictive_v2x, predictive_corrected_v2x, random_v2x — only after
                      ORACLE_HEADROOM passed on the development seeds; evaluation seeds only after that
    seeds             development 101-103 (used for calibration and the oracle gate), evaluation 201-205
                      (never used to choose anything)

Nothing here modifies a result: the gate is computed from report.json and written next to it.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from traffictwin.paths import REPO
sys.path.insert(0, str(REPO))

from pipeline.v2x import closed_loop as cl        # noqa: E402

KEY = "total_vehicle_hours_incl_never_inserted"
PASS_LABELS = {"HELPED", "BETTER"}                       # src/pipeline/routing/oracle_gate.paired() labels a lower-is-better metric HELPED / HURT / INCONCLUSIVE
# Fixed Scenario A evaluation: policy mechanics are identical; only the information source varies.
STAGES = {"oracle": ("baseline", "reactive", "oracle_v2x"), "learned": ("baseline", "reactive", "persistence_v2x", "predictive_v2x", "oracle_v2x", "random_v2x")}
SCENARIOS = {"A": {"profile": "peak", "fork_t0": 1200, "duration_s": 4800, "incident": None, "text": "forecastable congestion — demand rises to the calibrated level; no incident"},
             "B": {"profile": "uniform", "fork_t0": 1200, "duration_s": 4800, "incident_t": 1500, "incident_cap_mps": 2.0, "text": "unexpected incident — lane-speed cap on the busiest DIRECT edge at 1500 s"}}


def stress_level(city: str, od_rule: str) -> dict:
    cc = json.loads((REPO / "src/pipeline/v2x/controller_config.json").read_text())
    key = f"{city}:uniform:{od_rule}"
    lvl = (cc.get("stress_scenario") or {}).get(key)
    if not lvl:
        raise SystemExit(f"no calibrated stress level for {key}: run src/pipeline/v2x/stress_sweep.py first")
    return lvl


def incident_edge(city: str) -> str:
    f = REPO / "results/v2x/corridor_diversity" / city / "incident_edge.json"
    if f.exists():
        return json.loads(f.read_text())["edge"]
    c2 = REPO / "results/v2x/corridor_diversity/case2_incident.json"
    if city == "la_c2_hollywood_101_5" and c2.exists():
        return json.loads(c2.read_text())["edge"]
    raise SystemExit(f"no incident edge recorded for {city}")


def oracle_gate(rep: dict) -> dict:
    st = ((rep.get("paired") or {}).get("oracle_v2x_vs_reactive") or {}).get(KEY) or {}
    passed = st.get("label") in PASS_LABELS and (st.get("mean_pct") or 0) < 0 and (st.get("ci95") or [0, 0])[1] < 0
    return {"gate": "ORACLE_HEADROOM", "status": "PASSED" if passed else "FAILED", "rule": "oracle_v2x must beat reactive on total vehicle-hours with a paired 95 % CI that excludes zero (paired() label HELPED)",
            "oracle_vs_reactive": st, "oracle_vs_baseline": ((rep.get("paired") or {}).get("oracle_v2x_vs_baseline") or {}).get(KEY), "reactive_vs_baseline": ((rep.get("paired") or {}).get("reactive_vs_baseline") or {}).get(KEY),
            "seeds": rep.get("seeds"), "run_dir": rep.get("run_dir"), "fork_state_identical_across_arms": rep.get("fork_state_identical_across_arms"), "computed_utc": datetime.now(timezone.utc).isoformat()}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--scenario", choices=sorted(SCENARIOS), required=True); p.add_argument("--stage", choices=sorted(STAGES), default="oracle")
    p.add_argument("--city", default="la_c2_hollywood_101_5"); p.add_argument("--od-rule", dest="od_rule", default="arterial", choices=sorted(cl.OD_RULES))
    p.add_argument("--seeds", default="101,102,103", help="development seeds; pass 201,202,203,204,205 for the evaluation seeds only after the development gate passed")
    p.add_argument("--profile", default="ideal", help="V2X channel profile"); p.add_argument("--penetration", type=float, default=0.3)
    p.add_argument("--run-tag", default="", help="provenance-only suffix for a fresh immutable run directory")
    p.add_argument("--allow-rejected", action="store_true", help="run on a scenario whose stress gate FAILED (diagnostics only; the report is marked REJECTED_SCENARIO)")
    a = p.parse_args(); seeds = [int(x) for x in a.seeds.split(",")]; S = SCENARIOS[a.scenario]
    lvl = stress_level(a.city, a.od_rule)
    if lvl["gate"] != "VALID_TRAFFIC_STRESS_CASE" and not a.allow_rejected:
        raise SystemExit(f"stress gate for {a.city}:{a.od_rule} is {lvl['gate']} (chosen scale {lvl['chosen_scale']}): the scenario is REJECTED; nothing to test (use --allow-rejected for diagnostics)")
    out = REPO / "results/v2x/stress" / a.city; out.mkdir(parents=True, exist_ok=True)
    is_eval = all(s >= 200 for s in seeds)
    if a.stage == "learned":
        g = out / f"scenario{a.scenario}_oracle_gate_dev.json"
        if not g.exists() or json.loads(g.read_text())["status"] != "PASSED":
            raise SystemExit(f"stage learned refused: ORACLE_HEADROOM on the development seeds is {'missing' if not g.exists() else json.loads(g.read_text())['status']} for scenario {a.scenario} — no forecasting model is worth testing where perfect future information cannot beat reactive routing")
    if is_eval:
        g = out / f"scenario{a.scenario}_oracle_gate_dev.json"
        if not g.exists() or json.loads(g.read_text())["status"] != "PASSED":
            raise SystemExit("evaluation seeds refused: the development oracle gate has not passed")
    inc = [(incident_edge(a.city), float(S["incident_t"]), float(S["incident_cap_mps"]))] if a.scenario == "B" else None      # (edge, t_start_s, cap_mps) tuples, as protocol() expects
    tag = "_".join(x for x in (f"stress{a.scenario}{'_eval' if is_eval else ''}", a.run_tag) if x)
    print(f"[stress-exp] scenario {a.scenario} ({S['text']}) · {a.city} · scale {lvl['chosen_scale']}x · OD {a.od_rule} · stage {a.stage} · seeds {seeds} · fork {S['fork_t0']} s · incident {inc}", flush=True)
    rep = cl.run_point(a.city, seeds, a.profile, a.penetration, "prepeak", STAGES[a.stage], tag=tag, reuse=False, duration_s=S["duration_s"], incident=inc, fork_t0=S["fork_t0"],
                       demand_scale=float(lvl["chosen_scale"]), demand_profile=S["profile"], od_rule=a.od_rule)
    gate = oracle_gate(rep); gate.update({"scenario": a.scenario, "scenario_text": S["text"], "stage": a.stage, "stress_level": lvl, "od_rule": a.od_rule, "seed_set": "evaluation" if is_eval else "development", "scenario_gate": lvl["gate"]})
    gf = out / f"scenario{a.scenario}_oracle_gate_{'eval' if is_eval else 'dev'}.json"
    if a.stage == "oracle" or not gf.exists():
        gf.write_text(json.dumps(gate, indent=1, default=str))
    (out / f"scenario{a.scenario}_{a.stage}_{'eval' if is_eval else 'dev'}_report_pointer.json").write_text(json.dumps({"run_dir": rep.get("run_dir"), "arms": list(STAGES[a.stage]), "gate": gate["status"]}, indent=1))
    print(f"[stress-exp] ORACLE_HEADROOM {gate['status']}: oracle vs reactive {gate['oracle_vs_reactive']}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
