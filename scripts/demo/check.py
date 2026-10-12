"""make check: is this laptop ready for the three demos? No internet, AWS or login is used. Prints OK or the exact fix per line.

    python scripts/demo/check.py
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MESH_PY = REPO / "research/mesh_pons/.venv/bin/python"
SUMO_VERSION = "1.27.1"


def sumo_version(binary: str) -> str | None:
    path = shutil.which(binary)
    if not path:
        return None
    out = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=60).stdout
    return out.splitlines()[0] if out else None


def checks(repo: Path = REPO) -> list[tuple[str, bool, str, bool]]:
    """(what, ok, fix, needed) for every check. `needed` False = optional (only the video uses it)."""
    out = []
    add = lambda what, ok, fix, needed=True: out.append((what, bool(ok), fix, needed))  # noqa: E731
    add(f"Python 3.11 or newer (this is {sys.version.split()[0]})", sys.version_info >= (3, 11), "install Miniconda, then: conda install python=3.13")
    for b in ("sumo", "sumo-gui"):
        v = sumo_version(b)
        add(f"{b} {SUMO_VERSION}" + (f" (found: {v})" if v else ""), v and SUMO_VERSION in v, f"pip install eclipse-sumo=={SUMO_VERSION} traci=={SUMO_VERSION}")
    for mod, fix in (("traci", f"pip install traci=={SUMO_VERSION}"), ("matplotlib", "pip install matplotlib"), ("yaml", "pip install pyyaml")):
        add(f"Python module {mod}", importlib.util.find_spec(mod), fix)
    pons = MESH_PY.exists() and subprocess.run([str(MESH_PY), "-c", "import pons, matplotlib, yaml"], capture_output=True).returncode == 0
    add("mesh environment (research/mesh_pons/.venv with pons-dtn 0.2.1)", pons,
        "cd research/mesh_pons && python3.11 -m venv .venv && .venv/bin/pip install pons-dtn==0.2.1 pyyaml matplotlib")
    for rel, what in (("data/cities/dhaka/sumo/corridor/dhaka_corridor.net.xml.gz", "Dhaka corridor road network"),
                      ("data/cities/dhaka/sumo/corridor/dhaka_density.rou.xml", "Dhaka corridor traffic (Dhaka density)"),
                      ("core/simulation/ambulance/configs/ambulance.yaml", "ambulance study settings"),
                      ("results/emergency/dhaka/rq2/summary.json", "saved ambulance study results"),
                      ("results/forecasting/rq1/summary.json", "saved forecasting results (RQ1)"),
                      ("results/networking/mesh/dhaka/summary.json", "saved mesh study results")):
        add(f"{what}: {rel}", (repo / rel).exists(), "make fetch-data   (restores data kept off this Mac; see data/MANIFEST.yaml)")
    mv = repo / "research/mesh_pons/evidence/movement.json"
    ok = False
    if mv.exists():
        m = json.loads(mv.read_text())
        trace = repo / "research/mesh_pons" / m["ns2_trace"]
        ok = trace.exists() and hashlib.sha256(trace.read_bytes()).hexdigest() == m["ns2_trace_sha256"]
    add("mesh movement trace, sha256 as recorded", ok, "cd research/mesh_pons && .venv/bin/python scripts/02_export_movement.py")
    add("a screen for the SUMO window", sys.platform == "darwin" or os.environ.get("DISPLAY"), "run from a terminal on the laptop's own desktop (not over ssh)")
    add("ffmpeg (only for the walkthrough video)", shutil.which("ffmpeg"), "brew install ffmpeg", needed=False)
    return out


def main() -> int:
    print("CHECK: is this laptop ready for make demo-ambulance, demo-forecast and demo-mesh? Nothing here uses the internet.\n")
    bad = 0
    for what, ok, fix, needed in checks():
        print(f"  {'OK  ' if ok else ('FAIL' if needed else 'warn')}  {what}")
        if not ok:
            print(f"        FIX: {fix}")
            bad += needed
    print("\nReady." if not bad else f"\n{bad} needed item(s) missing: run the FIX lines above, then make check again.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
