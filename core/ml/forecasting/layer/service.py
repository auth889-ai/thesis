"""The map's forecast layer: what a city's config declares (`forecast_layer:`), answered from saved files only.

replay        recorded sensor speeds replayed at the same weekday and time of day as now (city time zone), with the model's
              forecast made at that recorded moment; card and skill from the build's summary (layer/build_la.py)
recorded_day  each located site at this hour on its one recorded day (DhaTraX); card from RQ1's per-site errors

"Best time to leave" is given only when the card shows skill (lower error than "no change") at every horizon it compares.
Nothing here is estimated: a missing file, hour or city gives an explicit "no data" answer.
"""
from __future__ import annotations

import json
from datetime import datetime
from functools import lru_cache
from zoneinfo import ZoneInfo

import numpy as np

from core.common.data import city_config
from core.common.paths import REPO

HORIZONS = ("15", "30", "60")
MPH_TO_KMH = 1.609344
CLEAR_DIFF = 1.0          # a best time is named only when its median speed beats leaving now by at least this much (city units)
ZERO_SHOT = ("chronos", "chronos2", "timesfm")   # RQ1's zero-shot models for Dhaka (the tree models were trained on Los Angeles)


def no_data(city_id: str, why: str) -> dict:
    return {"city_id": city_id, "available": False, "reason": why}


@lru_cache(maxsize=2)
def _replay(path: str) -> dict:
    z = np.load(REPO / path)
    times = [datetime.fromisoformat(t) for t in z["time"]]
    return {"time": times, "now": z["now"].astype("float32"), "forecast": z["forecast"].astype("float32"),
            "sensor_id": z["sensor_id"], "lat": z["lat"], "lon": z["lon"]}


def pick(times: list[datetime], local: datetime) -> int | None:
    """Index of the latest recorded step with the same weekday and the same 5-minute time of day as `local`. Pure."""
    slot = (local.weekday(), local.hour, local.minute - local.minute % 5)
    hits = [i for i, t in enumerate(times) if (t.weekday(), t.hour, t.minute) == slot]
    return hits[-1] if hits else None


def best_time(now: np.ndarray, fc: np.ndarray, card: dict, keep: np.ndarray) -> dict | None:
    """Of leaving now, in 15, 30 or 60 minutes: the highest median speed over the kept sensors. None without skill everywhere. Pure."""
    if not all(card[h]["skill"] > 0 for h in HORIZONS):
        return None
    ok = keep & (now > 0)
    if ok.sum() < 3:
        return None
    med = {"0": float(np.median(now[ok]))} | {h: float(np.median(fc[i][ok])) for i, h in enumerate(HORIZONS)}
    top = max(med, key=med.get)
    clear = med[top] - med["0"] >= CLEAR_DIFF
    return {"leave_in_min": int(top) if clear else 0, "clear": clear, "median_speed": {k: round(v, 1) for k, v in med.items()}, "sensors": int(ok.sum())}


def replay(cfg, at: datetime, bbox: tuple[float, float, float, float] | None) -> dict:
    fl = cfg.forecast_layer
    if not (REPO / fl.file).exists() or not (REPO / fl.summary).exists():
        return no_data(cfg.city_id, "the replay file has not been built (python -m core.ml.forecasting.layer.build_la)")
    r, s = _replay(fl.file), json.loads((REPO / fl.summary).read_text())
    local = at.astimezone(ZoneInfo(cfg.time_zone)) if cfg.time_zone else at
    i = pick(r["time"], local)
    if i is None:
        return no_data(cfg.city_id, "this weekday and time are not in the recorded replay")
    f = 1.0 if (cfg.units and cfg.units.speed == "mph") else MPH_TO_KMH
    now, fc = r["now"][i] * f, r["forecast"][i] * f
    keep = np.ones(len(now), bool)
    if bbox:
        w, so, e, n = bbox
        keep = (r["lon"] >= w) & (r["lon"] <= e) & (r["lat"] >= so) & (r["lat"] <= n)
    card = {h: {k: (round(v * f, 2) if k in ("mae", "no_change_mae") else v) for k, v in s["card"][h].items()} for h in HORIZONS}
    points = [{"id": str(r["sensor_id"][k]), "lat": float(r["lat"][k]), "lon": float(r["lon"][k]),
               "now": None if now[k] <= 0 else round(float(now[k]), 1), **{h: round(float(fc[j][k]), 1) for j, h in enumerate(HORIZONS)}}
              for k in range(len(now))]
    t = r["time"][i]
    return {"city_id": cfg.city_id, "available": True, "kind": "replay", "units": "mph" if f == 1.0 else "km/h",
            "recorded_at": t.isoformat(timespec="minutes"), "recorded_weekday": t.strftime("%A"), "local_now": local.isoformat(timespec="minutes"),
            "dataset": s["dataset"], "points": points, "horizons_min": [int(h) for h in HORIZONS],
            "card": {"model": s["model"]["name"], "paper": s["model"]["paper"], "where": f"METR-LA test split, {s['replay']['steps']} moments", "metric": s["metric"], "horizons": card},
            "best_time": (bt := best_time(now, fc, card, keep)),
            "best_time_reason": None if bt else ("no_skill" if not all(card[h]["skill"] > 0 for h in HORIZONS) else "few_sensors")}


def recorded_day(cfg, at: datetime) -> dict:
    from core.common.data.recorded import dhatrax
    fl = cfg.forecast_layer
    sites = [x for x in dhatrax.sites() if x["located"]]
    if not sites or not (REPO / fl.summary).exists():
        return no_data(cfg.city_id, "the recorded days are not on this machine")
    s = json.loads((REPO / fl.summary).read_text())
    d, names = s["dhaka"], s.get("names", {})
    local = at.astimezone(ZoneInfo(cfg.time_zone)) if cfg.time_zone else at
    hhmm = f"{local.hour:02d}:{local.minute:02d}"
    points, cards = [], {}
    for x in sites:
        r = dhatrax.reading_at(x["site"], hhmm)
        points.append({"id": x["site"], "lat": x["lat"], "lon": x["lon"], "day": x["day"], "now": r["median_kmh"] if r else None,
                       "interval_start": r["start"] if r else None})
        per = {}
        for h in HORIZONS:
            best = min(ZERO_SHOT, key=lambda m: d[m][h]["per_site"][x["site"]])
            m, p = d[best][h]["per_site"][x["site"]], d["persistence"][h]["per_site"][x["site"]]
            per[h] = {"model": names.get(best, best), "mae": m, "no_change_mae": p, "skill": round(1 - m / p, 4)}
        cards[x["site"]] = per
    skill_everywhere = all(c[h]["skill"] > 0 for c in cards.values() for h in HORIZONS)
    return {"city_id": cfg.city_id, "available": True, "kind": "recorded_day", "units": "km/h", "local_now": local.isoformat(timespec="minutes"),
            "dataset": "DhaTraX v1.0 (Roy, Zenodo, CC BY 4.0): one recorded day per camera site, 06:00-18:00", "points": points,
            "recorded_now": any(p["now"] is not None for p in points),
            "card": {"where": "RQ1, rolling origin over each site's recorded day", "metric": "MAE km/h", "sites": cards},
            "best_time": None,
            "best_time_reason": None if skill_everywhere else "no_skill"}


def layer(city_id: str, at: datetime, bbox: tuple[float, float, float, float] | None = None) -> dict:
    try:
        cfg = city_config.load(city_id)
    except Exception:                                                # noqa: BLE001 - an unknown city has no layer
        return no_data(city_id, "no such city")
    if not cfg.forecast_layer:
        return no_data(city_id, "no data for this city")
    return replay(cfg, at, bbox) if cfg.forecast_layer.kind == "replay" else recorded_day(cfg, at)
