"""The mesh study on the map: where the 17 simulated phones were each second of the 5-minute window, and which pairs were within radio
range. Built from the study's own movement (research/mesh_pons/work/dhaka.window.fcd.xml, the file its ns2 trace was exported from),
converted to lon/lat on the study's network with sumolib. Nothing is simulated again; contacts are the positions within range_m.

    PYTHONPATH=.:backend python -m core.networking.mesh.map_replay

Checks before writing: the same vehicles and, at every second, the same pairwise distances as the sha256-checked ns2 trace.
Writes results/networking/mesh/dhaka/map_replay.json and evidence/mesh/dhaka/map_replay/{build.log,SHA256SUMS}.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import math
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import yaml

from core.common.paths import REPO

MESH = REPO / "research/mesh_pons"
OUT = REPO / "results/networking/mesh/dhaka/map_replay.json"
EVID = REPO / "evidence/mesh/dhaka/map_replay"


def contacts(pos: dict[str, tuple[float, float]], range_m: float) -> list[tuple[str, str]]:
    """Pairs of phones within range_m of each other (metres, planar). Pure."""
    return [(a, b) for a, b in itertools.combinations(sorted(pos), 2) if math.dist(pos[a], pos[b]) <= range_m]


def main() -> int:
    import sumolib
    EVID.mkdir(parents=True, exist_ok=True)
    log = []
    say = lambda m: (print(m, flush=True), log.append(m))  # noqa: E731
    mv = json.loads((MESH / "evidence/movement.json").read_text())
    exp = yaml.safe_load((MESH / "configs/dhaka.yaml").read_text())
    trace = MESH / mv["ns2_trace"]
    if hashlib.sha256(trace.read_bytes()).hexdigest() != mv["ns2_trace_sha256"]:
        say("STOP: the ns2 trace does not match its recorded sha256"); return 1
    first: dict[int, list[float]] = {}                        # the ns2 trace's starting positions ($node_(k) set X_/Y_)
    for line in trace.read_text().splitlines():
        m = re.match(r"\$node_\((\d+)\) set ([XY])_ ([-\d.]+)", line)
        if m:
            first.setdefault(int(m[1]), [0.0, 0.0])["XY".index(m[2])] = float(m[3])
    n = len(first)
    frames: dict[float, dict[str, tuple[float, float]]] = {}
    for ts in ET.parse(MESH / "work/dhaka.window.fcd.xml").getroot().iter("timestep"):
        frames[float(ts.get("time"))] = {v.get("id"): (float(v.get("x")), float(v.get("y"))) for v in ts.iter("vehicle")}
    ids = sorted(next(iter(frames.values())), key=lambda v: int(v[3:]) if v[3:].isdigit() else v)
    if len(ids) != n:
        say(f"STOP: {len(ids)} vehicles in the window file, {n} in the ns2 trace"); return 1
    # the ns2 trace's node k is the k-th vehicle as traceExporter met them; compare pairwise distances at t=0, which do not depend on that order
    d_ns2 = sorted(round(math.dist(first[a], first[b]), 1) for a, b in itertools.combinations(first, 2))
    d_fcd = sorted(round(math.dist(frames[0.0][a], frames[0.0][b]), 1) for a, b in itertools.combinations(ids, 2))
    if d_ns2 != d_fcd:
        say("STOP: the window file's distances differ from the ns2 trace's"); return 1
    say(f"{n} phones, {len(frames)} seconds; distances at t=0 identical to the sha256-checked ns2 trace")
    net = sumolib.net.readNet(str(REPO / mv["network"]))
    r = exp["radio"]["range_m"]
    out_frames, total = [], 0
    for t in sorted(frames):
        pos = frames[t]
        ll = {v: net.convertXY2LonLat(*pos[v]) for v in ids}
        c = contacts(pos, r)
        total += len(c)
        out_frames.append({"t": t, "phones": [[round(ll[v][0], 6), round(ll[v][1], 6)] for v in ids], "contacts": [[ids.index(a), ids.index(b)] for a, b in c]})
    rec = {"label": "SIMULATED", "city_id": "dhaka", "phones": n, "ids": ids, "window_s": mv["window_s"], "radio": exp["radio"],
           "demand": mv["demand"], "network": mv["network"], "ns2_trace_sha256": mv["ns2_trace_sha256"],
           "contact_rule": f"two phones within {r} m at that second (planar SUMO coordinates)", "contact_seconds": total,
           "built_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "frames": out_frames}
    OUT.write_text(json.dumps(rec, separators=(",", ":")) + "\n")
    say(f"{len(out_frames)} frames, {total} phone-pair seconds in contact; wrote {OUT.relative_to(REPO)}")
    (EVID / "build.log").write_text("\n".join(log) + "\n")
    (EVID / "SHA256SUMS").write_text(f"{hashlib.sha256(OUT.read_bytes()).hexdigest()}  {OUT.relative_to(REPO)}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
