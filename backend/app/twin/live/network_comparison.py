"""BASELINE vs REACTIVE on any network the twin can run — paired seeds, a real verdict.

For a city with no observed corridors there is no forecast to price a prediction-aware arm, but
the question "does rerouting help here?" can still be measured: the same generated network and
demand, the same seeds, nobody rerouting versus equipped vehicles rerouting on current travel
times. Each run is a real LiveSim run (SUMO through TraCI) scored by the chain's parse_metrics;
the verdict is the chain's own paired-seed 95 % CI rule.
"""
from __future__ import annotations

import sys
import threading
import time
import uuid
from datetime import datetime, timezone

from app import evidence_paths as config
from app.twin.live.runtime import live_sim

sys.path.insert(0, str(config.REPO))
_JOBS: dict[str, dict] = {}
_LOCK = threading.Lock()


def _run(job: str, p: dict) -> None:
    from app.protocols.chains import integrated_chain as ic
    seeds = [int(x) for x in str(p.get("seeds", "11,12,13")).split(",")]
    arms = ("baseline", "reactive")
    total = len(seeds) * len(arms)
    runs, done = [], 0
    live_sim.owner = job                       # nobody else starts the twin until we are done
    try:
        for _ in range(120):                   # let a run started by hand finish first
            if live_sim.state(with_vehicles=False).get("status") not in ("running", "paused", "starting"):
                break
            time.sleep(0.5)
        else:
            live_sim.stop()
        for seed in seeds:
            for arm in arms:
                with _LOCK:
                    _JOBS[job].update(stage=f"Simulating {arm} · seed {seed}", done=done, total=total)
                r = live_sim.start({"network": p["network"], "seed": seed, "arm": arm,
                                    "duration_s": int(p.get("duration_s", 900)),
                                    "scale": float(p.get("scale", 4.0)),
                                    "compliance": float(p.get("compliance", 0.3)),
                                    "step_delay_ms": 0, "continuous": False}, owner=job)
                if not r.get("started"):
                    raise RuntimeError(r.get("reason", "could not start the twin"))
                for _ in range(1800):
                    s = live_sim.state(with_vehicles=False)
                    if s["status"] in ("done", "failed", "stopped"):
                        break
                    time.sleep(0.5)
                if s["status"] != "done":
                    raise RuntimeError(s.get("message") or f"run ended as {s['status']}")
                res = s["result"]
                runs.append({"arm": arm, "seed": seed, "routes_changed": res.get("reroutes", 0),
                             "advisories_delivered": 0, "run_id": res["run_id"], "metrics": res["metrics"]})
                done += 1
        with _LOCK:
            _JOBS[job].update(stage="Computing result", done=done, total=total)
        summary = ic.summarise(runs)
        with _LOCK:
            _JOBS[job].update(status="done", stage="done", result={
                "network": p["network"], "seeds": seeds, "duration_s": int(p.get("duration_s", 900)),
                "scale": float(p.get("scale", 4.0)), "compliance": float(p.get("compliance", 0.3)),
                "runs": runs, "summary": summary, "finished_utc": datetime.now(timezone.utc).isoformat(),
                "label": "SIMULATED — generated demand on a real OpenStreetMap network (what-if)"})
    except Exception as exc:                        # noqa: BLE001 - shown on the page
        with _LOCK:
            _JOBS[job].update(status="failed", stage="failed", error=f"{type(exc).__name__}: {exc}")
    finally:
        live_sim.owner = None


def start(payload: dict) -> str:
    job = "cmp_" + uuid.uuid4().hex[:8]
    with _LOCK:
        _JOBS[job] = {"job": job, "status": "running", "stage": "Starting SUMO", "done": 0,
                      "started_utc": datetime.now(timezone.utc).isoformat(), "request": payload}
    threading.Thread(target=_run, args=(job, payload), name=job, daemon=True).start()
    return job


def status(job: str) -> dict:
    with _LOCK:
        return dict(_JOBS.get(job) or {"job": job, "status": "unknown"})
