from __future__ import annotations

ALIASES = {
    "day": ["day", "date"],
    "interval": ["interval", "interval_s", "time", "time_interval"],
    "detid": ["detid", "detector_id", "detector", "id"],
    "flow": ["flow", "q", "volume"],
    "occ": ["occ", "occupancy", "o"],
    "error": ["error", "err", "error_flag", "quality_flag"],
    "city": ["city", "town"],
    "speed": ["speed", "v", "velocity"],
    "linkid": ["linkid", "link_id", "edge_id", "edgeid"],
    "length": ["length", "length_m", "len", "link_length"],
    "lanes": ["lanes", "nlanes", "num_lanes"],
}


def resolve_columns(columns, required=("day", "interval", "detid", "flow", "city")):
    lower = {str(c).strip().lower(): c for c in columns}
    out = {}
    for canonical, aliases in ALIASES.items():
        for alias in aliases:
            if alias in lower:
                out[canonical] = lower[alias]
                break
    missing = [c for c in required if c not in out]
    if missing:
        raise ValueError(f"Required UTD19 columns not found: {missing}; actual={list(columns)}")
    return out
