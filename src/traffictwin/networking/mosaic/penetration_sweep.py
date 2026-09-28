#!/usr/bin/env python3
"""V2X penetration-rate sweep on the registered Dhaka R1 Eclipse MOSAIC scenario.

For every (P, seed) point the script
  1. copies results/artifacts/mosaic_dhaka/dhaka_r1 -> results/networking/generated_scenarios/dhaka_r1_p{P}_s{SEED}/
     (big, immutable inputs -- net/route/db/osm -- are symlinked, configs copied);
  2. rewrites mapping/mapping_config.json so that a fraction P of the SUMO-spawned
     vehicles is equipped with the official V2X app stack
     [WeatherWarningApp (sense hazard -> DENM -> NavigationModule reroute), SlowDownApp]
     and the remaining 1-P carry only SlowDownApp (no radio, no DENM, no reroute).

     THE MAPPING KNOB (verified in MappingAmbassador.handleInteraction(ScenarioVehicleRegistration)
     bytecode of mosaic-mapping-25.2.jar): vehicles that come from the SUMO route file are
     matched by their SUMO vehicle-type name against `typeDistributions[<vtype>]`, a list of
     prototypes with `weight`s. A WeightedSelector picks one prototype per vehicle
     (StochasticSelector driven by the RTI RandomNumberGenerator, i.e. scenario randomSeed,
     when config.fixedOrder=false; FixedOrderSelector otherwise). The chosen prototype's
     `group` and `applications` are what the vehicle gets. This is exactly how the official
     Barnim example expresses "Cellular 10 % / AdHoc 20 % / Unequipped 70 %".
     (Alternative knob, also in the bytecode: a single prototype with `weight: w` is equipped
     iff rng.nextDouble() < w -- "will not be equipped due to a weight condition".)
  3. sets randomSeed / duration in scenario_config.json (+ SUMO --seed via sumo_config.json
     additionalSumoParameters, tripinfo/summary outputs, absolute paths);
  4. runs `mosaic.sh -c <scenario_config.json> -l src/traffictwin/networking/mosaic/logback_sweep.xml -w 0`
     (logback_sweep.xml == etc/logback.xml with the per-vehicle app-log delegate at WARN:
      the 1000 s reference run wrote 37 GB of per-vehicle DENM reception lines);
  5. parses the MOSAIC log directory (logs/log-<ts>-dhaka_r1 under the MOSAIC install):
       visualizer.csv  (file output ambassador): VEHICLE_REGISTRATION -> equipped set,
                       V2X_MESSAGE_TRANSMISSION / V2X_MESSAGE_RECEPTION -> senders, receivers,
                       per-message latency (t_rx - t_tx by MessageId), VEHICLE_UPDATES -> positions
       Navigation.log: "Change to route X for vehicle veh_Y" -> route switches
       Mapping.log:    "Mapping Scenario Vehicle ... apps=[...]" -> cross-check of equipment
       MOSAIC.log:     wall-clock duration
       sumo/out/tripinfo.xml + summary.xml (SUMO, written via additionalSumoParameters)
  6. writes results/networking/penetration_p{P}_s{SEED}.json and re-aggregates
     results/networking/penetration.csv + penetration.md.

Definitions (also written into every JSON):
  equipped            vehicles registered with WeatherWarningApp in their application list
  denm_sent           V2X_MESSAGE_TRANSMISSION rows (every DENM broadcast, 1 per sender per second in hazard)
  senders             distinct sources of those rows
  receivers           distinct vehicles with >= 1 V2X_MESSAGE_RECEPTION row
  delivery_ratio_veh  receivers / equipped              (coverage: share of equipped fleet that heard >= 1 DENM)
  delivery_ratio_msg  receptions / (denm_sent * (equipped_at_tx - 1))  is NOT computable without
                      per-message reachability, so we report receptions_per_denm = receptions / denm_sent
  latency_ms          t_reception - t_transmission of the same MessageId (SNS ad-hoc, multi-hop)
  route_switches      lines "Change to route ... for vehicle" in Navigation.log (CentralNavigationComponent)
  travel time         SUMO tripinfo of finished trips (duration, timeLoss, waitingTime), split equipped/unequipped

Usage
  python -m traffictwin.networking.mosaic.penetration_sweep --p 0.25 --seed 11 --duration 600      # one point
  python -m traffictwin.networking.mosaic.penetration_sweep --all --seeds 11 22 33 --duration 600   # full sweep, sequential
  python -m traffictwin.networking.mosaic.penetration_sweep --parse-only <mosaic log dir> --p 0.25 --seed 11
  python -m traffictwin.networking.mosaic.penetration_sweep --aggregate                              # rebuild csv/md only
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import shutil
import statistics
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

from traffictwin.paths import REPO
NET_DIR = REPO / "src/pipeline/networking"
SRC_SCENARIO = REPO / "results/artifacts/mosaic_dhaka/dhaka_r1"
FALLBACK_NET = REPO / "data/cities/dhaka_r1/dhaka_r1.net.xml.gz"
MOSAIC_HOME = Path(os.environ.get("MOSAIC_HOME", Path.home() / ".dhakaflow/upstream/mosaic"))
LOGBACK = NET_DIR / "logback_sweep.xml"
RESULTS = REPO / "results/networking"
SCEN_ROOT = RESULTS / "generated_scenarios"

WWA = "org.eclipse.mosaic.app.tutorial.WeatherWarningApp"
SDA = "org.eclipse.mosaic.app.tutorial.SlowDownApp"
P_GRID = [0.0, 0.1, 0.25, 0.5, 1.0]
SYMLINK_SUFFIXES = {".net.xml", ".rou.xml", ".db", ".osm"}   # big immutable inputs
NS = 1_000_000_000


def ptag(p: float) -> str:
    return f"{p:g}"


def point_name(p: float, seed: int) -> str:
    return f"dhaka_r1_p{ptag(p)}_s{seed}"


# --------------------------------------------------------------------------- scenario
def ensure_net_file() -> None:
    net = SRC_SCENARIO / "sumo/dhaka_r1.net.xml"
    if not net.exists():
        if not FALLBACK_NET.exists():
            sys.exit(f"missing {net} and fallback {FALLBACK_NET}")
        print(f"[scenario] {net} missing -> copying frozen net from {FALLBACK_NET}")
        shutil.copy2(FALLBACK_NET, net)


def mapping_config(p: float) -> dict:
    equipped = {"name": "DEFAULT_VEHTYPE", "group": "AdHoc", "weight": p,
                "applications": [WWA, SDA]}
    unequipped = {"name": "DEFAULT_VEHTYPE", "group": "Unequipped", "weight": round(1.0 - p, 6),
                  "applications": [SDA]}
    dist = [d for d in (equipped, unequipped) if d["weight"] > 0]
    return {
        "config": {"fixedOrder": False},          # stochastic selector -> seed-dependent equipment
        "prototypes": [{"name": "DEFAULT_VEHTYPE"}],  # base prototype: vehicle params stay SUMO's
        "typeDistributions": {"DEFAULT_VEHTYPE": dist},
    }


OUTPUT_CONFIG = """<?xml version="1.0" encoding="UTF-8"?>
<configuration xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
               xsi:noNamespaceSchemaLocation="http://www.dcaiti.tu-berlin.de/research/simulation/download/get/scenarios/scenarioname/visualizer/visualizer_config.xsd">
    <output id="fileoutput" enabled="true" update="1" loader="org.eclipse.mosaic.fed.output.generator.file.FileOutputLoader">
        <filename>visualizer.csv</filename>
        <directory>.</directory>
        <separator>;</separator>
        <subscriptions>
            <subscription id="VehicleRegistration" enabled="true">
                <entries>
                    <entry>"VEHICLE_REGISTRATION"</entry>
                    <entry>Time</entry>
                    <entry>Mapping.Name</entry>
                    <entry>Mapping.Applications</entry>
                    <entry>Mapping.VehicleType.Name</entry>
                </entries>
            </subscription>
            <subscription id="V2xMessageTransmission" enabled="true">
                <entries>
                    <entry>"V2X_MESSAGE_TRANSMISSION"</entry>
                    <entry>Time</entry>
                    <entry>MessageId</entry>
                    <entry>SourceName</entry>
                    <entry>Type</entry>
                </entries>
            </subscription>
            <subscription id="V2xMessageReception" enabled="true">
                <entries>
                    <entry>"V2X_MESSAGE_RECEPTION"</entry>
                    <entry>Time</entry>
                    <entry>MessageId</entry>
                    <entry>ReceiverName</entry>
                    <entry>Type</entry>
                </entries>
            </subscription>
            <subscription id="VehicleUpdates" enabled="true">
                <entries>
                    <entry>"VEHICLE_UPDATES"</entry>
                    <entry>Time</entry>
                    <entry>Updated:Name</entry>
                    <entry>Updated:Position.Latitude</entry>
                    <entry>Updated:Position.Longitude</entry>
                    <entry>Updated:Speed</entry>
                    <entry>Updated:Heading</entry>
                </entries>
            </subscription>
        </subscriptions>
    </output>
    <output id="websocket" enabled="false" loader="org.eclipse.mosaic.fed.output.generator.websocket.WebsocketVisualizerLoader">
        <synchronized>true</synchronized>
        <port>46587</port>
        <subscriptions>
            <subscription id="VehicleUpdates" enabled="true"/>
        </subscriptions>
    </output>
</configuration>
"""


def build_scenario(p: float, seed: int, duration: int) -> Path:
    ensure_net_file()
    dst = SCEN_ROOT / point_name(p, seed)
    if dst.exists():
        shutil.rmtree(dst)
    for src in SRC_SCENARIO.rglob("*"):
        rel = src.relative_to(SRC_SCENARIO)
        out = dst / rel
        if src.is_dir():
            out.mkdir(parents=True, exist_ok=True)
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        if any(src.name.endswith(s) for s in SYMLINK_SUFFIXES):
            out.symlink_to(src.resolve())
        else:
            shutil.copy2(src, out)

    # 1. mapping: penetration knob
    (dst / "mapping/mapping_config.json").write_text(json.dumps(mapping_config(p), indent=1))
    # 2. scenario: seed + duration (id kept = dhaka_r1 so application/dhaka_r1.db is found)
    sc = json.loads((dst / "scenario_config.json").read_text())
    sc["simulation"]["duration"] = f"{duration}s"
    sc["simulation"]["randomSeed"] = int(seed)
    (dst / "scenario_config.json").write_text(json.dumps(sc, indent=4))
    # 3. environment: hazard window follows duration
    env = json.loads((dst / "environment/environment_config.json").read_text())
    for ev in env["events"]:
        ev["time"]["end"] = f"{duration} s"
    (dst / "environment/environment_config.json").write_text(json.dumps(env, indent=4))
    # 4. sumo: end time, seed, tripinfo/summary outputs (absolute paths: SUMO runs in MOSAIC's tmp/sumo)
    cfg = dst / "sumo/dhaka_r1.sumocfg"
    cfg.write_text(re.sub(r'<end value="\d+"/>', f'<end value="{duration}"/>', cfg.read_text()))
    outd = dst / "sumo/out"
    outd.mkdir(exist_ok=True)
    (dst / "sumo/sumo_config.json").write_text(json.dumps({
        "updateInterval": 1000,
        "sumoConfigurationFile": "dhaka_r1.sumocfg",
        "additionalSumoParameters": " ".join([
            "--time-to-teleport 0", f"--seed {seed}",
            f"--tripinfo-output {outd / 'tripinfo.xml'}",
            "--tripinfo-output.write-unfinished true",
            f"--summary-output {outd / 'summary.xml'}",
        ]),
    }, indent=1))
    # 5. output ambassador: V2X tx/rx + registrations + trajectories, websocket off
    (dst / "output/output_config.xml").write_text(OUTPUT_CONFIG)
    return dst


# --------------------------------------------------------------------------- run
def run_mosaic(scenario: Path, stdout_path: Path) -> tuple[Path, float]:
    logs = MOSAIC_HOME / "logs"
    before = {d.name for d in logs.iterdir()} if logs.exists() else set()
    cmd = ["./mosaic.sh", "-c", str(scenario / "scenario_config.json"), "-l", str(LOGBACK), "-w", "0"]
    print(f"[run] {' '.join(cmd)}  (cwd={MOSAIC_HOME})  stdout -> {stdout_path}", flush=True)
    t0 = time.time()
    with open(stdout_path, "w") as fh:
        rc = subprocess.call(cmd, cwd=MOSAIC_HOME, stdout=fh, stderr=subprocess.STDOUT)
    wall = time.time() - t0
    new = sorted((d for d in logs.iterdir() if d.name not in before), key=lambda d: d.stat().st_mtime)
    if rc != 0 or not new:
        sys.exit(f"[run] mosaic exit code {rc}; new log dirs: {[d.name for d in new]}")
    print(f"[run] finished rc={rc} wall={wall:.0f}s log dir={new[-1]}", flush=True)
    return new[-1], wall


# --------------------------------------------------------------------------- parse
def pct(sorted_vals, q):
    if not sorted_vals:
        return None
    k = (len(sorted_vals) - 1) * q
    f, c = math.floor(k), math.ceil(k)
    return sorted_vals[f] if f == c else sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)


def hist_percentile(counter: Counter, total: int, q: float, bin_ns: int) -> float | None:
    """Percentile from an integer-bin histogram (bins of bin_ns ns)."""
    if total == 0:
        return None
    target = q * (total - 1)
    seen = 0
    for b in sorted(counter):
        seen += counter[b]
        if seen - 1 >= target:
            return (b + 0.5) * bin_ns / 1e6
    return None


def parse_visualizer(path: Path):
    """Stream visualizer.csv once. Returns registration/equipment sets, tx/rx statistics and
    per-vehicle trajectories (1 Hz, downsampled to every 2 s to save memory)."""
    registered, equipped = {}, set()
    tx = {}                                   # msgid -> (t_ns, source)
    senders = Counter()                       # source -> #DENM sent
    rx_first = {}                             # receiver -> (t_rx_ns, msgid)
    rx_count = Counter()                      # receiver -> #receptions
    lat_hist = Counter()                      # 10 us bins
    lat_sum_ns = 0
    lat_n = 0
    lat_min = None
    lat_max = 0
    traj = defaultdict(list)                  # veh -> [(t_s, lat, lon, speed, edge)]
    denm_types = Counter()
    BIN = 10_000                              # ns
    with open(path, "r", buffering=1 << 20) as fh:
        for line in fh:
            if line.startswith("V2X_MESSAGE_RECEPTION;"):
                _, t, mid, rcv, typ = line.rstrip("\n").split(";")
                t = int(t)
                src = tx.get(mid)
                rx_count[rcv] += 1
                if rcv not in rx_first:
                    rx_first[rcv] = (t, mid)
                if src is not None:
                    d = t - src[0]
                    lat_hist[d // BIN] += 1
                    lat_sum_ns += d
                    lat_n += 1
                    lat_min = d if lat_min is None or d < lat_min else lat_min
                    lat_max = d if d > lat_max else lat_max
            elif line.startswith("VEHICLE_UPDATES;"):
                parts = line.rstrip("\n").split(";")
                t = int(parts[1])
                if t % (2 * NS) == 0:
                    try:
                        traj[parts[2]].append((t / NS, float(parts[3]), float(parts[4]),
                                               float(parts[5]), parts[6] if len(parts) > 6 else ""))
                    except ValueError:
                        pass
            elif line.startswith("V2X_MESSAGE_TRANSMISSION;"):
                _, t, mid, src, typ = line.rstrip("\n").split(";")
                tx[mid] = (int(t), src)
                senders[src] += 1
                denm_types[typ] += 1
            elif line.startswith("VEHICLE_REGISTRATION;"):
                _, t, name, apps, vtype = line.rstrip("\n").split(";")
                registered[name] = int(t) / NS
                if WWA in apps:
                    equipped.add(name)
    lat = {
        "n": lat_n,
        "mean_ms": (lat_sum_ns / lat_n / 1e6) if lat_n else None,
        "min_ms": (lat_min / 1e6) if lat_n else None,
        "p50_ms": hist_percentile(lat_hist, lat_n, 0.50, BIN),
        "p95_ms": hist_percentile(lat_hist, lat_n, 0.95, BIN),
        "p99_ms": hist_percentile(lat_hist, lat_n, 0.99, BIN),
        "max_ms": (lat_max / 1e6) if lat_n else None,
        "hist_10us_bins": {str(k): v for k, v in sorted(lat_hist.items())} if lat_n < 5_000_000 else "omitted (too large)",
    }
    return dict(registered=registered, equipped=equipped, tx=tx, senders=senders, rx_first=rx_first,
                rx_count=rx_count, latency=lat, traj=traj, denm_types=denm_types)


def parse_navigation(path: Path):
    switches = []
    if path.exists():
        rx = re.compile(r"Change to route (\S+) for vehicle (\S+)\.")
        for line in path.read_text(errors="replace").splitlines():
            m = rx.search(line)
            if m:
                switches.append((m.group(2), m.group(1)))
    return switches


def parse_id_map(traffic_log: Path) -> dict:
    """SUMO vehicle id -> MOSAIC unit name (Traffic.log: Assigned unit MOSAIC-ID: "veh_0" to external unit: "od000_0")."""
    idmap = {}
    if traffic_log.exists():
        rx = re.compile(r'Assigned unit MOSAIC-ID: "([^"]+)" to external unit: "([^"]+)"')
        for line in traffic_log.read_text(errors="replace").splitlines():
            m = rx.search(line)
            if m:
                idmap[m.group(2)] = m.group(1)
    return idmap


def equipped_from_mapping_log(path: Path) -> set:
    eq = set()
    if path.exists():
        rx = re.compile(r"Mapping Scenario Vehicle\. time=\d+, name=(\S+), type=\S+, apps=\[([^\]]*)\]")
        for line in path.read_text(errors="replace").splitlines():
            m = rx.search(line)
            if m and WWA in m.group(2):
                eq.add(m.group(1))
    return eq


def parse_mapping(path: Path):
    n_total, n_wwa = 0, 0
    if path.exists():
        for line in path.read_text(errors="replace").splitlines():
            if "Mapping Scenario Vehicle" in line:
                n_total += 1
                if WWA in line:
                    n_wwa += 1
    return n_total, n_wwa


def parse_mosaic_log(path: Path):
    wall_s, ended = None, None
    if path.exists():
        for line in path.read_text(errors="replace").splitlines():
            m = re.search(r"Duration: (\d+)h (\d+)m ([\d.]+)s", line)
            if m:
                wall_s = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
            m = re.search(r"Simulation ended after (\d+)s of (\d+)s", line)
            if m:
                ended = (int(m.group(1)), int(m.group(2)))
    return wall_s, ended


def parse_tripinfo(path: Path, equipped: set, idmap: dict | None = None):
    idmap = idmap or {}
    out = {"available": path.exists(), "id_map_entries": len(idmap)}
    if not path.exists():
        return out
    fin = {"all": [], "equipped": [], "unequipped": []}
    unfinished = 0
    for _, el in ET.iterparse(path, events=("end",)):
        if el.tag != "tripinfo":
            continue
        if float(el.get("arrival", "-1")) < 0:
            unfinished += 1
            el.clear()
            continue
        rec = (float(el.get("duration")), float(el.get("timeLoss", "nan")),
               float(el.get("waitingTime", "nan")), float(el.get("routeLength", "nan")))
        fin["all"].append(rec)
        fin["equipped" if idmap.get(el.get("id"), el.get("id")) in equipped else "unequipped"].append(rec)
        el.clear()

    def stats(rows):
        if not rows:
            return {"n": 0}
        dur = sorted(r[0] for r in rows)
        tl = sorted(r[1] for r in rows)
        wt = sorted(r[2] for r in rows)
        rl = [r[3] for r in rows]
        return {"n": len(rows),
                "duration_mean_s": statistics.fmean(dur), "duration_p50_s": pct(dur, .5), "duration_p95_s": pct(dur, .95),
                "timeLoss_mean_s": statistics.fmean(tl), "timeLoss_p95_s": pct(tl, .95),
                "waitingTime_mean_s": statistics.fmean(wt),
                "routeLength_mean_m": statistics.fmean(rl)}
    out.update({"finished": stats(fin["all"]), "finished_equipped": stats(fin["equipped"]),
                "finished_unequipped": stats(fin["unequipped"]), "unfinished": unfinished})
    return out


def parse_summary(path: Path):
    if not path.exists():
        return {"available": False}
    last = None
    n_steps = 0
    mean_speed_sum = 0.0
    halting_sum = 0.0
    for _, el in ET.iterparse(path, events=("end",)):
        if el.tag == "step":
            last = dict(el.attrib)
            n_steps += 1
            mean_speed_sum += float(el.get("meanSpeed", "0") or 0)
            halting_sum += float(el.get("halting", "0") or 0)
            el.clear()
    if last is None:
        return {"available": False}
    return {"available": True, "final_step": last,
            "meanSpeed_avg_over_steps_m_s": mean_speed_sum / n_steps,
            "halting_avg_over_steps": halting_sum / n_steps}


HAZARD = {"lat_min": 23.7500, "lat_max": 23.7555, "lon_min": 90.3915, "lon_max": 90.3975}


def dist_to_hazard_m(lat, lon):
    """Straight-line distance (m) from a point to the hazard rectangle (0 if inside)."""
    dlat = max(HAZARD["lat_min"] - lat, 0, lat - HAZARD["lat_max"])
    dlon = max(HAZARD["lon_min"] - lon, 0, lon - HAZARD["lon_max"])
    return math.hypot(dlat * 111_320.0, dlon * 111_320.0 * math.cos(math.radians(lat)))


def time_to_hazard(vis, switches):
    """Per rerouting vehicle: state at the moment of its FIRST DENM reception ->
    distance to hazard zone / current speed = time budget the advisory had (analytic)."""
    rows = []
    switched = {v for v, _ in switches}
    for veh in switched:
        first = vis["rx_first"].get(veh)
        tr = vis["traj"].get(veh)
        if not first or not tr:
            continue
        t_rx = first[0] / NS
        # nearest trajectory sample at or before t_rx (2 s grid), else first after
        cand = [s for s in tr if s[0] <= t_rx] or tr[:1]
        t, lat, lon, spd, edge = cand[-1]
        d = dist_to_hazard_m(lat, lon)
        speeds = [s[3] for s in tr if s[3] > 0.5]
        v_mean = statistics.fmean(speeds) if speeds else 5.0
        v_eff = max(spd, 0.3 * v_mean, 1.0)
        rows.append({"veh": veh, "t_rx_s": round(t_rx, 3), "t_sample_s": t, "dist_m": round(d, 1),
                     "speed_m_s": round(spd, 2), "v_mean_m_s": round(v_mean, 2),
                     "tth_s": round(d / v_eff, 1), "edge": edge})
    return rows


def parse_point(log_dir: Path, scenario: Path, p: float, seed: int, duration: int, wall_s=None):
    vis_path = log_dir / "visualizer.csv"
    if not vis_path.exists():
        sys.exit(f"no visualizer.csv in {log_dir}")
    print(f"[parse] {vis_path} ({vis_path.stat().st_size/1e6:.0f} MB)", flush=True)
    vis = parse_visualizer(vis_path)
    switches = parse_navigation(log_dir / "Navigation.log")
    map_total, map_wwa = parse_mapping(log_dir / "Mapping.log")
    wall_log, ended = parse_mosaic_log(log_dir / "MOSAIC.log")
    idmap = parse_id_map(log_dir / "Traffic.log")
    trip = parse_tripinfo(scenario / "sumo/out/tripinfo.xml", vis["equipped"], idmap)
    summ = parse_summary(scenario / "sumo/out/summary.xml")
    tth = time_to_hazard(vis, switches)

    registered = len(vis["registered"])
    equipped = len(vis["equipped"])
    receivers = set(vis["rx_first"])
    n_rx = sum(vis["rx_count"].values())
    n_tx = len(vis["tx"])
    first_tx = min((t for t, _ in vis["tx"].values()), default=None)
    switched_vehicles = {v for v, _ in switches}
    res = {
        "point": {"p": p, "seed": seed, "duration_s": duration, "scenario": str(scenario.relative_to(REPO)),
                  "log_dir": str(log_dir)},
        "wall_s": wall_log if wall_log is not None else wall_s,      # MOSAIC SequentialTimeManagement duration
        "wall_total_s": wall_s,                                       # whole mosaic.sh process incl. JVM/SUMO start-up
        "sim_ended_s": ended[0] if ended else None,
        "vehicles": {
            "registered": registered,
            "equipped": equipped,
            "unequipped": registered - equipped,
            "equipped_fraction": (equipped / registered) if registered else None,
            "mapping_log_total": map_total, "mapping_log_with_wwa": map_wwa,
        },
        "v2x": {
            "denm_sent": n_tx,
            "message_types": dict(vis["denm_types"]),
            "senders": len(vis["senders"]),
            "first_denm_s": (first_tx / NS) if first_tx is not None else None,
            "receptions": n_rx,
            "receivers": len(receivers),
            "receivers_equipped": len(receivers & vis["equipped"]),
            "delivery_ratio_veh": (len(receivers) / equipped) if equipped else None,
            "receptions_per_denm": (n_rx / n_tx) if n_tx else None,
            "receptions_per_receiver": (n_rx / len(receivers)) if receivers else None,
            "latency": vis["latency"],
        },
        "routing": {
            "route_switches": len(switches),
            "vehicles_switched": len(switched_vehicles),
            "switch_fraction_of_receivers": (len(switched_vehicles) / len(receivers)) if receivers else None,
            "switch_fraction_of_equipped": (len(switched_vehicles) / equipped) if equipped else None,
        },
        "sumo": {"tripinfo": trip, "summary": summ},
        "time_to_hazard": {
            "model": "analytic: straight-line distance from the vehicle's position at its FIRST DENM "
                     "reception to the hazard rectangle boundary, divided by max(current speed, 0.3*mean "
                     "trip speed, 1 m/s); vehicles = those that actually switched route",
            "n": len(tth),
            "tth_zero_fraction": (sum(1 for r in tth if r["tth_s"] <= 0) / len(tth)) if tth else None,
            "tth_s_p10": pct(sorted(r["tth_s"] for r in tth), .10) if tth else None,
            "tth_s_p50": pct(sorted(r["tth_s"] for r in tth), .50) if tth else None,
            "tth_s_p90": pct(sorted(r["tth_s"] for r in tth), .90) if tth else None,
            "rows": tth,
        },
        "definitions": {
            "equipped": "VEHICLE_REGISTRATION rows whose application list contains WeatherWarningApp",
            "delivery_ratio_veh": "distinct DENM receivers / equipped vehicles",
            "receptions_per_denm": "V2X_MESSAGE_RECEPTION rows / V2X_MESSAGE_TRANSMISSION rows",
            "latency": "reception time - transmission time of the same MessageId (SNS ad-hoc ITS-G5, multi-hop)",
            "route_switches": "CentralNavigationComponent 'Change to route' lines in Navigation.log",
            "travel_time": "SUMO tripinfo (finished trips only; unfinished counted separately)",
        },
    }
    out = RESULTS / f"penetration_p{ptag(p)}_s{seed}.json"
    out.write_text(json.dumps(res, indent=1))
    print(f"[parse] -> {out}", flush=True)
    return res


def keep_small_logs(log_dir: Path, p: float, seed: int):
    dst = RESULTS / "logs" / point_name(p, seed)
    dst.mkdir(parents=True, exist_ok=True)
    for f in ("MOSAIC.log", "Navigation.log", "Mapping.log", "Traffic.log", "Communication.log", "Environment.log"):
        if (log_dir / f).exists():
            shutil.copy2(log_dir / f, dst / f)
    return dst


def refresh_tripinfo():
    """Recompute the equipped/unequipped tripinfo split of every point JSON from the kept small logs
    (Mapping.log -> equipped set, Traffic.log -> SUMO id map) and the scenario's tripinfo.xml."""
    for f in sorted(RESULTS.glob("penetration_p*_s*.json")):
        r = json.loads(f.read_text())
        p, seed = r["point"]["p"], r["point"]["seed"]
        kept = RESULTS / "logs" / point_name(p, seed)
        scenario = SCEN_ROOT / point_name(p, seed)
        eq = equipped_from_mapping_log(kept / "Mapping.log")
        idmap = parse_id_map(kept / "Traffic.log")
        if not eq and p > 0:
            print(f"[refresh] {f.name}: no Mapping.log in {kept}, skipped")
            continue
        r["sumo"]["tripinfo"] = parse_tripinfo(scenario / "sumo/out/tripinfo.xml", eq, idmap)
        f.write_text(json.dumps(r, indent=1))
        ti = r["sumo"]["tripinfo"]
        print(f"[refresh] {f.name}: equipped finished n={ti.get('finished_equipped', {}).get('n')} "
              f"unequipped n={ti.get('finished_unequipped', {}).get('n')} (id map {len(idmap)})")
    aggregate()


# --------------------------------------------------------------------------- aggregate
def aggregate():
    rows = []
    for f in sorted(RESULTS.glob("penetration_p*_s*.json")):
        r = json.loads(f.read_text())
        v, x, rt, lat = r["vehicles"], r["v2x"], r["routing"], r["v2x"]["latency"]
        ti = r["sumo"]["tripinfo"]
        fin = ti.get("finished", {}) if ti.get("available") else {}
        fe = ti.get("finished_equipped", {}) if ti.get("available") else {}
        fu = ti.get("finished_unequipped", {}) if ti.get("available") else {}
        rows.append({
            "p": r["point"]["p"], "seed": r["point"]["seed"], "duration_s": r["point"]["duration_s"],
            "wall_s": round(r["wall_s"] or 0),
            "registered": v["registered"], "equipped": v["equipped"],
            "equipped_frac": round(v["equipped_fraction"] or 0, 3),
            "denm_sent": x["denm_sent"], "senders": x["senders"],
            "receptions": x["receptions"], "receivers": x["receivers"],
            "delivery_ratio_veh": round(x["delivery_ratio_veh"], 3) if x["delivery_ratio_veh"] is not None else "",
            "receptions_per_denm": round(x["receptions_per_denm"], 1) if x["receptions_per_denm"] is not None else "",
            "lat_mean_ms": round(lat["mean_ms"], 2) if lat["mean_ms"] is not None else "",
            "lat_p50_ms": round(lat["p50_ms"], 2) if lat["p50_ms"] is not None else "",
            "lat_p95_ms": round(lat["p95_ms"], 2) if lat["p95_ms"] is not None else "",
            "lat_p99_ms": round(lat["p99_ms"], 2) if lat["p99_ms"] is not None else "",
            "route_switches": rt["route_switches"], "vehicles_switched": rt["vehicles_switched"],
            "trips_finished": fin.get("n", ""), "trips_unfinished": ti.get("unfinished", ""),
            "tt_mean_s": round(fin["duration_mean_s"], 1) if fin.get("n") else "",
            "tt_p95_s": round(fin["duration_p95_s"], 1) if fin.get("n") else "",
            "timeLoss_mean_s": round(fin["timeLoss_mean_s"], 1) if fin.get("n") else "",
            "tt_mean_equipped_s": round(fe["duration_mean_s"], 1) if fe.get("n") else "",
            "tt_mean_unequipped_s": round(fu["duration_mean_s"], 1) if fu.get("n") else "",
            "tth_p50_s": r["time_to_hazard"]["tth_s_p50"] if r["time_to_hazard"]["n"] else "",
        })
    rows.sort(key=lambda r: (r["p"], r["seed"]))
    if not rows:
        print("[aggregate] no point JSONs yet")
        return
    csv_path = RESULTS / "penetration.csv"
    with open(csv_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # per-P means over seeds
    byp = defaultdict(list)
    for r in rows:
        byp[r["p"]].append(r)

    def m(key, rs, nd=2):
        vals = [r[key] for r in rs if r[key] != ""]
        return round(statistics.fmean(vals), nd) if vals else "-"

    md = ["# V2X penetration sweep - Eclipse MOSAIC 25.2, Dhaka R1 (registered scenario)", "",
          "Knob: `mapping_config.json` -> `typeDistributions.DEFAULT_VEHTYPE` = [{AdHoc: WeatherWarningApp+SlowDownApp, weight p}, "
          "{Unequipped: SlowDownApp, weight 1-p}], `config.fixedOrder=false` (stochastic, seed-driven). "
          "Hazard: TRACTION_HAZARD/ICE rectangle at Karwan Bazar (environment_config.json); equipped vehicles that sense it "
          "broadcast DENMs over SNS ad-hoc (ITS-G5, multi-hop TTL 20); receivers with the hazard on their route reroute "
          "through the official NavigationModule.", "",
          "Definitions: equipped = registered with WeatherWarningApp; delivery_ratio_veh = distinct receivers / equipped; "
          "latency = t_rx - t_tx per MessageId; route switches = CentralNavigationComponent 'Change to route' lines; "
          "travel time = SUMO tripinfo of finished trips (equipped vs unequipped split).", "",
          "## Per point", "",
          "| p | seed | wall s | registered | equipped | DENM sent | senders | receptions | receivers | deliv. ratio | lat mean ms | lat p95 ms | route switches | veh switched | trips fin. | TT mean s | TT p95 s | timeLoss mean s | TT eq. s | TT uneq. s |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        md.append(f"| {r['p']} | {r['seed']} | {r['wall_s']} | {r['registered']} | {r['equipped']} | {r['denm_sent']} | {r['senders']} | "
                  f"{r['receptions']} | {r['receivers']} | {r['delivery_ratio_veh']} | {r['lat_mean_ms']} | {r['lat_p95_ms']} | "
                  f"{r['route_switches']} | {r['vehicles_switched']} | {r['trips_finished']} | {r['tt_mean_s']} | {r['tt_p95_s']} | "
                  f"{r['timeLoss_mean_s']} | {r['tt_mean_equipped_s']} | {r['tt_mean_unequipped_s']} |")
    md += ["", "## Mean over seeds", "",
           "| p | n seeds | equipped frac | receivers | deliv. ratio | lat mean ms | lat p95 ms | route switches | TT mean s | TT p95 s | timeLoss mean s |",
           "|---|---|---|---|---|---|---|---|---|---|---|"]
    for p_, rs in sorted(byp.items()):
        md.append(f"| {p_} | {len(rs)} | {m('equipped_frac', rs, 3)} | {m('receivers', rs, 0)} | {m('delivery_ratio_veh', rs, 3)} | "
                  f"{m('lat_mean_ms', rs)} | {m('lat_p95_ms', rs)} | {m('route_switches', rs, 0)} | {m('tt_mean_s', rs, 1)} | "
                  f"{m('tt_p95_s', rs, 1)} | {m('timeLoss_mean_s', rs, 1)} |")
    md += ["", f"Source JSONs: `results/networking/penetration_p{{P}}_s{{SEED}}.json`; regenerate with "
               "`python -m traffictwin.networking.mosaic.penetration_sweep --aggregate`."]
    (RESULTS / "penetration.md").write_text("\n".join(md) + "\n")
    print(f"[aggregate] {len(rows)} points -> {csv_path}, {RESULTS / 'penetration.md'}")


# --------------------------------------------------------------------------- main
def run_point(p: float, seed: int, duration: int, keep_logs: bool, stdout_dir: Path):
    scenario = build_scenario(p, seed, duration)
    stdout_dir.mkdir(parents=True, exist_ok=True)
    log_dir, wall = run_mosaic(scenario, stdout_dir / f"mosaic_{point_name(p, seed)}.out")
    res = parse_point(log_dir, scenario, p, seed, duration, wall_s=wall)
    kept = keep_small_logs(log_dir, p, seed)
    if not keep_logs:
        shutil.rmtree(log_dir, ignore_errors=True)   # visualizer.csv can be GBs; parsed JSON is the record
        print(f"[clean] removed {log_dir} (small logs kept in {kept})", flush=True)
    aggregate()
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--p", type=float, help="penetration rate in [0,1]")
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--seeds", type=int, nargs="*", default=[11, 22, 33], help="seeds for --all")
    ap.add_argument("--duration", type=int, default=600, help="simulation duration in s")
    ap.add_argument("--all", action="store_true", help="run the full grid P x seeds sequentially")
    ap.add_argument("--skip-done", action="store_true", help="with --all: skip points whose JSON exists")
    ap.add_argument("--parse-only", type=Path, help="parse an existing MOSAIC log dir for --p/--seed")
    ap.add_argument("--aggregate", action="store_true", help="only rebuild penetration.csv/.md")
    ap.add_argument("--refresh-tripinfo", action="store_true",
                    help="recompute equipped/unequipped travel-time split of existing JSONs from kept logs")
    ap.add_argument("--keep-logs", action="store_true", help="do not delete the MOSAIC log dir after parsing")
    ap.add_argument("--stdout-dir", type=Path, default=RESULTS / "logs", help="where mosaic stdout goes")
    a = ap.parse_args()
    RESULTS.mkdir(parents=True, exist_ok=True)

    if a.aggregate:
        aggregate()
        return
    if a.refresh_tripinfo:
        refresh_tripinfo()
        return
    if a.parse_only:
        if a.p is None:
            sys.exit("--parse-only needs --p")
        scenario = SCEN_ROOT / point_name(a.p, a.seed)
        parse_point(a.parse_only, scenario, a.p, a.seed, a.duration)
        aggregate()
        return
    if a.all:
        for seed in a.seeds:
            for p in P_GRID:
                out = RESULTS / f"penetration_p{ptag(p)}_s{seed}.json"
                if a.skip_done and out.exists():
                    print(f"[all] skip {out.name} (exists)")
                    continue
                run_point(p, seed, a.duration, a.keep_logs, a.stdout_dir)
        return
    if a.p is None:
        sys.exit("give --p (and --seed) or --all")
    run_point(a.p, a.seed, a.duration, a.keep_logs, a.stdout_dir)


if __name__ == "__main__":
    main()
