"""Seeded random demand stress test: randomTrips -> duarouter (error census) -> SUMO run."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path


def _tool(name: str) -> str:
    """Locate a SUMO python tool across install layouts (SUMO_HOME, pip wheel, conda)."""
    import shutil
    candidates = []
    if os.environ.get("SUMO_HOME"):
        candidates.append(Path(os.environ["SUMO_HOME"]) / "tools" / name)
    try:
        import sumo  # eclipse-sumo pip wheel
        candidates.append(Path(sumo.SUMO_HOME) / "tools" / name)
    except ImportError:
        pass
    binary = shutil.which("sumo")
    if binary:
        prefix = Path(binary).resolve().parent.parent
        candidates.append(prefix / "share" / "sumo" / "tools" / name)
    for c in candidates:
        if c.exists():
            return str(c)
    raise FileNotFoundError(f"SUMO tool not found: {name}; tried {[str(c) for c in candidates]}")


def generate_and_route(net_file: Path, out_dir: Path, seed: int,
                       end_time: float, period: float) -> dict:
    """period = mean seconds between trip insertions (randomTrips semantics)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    trips = out_dir / f"trips_seed{seed}.trips.xml"
    routes = out_dir / f"routes_seed{seed}.rou.xml"
    rt_cmd = [sys.executable, _tool("randomTrips.py"), "-n", str(net_file),
              "-o", str(trips), "--seed", str(seed), "-b", "0", "-e", str(end_time),
              "-p", str(period), "--fringe-factor", "5"]
    rt = subprocess.run(rt_cmd, capture_output=True, text=True)
    if rt.returncode != 0:
        raise RuntimeError(f"randomTrips failed: {rt.stderr[-500:]}")
    dr_cmd = ["duarouter", "-n", str(net_file), "--route-files", str(trips),
              "-o", str(routes), "--ignore-errors", "--seed", str(seed),
              "--no-warnings", "false"]
    dr = subprocess.run(dr_cmd, capture_output=True, text=True)
    (out_dir / f"duarouter_seed{seed}.log").write_text(dr.stdout + "\n" + dr.stderr)
    n_trips = sum(1 for line in trips.read_text().splitlines() if "<trip " in line)
    n_routed = sum(1 for line in routes.read_text().splitlines() if "<vehicle " in line) \
        if routes.exists() else 0
    unroutable = len(re.findall(r"No connection between|Mandatory edge|not found",
                                dr.stdout + dr.stderr))
    record = {
        "seed": seed, "n_trips": n_trips, "n_routed": n_routed,
        "n_unroutable_msgs": unroutable,
        "unroutable_fraction": round(1 - n_routed / n_trips, 4) if n_trips else None,
        "randomTrips_cmd": rt_cmd, "duarouter_cmd": dr_cmd,
        "routes_file": str(routes),
    }
    (out_dir / f"demand_record_seed{seed}.json").write_text(json.dumps(record, indent=2))
    return record


def run_simulation(net_file: Path, routes_file: Path, out_dir: Path, seed: int,
                   end_time: float) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    tripinfo = out_dir / "tripinfo.xml"
    summary = out_dir / "summary.xml"
    log = out_dir / "sumo.log"
    cmd = ["sumo", "-n", str(net_file), "--route-files", str(routes_file),
           "--begin", "0", "--end", str(end_time), "--seed", str(seed),
           "--step-length", "1", "--tripinfo-output", str(tripinfo),
           "--summary-output", str(summary), "--log", str(log),
           "--no-step-log", "true", "--duration-log.statistics", "true"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    logtxt = log.read_text(errors="ignore") if log.exists() else ""
    # Count EVENTS, not any line containing the word: one teleport emits both a
    # "Teleporting vehicle" warning and an "ends teleporting" line, plus the
    # word appears in SUMO's closing statistics.
    teleport_events = re.findall(r"Teleporting vehicle '([^']+)'; waited too long \((\w+)\)",
                                 logtxt)
    record = {
        "command": cmd, "returncode": proc.returncode,
        "teleports": len(teleport_events),
        "teleport_reasons": Counter(reason for _, reason in teleport_events),
        "collisions": (int(m.group(1)) if (m := re.search(r"Collisions:\s*(\d+)", logtxt))
                       else len(re.findall(r"Warning:.*collision", logtxt))),
        "emergency_braking": len(re.findall(
            r"performs emergency braking", logtxt)),
        "tripinfo": str(tripinfo), "summary": str(summary),
    }
    (out_dir / "sim_record.json").write_text(json.dumps(record, indent=2))
    if proc.returncode != 0:
        raise RuntimeError(f"sumo failed rc={proc.returncode}: {proc.stderr[-500:]}")
    return record
