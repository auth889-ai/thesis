"""Veins (OMNeT++ 6.2.0 + SUMO 1.21.0, IEEE 802.11p) on the Dhaka corridor: an independent second view, with OMNeT++'s GUI (Qtenv), where
radio frames are animated between cars. Its numbers are Veins's own (its PHY/MAC models), never presented as the thesis's.

    python scripts/live/run_veins.py sos [--share 1.0] [--txpower 20] [--seed 0] [--window 300] [--no-gui] [--sumo-gui]

sos   Veins's own TraCIDemo11p application, unchanged (Sommer et al.; the example in veins/examples/veins): a car that has stood still for
      10 s turns red and broadcasts a warning with its road; a car that hears it turns green, reroutes around that road
      (changeRoute(road, 9999)) and repeats the warning once. On the Dhaka corridor at Dhaka's density, queues make many cars "stand
      still", so the app warns about queues as well as the crash it was written for: that is its rule, shown as it is.
The scenario: the thesis's corridor network and Dhaka-density traffic (data/cities/dhaka/sumo/corridor), a --window of simulated
seconds starting at 600 s. Veins's example settings otherwise (config.xml, antenna.xml, 20 mW, 6 Mbit/s), only paths and the chosen
parameters changed. Built in research/veins_dhaka/ (generated). Veins and SUMO 1.21.0: third_party/veins/fetch.sh, SOURCES.md.
"""
from __future__ import annotations

import argparse
import gzip
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
UP = Path.home() / ".dhakaflow/upstream"
VEINS, OPP = UP / "veins", UP / "omnetpp-6.2.0"
SUMO_VENV = Path.home() / ".dhakaflow/venvs/sumo-veins"
CORRIDOR = REPO / "data/cities/dhaka/sumo/corridor"
WORK = REPO / "research/veins_dhaka"
PORT = 9999
BEGIN = 600


def sumo_bin(gui: bool) -> str:
    out = subprocess.run([str(SUMO_VENV / "bin/python"), "-c", "import sumo, os; print(sumo.SUMO_HOME)"], capture_output=True, text=True, check=True)
    return str(Path(out.stdout.strip()) / "bin" / ("sumo-gui" if gui else "sumo"))


def scenario(a) -> None:
    """Write the Dhaka scenario next to Veins's example settings; nothing in Veins is changed."""
    WORK.mkdir(parents=True, exist_ok=True)
    net = WORK / "dhaka_corridor.net.xml"
    if not net.exists():
        net.write_bytes(gzip.decompress((CORRIDOR / "dhaka_corridor.net.xml.gz").read_bytes()))
    shutil.copy(CORRIDOR / "dhaka_density.rou.xml", WORK / "dhaka_density.rou.xml")
    sys.path[:0] = [str(REPO), str(REPO / "backend")]
    from core.simulation.ambulance import service                 # the study's own ambulance: its vehicle type and its route on the corridor
    vt = service.write_vtype(WORK / "ambulance_type.rou.xml", service.settings())
    scen = service.scenario("dhaka", "dhaka_density")
    body = vt.read_text().replace("</routes>", "").replace("<routes>", "").strip()
    (WORK / "ambulance.rou.xml").write_text(f"""<routes>
{body}
  <route id="{service.ROUTE}" edges="{' '.join(scen['edges'])}"/>
  <vehicle id="{service.AMBULANCE}" type="{service.VTYPE}" route="{service.ROUTE}" depart="{BEGIN + a.ambulance_at}" departLane="best" departSpeed="max"/>
</routes>
""")
    for f in ("config.xml", "antenna.xml"):
        shutil.copy(VEINS / "examples/veins" / f, WORK / f)
    x0, y0, x1, y1 = [float(v) for v in re.search(r'convBoundary="([^"]+)"', net.read_text()[:20000]).group(1).split(",")]
    poly = WORK / "dhaka_buildings.poly.xml"
    if not poly.exists():                                  # OpenStreetMap buildings (ODbL) as SUMO polygons: what Veins's obstacle model shades
        import json
        import sumolib
        n = sumolib.net.readNet(str(net))
        out = ['<additional>']
        for i, el in enumerate(json.loads((REPO / "data/cities/dhaka/sumo/dhaka.buildings.json").read_text())["elements"]):
            pts = [n.convertLonLat2XY(g["lon"], g["lat"]) for g in el.get("geometry", [])]
            if len(pts) >= 3 and all(x0 - 50 <= x <= x1 + 50 and y0 - 50 <= y <= y1 + 50 for x, y in pts):
                out.append(f'  <poly id="b{el.get("id", i)}" type="building" color="200,180,160" fill="1" layer="-1" shape="{" ".join(f"{x:.1f},{y:.1f}" for x, y in pts)}"/>')
        out.append("</additional>")
        poly.write_text("\n".join(out) + "\n")
    (WORK / "dhaka.sumo.cfg").write_text(f"""<configuration>
  <input><net-file value="dhaka_corridor.net.xml"/><route-files value="dhaka_density.rou.xml,ambulance.rou.xml"/><additional-files value="dhaka_buildings.poly.xml"/></input>
  <time><begin value="{BEGIN}"/><end value="{BEGIN + a.window + 60}"/><step-length value="0.1"/></time>
  <processing><scale value="0.78"/><lateral-resolution value="0.8"/><time-to-teleport value="300"/><ignore-route-errors value="true"/></processing>
  <report><no-step-log value="true"/><no-warnings value="true"/></report>
</configuration>
""")
    (WORK / "dhaka.launchd.xml").write_text("""<?xml version="1.0"?>
<launch>
  <copy file="dhaka_corridor.net.xml"/>
  <copy file="dhaka_density.rou.xml"/>
  <copy file="ambulance.rou.xml"/>
  <copy file="dhaka_buildings.poly.xml"/>
  <copy file="dhaka.sumo.cfg" type="config"/>
</launch>
""")
    (WORK / "DhakaScenario.ned").write_text("""// The Dhaka corridor for Veins: Veins's own Scenario (cars, obstacles, annotations, connection manager), no road-side unit.
import org.car2x.veins.nodes.Scenario;
import org.car2x.veins.nodes.TrafficLight;

network DhakaScenario extends Scenario
{
    submodules:
        tls[0]: TrafficLight {
        }
}
""")
    ini = (VEINS / "examples/veins/omnetpp.ini").read_text()
    ini = re.sub(r"^network = .*$", "network = DhakaScenario", ini, flags=re.M)
    ini = re.sub(r"^debug-on-errors = .*$", "debug-on-errors = false", ini, flags=re.M)        # an error ends the run instead of waiting for a debugger
    ini = re.sub(r"^image-path = .*$", f"image-path = {VEINS / 'images'}", ini, flags=re.M)
    ini = re.sub(r"^sim-time-limit = .*$", f"sim-time-limit = {BEGIN + a.window}s", ini, flags=re.M)
    ini = re.sub(r"^\*\.playgroundSizeX = .*$", f"*.playgroundSizeX = {x1 + 200:.0f}m", ini, flags=re.M)
    ini = re.sub(r"^\*\.playgroundSizeY = .*$", f"*.playgroundSizeY = {y1 + 200:.0f}m", ini, flags=re.M)
    ini = re.sub(r'^\*\.obstacles\.obstacles = .*$', '*.obstacles.obstacles = xmldoc("config.xml", "//AnalogueModel[@type=\'SimpleObstacleShadowing\']/obstacles")', ini, flags=re.M)
    ini = re.sub(r'^\*\.manager\.launchConfig = .*$', '*.manager.launchConfig = xmldoc("dhaka.launchd.xml")', ini, flags=re.M)
    ini = re.sub(r"^\*\.\*\*\.nic\.mac1609_4\.txPower = .*$", f"*.**.nic.mac1609_4.txPower = {a.txpower:g}mW", ini, flags=re.M)
    ini = re.sub(r"^\*\.manager\.port = .*$", f"*.manager.port = {PORT}\n*.manager.connectAt = {BEGIN}s\n*.manager.penetrationRate = {a.share:g}\n*.manager.seed = {a.seed}", ini, flags=re.M)
    ini = re.sub(r"^\*\.connectionManager\.maxInterfDist = .*$", "*.connectionManager.maxInterfDist = 2600m", ini, flags=re.M)
    ini = re.sub(r"^\*\.rsu\[.*$\n?", "", ini, flags=re.M)                 # no road-side unit in this scenario
    ini = re.sub(r"^\*\.node\[\*0\]\.veinsmobility\.accident.*$\n?", "", ini, flags=re.M)
    if a.mode == "v2x":                                    # our ambulance application (research/veins_dhaka/src); no crash
        ini = ini.replace('*.node[*].applType = "TraCIDemo11p"', '*.node[*].applType = "AmbulanceAlert11p"')
        ini = re.sub(r"^\*\.manager\.penetrationRate = .*$", "*.manager.penetrationRate = 1", ini, flags=re.M)   # every car gets a radio; the app applies the share
        ini = ini.replace("[Config Default]", f"*.node[*].appl.makewayDistance = {a.makeway:g}m\n*.node[*].appl.equippedShare = {a.share:g}\n"
                          f"*.node[*].appl.guiColours = {'true' if getattr(a, 'gui_colours', False) else 'false'}\n\n[Config Default]")
        (WORK / "omnetpp.ini").write_text(ini)
        return
    ini = ini.replace("[Config Default]", f"""*.node[{a.crash_node}].veinsmobility.accidentCount = 1
*.node[{a.crash_node}].veinsmobility.accidentStart = {a.crash_at}s
*.node[{a.crash_node}].veinsmobility.accidentDuration = {a.window}s

[Config Default]""")
    (WORK / "omnetpp.ini").write_text(ini)


WATCH = """  What to watch (make gui-veins; display only, the run's logic is unchanged):
    OMNeT++ Qtenv window   press RUN (F5) or FAST (F6). Each car is a node; a line drawn between two nodes is an 802.11p frame in the
                           air (Veins's own animation). The ambulance's icon is green and shows "alerts sent N"; a car that heard the
                           alert within 100 m turns yellow while it makes way (lane-change mode 1605, keep right); grey = no radio.
    sumo-gui window        the same traffic, driven by Veins through SUMO 1.21: the ambulance green, cars making way yellow, back to
                           grey when released (30 s). Zoom to the ambulance: Edit > Locate vehicle > ambulance_alert.
  The numbers printed at the end are Veins's (its PHY/MAC and building shadowing), not the thesis's (make run-v2x)."""


def port_free(p: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", p)) != 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["sos", "v2x"])
    ap.add_argument("--ambulance-at", type=int, default=20, help="v2x: seconds into the window when the ambulance departs")
    ap.add_argument("--makeway", type=float, default=100.0, help="v2x: metres within which a car that hears the alert makes way (thesis: 100)")
    ap.add_argument("--share", type=float, default=1.0, help="Veins penetrationRate: share of cars with a radio")
    ap.add_argument("--txpower", type=float, default=20.0, help="transmit power, mW (Veins's example: 20)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--window", type=int, default=300, help="simulated seconds")
    ap.add_argument("--crash-node", type=int, default=10, help="the car (in order of entering) that crashes")
    ap.add_argument("--crash-at", type=int, default=60, help="seconds into the window")
    ap.add_argument("--no-gui", action="store_true")
    ap.add_argument("--sumo-gui", action="store_true", help="also show SUMO's own window of the same traffic")
    ap.add_argument("--gui-colours", action="store_true", help="v2x, display only: alerted cars yellow, the ambulance green (both windows); prints what to watch")
    a = ap.parse_args(argv)
    if not (VEINS / "src/libveins.dylib").exists():
        print("STOP: Veins is not built: third_party/veins/fetch.sh"); return 1
    scenario(a)
    print(f"SECOND VIEW (independent simulator, not the thesis's): Veins 5.3.1 + OMNeT++ 6.2.0 + SUMO 1.21.0, IEEE 802.11p,"
          f" Dhaka corridor at Dhaka density, {int(a.share * 100)} % cars with a radio, {a.txpower:g} mW, seed {a.seed};"
          + (f" car {a.crash_node} crashes at {a.crash_at} s. App: Veins's TraCIDemo11p, unchanged." if a.mode == "sos" else
             f" the study's ambulance departs at {a.ambulance_at} s and broadcasts an alert every second; cars within {a.makeway:g} m make way"
             " (rule v2). App: research/veins_dhaka/src/AmbulanceAlert11p (ours).") + ("" if a.no_gui else
             "\n  In the OMNeT++ window press RUN (F5) or FAST (F6): radio frames are drawn between cars; blue = ambulance, orange = making way."), flush=True)
    if getattr(a, "gui_colours", False) and not a.no_gui:
        print(WATCH, flush=True)
    if not port_free(PORT):
        print(f"STOP: port {PORT} is in use (another veins_launchd?)."); return 1
    launchd = subprocess.Popen([sys.executable, str(VEINS / "bin/veins_launchd"), "-c", sumo_bin(a.sumo_gui), "-p", str(PORT)],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            if not port_free(PORT):
                break
            time.sleep(0.1)
        env = os.environ.copy()
        env["PATH"] = f"{OPP / 'bin'}:{env['PATH']}"
        env["DYLD_LIBRARY_PATH"] = f"{OPP / 'lib'}:{VEINS / 'src'}"
        lib = WORK / "src/libdhakaveins.dylib"
        if a.mode == "v2x" and not lib.exists():
            print("STOP: build the ambulance app first: cd research/veins_dhaka/src && opp_makemake ... (docs/LIVE_RUNS.md)"); return 1
        cmd = ["opp_run", "-u", "Cmdenv" if a.no_gui else "Qtenv", "-c", "Default", "-l", str(VEINS / "src/veins"), "-l", str(WORK / "src/dhakaveins"),
               "-n", f"{VEINS / 'src/veins'}:{WORK / 'src'}:{WORK}", f"--image-path={VEINS / 'images'}", "omnetpp.ini"]
        r = subprocess.run(cmd, cwd=WORK, env=env, capture_output=a.no_gui, text=True)
        if a.no_gui:
            (WORK / "last_cmdenv.log").write_text(r.stdout + r.stderr)
            if r.returncode:
                print((r.stdout + r.stderr)[-1500:]); return r.returncode
    finally:
        launchd.terminate()
    sca = sorted((WORK / "results").glob("Default-*.sca"), key=lambda p: p.stat().st_mtime)
    if sca:
        text = sca[-1].read_text()
        def total(name: str) -> int:
            return int(sum(float(v) for v in re.findall(rf"^scalar \S+ {name} (\S+)$", text, re.M)))
        print(f"  Veins: cars {len(set(re.findall(r'^scalar \S*node\[(\d+)\]', text, re.M)))}, messages generated {total('generatedWSMs')},"
              f" received {total('receivedWSMs')}, frames lost (collisions, low signal) {total('RXTXLostPackets') + total('SNIRLostPackets')}")
        if a.mode == "v2x":
            amb = re.findall(r"^scalar \S+ ambulanceTimeInNetwork (\S+)$", text, re.M)
            print(f"  Veins: ambulance alerts sent {total('alertsSent')}, alert receptions {total('alertsReceived')}, cars that made way {total('madeWay')},"
                  f" ambulance time in the window {amb[0] if amb else 'not finished'} s")
            print("  These are Veins's numbers (its 802.11p PHY/MAC and building shadowing); the thesis's RQ3 numbers come from make run-v2x.")
        else:
            print("  These are Veins's numbers (its 802.11p PHY/MAC); the thesis's car-to-car SOS numbers come from make run-sos-v2v.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
