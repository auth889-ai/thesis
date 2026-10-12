"""Does SUMO stop in the live twin when an ambulance drives? N twins (seeds from the clock, as the page), each: warm-up, one ambulance
click at the city's ambulance origin (to the hospital), run until the ambulance arrives or MAX_S simulated seconds after the click.
Records each twin's seed, whether SUMO stopped (and its exit code), the ambulance's state and time, and the alert counts.
Writes evidence/live_twin/crash_check.json and prints its sha256.

    PYTHONPATH=.:backend python scripts/live_twin/crash_check.py [--twins 20]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import datetime, timezone

from core.common.paths import REPO
from core.simulation.live_twin import session as ses

MAX_S = 1800


def one(i: int) -> dict:
    s = ses.Session("dhaka", f"crash-check-{i}", speed=1e9)
    s.start()
    while s.status in ("starting", "warming"):
        time.sleep(0.2)
    o = s.cfg.emergency.origin
    s.command({"cmd": "ambulance", "lon": o.lon, "lat": o.lat})
    t_click = s.t
    while s.status == "running" and s.t < t_click + MAX_S:
        time.sleep(0.2)
        s.last_seen = time.time()
        a = s.amb
        if a is not None and a.run.state == "arrived":
            break
    counts = s._counts()["ambulance"]
    row = {"twin": i, "seed": s.seed, "status": s.status, "sumo_stopped": s.status == "failed", "message": s.message,
           "bluelight": s.amb_cfg["ambulance"]["vtype"]["bluelight"], "sim_s_after_click": round(s.t - t_click),
           "ambulance": counts and {k: counts[k] for k in ("state", "time_so_far_s", "messages", "cars_alerted")},
           "refused": [e["text"] for e in s.events if e["kind"] in ("refused", "error")]}
    s.stop()
    s.thread.join(30)
    return row


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--twins", type=int, default=20)
    a = ap.parse_args()
    rows = []
    for i in range(a.twins):
        r = one(i)
        rows.append(r)
        print(f"twin {i:2d} seed {r['seed']} sumo_stopped={r['sumo_stopped']} ambulance={r['ambulance'] and r['ambulance']['state']} "
              f"time={r['ambulance'] and r['ambulance']['time_so_far_s']} s", flush=True)
        time.sleep(1.1)                                          # the next twin's clock seed differs
    body = {"what": "live twin crash check: one ambulance click per twin, ambulance without SUMO's bluelight device (live twin only)",
            "city": "dhaka", "twins": len(rows), "sumo_stopped": sum(r["sumo_stopped"] for r in rows),
            "ambulances_arrived": sum(bool(r["ambulance"] and r["ambulance"]["state"] == "arrived") for r in rows),
            "distinct_seeds": len({r["seed"] for r in rows}), "max_s_after_click": MAX_S, "rows": rows,
            "when": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    out = REPO / "evidence/live_twin/crash_check.json"
    out.write_text(json.dumps(body, indent=1))
    print(json.dumps({k: body[k] for k in ("twins", "sumo_stopped", "ambulances_arrived", "distinct_seeds")}))
    print("sha256", hashlib.sha256(out.read_bytes()).hexdigest(), out.relative_to(REPO))


if __name__ == "__main__":
    main()
