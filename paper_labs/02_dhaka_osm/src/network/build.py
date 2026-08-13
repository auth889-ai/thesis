"""netconvert wrapper: OSM -> .net.xml with recorded command, classified warnings."""
from __future__ import annotations

import json
import os
import re
import subprocess
from collections import Counter
from pathlib import Path

# Option set justified in ASSUMPTIONS.md; changing it is a documented decision.
NETCONVERT_OPTIONS = [
    # --- CRITICAL for Bangladesh: left-hand traffic. -------------------------
    # Bangladesh drives on the LEFT. Without this flag netconvert builds
    # right-hand-drive geometry: internal junction lanes, turn connections and
    # right-of-way are all mirrored, which silently invalidates every downstream
    # control experiment. Added 2026-08-13 after auditing the 090ec31 scaffold,
    # which omitted it (defect recorded in ASSUMPTIONS.md -> MODIFIED_BY_US).
    "--lefthand",
    "--geometry.remove",
    "--junctions.join",
    "--tls.guess-signals",
    "--tls.join",
    "--tls.default-type", "static",
    "--remove-edges.isolated",
    "--keep-edges.components", "1",
    "--no-turnarounds.tls",
    # keep OSM street names so signalized junctions can be sampled by real name
    "--output.street-names", "true",
]

# Warning classes we know and accept WITH documentation; anything else lands in
# 'unclassified' and must be reviewed before PASS.
WARNING_PATTERNS = {
    "removed_geometry_node": r"Removed \d+ geometry",
    "discarded_isolated_edges": r"Discarded .* isolated|Removed \d+ edges",
    "kept_components": r"Found \d+ components|keeping the largest",
    "junction_join": r"Joining junctions|joined \d+ junction",
    "tls_guess": r"Guessed|guessed .* tls|traffic light",
    "turnaround": r"turnaround",
    "speed_or_lane_default": r"(no|missing) .*(speed|lane)|using default",
    "edge_shape": r"shape|geometry.*(broken|invalid)",
    "connection_guess": r"connection|Connection",
}


def classify_warnings(log_text: str) -> dict:
    counts: Counter = Counter()
    unclassified: list[str] = []
    for line in log_text.splitlines():
        if "Warning" not in line and "Error" not in line:
            continue
        for name, pat in WARNING_PATTERNS.items():
            if re.search(pat, line, flags=re.IGNORECASE):
                counts[name] += 1
                break
        else:
            counts["unclassified"] += 1
            if len(unclassified) < 40:
                unclassified.append(line.strip())
    return {"counts": dict(counts), "unclassified_samples": unclassified}


def build_network(osm_file: Path, net_file: Path, out_dir: Path,
                  typemap: Path | None = None) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    net_file = Path(net_file)
    net_file.parent.mkdir(parents=True, exist_ok=True)
    if typemap is None:
        sumo_home = os.environ.get("SUMO_HOME", "")
        cand = Path(sumo_home) / "data/typemap/osmNetconvert.typ.xml"
        typemap = cand if cand.exists() else None
    cmd = ["netconvert", "--osm-files", str(osm_file), "-o", str(net_file)]
    if typemap:
        cmd += ["--type-files", str(typemap)]
    cmd += NETCONVERT_OPTIONS
    proc = subprocess.run(cmd, capture_output=True, text=True)
    log = proc.stdout + "\n" + proc.stderr
    (out_dir / "netconvert.log").write_text(log)
    from ..osm.download import sha256_file
    record = {
        "command": cmd,
        "returncode": proc.returncode,
        "typemap": str(typemap) if typemap else None,
        "net_sha256": sha256_file(net_file) if net_file.exists() else None,
        "net_bytes": net_file.stat().st_size if net_file.exists() else 0,
        "warnings": classify_warnings(log),
    }
    (out_dir / "netconvert_record.json").write_text(json.dumps(record, indent=2))
    if proc.returncode != 0:
        raise RuntimeError(f"netconvert failed rc={proc.returncode}; see netconvert.log")
    return record
