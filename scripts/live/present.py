"""make present: every feature running live, in the order of the talk, timed (about 7 minutes). Each step is a real run computed now.

    python scripts/live/present.py [--dry] [--only v2x,sos]

Steps (the supervisor can stop after any one and change its parameters: docs/LIVE_RUNS.md):
  1 run-v2x       RQ3  ambulance + V2X alert in SUMO's window, thesis settings, checked against the saved run
  2 run-sos-v2v   crash SOS rule + car-to-car warning and reroute in SUMO's window
  3 run-signals   RQ3  fixed-time vs Q-learning signals, two windows side by side
  4 run-forecast  RQ1  the Model Lab page opens; the same forecast is computed in the terminal and checked
  5 run-mesh      RQ4  PONS phone-to-phone mesh drawn as it runs, checked seed by seed
  6 run-offline   RQ5  Chrome with DevTools: the trip goes offline and still works
  7 crash graph   RQ6  the SOS screen's live accelerometer graph (a phone over HTTPS; on the laptop the thesis crash trace is replayed)
Each step's log, time and exit code go to evidence/live_runs/present_<stamp>/.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
import webbrowser
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PY, MESH_PY = sys.executable, str(REPO / "research/mesh_pons/.venv/bin/python")
LOCAL = os.environ.get("LOCAL_URL", "http://127.0.0.1:8011/")
STEPS = [
    ("v2x", "1 · Ambulance V2X alert (RQ3)", [PY, "scripts/live/run_v2x.py", "--speed", "10"], 80),
    ("sos", "2 · Crash SOS, car to car (a real collision inside SUMO)", [PY, "scripts/live/run_sos_v2v.py", "--collide", "--after", "300", "--speed", "10"], 70),   # R1: SUMO's own collision; its record feeds step 7
    ("signals", "3 · Smart signals: fixed time vs Q-learning (RQ3)", [PY, "scripts/live/run_signals.py", "--speed", "14"], 110),
    ("forecast", "4 · Traffic prediction, Model Lab (RQ1)", [PY, "-m", "core.ml.forecasting.layer.lab", "--sensor", "5"], 20),
    ("mesh", "5 · Phone-to-phone mesh (RQ4)", [MESH_PY, "-W", "ignore", "scripts/live/run_mesh.py", "--protocol", "epidemic", "--speed", "40"], 25),
    ("offline", "6 · Weak signal: offline trip (RQ5)", ["node", "frontend/tests/live/run_offline.cjs"], 95),
    ("graph", "7 · Crash detection graph (RQ6), the trace from step 2's collision", ["node", "frontend/tests/live/sos_graph.cjs", "--trace=sumo_collision"], 25),
]


def server_up() -> bool:
    try:
        return urllib.request.urlopen(LOCAL, timeout=3).status == 200
    except Exception:                                                  # noqa: BLE001
        return False


def start_server(log: Path) -> subprocess.Popen | None:
    if server_up():
        return None
    env = os.environ | {k: v for k, v in (l.split("=", 1) for l in (REPO / ".env").read_text().splitlines() if "=" in l and not l.startswith("#"))}
    env |= {"TRAFFICTWIN_TRAVELMUX_URL_DHAKA": env.get("TRAFFICTWIN_TRAVELMUX_URL_DHAKA", "http://127.0.0.1:9101")}
    p = subprocess.Popen([PY, "-m", "uvicorn", "app.main:app", "--app-dir", "backend", "--host", "127.0.0.1", "--port", LOCAL.rsplit(":", 1)[1].strip("/")],
                         cwd=REPO, env=env, stdout=log.open("w"), stderr=subprocess.STDOUT)
    for _ in range(60):
        if server_up():
            return p
        time.sleep(1)
    return p


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry", action="store_true", help="list the steps and their commands only")
    ap.add_argument("--only", default="", help="comma-separated step keys, e.g. v2x,mesh")
    a = ap.parse_args()
    steps = [s for s in STEPS if not a.only or s[0] in a.only.split(",")]
    if a.dry:
        for k, title, cmd, slot in steps:
            print(f"{title:55} ~{slot:>3} s  {' '.join(cmd)}")
        print(f"planned total ~{sum(s[3] for s in steps) / 60:.1f} min"); return 0
    out = REPO / "evidence/live_runs" / f"present_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    out.mkdir(parents=True, exist_ok=True)
    srv = start_server(out / "server.log") if any(k in ("forecast", "offline", "graph") for k, *_ in steps) else None
    env = os.environ | {"PYTHONPATH": f"{REPO}:{REPO / 'backend'}", "LOCAL_URL": LOCAL}
    rows, t_all = [], time.time()
    for k, title, cmd, slot in steps:
        print(f"\n{'=' * 78}\n{title}   (slot ~{slot} s)\n{'=' * 78}", flush=True)
        if k == "forecast":
            webbrowser.open(LOCAL + "app/lab/model-lab")
        t0 = time.time()
        with (out / f"{k}.log").open("w") as log:
            p = subprocess.Popen(cmd, cwd=REPO, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            for line in p.stdout:                                     # shown live and kept
                print(line, end="", flush=True); log.write(line)
            code = p.wait()
        used = round(time.time() - t0, 1)
        rows.append({"step": k, "title": title, "exit": code, "seconds": used, "slot_s": slot})
        print(f"--> {title}: exit {code}, {used} s (slot {slot} s)", flush=True)
    total = round(time.time() - t_all, 1)
    (out / "timing.json").write_text(json.dumps({"total_s": total, "steps": rows}, indent=1) + "\n")
    print(f"\nPRESENT: {sum(r['exit'] == 0 for r in rows)} of {len(rows)} steps exit 0, total {total / 60:.1f} min. Logs: {out.relative_to(REPO)}")
    if srv:
        srv.terminate()
    return 0 if all(r["exit"] == 0 for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
