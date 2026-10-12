"""make run-routing-quick (step L, 2026-10-11): the RQ2 closed loop (forecast -> route costs -> rerouting in SUMO) run live on the
Los Angeles twin with the thesis's own settings, and checked against the saved run's numbers seed by seed.

    PYTHONPATH=.:backend python scripts/live/run_routing_quick.py [--seeds 201 202] [--arms baseline,reactive,predictive_corrected_v2x] [--quick]

Settings = the saved run's PROTOCOL (results/v2x/closed_loop/la_c4_central_wide_prepeak_ideal_p30_cfgea08dddedc14_stressA_eval_fork1200_x8_peak_arterial):
city la_c4_central_wide, moment prepeak (a held-out weekday), ideal V2X link, 30 % penetration, demand x8 peak on the arterials, every
arm started from one SUMO state saved at 1 200 s, 4 800 s in all, Graph WaveNet's forecast table every 300 s. The run itself is
`core.simulation.closed_loop.control.closed_loop.run_point` with reuse off: every arm is simulated now.
THESIS CHECK: for each seed and arm, total vehicle-hours (incl. never inserted) and arrivals against the saved report.json:
REPRODUCED exactly / DIFFERENT (with the difference). Time on this machine, from the saved run's own wall clocks: baseline about
70 s, each V2X arm about 5.5 min per seed, so two seeds with three arms take about 25 min. `--quick` runs ONE seed with baseline and
predictive_corrected_v2x only (about 6.5 min) and is checked the same way; it is not the full RQ2 evidence.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO), str(REPO / "backend")]
SAVED = REPO / "results/v2x/closed_loop/la_c4_central_wide_prepeak_ideal_p30_cfgea08dddedc14_stressA_eval_fork1200_x8_peak_arterial"
SETTINGS = dict(city="la_c4_central_wide", profile="ideal", penetration=0.3, moment="prepeak", round_s=300, horizon_min=15, status_period_s=10,
                duration_s=4800, fork_t0=1200, demand_scale=8.0, demand_profile="peak", od_rule="arterial")
METRICS = ("total_vehicle_hours_incl_never_inserted", "arrived", "teleports")


def check(rep: dict, saved: dict) -> list[dict]:
    by = {(p["seed"], arm): a["metrics"] for p in saved["per_seed"] for arm, a in p["arms"].items()}
    out = []
    for p in rep["per_seed"]:
        for arm, a in p["arms"].items():
            s = by.get((p["seed"], arm))
            if s is None:
                out.append({"seed": p["seed"], "arm": arm, "check": "new: the saved run has no such seed/arm"}); continue
            diffs = {m: (a["metrics"].get(m), s.get(m)) for m in METRICS if a["metrics"].get(m) != s.get(m)}
            out.append({"seed": p["seed"], "arm": arm, "check": "REPRODUCED exactly" if not diffs else "DIFFERENT", "differences": diffs,
                        "vehicle_hours": a["metrics"].get("total_vehicle_hours_incl_never_inserted"), "wall_s": round(a["metrics"].get("wall_s", 0))})
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seeds", type=int, nargs="+", default=[201, 202])
    ap.add_argument("--arms", default="baseline,reactive,predictive_corrected_v2x")
    ap.add_argument("--quick", action="store_true", help="one seed, baseline and predictive_corrected_v2x only (about 6.5 min)")
    a = ap.parse_args()
    seeds, arms = (a.seeds[:1], ("baseline", "predictive_corrected_v2x")) if a.quick else (a.seeds, tuple(a.arms.split(",")))
    from core.simulation.closed_loop.control import closed_loop as cl
    saved = json.loads((SAVED / "report.json").read_text())
    print(f"LIVE RUN (RQ2 closed loop, Los Angeles twin, SIMULATION): seeds {seeds}, arms {list(arms)}; {SETTINGS['demand_scale']:g}x peak demand, fork at {SETTINGS['fork_t0']} s,"
          f" {SETTINGS['duration_s']} s; Graph WaveNet forecasts every {SETTINGS['round_s']} s. Every arm is simulated now (reuse off).", flush=True)
    t0 = time.time()
    rep = cl.run_point(seeds=seeds, arms=arms, tag=f"quick{int(t0)}", reuse=False, **SETTINGS)
    rows = check(rep, saved)
    for r in rows:
        print(f"  seed {r['seed']} {r['arm']:26s} vehicle-hours {r['vehicle_hours']:.1f}  wall {r['wall_s']} s  THESIS CHECK: {r['check']}"
              + (f"  {r['differences']}" if r.get("differences") else ""))
    ok = all(r["check"].startswith("REPRODUCED") for r in rows)
    print(f"  total {time.time() - t0:.0f} s; run folder {rep['run_dir']}; saved run {SAVED.relative_to(REPO)}")
    print(f"THESIS CHECK: {'REPRODUCED exactly' if ok else 'DIFFERENT'} ({sum(r['check'].startswith('REPRODUCED') for r in rows)} of {len(rows)} seed-arms)")
    out = REPO / "evidence/live_runs/routing_quick"
    out.mkdir(parents=True, exist_ok=True)
    (out / "last_run.json").write_text(json.dumps({"seeds": seeds, "arms": list(arms), "quick": a.quick, "settings": SETTINGS, "rows": rows, "ok": ok, "real_s": round(time.time() - t0), "run_dir": rep["run_dir"]}, indent=1))
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
