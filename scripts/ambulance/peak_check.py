"""Step 2 check (2026-10-12): the ambulance arms on the corridor at the FULL recorded DhaTraX morning-peak counts.

The "Dhaka density" level of the thesis is the corridor demand (routeSampler fitted to DhaTraX's 07:00-08:00 counts at INT and BM,
core.simulation.ambulance.corridor) scaled DOWN to x0.78, the factor at which the INT section's simulated density sits inside the
recorded range (evidence/ambulance_rq2/dhaka_density/match.json). This check runs the same routes at x1.0, i.e. at the recorded
counts themselves (the hourly counts are read from calibration.json, not typed): 5 seeds x {no alert, alert, alert + pre-emption},
ITS-G5, every car equipped. Nothing of the saved study is touched: the runs go under evidence/ambulance_rq2/dhatrax_peak/.

    PYTHONPATH=.:backend python scripts/ambulance/peak_check.py [--seeds 11 12 13 14 15] [--share 1.0] [--tech its_g5]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO), str(REPO / "backend")]

from core.simulation.ambulance import corridor, service  # noqa: E402

OUT = REPO / "evidence/ambulance_rq2/dhatrax_peak"
ARMS = ("no_alert", "alert", "alert_preemption")


def recorded_counts() -> dict:
    """The hourly counts the corridor demand was fitted to, summed from the 12 five-minute counts per site in calibration.json."""
    cal = json.loads((corridor.EVIDENCE / "calibration.json").read_text())
    match = json.loads((corridor.EVIDENCE / "match.json").read_text())
    sites = {s["site"]: {"section": s["section"], "day": s["day"], "vehicles_per_hour": int(sum(s["counts"])), "five_minute_counts": len(s["counts"])} for s in cal["sites"]}
    return {"window": cal.get("window"), "sites": sites, "thesis_level_scale": match["chosen_scale"], "this_check_scale": 1.0,
            "calibration_sha256": hashlib.sha256((corridor.EVIDENCE / "calibration.json").read_bytes()).hexdigest()}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--wanted", type=int, default=5, help="seeds with all three arms completed (SUMO 1.27.1's bluelight device crashes on some seeds; as in the study, a crashed seed is recorded and the next one tried)")
    ap.add_argument("--first-seed", type=int, default=11)
    ap.add_argument("--max-seeds", type=int, default=40)
    ap.add_argument("--share", type=float, default=1.0)
    ap.add_argument("--tech", default="its_g5")
    ap.add_argument("--summarise", action="store_true", help="no new runs: build summary.json from the metrics.json files already on disk (a stopped check)")
    a = ap.parse_args(argv)
    OUT.mkdir(parents=True, exist_ok=True)
    log = open(OUT / "run.log", "a")

    def say(s: str) -> None:
        print(s, flush=True); log.write(s + "\n"); log.flush()

    counts = recorded_counts()
    say(f"PEAK CHECK {datetime.now(timezone.utc).isoformat()}: corridor at the recorded counts (scale 1.0; thesis level x{counts['thesis_level_scale']}), "
        f"{a.tech}, {int(a.share * 100)} % equipped, {a.wanted} complete seeds wanted from seed {a.first_seed}; recorded: " + ", ".join(f"{k} {v['vehicles_per_hour']} veh/h" for k, v in counts["sites"].items()))
    rows, crashed = [], []
    for seed in range(a.first_seed, a.first_seed + a.max_seeds):
        if len(rows) >= a.wanted:
            break
        row = {"seed": seed}
        for arm in ARMS:
            t0 = time.time()
            folder = OUT / "runs/dhaka/dhaka_density" / service.run_name(arm, None if arm == "no_alert" else a.tech, 0.0 if arm == "no_alert" else a.share, seed)
            if a.summarise:
                if not (folder / "metrics.json").exists():
                    break
                m = json.loads((folder / "metrics.json").read_text())
            else:
                m = service.run_one("dhaka", arm, None if arm == "no_alert" else a.tech, 0.0 if arm == "no_alert" else a.share, seed, "dhaka_density", root=OUT / "runs", scale=1.0)
            amb = m.get("ambulance") or {}
            row[arm] = {"travel_time_s": amb.get("travel_time_s"), "arrived": amb.get("arrived"), "state": m.get("state", "ok"), "crashed_after_s": m.get("crashed_after_s"),
                        "teleports": m.get("teleports"), "messages": m.get("messages"), "vehicles_alerted": m.get("vehicles_alerted"),
                        "junctions_preempted": len(m.get("junctions_preempted") or []), "wall_s": m.get("wall_s") if a.summarise else round(time.time() - t0, 1)}
            say(f"  seed {seed} {arm:17s}: travel {amb.get('travel_time_s')} s, arrived {amb.get('arrived')}, state {m.get('state', 'ok')}"
                f"{' at ' + str(m.get('crashed_after_s')) + ' s' if m.get('state') == 'sumo_crashed' else ''}, teleports {m.get('teleports')}, wall {row[arm]['wall_s']} s")
            if m.get("state") == "sumo_crashed":
                crashed.append({"seed": seed, "arm": arm, "crashed_after_s": m.get("crashed_after_s")})
                break
        if all(arm in row and row[arm]["state"] != "sumo_crashed" for arm in ARMS):
            rows.append(row)
    def saving(arm):
        return [r["no_alert"]["travel_time_s"] - r[arm]["travel_time_s"] for r in rows if r["no_alert"]["travel_time_s"] and r[arm]["travel_time_s"]]
    summary = {"generated_utc": datetime.now(timezone.utc).isoformat(), "label": "SIMULATION, corridor at the recorded DhaTraX counts (scale 1.0), not the thesis level",
               "recorded": counts, "tech": a.tech, "share": a.share, "seeds_completed": [r["seed"] for r in rows],
               "seeds_crashed_in_sumo": crashed, "crash_note": "SUMO 1.27.1's bluelight device segfault (evidence/emergency/dhaka/sumo_bluelight_crash.json); a crashed seed is recorded and the next tried, as in the study",
               "rows": rows,
               "arrived": {arm: sum(1 for r in rows if r[arm]["arrived"]) for arm in ARMS},
               "median_travel_s": {arm: (statistics.median(v) if (v := [r[arm]["travel_time_s"] for r in rows if r[arm]["travel_time_s"]]) else None) for arm in ARMS},
               "saving_s_vs_no_alert": {arm: {"values": saving(arm), "median": statistics.median(saving(arm)) if saving(arm) else None} for arm in ARMS[1:]}}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1))
    (OUT / "summary.sha256").write_text(hashlib.sha256((OUT / "summary.json").read_bytes()).hexdigest() + "  summary.json\n")
    say(json.dumps({k: summary[k] for k in ("arrived", "median_travel_s", "saving_s_vs_no_alert")}, indent=1))
    say("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
