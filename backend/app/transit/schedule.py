"""Operator facts a line needs that OpenStreetMap does not always carry: headway, operating hours and
the commercial speed. OSM tags win when present; otherwise a published operator fact matched by the
line's name or network, with its source; otherwise an estimate, labelled as one."""
from __future__ import annotations

import re
from datetime import datetime

# Published operator facts. Each entry: how to match the OSM line, the facts, and where they come from.
PUBLISHED = [
    {"match": r"dhaka metro|mrt line 6|এমআরটি লাইন ৬", "headway_peak_s": 6 * 60, "headway_offpeak_s": 7 * 60,
     "hours": {"default": ("07:30", "21:00"), "fri": ("15:30", "21:00")}, "peak": [("07:00", "10:00"), ("17:00", "20:00")],
     "commercial_speed_kmh": 32.0,            # 21.26 km end to end in under 40 minutes
     "source": "Dhaka Mass Transit Company Ltd timetable, as reported on Wikipedia: Dhaka Metro Rail (2026)"},
]
DEFAULT = {"headway_peak_s": 10 * 60, "headway_offpeak_s": 12 * 60, "hours": {"default": ("06:00", "23:00")}, "peak": [("07:00", "10:00"), ("16:30", "19:30")],
           "commercial_speed_kmh": 30.0, "source": "estimate: no operator timetable known for this line (typical urban rail headway and speed)"}
DWELL_S = 30                                   # per intermediate stop, in the ride estimate


def facts_for(line: dict) -> dict:
    """The schedule facts for a line, OSM tags first, then a published fact, then the estimate."""
    text = " ".join(str(line.get(k) or "") for k in ("name", "network", "operator", "ref")).lower()
    pub = next((p for p in PUBLISHED if re.search(p["match"], text)), None)
    base = {**DEFAULT, **({k: v for k, v in pub.items() if k != "match"} if pub else {})}
    out = {"headway_peak_s": base["headway_peak_s"], "headway_offpeak_s": base["headway_offpeak_s"], "hours": base["hours"], "peak": base["peak"],
           "commercial_speed_kmh": base["commercial_speed_kmh"], "source": base["source"], "from_osm": {}}
    if line.get("interval_s"):
        out["headway_peak_s"] = out["headway_offpeak_s"] = line["interval_s"]; out["from_osm"]["headway"] = True
    if line.get("duration_s") and line.get("length_km"):
        out["commercial_speed_kmh"] = line["length_km"] / (line["duration_s"] / 3600); out["from_osm"]["speed"] = True
    return out


def _hm(s: str) -> int:
    h, m = s.split(":"); return int(h) * 60 + int(m)


def is_open(facts: dict, local: datetime) -> bool:
    key = "fri" if local.weekday() == 4 and "fri" in facts["hours"] else "default"
    a, b = facts["hours"][key]
    t = local.hour * 60 + local.minute
    return _hm(a) <= t <= _hm(b)


def headway_s(facts: dict, local: datetime) -> int:
    t = local.hour * 60 + local.minute
    peak = any(_hm(a) <= t <= _hm(b) for a, b in facts["peak"])
    return int(facts["headway_peak_s"] if peak else facts["headway_offpeak_s"])
