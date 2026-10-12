"""The live twin's demand: the city's configured route file (one hour for Dhaka: RQ2b's corridor demand), repeated hour after hour so
the twin keeps running. Each copy keeps every vehicle and route and shifts departures by whole periods; ids get a suffix. SUMO's own
randomness (the seed: departure lanes, speeds, sublane positions) makes each hour different.
"""
from __future__ import annotations

import re
from pathlib import Path

DEPART = re.compile(r'depart="([\d.]+)"')


def repeated(src: Path, dst: Path, copies: int) -> Path:
    text = src.read_text()
    head, body = text.split("<vehicle", 1)
    body = "<vehicle" + body.rsplit("</routes>", 1)[0]
    departs = [float(x) for x in DEPART.findall(body)]
    period = 3600.0 * max(1, int(max(departs) // 3600) + 1)
    parts = [head]
    for k in range(copies):
        shifted = DEPART.sub(lambda m: f'depart="{float(m.group(1)) + k * period:.2f}"', body)
        parts.append(re.sub(r'<vehicle id="([^"]+)"', lambda m: f'<vehicle id="{m.group(1)}_h{k}"', shifted))
    parts.append("</routes>\n")
    dst.write_text("".join(parts))
    return dst
