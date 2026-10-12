"""make compare-signals (step S, 2026-10-11): four signal controllers on the same seeds and traffic level, headless, every run computed now:
fixed time (SUMO's programs), Q-learning (sumo-rl's frozen tables, in its venv), Max-Pressure (Varaiya 2013), Max-Pressure + EV priority.
Measures per seed: the ambulance's travel time, the mean time loss of every other vehicle ("mean delay"), vehicle-hours, the queue at the
signals. Fixed time and Q-learning are checked against the study's saved runs (REPRODUCED / DIFFERENT); Max-Pressure is new.

    PYTHONPATH=.:backend python scripts/live/compare_signals.py [--level dhaka] [--seeds 11 12 13 14 15] [--workers 3] [--quick]

Outputs: evidence/signals/controllers/compare.{csv,json,png} (sha256 printed); runs under evidence/signals/controllers/runs/.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import statistics
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO), str(REPO / "backend"), str(REPO / "scripts/live")]
import run_signals as rs  # noqa: E402

OUT = REPO / "evidence/signals/controllers"
ARMS = ("fixed", "rl", "maxpressure", "maxpressure_ev")
NAMES = {"fixed": "fixed time", "rl": "Q-learning (sumo-rl)", "maxpressure": "Max-Pressure", "maxpressure_ev": "Max-Pressure + EV priority"}
KEYS = ("travel_time_s", "mean_time_loss_s", "total_vehicle_hours", "queue_at_signals", "blocked_s")


def one(arm: str, seed: int, demand: str, scale: float) -> dict:
    t0 = time.time()
    if arm == "fixed":
        from core.simulation.ambulance import service
        m = service.run_one("dhaka", "no_alert", None, 0.0, seed, demand, root=OUT / "runs", scale=scale, observe=True)
    else:
        from core.simulation.ambulance import mp_signals
        m = mp_signals.run(scale, seed, arm, root=OUT / "runs", demand=demand)
    return {"arm": arm, "seed": seed, **rs.measures(m), "state": m.get("state"), "real_s": round(time.time() - t0, 1)}


def rl_one(seed: int, level: str) -> dict:
    """The Q-learning arm runs in the sumo-rl venv (NumPy < 2) through run_signals.py --side rl, as the live run does."""
    import sumo
    t0 = time.time()
    env = os.environ | {"PYTHONPATH": f"{REPO}:{REPO / 'backend'}", "SUMO_HOME": os.path.dirname(sumo.__file__), "DHAKAFLOW_NO_OBSERVATORY": "1"}
    (rs.OUT / "last_rl.json").unlink(missing_ok=True)
    rs.OUT.mkdir(parents=True, exist_ok=True)
    subprocess.run([str(rs.RL_PY), str(REPO / "scripts/live/run_signals.py"), "--level", level, "--seed", str(seed), "--no-gui", "--side", "rl"], env=env, check=True, capture_output=True)
    got = json.loads((rs.OUT / "last_rl.json").read_text())
    return {"arm": "rl", "seed": seed, **{k: got.get(k) for k in rs.measures({"ambulance": {"travel_time_s": None}, "why": {"queue_at_signals": None, "blocked_s": None, "queue_peaks": None}})}, "state": got.get("state"), "real_s": round(time.time() - t0, 1)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--level", default="dhaka", choices=list(rs.LEVELS))
    ap.add_argument("--seeds", type=int, nargs="+", default=[11, 12, 13, 14, 15])
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--quick", action="store_true", help="seeds 11 and 12 only")
    a = ap.parse_args()
    seeds = a.seeds[:2] if a.quick else a.seeds
    demand, scale = rs.LEVELS[a.level]
    print(f"COMPARE (RQ3 signals, SIMULATION, level {a.level} = {demand} x{scale:g}, seeds {seeds}): {', '.join(NAMES.values())}; every run computed now.", flush=True)
    t0 = time.time()
    jobs = [(arm, sd) for sd in seeds for arm in ("fixed", "maxpressure", "maxpressure_ev")]
    with ProcessPoolExecutor(a.workers) as ex:
        fut = ex.map(one, [j[0] for j in jobs], [j[1] for j in jobs], [demand] * len(jobs), [scale] * len(jobs))
        rl_rows = [rl_one(sd, a.level) for sd in seeds]                 # serial, in the venv, alongside the pool
        rows = list(fut) + rl_rows
    for r in rows:
        if r["arm"] in ("fixed", "rl"):
            w = rs.saved(r["arm"], r["seed"], demand, scale)
            r["check"] = "new: no saved run" if w is None else ("REPRODUCED exactly" if all(w[k] == r[k] for k in rs.KEYS) else "DIFFERENT")
        else:
            r["check"] = "new (Max-Pressure, step S)"
    OUT.mkdir(parents=True, exist_ok=True)
    cols = ["arm", "seed", *KEYS, "ev_priority_requests", "state", "check", "real_s"]
    with (OUT / "compare.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows({k: r.get(k) for k in cols} for r in rows)
    summary = {}
    for arm in ARMS:
        rr = [r for r in rows if r["arm"] == arm]
        summary[arm] = {"name": NAMES[arm], "runs": len(rr), "arrived": sum(r["travel_time_s"] is not None for r in rr)}
        for k in KEYS:
            v = [r[k] for r in rr if r.get(k) is not None]
            summary[arm][k] = {"mean": round(statistics.fmean(v), 2), "median": round(statistics.median(v), 2), "min": min(v), "max": max(v), "n": len(v)} if v else None
    base = {r["seed"]: r for r in rows if r["arm"] == "fixed"}
    paired = {}
    for arm in ("rl", "maxpressure", "maxpressure_ev"):
        d_amb = [r["travel_time_s"] - base[r["seed"]]["travel_time_s"] for r in rows if r["arm"] == arm and r["travel_time_s"] is not None and base[r["seed"]]["travel_time_s"] is not None]
        d_loss = [r["mean_time_loss_s"] - base[r["seed"]]["mean_time_loss_s"] for r in rows if r["arm"] == arm and r.get("mean_time_loss_s") is not None and base[r["seed"]].get("mean_time_loss_s") is not None]
        paired[arm] = {"ambulance_vs_fixed_s": {"mean": round(statistics.fmean(d_amb), 1), "sd": round(statistics.stdev(d_amb), 1) if len(d_amb) > 1 else None, "better": sum(x < 0 for x in d_amb), "n": len(d_amb)} if d_amb else None,
                       "others_time_loss_vs_fixed_s": {"mean": round(statistics.fmean(d_loss), 1), "sd": round(statistics.stdev(d_loss), 1) if len(d_loss) > 1 else None, "better": sum(x < 0 for x in d_loss), "n": len(d_loss)} if d_loss else None}
    checks = [r["check"] for r in rows if r["arm"] in ("fixed", "rl")]
    body = {"what": "Signal controllers compared on the Dhaka corridor: fixed time, Q-learning, Max-Pressure, Max-Pressure + EV priority; same seeds and traffic level; computed now",
            "label": "SIMULATION", "level": a.level, "demand": demand, "scale": scale, "seeds": seeds, "summary": summary, "paired_vs_fixed": paired, "rows": rows,
            "reproduced": sum(c.startswith("REPRODUCED") for c in checks), "checked": len(checks), "real_s": round(time.time() - t0), "when": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "csv": "evidence/signals/controllers/compare.csv", "png": "evidence/signals/controllers/compare.png"}
    (OUT / "compare.json").write_text(json.dumps(body, indent=1))
    plot(body, OUT / "compare.png")
    print(f"  {'controller':30}{'ambulance s (mean)':>20}{'others time loss s':>20}{'vehicle-hours':>16}{'queue':>8}")
    for arm in ARMS:
        s = summary[arm]
        print(f"  {s['name']:30}{(s['travel_time_s'] or {}).get('mean', '-'):>20}{(s['mean_time_loss_s'] or {}).get('mean', '-'):>20}{(s['total_vehicle_hours'] or {}).get('mean', '-'):>16}{(s['queue_at_signals'] or {}).get('mean', '-'):>8}  (arrived {s['arrived']} of {s['runs']})")
    for arm, p in paired.items():
        print(f"  {NAMES[arm]} vs fixed: ambulance {p['ambulance_vs_fixed_s']}  others' time loss {p['others_time_loss_vs_fixed_s']}")
    print(f"  THESIS CHECK: fixed time and Q-learning {body['reproduced']} of {body['checked']} runs REPRODUCED exactly; Max-Pressure arms are new. {body['real_s']} s in all")
    print(f"  sha256 {hashlib.sha256((OUT / 'compare.json').read_bytes()).hexdigest()} evidence/signals/controllers/compare.json; {body['png']}")
    return 0


def plot(body: dict, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    seeds = body["seeds"]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4))
    for ax, key, title in zip(axes, ("travel_time_s", "mean_time_loss_s"), ("ambulance travel time, s", "mean time loss of every other vehicle, s")):
        w = 0.8 / len(ARMS)
        for i, arm in enumerate(ARMS):
            vals = [next((r[key] for r in body["rows"] if r["arm"] == arm and r["seed"] == sd), None) for sd in seeds]
            ax.bar([j + i * w for j in range(len(seeds))], [v if v is not None else 0 for v in vals], w, label=NAMES[arm])
            for j, v in enumerate(vals):
                if v is None:
                    ax.text(j + i * w, 1, "x", ha="center", fontsize=8)
        ax.set_xticks([j + w * (len(ARMS) - 1) / 2 for j in range(len(seeds))]); ax.set_xticklabels([f"seed {sd}" for sd in seeds]); ax.set_title(title, fontsize=9); ax.grid(axis="y", alpha=0.3)
    axes[0].legend(fontsize=7)
    fig.suptitle(f"SIMULATION: signal controllers, Dhaka corridor, level {body['level']} (x{body['scale']:g}); x = SUMO stopped (bluelight device)", fontsize=9)
    fig.tight_layout(); fig.savefig(path, dpi=130)


if __name__ == "__main__":
    sys.exit(main())
