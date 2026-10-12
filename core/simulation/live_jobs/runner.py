"""Live simulation jobs for the map (owner, 2026-10-10): the terminal runs (scripts/live/run_*.py) started from the web app, computed now
on this server by the thesis's own code, streamed as frames (lon/lat, once a simulated second) and ended with the measured result and
the check against the saved thesis run. Never replayed.

One job at a time for the whole site, shared with the live 3D twin (core/simulation/twin/live/runtime.py); per-visitor limits are in
backend/app/platform/ratelimit.py (hosted only). Frames are kept in memory for the job's lifetime.
"""
from __future__ import annotations

import importlib.util
import threading
import time
import traceback
import uuid
from functools import lru_cache
from pathlib import Path

from core.common.paths import REPO

MAX_FRAMES = 4000
KINDS = ("v2x", "sos", "mesh", "signals")


class Stop(Exception):
    """The viewer pressed Stop."""


def live_script(name: str):
    """A terminal-run module (scripts/live/<name>.py), loaded once: the jobs reuse its functions unchanged."""
    return _load(name)


@lru_cache(maxsize=8)
def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"live_{name}", REPO / f"scripts/live/{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@lru_cache(maxsize=4)
def net(path: str):
    import sumolib
    return sumolib.net.readNet(path)


class Job:
    def __init__(self, kind: str, params: dict):
        self.id = f"{kind}-{uuid.uuid4().hex[:8]}"
        self.kind, self.params = kind, params
        self.status, self.message, self.result = "starting", "", None
        self.frames: list[dict] = []
        self.first_index = 0                                      # index of frames[0] once old frames are dropped
        self.stop_event = threading.Event()
        self.started = time.time()
        self.lock = threading.Lock()

    def emit(self, frame: dict) -> None:
        with self.lock:
            self.frames.append(frame)
            if len(self.frames) > MAX_FRAMES:
                drop = len(self.frames) - MAX_FRAMES
                self.frames, self.first_index = self.frames[drop:], self.first_index + drop

    def say(self, message: str) -> None:
        self.message = message

    def check_stop(self) -> None:
        if self.stop_event.is_set():
            raise Stop

    def view(self, since: int = 0) -> dict:
        with self.lock:
            start = max(since, self.first_index)
            frames = self.frames[start - self.first_index:]
            return {"id": self.id, "kind": self.kind, "params": self.params, "label": "SIMULATION", "status": self.status, "message": self.message,
                    "next": self.first_index + len(self.frames), "frames": frames, "result": self.result, "elapsed_s": round(time.time() - self.started, 1)}


class Runner:
    def __init__(self):
        self.jobs: dict[str, Job] = {}
        self.current: Job | None = None
        self.lock = threading.Lock()

    def busy(self) -> bool:
        return bool(self.current and self.current.status in ("starting", "running"))

    def start(self, kind: str, params: dict) -> dict:
        from core.simulation.live_jobs import jobs
        from core.simulation.twin.live import runtime as twin
        if kind not in KINDS:
            return {"started": False, "reason": f"unknown simulation {kind!r}"}
        try:
            clean = jobs.validate(kind, params or {})
        except ValueError as exc:
            return {"started": False, "reason": str(exc)}
        with self.lock:
            if self.busy():
                return {"started": False, "reason": "a simulation is already running on this server (one at a time)", "job": self.current.id}
            if twin.live_sim.state(with_vehicles=False).get("status") in ("starting", "running", "paused"):
                return {"started": False, "reason": "the 3D City simulation is running on this server; one simulation at a time"}
            job = Job(kind, clean)
            self.jobs[job.id], self.current = job, job
        threading.Thread(target=self._run, args=(job,), daemon=True, name=job.id).start()
        return {"started": True, "job": job.id, "label": "SIMULATION"}

    def _run(self, job: Job) -> None:
        from core.simulation.live_jobs import jobs
        job.status = "running"
        try:
            job.result = getattr(jobs, job.kind)(job)
            job.status = "done"
        except Stop:
            job.status = "stopped"
        except Exception as exc:                                     # noqa: BLE001 - the page shows the reason
            job.status, job.message = "failed", f"{type(exc).__name__}: {exc}"
            traceback.print_exc()

    def get(self, job_id: str) -> Job | None:
        return self.jobs.get(job_id)

    def stop(self, job_id: str) -> dict:
        job = self.jobs.get(job_id)
        if not job:
            return {"stopped": False, "reason": "no such job"}
        job.stop_event.set()
        return {"stopped": True, "job": job_id}


RUNNER = Runner()


def busy() -> bool:
    return RUNNER.busy()


def repo_path(*parts: str) -> Path:
    return REPO.joinpath(*parts)
