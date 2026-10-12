"""Does steering traffic with a forecast help? The live twin (core/simulation/live_twin) with steering on, following SUMO's
device.rerouting: every simulated minute the forecaster's 15-minute prediction sets each detector road's travel time
(traci.edge.adaptTraveltime) and an informed share of vehicles reroute on it (traci.vehicle.rerouteTraveltime).

Arms, all on the same seeds (paired) and the same informed vehicles:
  off        no rerouting
  current    rerouting on the edges' current travel times (SUMO's own idea, no forecast)
  no_change  the last observed speed as the prediction
  online     River, learning live
  chronos    Chronos-Bolt zero-shot
Measured, in the exact window from the end of the 15-minute warm-up to the cut-off: every trip that departed in it (the cohort), its
travel time if it arrived, else its time so far at the cut-off. The cohort mean is the primary measure: it does not drop the trips a
reroute made longer. The mean of finished trips alone is kept as a secondary number (it favours whatever finishes fewer, longer trips).
Writes evidence/live_twin/steer_compare.json (sha256 printed).

    PYTHONPATH=.:backend python scripts/live_twin/steer_compare.py [--seeds 11 12 13 14 15] [--minutes 60] [--share 0.3]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import time
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone

from core.common.paths import REPO

ARMS = ("off", "current", "no_change", "online", "chronos")


def one(arm: str, seed: int, minutes: int, share: float) -> dict:
    from core.simulation.live_twin import session as ses
    steer = None if arm == "off" else {"forecaster": arm, "share": share}
    s = ses.Session("dhaka", f"steer-{arm}-{seed}", speed=1e9, sync_forecasts=True, steer=steer, record_trips=True, chronos=arm == "chronos")
    s.seed = seed
    t0 = time.time()
    s.start()
    while s.status in ("starting", "warming", "running") and s.t < minutes * 60:
        time.sleep(1)
        s.last_seen = time.time()
    s.stop(); s.thread.join(60)
    start, cut = ses.WARMUP_MIN * 60, minutes * 60          # an exact window, the same for every arm (the run itself stops a little later)
    done = [a - d for d, a in s.trips["done"] if start <= d <= cut and a <= cut]
    # the cohort: every trip that departed in the window; one still driving at the cut counts its time so far (cut - depart)
    open_ = [cut - d for d, a in s.trips["done"] if start <= d <= cut and a > cut] + [cut - d for d in s.trips["depart"].values() if start <= d <= cut]
    cohort = done + open_
    return {"arm": arm, "seed": seed, "status": s.status, "message": s.message, "end_s": s.t, "real_s": round(time.time() - t0, 1),
            "cohort_trips": len(cohort), "cohort_mean_s": round(statistics.fmean(cohort), 2) if cohort else None,
            "trips_done": len(done), "mean_travel_s": round(statistics.fmean(done), 2) if done else None,
            "median_travel_s": round(statistics.median(done), 2) if done else None, "still_driving": len(open_), "steer_stats": s.steer_stats}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+", default=[11, 12, 13, 14, 15])
    ap.add_argument("--minutes", type=int, default=60)
    ap.add_argument("--share", type=float, default=0.3)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    jobs = [(arm, seed) for seed in a.seeds for arm in ARMS]
    with ProcessPoolExecutor(a.workers) as ex:
        rows = list(ex.map(one, [j[0] for j in jobs], [j[1] for j in jobs], [a.minutes] * len(jobs), [a.share] * len(jobs)))
    by = {(r["arm"], r["seed"]): r for r in rows}
    summary = []
    ok = [s for s in a.seeds if all(by[(arm, s)]["status"] == "stopped" and by[(arm, s)]["cohort_mean_s"] is not None for arm in ARMS)]
    for arm in ARMS:
        cm = [by[(arm, s)]["cohort_mean_s"] for s in ok]
        diffs = [by[(arm, s)]["cohort_mean_s"] - by[("off", s)]["cohort_mean_s"] for s in ok]
        fin = [by[(arm, s)]["mean_travel_s"] for s in ok if by[(arm, s)]["mean_travel_s"] is not None]
        summary.append({"arm": arm, "seeds": len(ok), "cohort_mean_s": round(statistics.fmean(cm), 2) if cm else None,
                        "sd_over_seeds": round(statistics.stdev(cm), 2) if len(cm) > 1 else None,
                        "paired_diff_vs_off_s": round(statistics.fmean(diffs), 2) if diffs else None,
                        "seeds_better_than_off": sum(d < 0 for d in diffs),
                        "finished_mean_s": round(statistics.fmean(fin), 2) if fin else None,
                        "finished_trips_mean": round(statistics.fmean(by[(arm, s)]["trips_done"] for s in ok), 1) if ok else None,
                        "still_driving_mean": round(statistics.fmean(by[(arm, s)]["still_driving"] for s in ok), 1) if ok else None})
    body = {"what": "live twin steered by a forecast (SUMO device.rerouting style): mean travel time of trips departing after the warm-up",
            "label": "SIMULATION", "city": "dhaka", "demand": "RQ2b corridor demand at scale 0.78, generated traffic", "seeds": a.seeds,
            "minutes": a.minutes, "warmup_min": 15, "informed_share": a.share, "summary": summary, "rows": rows,
            "caveat": "primary: cohort_mean_s (all trips that departed in the window; unfinished counted to the cut-off). finished_mean_s alone is biased toward short trips",
            "when": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    out = REPO / "evidence/live_twin/steer_compare.json"
    out.write_text(json.dumps(body, indent=1))
    for r in summary:
        print(r)
    print("sha256", hashlib.sha256(out.read_bytes()).hexdigest(), out.relative_to(REPO))


if __name__ == "__main__":
    main()
