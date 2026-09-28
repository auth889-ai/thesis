"""One (P, seed) scenario: the registered Dhaka R1 scenario copied with big immutable inputs
symlinked, the mapping rewritten so a fraction P of vehicles carries the official V2X app stack,
the seed and duration set, SUMO outputs enabled; then mosaic.sh run on it.

THE MAPPING KNOB (verified in MappingAmbassador.handleInteraction(ScenarioVehicleRegistration)
bytecode of mosaic-mapping-25.2.jar): vehicles from the SUMO route file are matched by their SUMO
vehicle-type name against `typeDistributions[<vtype>]`, a list of prototypes with `weight`s; a
WeightedSelector picks one prototype per vehicle (StochasticSelector driven by the scenario
randomSeed when config.fixedOrder=false). This is exactly how the official Barnim example expresses
"Cellular 10 % / AdHoc 20 % / Unequipped 70 %"."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from app.paths import REPO

NET_DIR = Path(__file__).resolve().parents[1]                    # backend/app/networking/mosaic
SRC_SCENARIO = REPO / "results/artifacts/mosaic_dhaka/dhaka_r1"
FALLBACK_NET = REPO / "data/cities/dhaka_r1/dhaka_r1.net.xml.gz"
MOSAIC_HOME = Path(os.environ.get("MOSAIC_HOME", Path.home() / ".dhakaflow/upstream/mosaic"))
LOGBACK = NET_DIR / "logback_sweep.xml"       # etc/logback.xml with the per-vehicle app-log delegate at WARN (the 1000 s reference run wrote 37 GB otherwise)
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


def ensure_net_file() -> None:
    net = SRC_SCENARIO / "sumo/dhaka_r1.net.xml"
    if not net.exists():
        if not FALLBACK_NET.exists():
            sys.exit(f"missing {net} and fallback {FALLBACK_NET}")
        print(f"[scenario] {net} missing -> copying frozen net from {FALLBACK_NET}")
        shutil.copy2(FALLBACK_NET, net)


def mapping_config(p: float) -> dict:
    equipped = {"name": "DEFAULT_VEHTYPE", "group": "AdHoc", "weight": p, "applications": [WWA, SDA]}
    unequipped = {"name": "DEFAULT_VEHTYPE", "group": "Unequipped", "weight": round(1.0 - p, 6), "applications": [SDA]}
    dist = [d for d in (equipped, unequipped) if d["weight"] > 0]
    return {
        "config": {"fixedOrder": False},          # stochastic selector -> seed-dependent equipment
        "prototypes": [{"name": "DEFAULT_VEHTYPE"}],  # base prototype: vehicle params stay SUMO's
        "typeDistributions": {"DEFAULT_VEHTYPE": dist},
    }


def _subscription(sid: str, entries: list[str]) -> str:
    rows = "\n".join(f"                    <entry>{e}</entry>" for e in entries)
    return f'            <subscription id="{sid}" enabled="true">\n                <entries>\n{rows}\n                </entries>\n            </subscription>'


OUTPUT_CONFIG = f"""<?xml version="1.0" encoding="UTF-8"?>
<configuration xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
               xsi:noNamespaceSchemaLocation="http://www.dcaiti.tu-berlin.de/research/simulation/download/get/scenarios/scenarioname/visualizer/visualizer_config.xsd">
    <output id="fileoutput" enabled="true" update="1" loader="org.eclipse.mosaic.fed.output.generator.file.FileOutputLoader">
        <filename>visualizer.csv</filename>
        <directory>.</directory>
        <separator>;</separator>
        <subscriptions>
{_subscription("VehicleRegistration", ['"VEHICLE_REGISTRATION"', "Time", "Mapping.Name", "Mapping.Applications", "Mapping.VehicleType.Name"])}
{_subscription("V2xMessageTransmission", ['"V2X_MESSAGE_TRANSMISSION"', "Time", "MessageId", "SourceName", "Type"])}
{_subscription("V2xMessageReception", ['"V2X_MESSAGE_RECEPTION"', "Time", "MessageId", "ReceiverName", "Type"])}
{_subscription("VehicleUpdates", ['"VEHICLE_UPDATES"', "Time", "Updated:Name", "Updated:Position.Latitude", "Updated:Position.Longitude", "Updated:Speed", "Updated:Heading"])}
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
