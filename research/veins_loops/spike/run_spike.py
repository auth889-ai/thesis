"""Feasibility spike (2026-10-12): SUMO 1.21 with --num-clients 2, Veins (order 1, 802.11p) + our Python client (order 2), lockstep.
    python research/veins_loops/spike/run_spike.py [--gui]
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
UP = Path.home() / ".dhakaflow/upstream"
VEINS, OPP = UP / "veins", UP / "omnetpp-6.2.0"
HERE = Path(__file__).resolve().parent
DHAKA = REPO / "research/veins_dhaka"
PY121 = Path.home() / ".dhakaflow/venvs/sumo-veins/bin/python"
PORT = 9998
gui = "--gui" in sys.argv
env = os.environ.copy()
env["PATH"] = f"{OPP / 'bin'}:{env['PATH']}"
env["DYLD_LIBRARY_PATH"] = f"{OPP / 'lib'}:{VEINS / 'src'}"
out = HERE / "spike_client.json"
if out.exists():
    out.rename(HERE / f"spike_client.{int(time.time())}.json")
t0 = time.time()
client = subprocess.Popen([str(PY121), str(HERE / "client.py"), str(PORT), str(out)], cwd=HERE)
cmd = ["opp_run", "-u", "Qtenv" if gui else "Cmdenv", "-c", "Default", "-l", str(VEINS / "src/veins"), "-l", str(DHAKA / "src/dhakaveins"),
       "-n", f"{VEINS / 'src/veins'}:{DHAKA / 'src'}:{HERE.parent}", f"--image-path={VEINS / 'images'}", "omnetpp.ini"]
r = subprocess.run(cmd, cwd=HERE, env=env, capture_output=True, text=True)
(HERE / "veins_cmdenv.log").write_text(r.stdout + r.stderr)
rc = client.wait(timeout=120)
print(f"veins exit {r.returncode}, client exit {rc}, wall {time.time() - t0:.0f} s; veins log tail:\n" + "\n".join((r.stdout + r.stderr).strip().splitlines()[-8:]))
if out.exists():
    d = json.loads(out.read_text()); print("client:", {k: v for k, v in d.items() if k != "times"})
