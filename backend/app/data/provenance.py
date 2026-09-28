"""PROVENANCE — every prediction request leaves a record that says exactly what computed it.

    run_id, city, origin, destination, dataset_hash, graph_hash, requested_model, resolved_model,
    checkpoint_path, checkpoint_sha256, input_window_hash, raw_prediction_hash,
    postprocessed_prediction_hash, start_time, end_time, stages (measured), result_source,
    cache_hit_training, inference_recomputed

Records live in results/runs/provenance/<run_id>.json and are served by GET /api/runs/{run_id}.
A stage's seconds are measured wall-clock around the real work; nothing here sleeps.

result_source values:
    LIVE_COMPUTATION   computed now from the current inputs
    CHECKPOINT_CACHE   a stored, validated training artefact was reused (inference still recomputed)
    RESEARCH_BENCHMARK a precomputed experiment file (never a new live result)
    SYNTHETIC_WHAT_IF  a what-if scenario with synthetic inputs (never a live result)
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from app.paths import REPO

DIR = REPO / "results/runs/provenance"
STAGES = ["Resolving city", "Loading graph", "Validating traffic data", "Loading checkpoint", "Running inference", "Evaluating routes", "Preparing result"]
_LOCK = threading.Lock()


def sha_array(a) -> str:
    import numpy as np
    arr = np.ascontiguousarray(np.asarray(a, dtype="float64"))
    return hashlib.sha256(arr.tobytes()).hexdigest()[:16]


def sha_file(p: str | Path | None, n: int = 12) -> str | None:
    if not p or not Path(p).exists():
        return None
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:n]


def sha_json(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:16]


class Run:
    def __init__(self, run_id: str, **fields):
        self.rec = {"run_id": run_id, "start_time": datetime.now(timezone.utc).isoformat(), "end_time": None,
                    "stages": [], "result_source": "LIVE_COMPUTATION", "cache_hit_training": False, "inference_recomputed": True, **fields}
        self._t0 = time.perf_counter(); self._cur = None; self._cur_t = None

    def stage(self, name: str, emit=None) -> None:
        """Close the running stage (measured) and open `name`."""
        now = time.perf_counter()
        if self._cur is not None:
            self.rec["stages"][-1]["seconds"] = round(now - self._cur_t, 3)
        self.rec["stages"].append({"name": name, "seconds": None, "at": round(now - self._t0, 3)})
        self._cur, self._cur_t = name, now
        if emit:
            emit(stage=name, stages=list(self.rec["stages"]))

    def set(self, **kw) -> None:
        self.rec.update(kw)

    def finish(self, status: str = "done", error: str | None = None) -> dict:
        now = time.perf_counter()
        if self._cur is not None and self.rec["stages"]:
            self.rec["stages"][-1]["seconds"] = round(now - self._cur_t, 3)
        self.rec["end_time"] = datetime.now(timezone.utc).isoformat()
        self.rec["elapsed_seconds"] = round(now - self._t0, 3)
        self.rec["status"] = status
        if error:
            self.rec["error"] = error
        save(self.rec)
        return dict(self.rec)

    def summary(self) -> dict:
        keys = ("run_id", "requested_model", "resolved_model", "checkpoint_path", "checkpoint_sha256", "dataset_hash", "graph_hash",
                "input_window_hash", "raw_prediction_hash", "postprocessed_prediction_hash", "result_source", "cache_hit_training",
                "inference_recomputed", "start_time", "end_time", "elapsed_seconds", "stages")
        return {k: self.rec.get(k) for k in keys}


def save(rec: dict) -> None:
    DIR.mkdir(parents=True, exist_ok=True)
    with _LOCK:
        tmp = DIR / f"{rec['run_id']}.json.tmp"
        tmp.write_text(json.dumps(rec, indent=1, default=str))
        tmp.replace(DIR / f"{rec['run_id']}.json")


def load(run_id: str) -> dict | None:
    f = DIR / f"{run_id}.json"
    return json.loads(f.read_text()) if f.exists() else None


def recent(limit: int = 20) -> list[dict]:
    files = sorted(DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit] if DIR.exists() else []
    out = []
    for f in files:
        try:
            r = json.loads(f.read_text())
        except json.JSONDecodeError:
            continue
        out.append({k: r.get(k) for k in ("run_id", "city", "origin", "destination", "requested_model", "resolved_model", "checkpoint_path",
                                          "raw_prediction_hash", "result_source", "start_time", "elapsed_seconds", "status")})
    return out
