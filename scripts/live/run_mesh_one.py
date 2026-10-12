"""The ONE simulator (Keranen, Ott, Karkkainen, SIMUTools 2009; GPL-3.0, built by third_party/the-one/fetch.sh) on the RQ4 Dhaka movement:
an independent second view of the mesh, with its own GUI. Its numbers are reported as The ONE's, not as the thesis's (the thesis used PONS).

    python scripts/live/run_mesh_one.py [--protocol epidemic|spray_and_wait|prophet] [--range 10] [--seed 1] [--no-gui]

Movement: the study's own 1-second positions of its 17 phones (research/mesh_pons/work/dhaka.window.fcd.xml, the file the sha256-checked
ns2 trace was exported from) in The ONE's ExternalMovement format. Radio, message rate, size and lifetime as in the study's config.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
ONE = Path.home() / ".dhakaflow/upstream/the-one"
MESH = REPO / "research/mesh_pons"
OUT = REPO / "evidence/live_runs/mesh_one"
ROUTER = {"epidemic": "EpidemicRouter", "spray_and_wait": "SprayAndWaitRouter", "prophet": "ProphetRouter"}


# What The ONE's own GUI draws, read from its sources at the pinned v1.6.0 (gui/playfield/NodeGraphic.java lines 29-37, 84-105, 110-121,
# 160-200; gui/playfield/MessageGraphic.java line 18): nothing here is ours, and the colours cannot be changed from a settings file.
LEGEND = """  The ONE's GUI (its own drawing; GPL-3.0, v1.6.0):
    blue square + blue name   a phone (one of the study's 17), at the SUMO position of that second
    green circle              the phone's radio range (10 m in the thesis setting), when "range" is ticked
    black line                a connection: two phones within range of each other right now
    red line                  a message being transferred between two phones (one copy spreading)
    small squares by a phone  its buffer: how many message copies it carries (blue/green alternate per copy; a blue/red stack = tens)
    magenta square            the phone selected in the node list
  Controls: Play runs it; the speed slider sets simulated seconds per real second; the event log lists each transfer and delivery.
  PONS (the thesis's simulator) has no GUI of its own: `make run-mesh` draws it live with matplotlib (our view of PONS's state)."""


def movement(out: Path) -> int:
    """The study's window as `t id x y` lines (y flipped so north is up in The ONE's window); returns the number of phones."""
    steps = [(float(ts.get("time")), [(v.get("id"), float(v.get("x")), float(v.get("y"))) for v in ts.iter("vehicle")])
             for ts in ET.parse(MESH / "work/dhaka.window.fcd.xml").getroot().iter("timestep")]
    ids = sorted({v for _, vs in steps for v, _, _ in vs}, key=lambda s: int(s[3:]) if s[3:].isdigit() else s)
    xs = [x for _, vs in steps for _, x, _ in vs]; ys = [y for _, vs in steps for _, _, y in vs]
    lines = [f"{steps[0][0]} {steps[-1][0]} 0 {max(xs) - min(xs):.2f} 0 {max(ys) - min(ys):.2f} 0 0"]     # the header describes the shifted coordinates below
    for t, vs in steps:
        for v, x, y in vs:
            lines.append(f"{t} {ids.index(v)} {x - min(xs):.2f} {max(ys) - y:.2f}")
    out.write_text("\n".join(lines) + "\n")
    return len(ids)


def settings(path: Path, mv: Path, n: int, a, exp: dict, report_dir: Path) -> None:
    xs = mv.read_text().splitlines()[0].split()
    width, height = float(xs[3]) - float(xs[2]) + 50, float(xs[5]) - float(xs[4]) + 50
    ttl_min = max(1, round(exp["messages"]["ttl_s"] / 60))
    path.write_text(f"""Scenario.name = dhaka_{a.protocol}_r{a.range:g}_s{a.seed}
Scenario.simulateConnections = true
Scenario.updateInterval = 1
Scenario.endTime = {exp['window']['end_s'] - exp['window']['begin_s']}
Scenario.nrofHostGroups = 1
btInterface.type = SimpleBroadcastInterface
btInterface.transmitSpeed = 250k
btInterface.transmitRange = {a.range:g}
Group.groupID = p
Group.nrofHosts = {n}
Group.movementModel = ExternalMovement
ExternalMovement.file = {mv}
Group.router = {ROUTER[a.protocol]}
Group.bufferSize = 5M
Group.nrofInterfaces = 1
Group.interface1 = btInterface
Group.msgTtl = {ttl_min}
Group.waitTime = 0, 0
Group.speed = 0, 0
Events.nrof = 1
Events1.class = MessageEventGenerator
Events1.interval = {exp['messages']['interval_s']},{exp['messages']['interval_s']}
Events1.size = {exp['messages']['size_bytes']},{exp['messages']['size_bytes']}
Events1.hosts = 0,{n}
Events1.prefix = M
SprayAndWaitRouter.nrofCopies = 7
SprayAndWaitRouter.binaryMode = false
ProphetRouter.secondsInTimeUnit = 30
MovementModel.rngSeed = {a.seed}
MovementModel.worldSize = {width:.0f}, {height:.0f}
MovementModel.warmup = 0
Report.nrofReports = 1
Report.warmup = 0
Report.reportDir = {report_dir}/
Report.report1 = MessageStatsReport
Optimization.cellSizeMult = 5
Optimization.randomizeUpdateOrder = true
""")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--protocol", default="prophet", choices=list(ROUTER))
    ap.add_argument("--range", type=float, default=10.0)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--no-gui", action="store_true")
    ap.add_argument("--legend", action="store_true", help="print what each colour and line in The ONE's GUI means (make gui-mesh)")
    a = ap.parse_args(argv)
    if not (ONE / "core/DTNSim.class").exists():
        print("STOP: The ONE is not built here: third_party/the-one/fetch.sh"); return 1
    exp = yaml.safe_load((MESH / "configs/dhaka.yaml").read_text())
    OUT.mkdir(parents=True, exist_ok=True)
    mv = OUT / "dhaka_movement.txt"
    n = movement(mv)
    st = OUT / "dhaka.settings.txt"
    rep = OUT / "reports"
    rep.mkdir(exist_ok=True)
    settings(st, mv, n, a, exp, rep)
    print(f"SECOND VIEW (independent simulator, not the thesis's): The ONE 1.6.0 on the RQ4 Dhaka movement, {n} phones, {ROUTER[a.protocol]},"
          f" radio {a.range:g} m. {'GUI: press Play; links appear when phones meet.' if not a.no_gui else ''}", flush=True)
    if a.legend and not a.no_gui:
        print(LEGEND, flush=True)
    cmd = ["java", "-Xmx1G", "-cp", ".:lib/*", "core.DTNSim"] + (["-b", "1"] if a.no_gui else []) + [str(st)]
    subprocess.run(cmd, cwd=ONE, check=False, stdout=None if not a.no_gui else subprocess.DEVNULL)
    f = rep / f"dhaka_{a.protocol}_r{a.range:g}_s{a.seed}_MessageStatsReport.txt"
    if not f.exists():
        print("  The ONE wrote no report (closed before the end?)."); return 0
    stats = dict(re.findall(r"^(\w+): (\S+)$", f.read_text(), re.M))
    print(f"  The ONE: created {stats.get('created')}, delivered {stats.get('delivered')} (delivery_prob {stats.get('delivery_prob')}),"
          f" latency_avg {stats.get('latency_avg')} s, overhead {stats.get('overhead_ratio')}")
    print("  These are The ONE's numbers (its own radio and routing implementations); the thesis's RQ4 numbers come from PONS (make run-mesh).")
    (OUT / "last_run.json").write_text(json.dumps({"args": vars(a), "phones": n, "stats": stats}, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
