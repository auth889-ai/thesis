"""Trip metrics from tripinfo.xml (pattern proven in Lab 01, adapted)."""
from __future__ import annotations

import json
import math
import statistics
import xml.etree.ElementTree as ET
from pathlib import Path


def percentile(xs, p):
    xs = sorted(float(x) for x in xs)
    if not xs:
        return float("nan")
    if len(xs) == 1:
        return xs[0]
    k = (len(xs) - 1) * (p / 100.0)
    f, c = math.floor(k), math.ceil(k)
    return xs[int(k)] if f == c else xs[f] * (c - k) + xs[c] * (k - f)


def summarize_tripinfo(tripinfo_path: Path, out_path: Path | None = None) -> dict:
    root = ET.parse(tripinfo_path).getroot()
    dur, wait, loss, lengths = [], [], [], []
    for t in root.findall("tripinfo"):
        dur.append(float(t.get("duration", 0)))
        wait.append(float(t.get("waitingTime", 0)))
        loss.append(float(t.get("timeLoss", 0)))
        lengths.append(float(t.get("routeLength", 0)))
    n = len(dur)
    speeds = [l / d for l, d in zip(lengths, dur) if d > 0]
    report = {
        "n_arrived_trips": n,
        "avg_travel_time_s": round(statistics.mean(dur), 2) if n else None,
        "p95_travel_time_s": round(percentile(dur, 95), 2) if n else None,
        "avg_waiting_time_s": round(statistics.mean(wait), 2) if n else None,
        "avg_time_loss_s": round(statistics.mean(loss), 2) if n else None,
        "avg_route_length_m": round(statistics.mean(lengths), 1) if n else None,
        "avg_speed_mps": round(statistics.mean(speeds), 2) if speeds else None,
    }
    if out_path:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_text(json.dumps(report, indent=2))
    return report


def summarize_run(summary_path: Path) -> dict:
    root = ET.parse(summary_path).getroot()
    last = root.findall("step")[-1]
    return {
        "sim_end_time": float(last.get("time")),
        "loaded": int(last.get("loaded")),
        "inserted": int(last.get("inserted")),
        "arrived": int(last.get("ended")),
        "running_at_end": int(last.get("running")),
        "waiting_to_insert_at_end": int(last.get("waiting")),
    }
