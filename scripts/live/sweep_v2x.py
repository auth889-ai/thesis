"""make sweep-v2x (step I, 2026-10-11): the V2X equipped share 0 / 25 / 50 / 75 / 100 % x 5 seeds at Dhaka density, computed now with
the thesis's own run (core/simulation/ambulance/service.run_one, make-way v2), each run checked against the study's saved run with the
same settings (REPRODUCED / DIFFERENT / new), then a CSV and a plot under evidence/sweeps/.

    PYTHONPATH=.:backend python scripts/live/sweep_v2x.py [--arm alert_preemption|alert] [--tech its_g5] [--seeds 11 12 13 14 15] [--quick] [--workers 4]

Share 0 is the siren-only run (no alert), the baseline every saving is measured against. `--quick` = seeds 11 and 12 only (10 runs,
under 5 min on 4 workers). Outputs: evidence/sweeps/v2x_share[_quick].csv, .png, .json (sha256 printed). The saved study results are
never touched: the runs go to evidence/sweeps/runs/.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO), str(REPO / "backend")]
from core.simulation.live_jobs.runner import live_script  # noqa: E402

SHARES = (0.0, 0.25, 0.5, 0.75, 1.0)
OUT = REPO / "evidence/sweeps"


def one(arm: str, tech: str, share: float, seed: int) -> dict:
    from core.simulation.ambulance import service
    rv = live_script("run_v2x")
    demand, scale = rv.LEVELS["dhaka"]
    a, t, s = ("no_alert", None, 0.0) if share == 0 else (arm, tech, share)
    t0 = time.time()
    m = service.run_one("dhaka", a, t, s, seed, demand, root=OUT / "runs", scale=scale)
    sv = rv.saved(a, t, s, seed, demand, scale)
    tt = m["ambulance"]["travel_time_s"]
    check = "new: no saved run with these settings" if sv is None else ("REPRODUCED exactly" if sv["ambulance"]["travel_time_s"] == tt else f"DIFFERENT (saved {sv['ambulance']['travel_time_s']})")
    if not m["ambulance"]["arrived"]:                                   # SUMO 1.27.1's bluelight device can stop the run (evidence/emergency/dhaka/sumo_bluelight_crash.json)
        check += "; no arrival (SUMO stopped" + (", as in the saved run)" if sv is not None and not sv["ambulance"]["arrived"] else ")")
    return {"seed": seed, "share": share, "arm": a, "technology": t or "", "travel_time_s": tt, "arrived": m["ambulance"]["arrived"],
            "messages_sent": m.get("messages", {}).get("sent", 0), "messages_delivered": m.get("messages", {}).get("delivered", 0),
            "vehicles_alerted": m.get("vehicles_alerted", 0), "check": check, "real_s": round(time.time() - t0, 1)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--arm", default="alert_preemption", choices=["alert_preemption", "alert"])
    ap.add_argument("--tech", default="its_g5", choices=["its_g5", "c_v2x", "cellular_4g"])
    ap.add_argument("--seeds", type=int, nargs="+", default=[11, 12, 13, 14, 15])
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    seeds = a.seeds[:2] if a.quick else a.seeds
    jobs = [(a.arm, a.tech, sh, sd) for sd in seeds for sh in SHARES]
    print(f"SWEEP (RQ3, Dhaka density, SIMULATION, make-way v2): {a.arm} over {a.tech}, shares {[int(s * 100) for s in SHARES]} %, seeds {seeds}: {len(jobs)} runs computed now, {a.workers} at a time", flush=True)
    t0 = time.time()
    with ProcessPoolExecutor(a.workers) as ex:
        rows = list(ex.map(one, *zip(*jobs)))
    base = {r["seed"]: r["travel_time_s"] for r in rows if r["share"] == 0}
    for r in rows:
        r["no_alert_s"] = base.get(r["seed"])
        r["saved_s"] = None if r["travel_time_s"] is None or r["no_alert_s"] is None else round(r["no_alert_s"] - r["travel_time_s"], 1)
    OUT.mkdir(parents=True, exist_ok=True)
    tag = "_quick" if a.quick else ""
    cols = ["seed", "share", "arm", "technology", "travel_time_s", "no_alert_s", "saved_s", "arrived", "messages_sent", "messages_delivered", "vehicles_alerted", "check", "real_s"]
    with (OUT / f"v2x_share{tag}.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows({k: r[k] for k in cols} for r in rows)
    summary = []
    for sh in SHARES[1:]:
        sv = [r["saved_s"] for r in rows if r["share"] == sh and r["saved_s"] is not None]
        summary.append({"share": sh, "seeds": len(sv), "saved_s_median": round(statistics.median(sv), 1) if sv else None, "saved_s_mean": round(statistics.fmean(sv), 1) if sv else None,
                        "saved_s_min": min(sv) if sv else None, "saved_s_max": max(sv) if sv else None, "slower_runs": sum(x < 0 for x in sv),
                        "no_arrival_runs": sum(1 for r in rows if r["share"] == sh and not r["arrived"])})
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(7, 4.2))
    for sd in seeds:
        pts = [(r["share"] * 100, r["saved_s"]) for r in rows if r["seed"] == sd and r["share"] > 0 and r["saved_s"] is not None]
        if pts:
            ax.plot(*zip(*pts), "o-", alpha=0.35, label=f"seed {sd}")
    med = [(s["share"] * 100, s["saved_s_median"]) for s in summary if s["saved_s_median"] is not None]
    if med:
        ax.plot(*zip(*med), "k-", lw=2.5, label="median")
    ax.axhline(0, color="grey", lw=0.8)
    ax.set_xlabel("cars with the alert, %"); ax.set_ylabel("ambulance time saved vs no alert, s")
    ax.set_title(f"SIMULATION: {a.arm} over {a.tech}, Dhaka density, seeds {seeds}, computed {datetime.now().strftime('%Y-%m-%d %H:%M')}", fontsize=9)
    ax.legend(fontsize=8); fig.tight_layout(); fig.savefig(OUT / f"v2x_share{tag}.png", dpi=130)
    checks = [r["check"] for r in rows]
    body = {"what": "V2X equipped-share sweep at Dhaka density, computed now, each run checked against the study's saved run", "label": "SIMULATION", "arm": a.arm, "technology": a.tech,
            "seeds": seeds, "shares": list(SHARES), "runs": len(rows), "reproduced": sum(c.startswith("REPRODUCED") for c in checks), "different": sum(c.startswith("DIFFERENT") for c in checks),
            "new": sum(c.startswith("new") for c in checks), "no_arrival": sum(not r["arrived"] for r in rows), "summary": summary, "rows": rows, "real_s": round(time.time() - t0), "csv": f"evidence/sweeps/v2x_share{tag}.csv", "png": f"evidence/sweeps/v2x_share{tag}.png",
            "when": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    p = OUT / f"v2x_share{tag}.json"
    p.write_text(json.dumps(body, indent=1))
    for s in summary:
        print(f"  share {int(s['share'] * 100):3d} %: median saving {s['saved_s_median']} s (mean {s['saved_s_mean']}, min {s['saved_s_min']}, max {s['saved_s_max']}; slower {s['slower_runs']} of {s['seeds']}; no arrival {s['no_arrival_runs']})")
    print(f"  THESIS CHECK: {body['reproduced']} of {len(rows)} runs REPRODUCED exactly, {body['different']} DIFFERENT, {body['new']} new; {body['no_arrival']} with no arrival (SUMO stopped); {body['real_s']} s in all")
    print(f"  {body['csv']}, {body['png']}, sha256 {hashlib.sha256(p.read_bytes()).hexdigest()} {p.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
