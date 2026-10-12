"""Standalone checks for this folder (not the project's test suite). Run: .venv/bin/python scripts/selfcheck.py"""
import hashlib, json, re, subprocess, sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "scripts"))
fails = []


def check(cond, msg):
    print(("ok   " if cond else "FAIL ") + msg)
    if not cond:
        fails.append(msg)


exp = yaml.safe_load(open(HERE / "configs/dhaka.yaml"))
mov = json.loads((HERE / "evidence/movement.json").read_text())
trace = HERE / mov["ns2_trace"]
check(hashlib.sha256(trace.read_bytes()).hexdigest() == mov["ns2_trace_sha256"], "ns2 trace matches hash in movement.json")

# the adapter reads exactly what traceExporter wrote: one entry per kept vehicle per second, times 0..window-1
import importlib
run = importlib.import_module("03_run_pons")
moves, n = run.read_ns2(trace)
win = exp["window"]["end_s"] - exp["window"]["begin_s"]
check(n == mov["vehicles_kept_present_whole_window"], f"adapter sees {n} nodes = kept vehicles")
times = sorted({m[0] for m in moves})
check(times == [float(t) for t in range(win)], f"trace spans 0..{win - 1} s, one entry per second")
check(len(moves) == n * win, "every node has an entry at every second (no parked phantom relays)")
# positions in the trace equal SUMO's positions in the window FCD (translation only)
fcd = (HERE / "work" / f"{mov['city']}.window.fcd.xml").read_text()
xy = re.findall(r'<vehicle id="([^"]+)" x="([^"]+)" y="([^"]+)"', fcd)
check(len(xy) == len(moves), "ns2 trace has one line per FCD vehicle record")
trace_xy = sorted((round(m[2], 2), round(m[3], 2)) for m in moves)
fcd_xy = sorted((round(float(x), 2), round(float(y), 2)) for _, x, y in xy)
check(trace_xy == fcd_xy, "ns2 positions equal SUMO FCD positions (rounded to cm)")

runs = list((HERE / "evidence/runs").glob("*.json"))
check(len(runs) == len(exp["routers"]) * len(exp["seeds"]), f"{len(runs)} run JSONs present")
for p in runs:
    r = json.loads(p.read_text())
    check(r["label"] == "SIMULATED" and r["ns2_trace_sha256"] == mov["ns2_trace_sha256"] and r["nodes"] == n, f"{p.name} labelled and bound to the trace")
eq = json.loads((HERE / "evidence/generator_equivalence.json").read_text())
check(len(eq) == 2 * len(exp["seeds"]) and all(e["identical_stats"] for e in eq), "adapter message generator == PONS generator on Epidemic and PRoPHET")

# RESULTS.md regenerates identically from the evidence
before = (HERE / "RESULTS.md").read_text()
subprocess.run([sys.executable, str(HERE / "scripts/04_report.py")], check=True, capture_output=True)
check((HERE / "RESULTS.md").read_text() == before, "RESULTS.md regenerates identically from evidence/")
sums = subprocess.run(["shasum", "-a", "256", "-c", "--quiet", "evidence/SHA256SUMS"], cwd=HERE, capture_output=True, text=True)
check(sums.returncode == 0, "evidence/SHA256SUMS verifies")
check("SIMULATED" in before and before.count("SIMULATED") >= 8, "RESULTS.md labels numbers as simulated")
check(subprocess.run(["git", "status", "--porcelain", "upstream/PONS"], cwd=HERE / "upstream/PONS", capture_output=True, text=True).stdout == "", "upstream PONS clone is unmodified")

print("\n" + ("ALL CHECKS PASSED" if not fails else f"{len(fails)} CHECK(S) FAILED"))
sys.exit(1 if fails else 0)
