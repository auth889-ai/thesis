"""Real recorded traffic: the vehicles a published dataset's cameras tracked, replayed at a chosen clock time of the
recording day. Every block says REAL · recorded, names the dataset, the day and the camera clock time, and says
"replay, not live". Only the metres each camera covered carry any vehicle; the rest of the map has none.

What is the authors' and what is ours: positions, classes and the per-vehicle speed are theirs (a detection and
tracking model through a four-point calibration they did not validate); the half-second sampling, the heading and the
latitude/longitude mapping from their calibration file are ours (dhatrax.build_replay).
"""
from __future__ import annotations

import gzip
import json
import re
from functools import lru_cache
from pathlib import Path

from core.common import tag
from core.common.data import real_speeds

AT = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)(?::([0-5]\d))?$")
MAX_SECONDS = 300


def parse_at(at: str) -> float:
    m = AT.match(at or "")
    if not m:
        raise ValueError("at must be HH:MM or HH:MM:SS")
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3) or 0)


def clock(t: float) -> str:
    h, rest = divmod(t, 3600)
    m, s = divmod(rest, 60)
    return f"{int(h):02d}:{int(m):02d}:{s:04.1f}"


@lru_cache(maxsize=8)
def _hour(path: str) -> dict:
    with gzip.open(path, "rt") as f:
        return json.load(f)


def _frames(reader, site: str, t0: float, seconds: float) -> tuple[list[dict], dict | None]:
    """The sampled frames of one site between t0 and t0 + seconds (camera clock), from every replay file whose span overlaps."""
    out, meta = [], None
    for span in reader.replay_available().get(site, []):
        if span["t_end"] < t0 or span["t_start"] >= t0 + seconds:
            continue
        rec = _hour(span["file"])
        meta = meta or rec
        for key, vehicles in rec["frames"].items():
            t = float(key)
            if t0 <= t < t0 + seconds:
                out.append({"t": t, "clock": clock(t), "vehicles": vehicles})
    out.sort(key=lambda f: f["t"])
    return out, meta


def window(city_id: str, at: str, seconds: int = 60, net=None, bbox=None) -> dict:
    """The real recorded vehicles of every located, replayable site of a city's recorded datasets, for `seconds` from `at`."""
    t0 = parse_at(at)
    seconds = max(1, min(int(seconds), MAX_SECONDS))
    blocks, missing = [], []
    for src in real_speeds.recorded_sources(city_id, net, bbox):
        if "sites" not in src:
            continue
        reader = next(r for r in real_speeds._readers().values() if r.NAME == src["dataset"])
        if not hasattr(reader, "replay_available"):
            continue
        for st in src["sites"]:
            if not st.get("located"):
                continue
            if st["site"] not in reader.replay_available():
                missing.append(st["site"])
                continue
            frames, meta = _frames(reader, st["site"], t0, seconds)
            tracks = {v[4] for f in frames for v in f["vehicles"]}
            t = tag.real(f"{src['dataset']} fixed camera, site {st['site']}: {src['caveat']}", f"{st['day']} {at} (camera clock)", f"{src['dataset']} v{src['version']}, {src['licence']}",
                         recorded=True, replay=True, label=f"REAL · recorded traffic, {src['dataset']}, {st['day']} {at} (camera clock) — replay, not live", citation=src["citation"],
                         coverage_m=(meta or {}).get("coverage_m"), sampling_hz=(meta or {}).get("hz"),
                         ours="half-second sampling, heading from successive positions, and the latitude/longitude mapping from the authors' calibration file are this project's; positions, classes and speeds are the authors'")
            blocks.append({"site": st["site"], "day": st["day"], "lat": st["lat"], "lon": st["lon"], "bearing_deg": st["bearing_deg"], "section": st.get("section"),
                           "coverage_m": (meta or {}).get("coverage_m"), "calibration_sha256": (meta or {}).get("calibration_sha256"), "dataset": src["dataset"],
                           "from": clock(t0), "seconds": seconds, "recorded_spans": [[clock(x["t_start"]), clock(x["t_end"])] for x in reader.replay_available()[st["site"]]],
                           "value": len(tracks), "unit": "tracked vehicles in the window", "tag": t, "frames": frames,
                           "note": None if frames else "no recorded frame at this time: the camera was not recording, or every vehicle was outside its active area"})
    if not blocks:
        reason = ("no data for this city: its recorded dataset's trajectories have not been converted on this machine (python -m core.common.data.recorded.dhatrax --fetch-trajectories --build-replay)"
                  if missing else "no data for this city: no recorded dataset with located cameras")
        return {"city_id": city_id, "available": False, "reason": reason, "sites": []}
    return {"city_id": city_id, "available": True, "label": "REAL · recorded traffic — replay, not live", "at": at, "window_s": seconds, "sites": blocks,
            "not_converted": missing, "limits": "only the metres each camera covered carry any vehicle; one day per site; the time is the camera's own clock"}
