"""The ambulance loop with a PACKET-LEVEL network: Q-learning signals + IEEE 802.11p in Veins, ONE SUMO run (2026-10-12; new file).

    make veins-ambulance-loop                    # seed 11, arm rl_v2i, OMNeT++ Qtenv + sumo-gui windows (press RUN in Qtenv)
    make veins-ambulance-loop ARGS="--no-gui --seeds 11 12 13 14 15 --arms fixed rl rl_v2i"   # evidence/veins_ambulance_loop/

How the two simulators share one SUMO (SUMO 1.21.0, the version Veins 5.3.1 speaks; `--num-clients 2`):
  * client 1 (order 1) is Veins (OMNeT++ 6.2.0): every car and the ambulance are 802.11p nodes, a road-side unit (RSU) stands at
    each of the 3 Q-learning junctions. The ambulance's app (research/veins_loops/src/AmbulanceLoop11p, GPL-2.0-or-later as Veins)
    broadcasts a DENM-like frame every second; whether a car or an RSU receives it is decided by Veins's PHY/MAC (path loss,
    building shadowing, interference, collisions), not by a delivery ratio. A car that receives it makes way (rule v2, inside the
    app); an RSU that receives it writes the reception into its traffic light's SUMO parameters (veins.rx, veins.rx_t).
  * client 2 (order 2) is this module, in SUMO-RL's environment: the three signals are driven by the FROZEN RQ3 Q-learning agents
    (rl_signals.py, Q-tables results/emergency/dhaka/rq2/rl/, greedy, alpha 0); each second it reads the RSU flags, and a junction
    whose RSU really received the ambulance's frame in that second is handed to the copied adaptive-traffic-signal-rl override
    UNCHANGED (sumo_adapter.SumoPreemption) until the ambulance has passed, then back to Q-learning. Which junctions may act follows
    EMVLight (primary = being entered, secondary = next), as in rl_v2x_loop.py.
  The two exchange nothing but SUMO parameters; neither drives the other. Arms on the same seed and traffic: fixed (SUMO's own
  programmes, radios silent), rl (Q-learning, radios silent), rl_v2i (Q-learning + 802.11p DENM + RSU pre-emption + make-way).
  Packet counts come from Veins's own scalars (results/*.sca): DENMs sent, received per RSU, frames lost to interference/collisions
  (SNIRLostPackets) or while transmitting (RXTXLostPackets) per RSU; "not received" = sent - received - lost (below the receiver's
  sensitivity, i.e. out of range, which Veins does not count per node). Every number is computed in the run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import pickle
import re
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(REPO), str(REPO / "backend")]

UP = Path.home() / ".dhakaflow/upstream"
VEINS, OPP = UP / "veins", UP / "omnetpp-6.2.0"
SUMO121 = Path(os.environ.get("DHAKAFLOW_VEINS_SUMO_HOME") or Path.home() / ".dhakaflow/venvs/sumo-veins/lib/python3.13/site-packages/sumo")   # default eclipse-sumo 1.21.0 (TraCI API 21, Veins 5.3.1); DHAKAFLOW_VEINS_SUMO_HOME=<SUMO 1.27.1 home> with the local Veins patch (API 22)
LOOPS = REPO / "research/veins_loops"
DHAKA_VEINS = REPO / "research/veins_dhaka"                    # config.xml, antenna.xml (Veins's example settings), the OSM buildings polygons
OUT = REPO / "evidence/veins_ambulance_loop"
CITY, DEMAND = "dhaka", "dhaka_density"
ARMS = ("fixed", "rl", "rl_v2i")
LINK = "Veins 5.3.1 IEEE 802.11p (packet level: PHY/MAC, building shadowing, interference), 20 mW, 6 Mbit/s"
PORT0 = 9960


def veins_env() -> None:
    """SUMO 1.21's own tools (traci, sumolib) first on the path and SUMO_HOME at that SUMO: Veins 5.3.1 accepts TraCI API <= 21.
    Called when a run starts, never at import."""
    os.environ["SUMO_HOME"] = str(SUMO121)
    os.environ.setdefault("DHAKAFLOW_NO_OBSERVATORY", "1")
    tools = str(SUMO121 / "tools")
    if tools not in sys.path:
        sys.path.insert(0, tools)
    mod = sys.modules.get("traci")                              # the TraCI protocol must be 1.21's; sumolib (network reading) may be either release
    if mod is not None and not str(getattr(mod, "__file__", "")).startswith(tools):
        raise RuntimeError(f"traci was already imported from {mod.__file__}; the Veins loop needs SUMO 1.21's (start it in its own process)")


def ready() -> str | None:
    """Why the loop cannot run here, or None."""
    for p, what in ((VEINS / "src/libveins.dylib", "Veins is not built (third_party/veins/fetch.sh)"), (OPP / "bin/opp_run", "OMNeT++ 6.2.0 is missing"),
                    (SUMO121 / "bin/sumo", "SUMO 1.21.0 for Veins is missing (~/.dhakaflow/venvs/sumo-veins)"),
                    (LOOPS / "src/libveinsloops.dylib", "the loop's Veins apps are not built (research/veins_loops/src: opp_makemake ... && gmake MODE=release)"),
                    (DHAKA_VEINS / "dhaka_buildings.poly.xml", "the corridor's buildings for Veins are missing (make gui-veins once)")):
        if not p.exists():
            return what
    return None



# ------------------------------------------------------------------ the real sumo-gui (SUMO 1.27.1 behind the local Veins API-22 patch)
def sumo_version() -> str:
    try:
        out = subprocess.run([str(SUMO121 / "bin" / "sumo"), "--version"], capture_output=True, text=True, timeout=30).stdout
        return re.search(r"(\d+\.\d+\.\d+)", out).group(1)
    except Exception:                                              # noqa: BLE001
        return "?"


def gui_view(out: Path, rsus: list[dict], span_m: float = 1500.0, net_width_m: float | None = None, max_span_m: float | None = None, delay_ms: int = 0) -> Path:
    """sumo-gui settings: the real-world look, cars drawn 3x, framed on the road-side units (not the whole city)."""
    xs = [r["sumo_xy"][0] for r in rsus]; ys = [r["sumo_xy"][1] for r in rsus]
    cx, cy = statistics.fmean(xs), statistics.fmean(ys)
    span = max(span_m, (max(xs) - min(xs)) * 1.3, (max(ys) - min(ys)) * 1.3)
    if max_span_m:
        span = min(span, max_span_m)
    vs = out / "viewsettings.xml"
    vs.write_text(f"""<viewsettings>
  <scheme name="real world x10">
    <background backgroundColor="51,128,51" showGrid="0"/>
    <edges laneEdgeMode="0" laneShowBorders="1" showLinkDecals="1" showRails="1" hideConnectors="0" spreadSuperposed="0">
      <colorScheme name="uniform"><entry color="110,110,110"/></colorScheme>
    </edges>
    <vehicles vehicleQuality="2" vehicle_minSize="1" vehicle_exaggeration="10" vehicle_constantSize="0" showBlinker="1">
      <colorScheme name="given vehicle/type/route color"><entry color="190,190,190"/></colorScheme>
    </vehicles>
    <junctions junctionMode="0" drawLinkTLIndex="0">
      <colorScheme name="uniform"><entry color="70,70,70"/></colorScheme>
    </junctions>
    <pois poiSize_minSize="1" poiSize_exaggeration="1" poiName_show="1" poiName_size="22" poiName_color="white" poiName_bgColor="0,0,0"/>
    <polys polySize_minSize="0" polySize_exaggeration="1" polyName_show="0">
      <colorScheme name="given polygon color"/>
    </polys>
  </scheme>
  <viewport zoom="{100.0 * (net_width_m or span) / span:.0f}" x="{cx:.1f}" y="{cy:.1f}"/>
  <delay value="{delay_ms}"/>
</viewsettings>
""")
    return vs


def add_legend(conn, rsus: list[dict], lines: list[str], span_m: float) -> None:
    """Text on the map saying what each colour means (points of interest with names, top-left of the starting view)."""
    xs = [r["sumo_xy"][0] for r in rsus]; ys = [r["sumo_xy"][1] for r in rsus]
    x0 = statistics.fmean(xs) - 0.46 * span_m; y0 = statistics.fmean(ys) + 0.27 * span_m
    for k, s in enumerate(lines):
        try:
            conn.poi.add(s, x0, y0 - k * 0.035 * span_m, (0, 0, 0, 0), layer=40, width=1, height=1)
        except Exception:                                          # noqa: BLE001
            pass


def mark_rsus(conn, rsus: list[dict], ring_m: float = 45.0, label: str | None = "RSU {i}") -> None:
    """A red ring at each road-side unit and its label beside it (a point of interest 1.6 rings to the right)."""
    import math
    for i, r in enumerate(rsus):
        x, y = r["sumo_xy"]
        ring = [(x + ring_m * math.cos(a / 12 * math.pi), y + ring_m * math.sin(a / 12 * math.pi)) for a in range(24)]
        try:
            conn.polygon.add(f"ring{i}", ring, (230, 20, 20, 255), fill=False, layer=30, lineWidth=8)
            if label:
                conn.poi.add(label.format(i=i), x + 1.6 * ring_m, y + ring_m, (0, 0, 0, 0), layer=31, width=1, height=1)
        except Exception:                                          # noqa: BLE001
            pass


def qtenv_left(proc, width: int = 990, height: int = 880, timeout_s: float = 120.0) -> None:
    """Move the OMNeT++ Qtenv window to the left half of the screen once it appears (sumo-gui opens on the right). Display only;
    runs in a background thread and gives up quietly if macOS refuses (no Accessibility permission)."""
    import threading

    def go():
        t0 = time.time()
        while time.time() - t0 < timeout_s and proc.poll() is None:
            r = subprocess.run(["osascript", "-e", 'tell application "System Events" to tell process "opp_run" to if (count of windows) > 0 then '
                                f'set position of window 1 to {{0, 25}}', "-e", f'tell application "System Events" to tell process "opp_run" to if (count of windows) > 0 then set size of window 1 to {{{width}, {height}}}'],
                               capture_output=True, text=True)
            if r.returncode == 0 and "error" not in (r.stderr or "").lower():
                chk = subprocess.run(["osascript", "-e", 'tell application "System Events" to tell process "opp_run" to get position of window 1'], capture_output=True, text=True)
                if chk.returncode == 0 and chk.stdout.strip().startswith("0,"):
                    return
            time.sleep(1.0)
    threading.Thread(target=go, daemon=True).start()


def omnet_mode_line(gui: bool) -> str:
    return ("  OMNeT++ mode: Qtenv (its window, LEFT; press RUN then EXPRESS)   |   SUMO: sumo-gui window, RIGHT" if gui
            else "  OMNeT++ mode: Cmdenv (no OMNeT++ window; the radio is simulated in the background)")

# ------------------------------------------------------------------ files of one run
def net_bounds(net_path: Path) -> tuple[float, float, float, float]:
    import gzip
    head = (gzip.open(net_path, "rb") if str(net_path).endswith(".gz") else open(net_path, "rb")).read(20000).decode()
    return tuple(float(v) for v in re.search(r'convBoundary="([^"]+)"', head).group(1).split(","))     # type: ignore[return-value]


def rsu_positions(net_path: Path, tls_ids: list[str], margin: float = 25.0) -> list[dict]:
    """One road-side unit per traffic light, at the junction (mean of its connections' end nodes), in Veins's coordinates
    (TraCICoordinateTransformation::traci2omnet: x - x0 + margin, (y1 - y0) - (y - y0) + margin; margin = the manager's default 25)."""
    import sumolib
    net = sumolib.net.readNet(str(net_path))
    x0, y0, x1, y1 = net_bounds(net_path)
    out = []
    for tls in tls_ids:
        nodes = {c[0].getEdge().getToNode() for c in net.getTLS(tls).getConnections()}
        xs, ys = zip(*[n.getCoord()[:2] for n in nodes])
        sx, sy = statistics.fmean(xs), statistics.fmean(ys)
        out.append({"tls": tls, "sumo_xy": [round(sx, 2), round(sy, 2)], "veins_xy": [round(sx - x0 + margin, 2), round((y1 - y0) - (sy - y0) + margin, 2)]})
    return out


def write_sumo_cfg(out: Path, scen: dict, vtype: Path, scale: float, horizon: int, cfg: dict) -> Path:
    """The same SUMO options SUMO-RL's environment + rl_signals._extra give the thesis loop, as a config file the Veins manager launches."""
    add = out / "additional.xml"
    add.write_text(f'<additional>\n  <edgeData id="ed" file="{out / "edgedata.xml"}" freq="300" excludeEmpty="true"/>\n</additional>\n')
    cfgf = out / "sumo.sumocfg"
    cfgf.write_text(f"""<configuration>
  <input><net-file value="{scen['net']}"/><route-files value="{scen['routes']},{vtype}"/><additional-files value="{add},{DHAKA_VEINS / 'dhaka_buildings.poly.xml'}"/></input>
  <time><begin value="0"/><end value="{horizon}"/></time>
  <processing><scale value="{scale}"/><lateral-resolution value="{cfg['sumo']['lateral_resolution']}"/><time-to-teleport value="{cfg['sumo']['time_to_teleport_s']}"/>
    <max-depart-delay value="-1"/><waiting-time-memory value="1000"/><ignore-route-errors value="true"/><device.rerouting.probability value="0"/></processing>
  <output><tripinfo-output value="{out / 'tripinfo.xml'}"/><tripinfo-output.write-unfinished value="true"/><statistic-output value="{out / 'statistic.xml'}"/></output>
  <report><no-step-log value="true"/><no-warnings value="true"/></report>
</configuration>
""")
    return cfgf


def wait_for_first_client(port: int, timeout_s: float | None, say=None, proc=None) -> bool:
    """Block until ONE client (Veins) holds an established connection to SUMO's port, then return True; False on timeout.
    SUMO 1.21 handles the two clients' first commands in the order they connected and clears its input buffer only between them:
    Veins's setOrder leaves spare bytes (it sends a compound, SUMO assumes a fixed length), which are harmless when Veins is the FIRST
    client and fatal (`Storage::readChar(): invalid position`) when it is the last. So this client always connects second. In Qtenv,
    Veins connects when RUN is pressed, so this also waits for the person at the window."""
    import subprocess
    t0 = time.time(); told = False; last_note = 0.0
    while timeout_s is None or time.time() - t0 < timeout_s:      # None (windows): wait as long as the person takes to press RUN
        if proc is not None and proc.poll() is not None:
            return False                                           # the OMNeT++ window was closed: give up, never connect first
        try:
            out = subprocess.run(["lsof", "-nP", f"-iTCP:{port}", "-sTCP:ESTABLISHED"], capture_output=True, text=True).stdout
        except FileNotFoundError:
            return True                                            # no lsof: fall back to the retry logic
        if sum(1 for ln in out.splitlines() if "ESTABLISHED" in ln) >= 2:      # one connection shows twice (SUMO's end and Veins's end)
            return True
        if say and (not told and time.time() - t0 > 8 or told and time.time() - last_note > 120):
            say(f"  waiting for Veins to connect first (in the OMNeT++ window press RUN) ... {time.time() - t0:.0f} s"); told = True; last_note = time.time()
        time.sleep(0.5)
    return False


def free_port(start: int | None = None, n: int = 40) -> int:
    """A free TCP port from a window that starts at a process-dependent offset, so two loops started in the same minute probe different ports."""
    import socket
    start = PORT0 + (os.getpid() % 25) if start is None else start
    for p in range(start, start + n):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", p)) != 0:
                return p
    raise RuntimeError(f"no free port in {start}..{start + n}")


def write_veins(out: Path, cfgf: Path, scen: dict, rsus: list[dict], seed: int, arm: str, share: float, horizon: int, port: int, gui: bool, cfg: dict, beacons: bool = False, pos_check: int | None = None) -> Path:
    """omnetpp.ini for this run: Veins's example radio settings (research/veins_dhaka/config.xml, antenna.xml), our two apps, the RSUs.
    `beacons`: every car also sends Veins's 1 Hz beacon (a CAM-like background load on the channel), so collisions can occur."""
    from core.simulation.ambulance import service
    v2i = arm.endswith("_v2i")
    x0, y0, x1, y1 = net_bounds(Path(scen["net"]))
    d = out / "veins"; d.mkdir(parents=True, exist_ok=True)
    sumo_bin = SUMO121 / "bin" / ("sumo-gui" if gui else "sumo")
    extra = f" --start --quit-on-end --window-size 1000,880 --window-pos 990,25 --gui-settings-file {gui_view(d, [r for r in rsus if r["tls"] in {s["tls"] for s in scen.get("signals", [])}] or rsus, span_m=900, net_width_m=x1 - x0, max_span_m=1200)}" if gui else ""
    mk = cfg["alert"]["makeway"]
    rsu_lines = "\n".join(f'*.rsu[{i}].mobility.x = {r["veins_xy"][0]}\n*.rsu[{i}].mobility.y = {r["veins_xy"][1]}\n*.rsu[{i}].mobility.z = 3\n*.rsu[{i}].appl.tlsId = "{r["tls"]}"' for i, r in enumerate(rsus))
    ini = f"""[General]
cmdenv-express-mode = true
cmdenv-autoflush = true
cmdenv-status-frequency = 300s
**.cmdenv-log-level = info
image-path = {VEINS / 'images'}
network = SharedSumoScenario
debug-on-errors = false
print-undisposed = false
sim-time-limit = {horizon}s
result-dir = results
**.scalar-recording = true
**.vector-recording = false
*.playgroundSizeX = {x1 - x0 + 200:.0f}m
*.playgroundSizeY = {y1 - y0 + 200:.0f}m
*.playgroundSizeZ = 50m
*.numRsu = {len(rsus)}
*.canvasScale = {min(0.5, 800.0 / max(x1 - x0 + 200, 1)):.4f}
*.annotations.draw = {'true' if gui else 'false'}
*.obstacles.obstacles = xmldoc("{DHAKA_VEINS / 'config.xml'}", "//AnalogueModel[@type='SimpleObstacleShadowing']/obstacles")
*.manager.updateInterval = 1s
*.manager.host = "localhost"
*.manager.port = {port}
*.manager.order = 1
*.manager.connectAt = 0s
*.manager.penetrationRate = 1
*.manager.seed = {seed}
*.manager.autoShutdown = true
*.manager.command = "{sumo_bin}"
*.manager.configFile = "{cfgf}"
*.manager.commandLine = "$command --configuration-file $configFile --remote-port $port --seed {seed} --num-clients 2{extra}"
*.manager.ignoreUnknownSubscriptionResults = true
*.connectionManager.sendDirect = true
*.connectionManager.maxInterfDist = 2600m
*.connectionManager.drawMaxIntfDist = false
*.**.nic.mac1609_4.useServiceChannel = false
*.**.nic.mac1609_4.txPower = 20mW
*.**.nic.mac1609_4.bitrate = 6Mbps
*.**.nic.phy80211p.minPowerLevel = -110dBm
*.**.nic.phy80211p.useNoiseFloor = true
*.**.nic.phy80211p.noiseFloor = -98dBm
*.**.nic.phy80211p.decider = xmldoc("{DHAKA_VEINS / 'config.xml'}")
*.**.nic.phy80211p.analogueModels = xmldoc("{DHAKA_VEINS / 'config.xml'}")
*.**.nic.phy80211p.usePropagationDelay = true
*.**.nic.phy80211p.antenna = xmldoc("{DHAKA_VEINS / 'antenna.xml'}", "/root/Antenna[@id='monopole']")
*.node[*].nic.phy80211p.antennaOffsetY = 0 m
*.node[*].nic.phy80211p.antennaOffsetZ = 1.895 m
*.rsu[*].nic.phy80211p.antennaOffsetZ = 0 m
*.rsu[*].applType = "AmbulanceLoopRSU11p"
*.rsu[*].appl.headerLength = 80 bit
*.rsu[*].appl.sendBeacons = false
*.rsu[*].appl.dataOnSch = false
*.rsu[*].appl.beaconInterval = 1s
*.rsu[*].appl.active = {'true' if v2i else 'false'}
{rsu_lines}
*.node[*].applType = "AmbulanceLoop11p"
*.node[*].appl.headerLength = 80 bit
*.node[*].appl.sendBeacons = {'true' if (beacons and v2i) else 'false'}
*.node[*].appl.dataOnSch = false
*.node[*].appl.beaconInterval = 1s
*.node[*].appl.ambulanceId = "{service.AMBULANCE}"
*.node[*].appl.alertInterval = 1s
*.node[*].appl.makewayDistance = {mk['distance_m']}m
*.node[*].appl.makewayHold = 30s
*.node[*].appl.equippedShare = {share:g}
*.node[*].appl.active = {'true' if v2i else 'false'}
*.node[*].appl.posReportAt = {pos_check if pos_check is not None else -1}s
*.node[*].veinsmobility.x = 0
*.node[*].veinsmobility.y = 0
*.node[*].veinsmobility.z = 0
*.node[*].veinsmobility.setHostSpeed = false

[Config Default]
"""
    (d / "omnetpp.ini").write_text(ini)
    return d


def opp_cmd(gui: bool) -> list[str]:
    return ["opp_run", "-u", "Qtenv" if gui else "Cmdenv", "-c", "Default", "-l", str(VEINS / "src/veins"), "-l", str(LOOPS / "src/veinsloops"),
            "-n", f"{VEINS / 'src/veins'}:{LOOPS / 'src'}:{LOOPS}", f"--image-path={VEINS / 'images'}", "omnetpp.ini"]


def opp_env() -> dict:
    env = os.environ.copy()
    env["PATH"] = f"{OPP / 'bin'}:{env['PATH']}"
    env["DYLD_LIBRARY_PATH"] = f"{OPP / 'lib'}:{VEINS / 'src'}:{LOOPS / 'src'}"
    return env


# ------------------------------------------------------------------ Veins's scalars
def read_scalars(results: Path) -> dict:
    sca = sorted(results.glob("*.sca"), key=lambda p: p.stat().st_mtime)
    if not sca:
        return {}
    text = sca[-1].read_text()
    vals: dict[str, dict[str, float]] = {}
    for mod, name, v in re.findall(r"^scalar (\S+) (\S+) (\S+)$", text, re.M):
        try:
            vals.setdefault(mod, {})[name] = float(v)
        except ValueError:
            pass
    return vals


def veins_stats(vals: dict, rsus: list[dict]) -> dict:
    def total(name: str, where: str = "") -> int:
        return int(sum(v.get(name, 0) for m, v in vals.items() if where in m))
    sent = total("alertsSent", ".node[")
    per = {}
    for i, r in enumerate(rsus):
        appl, phy = vals.get(f"SharedSumoScenario.rsu[{i}].appl", {}), vals.get(f"SharedSumoScenario.rsu[{i}].nic.phy80211p", {})
        rx, snir, rxtx = int(appl.get("denmReceived", 0)), int(phy.get("SNIRLostPackets", 0)), int(phy.get("RXTXLostPackets", 0))
        per[r["tls"]] = {"rsu": i, "sent": sent, "received": rx, "lost_interference_or_collision": snir, "lost_while_transmitting": rxtx,
                         "not_received_below_sensitivity": max(sent - rx - snir - rxtx, 0), "flags_written": int(appl.get("flagsWritten", 0))}
    amb = [v["ambulanceTimeInNetwork"] for v in vals.values() if "ambulanceTimeInNetwork" in v]
    phy = [v for m, v in vals.items() if m.endswith(".nic.phy80211p")]
    return {"source": "Veins scalars (results/*.sca), its PHY/MAC", "nodes": len({m for m in vals if ".node[" in m and m.endswith(".appl")}),
            "denm_sent": sent, "car_receptions": total("alertsReceived", ".node["), "cars_made_way": total("madeWay", ".node["),
            "rsu_receptions": sum(p["received"] for p in per.values()), "per_rsu": per,
            "beacons_generated": total("generatedBSMs"), "beacons_received": total("receivedBSMs"),
            "frames_lost_all_nodes": {"interference_or_collision": int(sum(v.get("SNIRLostPackets", 0) for v in phy)), "while_transmitting": int(sum(v.get("RXTXLostPackets", 0) for v in phy))},
            "ambulance_time_in_veins_s": sum(amb) if amb else None, "ambulance_modules": len(amb)}       # Veins re-creates a vehicle's module after a teleport: the parts are summed


# ------------------------------------------------------------------ the loop
def run(seed: int, arm: str, share: float = 1.0, scale: float | None = None, gui: bool = False, root: Path = OUT / "runs", horizon: int | None = None, port: int | None = None,
        beacons: bool = False, demo_early: bool = False, pos_check: int | None = None) -> dict:
    if arm not in ARMS:
        raise ValueError(f"arm must be one of {ARMS}")
    why = ready()
    if why:
        raise RuntimeError(why)
    veins_env()
    from core.simulation.ambulance import rl_signals, rl_v2x_loop, service
    scale = rl_v2x_loop.dhaka_scale() if scale is None else scale
    _, QLAgent, EpsilonGreedy = rl_signals._sumo_rl()
    rl, v2i = arm.startswith("rl"), arm.endswith("_v2i")
    q = pickle.loads((rl_signals.RQ2 / "rl" / f"q_{DEMAND}_x{scale:g}.pkl").read_bytes())
    ts_ids = list(q)
    out = root / f"{arm}{f'_p{int(round(share * 100)):03d}' if v2i else ''}{'_cam' if (beacons and v2i) else ''}{'_DEMO' if demo_early else ''}_s{seed}_x{scale:g}"
    out.mkdir(parents=True, exist_ok=True)
    cfg, scen = service.settings(), service.scenario(CITY, DEMAND)
    if demo_early:                                             # DEMO SETTING (printed): the ambulance leaves at 120 s so the alert is visible within a minute
        cfg = {**cfg, "ambulance": {**cfg["ambulance"], "depart_s": 120}}
    horizon = horizon or cfg["horizon_s"]
    port = port or free_port()
    vtype = service.write_vtype(out / "ambulance_type.rou.xml", cfg)
    rsus = rsu_positions(Path(scen["net"]), ts_ids)
    short = {r["tls"]: f"RSU{i}" for i, r in enumerate(rsus)}
    cfgf = write_sumo_cfg(out, scen, vtype, scale, horizon, cfg)
    vdir = write_veins(out, cfgf, scen, rsus, seed, arm, share, horizon, port, gui, cfg, beacons, pos_check)
    for old in (vdir / "results").glob("*"):
        old.rename(old.with_name(old.name + f".{int(time.time())}.old")) if old.suffix in (".sca", ".vec", ".vci") else None
    state: dict = {}

    class VeinsLoopRun(rl_v2x_loop.LoopRun):
        """rl_v2x_loop's bookkeeping; the delivery decision is Veins's: a junction is informed when its RSU's traffic-light parameter
        veins.rx_t shows a reception within the last second. Cars are handled inside Veins (AmbulanceLoop11p); nothing is sent here."""

        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self.rx_seen = {tls: 0 for tls in ts_ids}

        def _alert(self, t: float) -> None:
            ahead, index, pos = self._ahead()
            reach = {edge: start for edge, start in ahead}
            addressed = {s["tls"] for s in rl_v2x_loop.primary_secondary(self.all_signals, index)}
            tl = self.conn.trafficlight
            for tls in ts_ids:
                try:
                    self.rx_seen[tls] = int(tl.getParameter(tls, "veins.rx") or 0)
                except Exception:                              # noqa: BLE001 - no RSU flag yet
                    pass
            for s in self.all_signals:
                tls = s["tls"]
                if s["route_index"] < index and tls in self.informed:
                    self.preemption.passed(tls)
                    self.informed.pop(tls)
                elif tls in addressed and s["route_index"] >= index and s["in_edge"] in reach and tls not in self.informed:
                    try:
                        rx_t = float(tl.getParameter(tls, "veins.rx_t") or -1)
                    except Exception:                          # noqa: BLE001
                        rx_t = -1.0
                    if rx_t >= t - 1.0:                        # a REAL 802.11p reception at this junction's RSU in this second
                        self.per_junction[tls]["delivered"] += 1
                        if self.on_junction_delivered:
                            self.on_junction_delivered(tls)
                        self.preemption.request(tls, f"{s['in_edge']}_0", t)
                        self.informed[tls] = t

        def _send(self, sender, receiver, t):                  # never reached: no channel model in this loop
            raise AssertionError("the Veins loop sends nothing through the channel model")

    sumo_rl, _, _ = rl_signals._sumo_rl()
    import traci

    class VeinsEnv(sumo_rl.SumoEnvironment):
        """SUMO-RL's environment on a SUMO that Veins launched: client 2 (traci.init + setOrder) instead of traci.start; the rest as rl_v2x_loop._loop_env."""
        held: set[str] = set()
        programs: dict[str, str] = {}
        logics: dict = {}

        def _start_simulation(self):
            if not wait_for_first_client(port, None if gui else 180, say, veins_proc["p"]):   # Veins first, this client second (see wait_for_first_client)
                raise RuntimeError("Veins did not connect (the OMNeT++ window was closed, or Cmdenv failed)")
            traci.init(port=port, numRetries=600 if gui else 120, label=self.label)
            self.sumo = traci.getConnection(self.label)
            self.sumo.setOrder(2)
            if gui:
                mark_rsus(self.sumo, rsus)
                route_rsus = [r for r in rsus if r["tls"] in {s["tls"] for s in scen["signals"]}] or rsus
                try:
                    self.sumo.gui.setOffset("View #0", statistics.fmean(r_["sumo_xy"][0] for r_ in route_rsus), statistics.fmean(r_["sumo_xy"][1] for r_ in route_rsus))
                except Exception:                              # noqa: BLE001
                    pass
                pass  # the on-map legend was removed (owner, 2026-10-14)
            self.programs = {ts: self.sumo.trafficlight.getProgram(ts) for ts in self.ts_ids}
            self.logics = {ts: next(l for l in self.sumo.trafficlight.getAllProgramLogics(ts) if l.programID == self.programs[ts]) for ts in self.ts_ids}

        def _sumo_step(self):
            super()._sumo_step()
            hook(self.sumo, self.sim_step, self)

        def _apply_actions(self, actions):
            super()._apply_actions({ts: a for ts, a in actions.items() if ts not in self.held})

        def _run_steps(self):
            time_to_act = False
            while not time_to_act:
                self._sumo_step()
                for ts in self.ts_ids:
                    if ts in self.held:
                        continue
                    self.traffic_signals[ts].update()
                    if self.traffic_signals[ts].time_to_act:
                        time_to_act = True

    live: dict = {"tx": 0, "last_print": -1}

    def hook(conn, t, env):
        if "run" not in state:
            state["run"] = VeinsLoopRun(conn, scen, "alert_preemption" if v2i else "no_alert", "its_g5" if v2i else None, share if v2i else 0.0, seed, cfg)
        r = state["run"]
        if rl and v2i and r.on_junction_delivered is None:
            def restore(tls: str) -> None:                     # the override drives the junction's OWN programme (SUMO-RL drives by state string)
                if tls in env.logics:
                    conn.trafficlight.setProgramLogic(tls, env.logics[tls])
                    conn.trafficlight.setProgram(tls, env.programs[tls])
            r.on_junction_delivered = restore
        if pos_check is not None and int(t) == pos_check:
            state["sumo_pos"] = {v_: conn.vehicle.getPosition(v_) for v_ in conn.vehicle.getIDList()}   # SUMO's positions at this second, kept for the comparison
        if pos_check is not None and pos_check < int(t) <= pos_check + 5 and "pos_check" not in state:   # validation: SUMO's position vs Veins's TraCIMobility position, same second
            x0, y0, x1, y1 = net_bounds(Path(scen["net"])); margin = 25.0
            rows = []
            for vid in conn.vehicle.getIDList():
                try:
                    rep_ = conn.vehicle.getParameter(vid, "veins.xy")
                except Exception:                              # noqa: BLE001
                    rep_ = ""
                if not rep_:
                    continue
                xo, yo, tv = (float(v) for v in rep_.split())
                if abs(tv - pos_check) > 1e-6 or vid not in state.get("sumo_pos", {}):
                    continue                                   # Veins's report for second pos_check, readable one step later; compared with SUMO's position at pos_check
                vx, vy = xo + x0 - margin, (y1 - y0) - (yo - y0) + margin      # Veins's own omnet2traci (TraCICoordinateTransformation.cc:43)
                sx, sy = state["sumo_pos"][vid]
                rows.append({"vehicle": vid, "veins_stamp_s": tv, "sumo_xy": [round(sx, 3), round(sy, 3)], "veins_xy_in_sumo_frame": [round(vx, 3), round(vy, 3)], "veins_xy_omnet": [round(xo, 3), round(yo, 3)], "diff_m": round(math.dist((sx, sy), (vx, vy)), 4)})
                if len(rows) == 5:
                    break
            n_rep = sum(1 for v_ in conn.vehicle.getIDList() if conn.vehicle.getParameter(v_, 'veins.xy'))
            if not rows:
                say(f'  (t={t:.0f}s: {n_rep} cars carry a veins.xy report; none stamped within this step yet)')
                continue_check = True
            else:
                state["pos_check"] = rows
            if rows:
                say(f"  POSITION CHECK for second {pos_check} (SUMO getPosition at {pos_check} s vs Veins TraCIMobility report stamped {pos_check} s, read at {t:.0f} s):")
            for rr in rows:
                say(f"    {rr['vehicle']:>12s}  SUMO ({rr['sumo_xy'][0]:.3f}, {rr['sumo_xy'][1]:.3f})  Veins ({rr['veins_xy_in_sumo_frame'][0]:.3f}, {rr['veins_xy_in_sumo_frame'][1]:.3f})  diff {rr['diff_m']:.4f} m  (Veins stamp {rr['veins_stamp_s']:g} s)  {'OK' if rr['diff_m'] <= 0.1 else 'MISMATCH'}")
        if gui and "tracking" not in state and service.AMBULANCE in conn.vehicle.getIDList():
            try:
                conn.gui.trackVehicle("View #0", service.AMBULANCE); conn.gui.setZoom("View #0", 1500); state["tracking"] = True
                say(f"  t={t:.0f}s  the ambulance departs; the SUMO view now follows it")
            except Exception:                              # noqa: BLE001
                state["tracking"] = False
        n_ev = len(r.events)
        r.step(t)
        for e in r.events[n_ev:]:
            say(f"    t={t:.0f}s  {short.get(e['tls'], '?')} junction {e['tls'][:30]}  {e['what'].upper()}  (DENMs this RSU really received so far: {r.rx_seen.get(e['tls'], 0)})")
        held = r.held() if rl else set()
        for tls in env.held - held:
            ts = env.traffic_signals.get(tls)
            if ts is not None:
                ts.next_action_time = env.sim_step + 1
                ts.is_yellow = False
                ts.time_since_last_phase_change = ts.min_green + 1
        env.held = held
        if v2i and r.state == "driving" and service.AMBULANCE in conn.vehicle.getIDList():
            try:
                live["tx"] = int(conn.vehicle.getParameter(service.AMBULANCE, "veins.tx") or 0)
            except Exception:                                  # noqa: BLE001
                pass
        if int(t) % 300 == 0 and int(t) != live["last_print"]:
            live["last_print"] = int(t)
            say(f"  t={t:.0f}s  vehicles {len(conn.vehicle.getIDList())}  ambulance {r.state}  DENM sent {live['tx']}  RSU receptions {{{', '.join(f'{short[k]}: {v}' for k, v in r.rx_seen.items())}}}  held {sorted(short.get(x, x) for x in env.held)}")

    log = open(out / "run.log", "w")

    def say(s: str) -> None:
        print(s, flush=True); log.write(s + "\n"); log.flush()

    say(f"VEINS LOOP seed {seed} arm {arm}: SUMO {sumo_version()} --num-clients 2 on port {port}; client 1 Veins ({'Qtenv' if gui else 'Cmdenv'}), client 2 this process (SUMO-RL env, {'frozen Q-learning' if rl else 'fixed-time'});"
        f" {len(rsus)} RSUs at {[r['tls'][:12] for r in rsus]}; radios {'ACTIVE: DENM every 1 s, make-way rule v2 in the car app, RSU flags' if v2i else 'silent'}; horizon {horizon} s")
    say(omnet_mode_line(gui))
    if gui:
        say("  In the OMNeT++ window press RUN (F5) or FAST (F6); the sumo-gui window follows. This process waits for the connection.")
    if demo_early:
        say("  *** DEMO SETTING: the ambulance departs at 120 s instead of the thesis's 900 s, so the alert is visible within a minute. Not a thesis result. ***")
    t0 = time.time()
    crashed, env, veins, steps = None, None, None, {"n": 0}
    veins_proc: dict = {"p": None}
    for attempt in range(1, 6):                                # SUMO 1.21's two-client handshake fails now and then at connect (before any step): the run is restarted whole
        veins = subprocess.Popen(opp_cmd(gui), cwd=vdir, env=opp_env(), stdout=open(out / "veins.log", "a"), stderr=subprocess.STDOUT)
        veins_proc["p"] = veins
        if gui:
            qtenv_left(veins)
        crashed, env = None, None
        try:
            env = VeinsEnv(net_file=str(scen["net"]), route_file=f"{scen['routes']},{vtype}", num_seconds=horizon, time_to_teleport=cfg["sumo"]["time_to_teleport_s"],
                           sumo_seed=seed, ts_ids=ts_ids, add_system_info=False, add_per_agent_info=False, sumo_warnings=False, use_gui=False, fixed_ts=not rl)
            obs = env.reset()
            agents = {}
            if rl:
                agents = {ts: QLAgent(starting_state=env.encode(obs[ts], ts), state_space=env.observation_space, action_space=env.action_space,
                                      alpha=0.0, gamma=0.99, exploration_strategy=EpsilonGreedy(initial_epsilon=0.0, min_epsilon=0.0, decay=1.0)) for ts in env.ts_ids}
                for ts in agents:
                    agents[ts].q_table = q[ts]
            done = {"__all__": False}
            while not done["__all__"]:
                if rl:
                    s, rw, done, _ = env.step(action={ts: agents[ts].act() for ts in agents if ts not in env.held})
                    for ts in agents:
                        if ts in env.held or ts not in s:
                            continue
                        agents[ts].learn(next_state=env.encode(s[ts], ts), reward=rw[ts])
                else:
                    s, rw, done, _ = env.step(action={})
                steps["n"] += 1
        except Exception as e:                                 # noqa: BLE001
            crashed = str(e)[:300]
            say(f"  client 2 stopped: {crashed}")
        try:
            if env is not None:
                env.close()
        except Exception:                                      # noqa: BLE001
            pass
        try:
            veins.wait(timeout=30 if crashed else 600)
        except subprocess.TimeoutExpired:
            veins.terminate()
            try:
                veins.wait(timeout=20)
            except subprocess.TimeoutExpired:
                veins.kill()
            crashed = crashed or "Veins did not finish within 600 s after the loop"
        if not crashed or steps["n"] > 0 or attempt == 5:
            break
        for old in (vdir / "results").glob("*"):
            if old.suffix in (".sca", ".vec", ".vci"):
                old.rename(old.with_name(old.name + f".{int(time.time())}.handshake_failed"))
        port = free_port(port + 1)
        vdir = write_veins(out, cfgf, scen, rsus, seed, arm, share, horizon, port, gui, cfg, beacons, pos_check)
        say(f"  handshake failed before the first step (SUMO 1.21 two-client connect); attempt {attempt + 1} on port {port}")
        state.clear(); live.update({"tx": 0, "last_print": -1})
    r = state.get("run")
    vals = read_scalars(vdir / "results")
    vs = veins_stats(vals, rsus) if vals else {}
    per = {}
    for s in scen["signals"]:
        tls = s["tls"]
        v = (vs.get("per_rsu") or {}).get(tls, {})
        per[tls] = {"sent": v.get("sent", 0), "delivered": v.get("received", 0), "lost": v.get("lost_interference_or_collision", 0) + v.get("lost_while_transmitting", 0),
                    "out_of_range": v.get("not_received_below_sensitivity", 0), "preempted": bool(r and r.per_junction[tls]["delivered"])}
    head = {"city_id": CITY, "demand_id": DEMAND, "arm": arm, "signals": "sumo-rl Q-learning (frozen)" if rl else "SUMO fixed-time programmes", "signals_controlled": ts_ids,
            "v2i": v2i, "link": LINK if v2i else None, "technology": "802.11p_veins" if v2i else None, "equipped_share": share if v2i else 0.0, "seed": seed, "scale": scale,
            "design": rl_v2x_loop.EMVLIGHT if v2i else None, "sumo": f"{sumo_version()} --num-clients 2 (Veins order 1, this loop order 2)", "rsus": rsus, "horizon_s": horizon,
            "wall_s": round(time.time() - t0, 1), "run_utc": datetime.now(timezone.utc).isoformat(), "veins_exit": veins.returncode, "position_check": state.get("pos_check"),
            **(r.summary() if r else {}), "messages": {"sent": vs.get("denm_sent", 0), "delivered": vs.get("rsu_receptions", 0) + vs.get("car_receptions", 0),
                                                        "lost": sum(p["lost"] for p in per.values()), "out_of_range": sum(p["out_of_range"] for p in per.values())} if v2i else None,
            "messages_per_junction": per if v2i else {}, "preemption_events": r.events if r else [], "veins": vs}
    ok = (out / "tripinfo.xml").exists() and (out / "statistic.xml").exists() and not crashed
    m = {**head, **service.trip_metrics(out, horizon)} if ok else {**head, "state": "crashed", "crash": crashed or "no SUMO outputs", "ambulance": {"arrived": False, "travel_time_s": None}, "others": None, "teleports": None}
    (out / "metrics.json").write_text(json.dumps(m, indent=1))
    (out / "edgedata.xml").unlink(missing_ok=True)
    log.close()
    return m


def say_run(m: dict, log) -> None:
    amb, oth, vs = m.get("ambulance") or {}, m.get("others") or {}, m.get("veins") or {}
    lines = [f"seed {m['seed']}  arm {m['arm']:7s}  ambulance {amb.get('travel_time_s')} s  others {oth.get('total_vehicle_hours')} veh-h  teleports {m.get('teleports')}  "
             f"[{m.get('wall_s')} s wall]{'  CRASHED: ' + str(m.get('crash'))[:80] if m.get('state') == 'crashed' else ''}"]
    if m.get("v2i"):
        lines.append(f"    Veins 802.11p: DENM sent {vs.get('denm_sent')}, car receptions {vs.get('car_receptions')}, cars made way {vs.get('cars_made_way')}, RSU receptions {vs.get('rsu_receptions')}")
        for tls, c in m["messages_per_junction"].items():
            ev = {e["what"]: e["t"] for e in m.get("preemption_events", []) if e["tls"] == tls}
            lines.append(f"    RSU at {tls[:40]:40s} sent {c['sent']:3d} received {c['delivered']:3d} lost(SNIR/tx) {c['lost']:3d} below sensitivity {c['out_of_range']:3d}"
                         f"  informed {ev.get('informed')} s  takeover {ev.get('takeover')} s  released {ev.get('released')} s")
    for s in lines:
        print(s, flush=True); log.write(s + "\n"); log.flush()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seeds", nargs="+", default=["11"], help="integers, or `clock` = one seed taken from the clock at start (a new traffic draw every time)")
    ap.add_argument("--arms", nargs="+", default=["rl_v2i"], choices=ARMS)
    ap.add_argument("--share", type=float, default=1.0)
    ap.add_argument("--no-gui", action="store_true", help="Cmdenv + sumo (the evidence runs); default: Qtenv + sumo-gui windows")
    ap.add_argument("--horizon", type=int, default=None, help="simulated seconds (default: the thesis's 3600); tests only")
    ap.add_argument("--pos-check", type=int, default=None, help="validation: at this second, compare 5 cars' SUMO positions with Veins's TraCIMobility positions")
    ap.add_argument("--demo-early", action="store_true", help="DEMO SETTING: the ambulance departs at 120 s instead of 900 s (not the thesis protocol)")
    ap.add_argument("--beacons", action="store_true", help="rl_v2i: every car also sends Veins's 1 Hz beacon (CAM-like channel load; slower)")
    ap.add_argument("--out", type=Path, default=None, help="output folder; default evidence/live_runs/veins_ambulance_loop/<stamp> (the evidence run passes evidence/veins_ambulance_loop)")
    a = ap.parse_args(argv)
    a.seeds = [(int(time.time()) % 9000) + 1000 if str(s).lower() == "clock" else int(s) for s in a.seeds]
    why = ready()
    if why:
        print(f"STOP: {why}"); return 1
    root = (a.out or (REPO / "evidence/live_runs/veins_ambulance_loop" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))).resolve(); root.mkdir(parents=True, exist_ok=True)
    log = open(root / "run.log", "a")
    veins_env()
    from core.simulation.ambulance import rl_v2x_loop
    scale = rl_v2x_loop.dhaka_scale()
    head = f"VEINS AMBULANCE LOOP {datetime.now(timezone.utc).isoformat()}: Dhaka corridor at scale {scale:g} (match.json), arms {a.arms}, seeds {a.seeds}, {int(a.share * 100)} % equipped; {LINK}; {rl_v2x_loop.EMVLIGHT}"
    print(head, flush=True); log.write(head + "\n")
    rows = []
    for seed in a.seeds:
        row = {"seed": seed}
        for arm in a.arms:
            m = run(seed, arm, a.share, scale, gui=not a.no_gui, root=root / "runs", horizon=a.horizon, beacons=a.beacons, demo_early=a.demo_early, pos_check=a.pos_check)
            say_run(m, log)
            row[arm] = {"ambulance_s": (m.get("ambulance") or {}).get("travel_time_s"), "arrived": (m.get("ambulance") or {}).get("arrived"), "others_vehicle_hours": (m.get("others") or {}).get("total_vehicle_hours"),
                        "teleports": m.get("teleports"), "messages": m.get("messages"), "messages_per_junction": m.get("messages_per_junction"), "preemption_events": m.get("preemption_events"),
                        "veins": m.get("veins"), "state": m.get("state", "ok")}
        rows.append(row)

    def med(arm, key):
        v = [r[arm][key] for r in rows if arm in r and r[arm].get(key) is not None]
        return statistics.median(v) if v else None

    prev = REPO / "evidence/ambulance_loop/summary.json"
    channel_model = json.loads(prev.read_text()) if prev.exists() else None
    summary = {"generated_utc": datetime.now(timezone.utc).isoformat(), "label": "SIMULATION, Dhaka corridor at the thesis's Dhaka-density level; network: " + LINK, "scale": scale, "share": a.share,
               "design": rl_v2x_loop.EMVLIGHT, "horizon_s": a.horizon, "seeds": a.seeds, "beacons": a.beacons, "rows": rows,
               "median_ambulance_s": {arm: med(arm, "ambulance_s") for arm in a.arms}, "median_others_vehicle_hours": {arm: med(arm, "others_vehicle_hours") for arm in a.arms},
               "median_saving_s_vs_fixed": {arm: (statistics.median([r["fixed"]["ambulance_s"] - r[arm]["ambulance_s"] for r in rows if r.get("fixed", {}).get("ambulance_s") and r[arm]["ambulance_s"]])
                                                  if "fixed" in a.arms and arm != "fixed" and any(r.get("fixed", {}).get("ambulance_s") and r[arm]["ambulance_s"] for r in rows) else None) for arm in a.arms},
               "channel_model_loop_for_comparison": {"file": str(prev.relative_to(REPO)), "tech": channel_model.get("tech"), "median_ambulance_s": channel_model.get("median_ambulance_s"),
                                                     "median_others_vehicle_hours": channel_model.get("median_others_vehicle_hours")} if channel_model else None}
    (root / "summary.json").write_text(json.dumps(summary, indent=1))
    s = json.dumps({k: summary[k] for k in ("seeds", "median_ambulance_s", "median_others_vehicle_hours", "median_saving_s_vs_fixed", "channel_model_loop_for_comparison")}, indent=1)
    print(s, flush=True); log.write(s + "\ndone\n"); log.close()
    files = ["summary.json", "run.log"] + sorted(str(p.relative_to(root)) for p in (root / "runs").rglob("*") if p.is_file() and p.name in ("metrics.json", "run.log", "omnetpp.ini", "sumo.sumocfg") or p.suffix == ".sca")
    (root / "SHA256SUMS").write_text("".join(f"{hashlib.sha256((root / f).read_bytes()).hexdigest()}  {f}\n" for f in files))
    return 0


if __name__ == "__main__":
    sys.exit(main())
