"""One live twin run without a viewer, at full speed, to see whether the online model learns: the three forecasters' error per scored
minute over SIM_MIN simulated minutes. Same code as the web page (core/simulation/live_twin, core/ml/forecasting/live); Chronos waits
for each minute (sync) so no minute is skipped. Writes evidence/live_twin/learning_run.json and prints its sha256.

    PYTHONPATH=.:backend python scripts/live_twin/learning_run.py [--minutes 180] [--seed N]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import datetime, timezone

from core.common.paths import REPO
from core.simulation.live_twin import session as ses


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=int, default=180)
    ap.add_argument("--seed", type=int, default=None, help="default: from the clock, as the web page")
    a = ap.parse_args()
    s = ses.Session("dhaka", "learning-run", speed=1e9, sync_forecasts=True)
    if a.seed is not None:
        s.seed = a.seed
    from core.ml.forecasting.live import online
    t0 = time.time()
    s.start()
    while s.status in ("starting", "warming", "running") and s.t < a.minutes * 60:
        time.sleep(2)
        s.last_seen = time.time()
    s.stop(); s.thread.join(30)
    f = s.forecast
    hist = s.fc.history
    body = {"what": "live twin, no viewer, full speed: the three forecasters' errors per scored minute", "city": "dhaka", "seed": s.seed,
            "demand": s.lt.demand_label, "base_scale": s.lt.demand_scale, "simulated_min": round(s.t / 60, 1), "real_s": round(time.time() - t0, 1),
            "status": s.status, "message": s.message, "roads": f.get("roads"), "loops": f.get("loops"), "loops_sha256": f.get("loops_sha256"),
            "learned": s.fc.learned, "running_mae_kmh": f.get("running_mae_kmh"), "history": hist,
            "versions": {"river": __import__("river").__version__, "chronos_model": online.CHRONOS_MODEL, "chronos_revision": online.CHRONOS_REVISION},
            "when": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    out = REPO / "evidence/live_twin/learning_run.json"
    out.write_text(json.dumps(body, indent=1))
    print(json.dumps({k: body[k] for k in ("seed", "simulated_min", "real_s", "status", "learned", "running_mae_kmh")}))
    for h in hist[::15]:
        print(h["minute"], {k: h[k] for k in ("online_10", "chronos_10", "no_change_10")})
    print("sha256", hashlib.sha256(out.read_bytes()).hexdigest(), out.relative_to(REPO))


if __name__ == "__main__":
    main()
