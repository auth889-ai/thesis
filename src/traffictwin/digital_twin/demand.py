"""Demand scenario construction for the rolling twin.

make_repeating_routes: tiles the fair fixed DUE demand in time (same trips,
depart shifted by k*period, unique ids) to produce a CONTINUOUS scenario for
rolling-twin protocols (history preload, sustained control windows). This is
declared scenario construction — the per-cycle demand is byte-identical to
the audited DUE pulse, nothing is invented.
"""
from __future__ import annotations

import gzip
import xml.etree.ElementTree as ET
from pathlib import Path


def make_repeating_routes(src: Path, out: Path, cycles: int = 7,
                          period_s: float = 600.0) -> Path:
    if out.exists():
        return out
    with gzip.open(src) as f:
        tree = ET.parse(f)
    root = tree.getroot()
    vehicles = [e for e in root if e.tag == "vehicle"]
    for v in vehicles:
        root.remove(v)
    for k in range(cycles):
        for v in vehicles:
            c = ET.fromstring(ET.tostring(v))
            c.set("id", f'{v.get("id")}_c{k}')
            c.set("depart", f'{float(v.get("depart")) + k * period_s:.2f}')
            root.append(c)
    # SUMO requires sorted departs
    vs = sorted((e for e in list(root) if e.tag == "vehicle"),
                key=lambda e: float(e.get("depart")))
    for e in vs:
        root.remove(e)
    for e in vs:
        root.append(e)
    out.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(out, "wb") as f:
        tree.write(f)
    return out
