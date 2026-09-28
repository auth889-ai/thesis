"""Run a SUMO counterfactual from the live state, as a background job.

    from simulate import runner
    job = runner.start(corridor_id="karwanbazar_to_shahbagh", category="TRAFFIC_JAM", seeds=[11,12])
    runner.status(job)

WHAT THIS IS, AND IS NOT
    The live API tells us a Dhaka corridor is jammed right now. This takes that observed state as
    the SCENARIO INPUT, makes it real inside the frozen Dhaka R1 SUMO network (each affected edge's
    speed limit divided by the multiplier for its class), and runs three arms on identical demand
    and paired seeds:

        baseline           nobody reroutes
        reactive           equipped vehicles reroute on CURRENT edge travel times
        prediction_aware   equipped vehicles reroute on the forecast travel-time table

    Every number that comes back is a **SIMULATED COUNTERFACTUAL**. It is what the model says would
    have happened on a calibrated twin, not a measurement of the real road. The demand is the
    project's calibrated synthetic demand: the live feed supplies the congestion state, never the
    traffic volume. Both facts are attached to every result and shown in the interface.

WHY IT IS ASYNCHRONOUS
    Three arms over several paired seeds is minutes of wall clock. A synchronous request would time
    the browser out, so `start()` returns a job id immediately and the interface polls `status()`.
    Only one job runs at a time; a second request while one is running is refused rather than
    queued, so a demo cannot accidentally launch a dozen simulations.
"""
from __future__ import annotations

import json
import subprocess
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from backend.app.config import REPO
RESULTS = REPO / "results/routing"
SCRIPT = REPO / "src/pipeline/routing/live_chain.py"

# live category -> the recorder's ordinal level that live_to_edges maps to a travel-time multiplier
CATEGORY_LEVEL = {"NORMAL": 0.0, "SLOW": 1.0, "TRAFFIC_JAM": 2.5, "UNKNOWN": 0.0}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Runner:
    def __init__(self) -> None:
        self._jobs: dict[str, dict] = {}
        self._lock = threading.Lock()
        self._active: str | None = None

    def _set(self, job_id: str, **kw) -> None:
        with self._lock:
            self._jobs[job_id].update(kw)

    def start(self, corridor_id: str, category: str, seeds: list[int] | None = None,
              horizon: int = 1800, compliance: float = 0.3) -> dict:
        from backend.app.datasets import reference_corridors as _corridors
        c = _corridors.BY_ID.get(corridor_id)
        if not c:
            return {"error": "unknown_corridor", "corridor_id": corridor_id}
        if not c["sumo_mapped"]:
            return {"error": "not_simulatable",
                    "corridor_id": corridor_id,
                    "detail": (f"{c['name']} is monitored live but is not in the frozen Dhaka R1 "
                               f"SUMO network, so no honest counterfactual can be run for it. "
                               f"Corridors that can be simulated are marked sumo_mapped.")}
        with self._lock:
            if self._active and self._jobs[self._active]["status"] == "RUNNING":
                return {"error": "busy", "detail": "a simulation is already running",
                        "active_job": self._active}

        seeds = seeds or [11, 12, 13]
        level = CATEGORY_LEVEL.get(category, 0.0)
        job_id = uuid.uuid4().hex[:12]
        job = {
            "job_id": job_id, "status": "RUNNING", "started_at": _now(), "finished_at": None,
            "corridor_id": corridor_id, "corridor_name": c["name"],
            "live_category": category, "applied_level": level,
            "seeds": seeds, "horizon_s": horizon, "compliance": compliance,
            "label": "SIMULATED COUNTERFACTUAL",
            "not_a": "a measurement of the real road",
            "demand": "DHAKA_SIMULATED_DEMAND — the live feed supplies congestion state, never volume",
            "network": "frozen Dhaka R1 (real OSM topology)",
            "result": None, "error": None,
        }
        with self._lock:
            self._jobs[job_id] = job
            self._active = job_id
        threading.Thread(target=self._run, args=(job_id,), daemon=True).start()
        return job

    def _run(self, job_id: str) -> None:
        job = self._jobs[job_id]
        tag = f"_live_{job_id}"
        cmd = [sys.executable, str(SCRIPT),
               "--seeds", ",".join(str(s) for s in job["seeds"]),
               "--horizon", str(job["horizon_s"]),
               "--compliance", str(job["compliance"]),
               "--levels", f"{job['corridor_id']}={job['applied_level']}",
               "--tag", tag]
        try:
            proc = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, timeout=3600)
            out = RESULTS / f"live_chain{tag}.json"
            if proc.returncode != 0 and not out.exists():
                self._set(job_id, status="FAILED", finished_at=_now(),
                          error=(proc.stderr or proc.stdout or "")[-1500:])
                return
            if not out.exists():
                self._set(job_id, status="FAILED", finished_at=_now(),
                          error="the run produced no result file")
                return
            rec = json.loads(out.read_text())
            self._set(job_id, status="DONE", finished_at=_now(),
                      result=self._shape(rec), raw_file=str(out.relative_to(REPO)))
        except subprocess.TimeoutExpired:
            self._set(job_id, status="FAILED", finished_at=_now(), error="simulation timed out")
        except Exception as exc:                              # noqa: BLE001 - surfaced, not hidden
            self._set(job_id, status="FAILED", finished_at=_now(), error=f"{type(exc).__name__}: {exc}")
        finally:
            with self._lock:
                if self._active == job_id:
                    self._active = None

    @staticmethod
    def _shape(rec: dict) -> dict:
        """Per-arm means, so the interface can show before/after without doing arithmetic."""
        arms: dict[str, list] = {}
        for r in rec.get("runs", []):
            arms.setdefault(r["arm"], []).append(r)
        rows = []
        for arm, runs in arms.items():
            n = len(runs) or 1
            m = [r["metrics"] for r in runs]
            rows.append({
                "arm": arm,
                "seeds": [r["seed"] for r in runs],
                "total_vehicle_hours": round(sum(x["total_vehicle_hours"] for x in m) / n, 2),
                "mean_travel_time_s": round(sum(x.get("mean_travel_time_s", 0) for x in m) / n, 1),
                "total_waiting_s": round(sum(x.get("total_waiting_s", 0) for x in m) / n, 0),
                "mean_time_loss_s": round(sum(x.get("mean_time_loss_s", 0) for x in m) / n, 1),
                "arrived": round(sum(x["arrived"] for x in m) / n, 1),
                "teleports": round(sum(x["teleports"] for x in m) / n, 1),
                "routes_changed": round(sum(r.get("routes_changed", 0) for r in runs) / n, 1),
            })
        order = {"unaware": 0, "baseline": 0, "reactive": 1, "advised": 2, "prediction_aware": 2}
        rows.sort(key=lambda r: order.get(r["arm"], 9))
        base = next((r for r in rows if r["arm"] in ("unaware", "baseline")), None)
        if base:
            for r in rows:
                bv = base["total_vehicle_hours"] or 1
                r["vehicle_hours_pct_vs_baseline"] = round(
                    (r["total_vehicle_hours"] - bv) / bv * 100, 2)
                bw = base["total_waiting_s"] or 1
                r["waiting_pct_vs_baseline"] = round((r["total_waiting_s"] - bw) / bw * 100, 2)
        return {
            "arms": rows,
            "decision": rec.get("decision"),
            "edges_congested": rec.get("edges_congested"),
            "source": rec.get("source"),
            "label": "SIMULATED COUNTERFACTUAL",
            "not_live_road_outcome": True,
        }

    def status(self, job_id: str) -> dict:
        with self._lock:
            job = self._jobs.get(job_id)
        return job or {"error": "unknown_job", "job_id": job_id}

    def latest(self) -> dict | None:
        with self._lock:
            if not self._jobs:
                return None
            return max(self._jobs.values(), key=lambda j: j["started_at"])


runner = Runner()
