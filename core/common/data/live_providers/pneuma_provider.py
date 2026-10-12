"""PNEUMATrajectoryProvider — official pNEUMA CSV (open-traffic.epfl.ch).

Row format: track_id; type; traveled_d; avg_speed; then repeating
(lat; lon; speed[km/h]; lon_acc; lat_acc; time[s]) samples at 25 Hz.
Nothing synthetic: every sample is a real measured vehicle position.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Sample:
    t: float
    lat: float
    lon: float
    speed_kmh: float


@dataclass
class Track:
    vid: int
    vtype: str
    samples: list


def parse(csv_path: str, hz: float = 1.0):
    """Yield Track objects downsampled to `hz` (from the 25 Hz raw)."""
    step = max(int(round(25.0 / hz)), 1) * 6
    with open(csv_path) as f:
        next(f)
        for line in f:
            parts = [p.strip() for p in line.strip().strip(";").split(";")]
            if len(parts) < 10:
                continue
            vid, vtype = int(parts[0]), parts[1]
            flat = parts[4:]
            samples = []
            for j in range(0, len(flat) - 5, step):
                try:
                    samples.append(Sample(t=float(flat[j + 5]),
                                          lat=float(flat[j]),
                                          lon=float(flat[j + 1]),
                                          speed_kmh=float(flat[j + 2])))
                except ValueError:
                    break
            if samples:
                yield Track(vid, vtype, samples)
