"""Forecast routing (RQ2) with a PACKET-LEVEL network: the Graph WaveNet server + RSUs + IEEE 802.11p in Veins, ONE SUMO run
(Phase 2 of the Veins loops, 2026-10-12/13; new file; the design of PRE-VE: Santamaria et al., IEEE TVT 2019, RSUs + 802.11p +
predictive rerouting, no code of theirs exists).

    make veins-forecast-routing                              # seed 201, Qtenv + sumo-gui, baseline then predictive (press RUN in Qtenv for each)
    make veins-forecast-routing ARGS="--no-gui --minutes 15 --rsus 20"

One SUMO 1.21 (`--num-clients 2`) on the Los Angeles twin, the thesis's synthetic peak demand (randomTrips, drawn with the thesis's own
tools before the Veins environment is set, so the file hash can be compared with the channel-model runs), the real METR-LA speeds replayed as
lane caps in both arms:
  * client 1, Veins: every CONNECTED car (Veins's penetrationRate = the loop's share, 0.30) is an 802.11p node running RoutingCar11p
    (research/veins_loops/src): a status frame every status_period_s; an advice frame addressed to it, really received, changes its
    route (the checks of core/simulation/twin/route_application.py, in C++). RSUs (RoutingRSU11p) at the N busiest junctions: every
    status they really decode is written to their SUMO point of interest (the wired backhaul); every advice the server leaves there is
    broadcast as a frame.
  * client 2, this module: the EXISTING traffic-management server (core.simulation.routing.controller.RoutingController through
    closed_loop.Server, mode gwnet+correction: Graph WaveNet on the real METR-LA history + residual correction + the decision rules,
    all unchanged) fed ONLY with the statuses the RSUs received; every 300 s from the warm-up on it plans and hands each advice to the
    RSU nearest to the car (within rsu_reach_m); the outcome of every advice comes back through the "v2x_log" point of interest.
Arms on the same seed: baseline (radios silent, no server) and predictive_corrected_v2x. No fork state: SUMO 1.21 cannot load a 1.27
state, so both arms run from 0 s; nothing is sent before fork_t0 (the warm-up), as in the channel-model loop.
Packet numbers are Veins's scalars (statusSent / statusReceived / adviceSent / adviceReceived / adviceApplied, SNIRLostPackets,
RXTXLostPackets per node). Every number is computed in the run. Obstacle shadowing: none on the LA twin (no building polygons there).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import statistics
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
if sys.path and Path(sys.path[0]).resolve() == Path(__file__).resolve().parent:
    sys.path.pop(0)                                        # run as a script, this folder's signal.py would shadow the standard library's (torch needs it)
sys.path[:0] = [str(REPO), str(REPO / "backend")]
from core.simulation.ambulance import veins_loop as vl  # noqa: E402  (veins_env, free_port, opp_env, read_scalars, net_bounds: shared with Phase 1)

OUT = REPO / "evidence/veins_forecast_routing"
ARM = "predictive_corrected_v2x"
LINK = "Veins 5.3.1 IEEE 802.11p (packet level), 20 mW, 6 Mbit/s, no obstacle shadowing on the LA twin"
PREVE = "Santamaria, Fazio, Raimondo, Tropea, De Rango, IEEE TVT 68(5) 2019, doi:10.1109/TVT.2019.2905753 (design: RSUs + 802.11p + predictive rerouting; no code released)"


# ------------------------------------------------------------------ preparation (the thesis's own tools, before the Veins environment)
def prepare(seed: int, minutes: int, root: Path, demand_scale: float | None, share: float | None) -> dict:
    """Protocol, demand draw, forecaster and caps exactly as scripts/live/gui_routing.prepare, without the fork state."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("run_profile", REPO / "scripts/routing/run_profile.py"); rp = importlib.util.module_from_spec(spec); spec.loader.exec_module(rp)
    S = rp.settings()
    from core.simulation.closed_loop.control import closed_loop as cl
    duration = int(S["fork_t0"] + minutes * 60)
    ns = argparse.Namespace(city=S["city"], seeds=[seed], profile="ideal", penetration=share or S["penetration"], moment=S["moment"], round_s=S["round_s"], horizon_min=S["horizon_min"],
                            status_period_s=S["status_period_s"], duration_s=duration, tag="veins", incident=[], fuse_observed=False, fork_t0=S["fork_t0"],
                            demand_scale=demand_scale or S["demand_scale"], demand_profile=S["demand_profile"], od_rule=S["od_rule"])
    cfg = cl.ec.load_config(); P = cl.protocol(ns, cfg)
    (root / "PROTOCOL.json").write_text(json.dumps(P, indent=1))
    sdir = root / f"s{seed}"; sdir.mkdir(parents=True, exist_ok=True)
    routes, dinfo = cl.demand_for_seed(P, seed, sdir)
    fc = cl.Forecaster(P, seed); caps = fc.caps(P["simulation_duration_s"])
    return {"cl": cl, "S": S, "P": P, "cfg": cfg, "routes": routes, "dinfo": dinfo, "fc": fc, "caps": caps, "sdir": sdir, "duration": duration}


def busiest_junctions(net, edgedata: Path, n: int, min_gap_m: float = 500.0) -> list[dict]:
    """The n junctions with the most vehicles entering their incoming edges over a baseline run's edgeData (vehicles entered, summed over
    intervals), at least min_gap_m apart. Coordinates in SUMO's frame."""
    import xml.etree.ElementTree as ET
    entered: dict[str, float] = defaultdict(float)
    for iv in ET.parse(edgedata).getroot().iter("interval"):
        for e in iv.iter("edge"):
            entered[e.get("id")] += float(e.get("entered", 0))
    score: dict[str, float] = defaultdict(float)
    for eid, v in entered.items():
        try:
            score[net.getEdge(eid).getToNode().getID()] += v
        except KeyError:
            pass
    out: list[dict] = []
    for nid, s in sorted(score.items(), key=lambda kv: -kv[1]):
        x, y = net.getNode(nid).getCoord()[:2]
        if all(math.dist((x, y), tuple(o["sumo_xy"])) >= min_gap_m for o in out):
            out.append({"node": nid, "sumo_xy": [round(x, 2), round(y, 2)], "entered": round(s)})
        if len(out) >= n:
            break
    return out


# ------------------------------------------------------------------ files of one run
def write_sumo_cfg(out: Path, P: dict, routes: Path, horizon: int) -> Path:
    add = out / "additional.xml"
    add.write_text(f'<additional>\n  <edgeData id="ed" file="{out / "edgedata.xml"}" freq="300" excludeEmpty="true"/>\n</additional>\n')
    cfgf = out / "sumo.sumocfg"
    cfgf.write_text(f"""<configuration>
  <input><net-file value="{REPO / P['network']}"/><route-files value="{routes}"/><additional-files value="{add}"/></input>
  <time><begin value="0"/><end value="{horizon}"/></time>
  <processing><scale value="1.0"/><route-steps value="0"/><time-to-teleport value="{P['time_to_teleport_s']}"/><ignore-route-errors value="true"/>
    <device.rerouting.probability value="0"/><device.rerouting.adaptation-interval value="10"/><device.rerouting.adaptation-weight value="0.5"/></processing>
  <output><tripinfo-output value="{out / 'tripinfo.xml'}"/><tripinfo-output.write-unfinished value="true"/><statistic-output value="{out / 'statistic.xml'}"/><summary-output value="{out / 'summary.xml'}"/></output>
  <report><no-step-log value="true"/><no-warnings value="true"/></report>
</configuration>
""")
    return cfgf


def write_veins(out: Path, cfgf: Path, P: dict, rsus: list[dict], seed: int, arm: str, horizon: int, port: int, gui: bool, status_period_s: int) -> Path:
    v2x = arm != "baseline"
    x0, y0, x1, y1 = vl.net_bounds(REPO / P["network"])
    d = out / "veins"; d.mkdir(parents=True, exist_ok=True)
    sumo_bin = vl.SUMO121 / "bin" / ("sumo-gui" if gui else "sumo")
    extra = " --start --quit-on-end --window-size 1000,800 --window-pos 0,420" if gui else ""
    rsu_lines = "\n".join(f'*.rsu[{i}].mobility.x = {r["veins_xy"][0]}\n*.rsu[{i}].mobility.y = {r["veins_xy"][1]}\n*.rsu[{i}].mobility.z = 3\n*.rsu[{i}].appl.poiId = "rsu{i}"' for i, r in enumerate(rsus))
    ini = f"""[General]
cmdenv-express-mode = true
cmdenv-autoflush = true
cmdenv-status-frequency = 300s
**.cmdenv-log-level = info
image-path = {vl.VEINS / 'images'}
network = SharedSumoScenarioExt
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
*.annotations.draw = {'true' if gui else 'false'}
*.manager.updateInterval = 1s
*.manager.host = "localhost"
*.manager.port = {port}
*.manager.order = 1
*.manager.connectAt = 0s
*.manager.penetrationRate = {P['penetration']}
*.manager.seed = {seed}
*.manager.autoShutdown = true
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
*.**.nic.phy80211p.decider = xmldoc("{vl.LOOPS / 'config_no_obstacles.xml'}")
*.**.nic.phy80211p.analogueModels = xmldoc("{vl.LOOPS / 'config_no_obstacles.xml'}")
*.**.nic.phy80211p.usePropagationDelay = true
*.**.nic.phy80211p.antenna = xmldoc("{vl.DHAKA_VEINS / 'antenna.xml'}", "/root/Antenna[@id='monopole']")
*.node[*].nic.phy80211p.antennaOffsetY = 0 m
*.node[*].nic.phy80211p.antennaOffsetZ = 1.895 m
*.rsu[*].nic.phy80211p.antennaOffsetZ = 0 m
*.rsu[*].applType = "RoutingRSU11p"
*.rsu[*].appl.headerLength = 80 bit
*.rsu[*].appl.sendBeacons = false
*.rsu[*].appl.dataOnSch = false
*.rsu[*].appl.beaconInterval = 1s
*.rsu[*].appl.active = {'true' if v2x else 'false'}
{rsu_lines}
*.node[*].applType = "RoutingCar11p"
*.node[*].appl.headerLength = 80 bit
*.node[*].appl.sendBeacons = false
*.node[*].appl.dataOnSch = false
*.node[*].appl.beaconInterval = 1s
*.node[*].appl.statusInterval = {status_period_s}s
*.node[*].appl.active = {'true' if v2x else 'false'}
*.node[*].appl.guiColours = {'true' if gui else 'false'}
*.node[*].veinsmobility.x = 0
*.node[*].veinsmobility.y = 0
*.node[*].veinsmobility.z = 0
*.node[*].veinsmobility.setHostSpeed = false

[Config Default]
"""
    (d / "omnetpp.ini").write_text(ini)
    return d


def veins_stats(vals: dict, rsus: list[dict]) -> dict:
    def total(name: str, where: str = "") -> int:
        return int(sum(v.get(name, 0) for m, v in vals.items() if where in m))
    per = []
    by_suffix = {m.split(".", 1)[1]: v for m, v in vals.items() if "." in m}             # module names minus the network name (SharedSumoScenario / SharedSumoScenarioExt)
    for i, r in enumerate(rsus):
        appl, phy = by_suffix.get(f"rsu[{i}].appl", {}), by_suffix.get(f"rsu[{i}].nic.phy80211p", {})
        per.append({"rsu": i, "node": r["node"], "status_received": int(appl.get("statusReceived", 0)), "advice_sent": int(appl.get("adviceSent", 0)),
                    "lost_interference_or_collision": int(phy.get("SNIRLostPackets", 0)), "lost_while_transmitting": int(phy.get("RXTXLostPackets", 0))})
    phy = [v for m, v in vals.items() if m.endswith(".nic.phy80211p")]
    return {"source": "Veins scalars (results/*.sca), its PHY/MAC", "nodes": len({m for m in vals if ".node[" in m and m.endswith(".appl")}),
            "status_sent": total("statusSent", ".node["), "status_received_at_rsus": sum(p["status_received"] for p in per), "advice_sent_by_rsus": sum(p["advice_sent"] for p in per),
            "advice_received": total("adviceReceived", ".node["), "advice_applied": total("adviceApplied", ".node["), "advice_inapplicable": total("adviceInapplicable", ".node["),
            "advice_deferred_on_junction": total("adviceDeferred", ".node["),
            "frames_lost_all_nodes": {"interference_or_collision": int(sum(v.get("SNIRLostPackets", 0) for v in phy)), "while_transmitting": int(sum(v.get("RXTXLostPackets", 0) for v in phy))},
            "per_rsu": per}


# ------------------------------------------------------------------ one run
def run(arm: str, seed: int, pre: dict, rsus: list[dict], out: Path, gui: bool, rsu_reach_m: float, port: int | None = None, say=print) -> dict:
    P, cfg, fc, caps, routes = pre["P"], pre["cfg"], pre["fc"], pre["caps"], pre["routes"]
    cl = pre["cl"]
    from core.simulation.twin import runtime as pr
    from core.simulation.twin.metrics import congestion_metrics
    from core.simulation.closed_loop.protocols.oracle_gate import never_inserted_charge
    import traci
    out.mkdir(parents=True, exist_ok=True)
    net_path = REPO / P["network"]; H = int(P["simulation_duration_s"]); t_begin = int(P["fork_t0_s"]); round_s = int(P["round_s"])
    port = port or vl.free_port()
    cfgf = write_sumo_cfg(out, P, routes, H)
    vdir = write_veins(out, cfgf, P, rsus, seed, arm, H, port, gui, int(P["status_period_s"]))
    sim_id = f"sim_veins_s{seed}_{arm}"
    server = cl.Server(P, seed, cfg, fc, net_path, out, sim_id, "gwnet+correction", None, "vehicle") if arm != "baseline" else None
    say(f"VEINS ROUTING seed {seed} arm {arm}: SUMO 1.21.0 --num-clients 2 on port {port}; client 1 Veins ({'Qtenv' if gui else 'Cmdenv'}), {len(rsus)} RSUs; client 2 this process"
        f" ({'the Graph WaveNet + correction server, decisions every ' + str(round_s) + ' s from ' + str(t_begin) + ' s' if server else 'no server'}); radios {'ACTIVE' if arm != 'baseline' else 'silent'}; {H} s")
    if gui:
        say("  In the OMNeT++ window press RUN (F5) or FAST (F6); the sumo-gui window follows. This process waits for the connection.")
    t0 = time.time()
    sumo_bin = vl.SUMO121 / "bin" / ("sumo-gui" if gui else "sumo")
    for attempt in range(1, 6):                                      # SUMO 1.21's two-client handshake fails now and then before the first step: restart whole on a fresh port
      sumo_cmd = [str(sumo_bin), "-c", str(cfgf), "--remote-port", str(port), "--seed", str(seed), "--num-clients", "2"] + (["--start", "--quit-on-end", "--window-size", "1000,800", "--window-pos", "0,420"] if gui else [])
      sumo = subprocess.Popen(sumo_cmd, cwd=out, stdout=open(out / "sumo.log", "a"), stderr=subprocess.STDOUT)      # this process owns SUMO: its outputs are complete when it exits
      veins = subprocess.Popen(vl.opp_cmd(gui), cwd=vdir, env=vl.opp_env(), stdout=open(out / "veins.log", "a"), stderr=subprocess.STDOUT)
      label = f"{sim_id}-{int(time.time())}-{attempt}"
      crashed, stepped = None, 0
      conn: set[str] = set(); present_conn: set[str] = set(); recent: list[list[str]] = []; classified: set[str] = set()
      up_rx, up_dup, down_tx, applied, inapplicable, no_rsu, expired, decided = 0, 0, 0, 0, 0, 0, 0, 0
      seen_status: set[tuple] = set(); pending: list[dict] = []; handed: dict[str, dict] = {}; reroute_log: list[dict] = []; teleports: list[dict] = []
      rsu_rx = [0] * len(rsus); adv_seq = [0] * len(rsus); lanes: dict[str, list[str]] = {}
      if server is not None and attempt > 1:
          server = cl.Server(P, seed, cfg, fc, net_path, out, sim_id, "gwnet+correction", None, "vehicle")
      try:
        traci.init(port=port, numRetries=600 if gui else 120, label=label); c = traci.getConnection(label); c.setOrder(2)
        for i, r in enumerate(rsus):                                     # the RSUs' points of interest = the wired backhaul; visible in sumo-gui
            c.poi.add(f"rsu{i}", r["sumo_xy"][0], r["sumo_xy"][1], (220, 30, 30, 255), poiType="rsu", layer=10, width=12, height=12)
            c.poi.setParameter(f"rsu{i}", "obs", ""); c.poi.setParameter(f"rsu{i}", "adv", ""); c.poi.setParameter(f"rsu{i}", "adv_seq", "0")
        c.poi.add("v2x_log", rsus[0]["sumo_xy"][0], rsus[0]["sumo_xy"][1], (0, 0, 0, 0), poiType="log", layer=0)
        c.poi.setParameter("v2x_log", "log", "")
        for edge in caps:
            try:
                lanes[edge] = [f"{edge}_{i}" for i in range(c.edge.getLaneNumber(edge))]
            except traci.TraCIException:
                lanes[edge] = []

        def apply_caps(t_now):
            for edge, steps in caps.items():
                cap = next((cp for tf, cp in reversed(steps) if tf <= t_now), steps[0][1])
                for lid in lanes.get(edge, []):
                    try:
                        c.lane.setMaxSpeed(lid, cap)
                    except traci.TraCIException:
                        pass
        apply_caps(0)
        t, k = 0, 0
        next_round = (t_begin // round_s + 1) * round_s
        last_say = -1
        while t < H and c.simulation.getMinExpectedNumber() > 0:
            c.simulationStep(); t = int(c.simulation.getTime()); stepped += 1
            if t % 30 == 0 and veins.poll() is not None:
                raise RuntimeError(f"Veins ended at {t} s (exit {veins.returncode}): see veins.log")   # SUMO would carry on with this client alone: not a two-client run
            if t % 300 == 0:
                apply_caps(t)
            recent.append(list(c.simulation.getDepartedIDList()))       # Veins creates a vehicle's module one step after its departure (subscription result), then marks it
            if len(recent) > 3:
                recent.pop(0)
            for vid in [v for lst in recent for v in lst]:
                if vid in classified:
                    continue
                try:
                    if c.vehicle.getParameter(vid, "v2x.connected") == "1":
                        conn.add(vid); present_conn.add(vid); classified.add(vid)
                except traci.TraCIException:
                    classified.add(vid)
            for lst in recent[:-3]:
                classified.update(lst)
            for vid in c.simulation.getArrivedIDList():
                present_conn.discard(vid)
            for vid in c.simulation.getStartingTeleportIDList():
                teleports.append({"vehicle_id": vid, "sim_time_s": t, "connected": vid in conn})
            if arm == "baseline":
                if t % 300 == 0 and t != last_say:
                    last_say = t; say(f"  t={t}s  vehicles {c.vehicle.getIDCount()}  connected (Veins nodes) {len(present_conn)}  [{time.time() - t0:.0f} s wall]")
                continue
            # ---- uplink: what the RSUs really received (their point of interest), to the server
            for i in range(len(rsus)):
                obs = c.poi.getParameter(f"rsu{i}", "obs")
                if not obs:
                    continue
                c.poi.setParameter(f"rsu{i}", "obs", "")
                for item in obs.split(";"):
                    if not item:
                        continue
                    vid, road, pos, speed, ts = item.split("|")
                    rsu_rx[i] += 1
                    if t < t_begin:
                        continue                                         # warm-up: nothing reaches the server before the fork time, as in the channel-model loop
                    key = (vid, ts)
                    if key in seen_status:
                        up_dup += 1; continue                           # the same frame decoded by two RSUs
                    seen_status.add(key); up_rx += 1
                    server.receive({"payload": {"type": "VEHICLE_STATUS", "from": vid, "to": "TMS", "vehicle_id": vid, "t": float(ts), "edge": road, "lane_pos_m": round(float(pos), 1), "speed_mps": round(float(speed), 2),
                                                "route_index": None}, "latency_ms": round((t - float(ts)) * 1000, 1), "msg_id": f"st-{vid}-{ts}"}, t)
            server.detect(t)
            # ---- the round
            if t >= next_round:
                vehicles = {}
                for vid in list(present_conn):
                    try:
                        edge = c.vehicle.getRoadID(vid)
                        if edge.startswith(":"):
                            continue
                        route = list(c.vehicle.getRoute(vid)); idx = c.vehicle.getRouteIndex(vid)
                        if idx < 0 or idx >= len(route) - 2:
                            continue
                        vehicles[vid] = (route[idx], route[idx:])
                    except traci.TraCIException:
                        present_conn.discard(vid)
                msgs, rrec = server.plan_round(k, t, vehicles, None)
                pending.extend(msgs); decided += len(msgs)
                say(f"  round {k} t={t}s as_of={rrec['as_of_index']} priced={rrec['priced_edges']} considered={rrec['vehicles_considered']} decisions={rrec['decisions']} advice={len(msgs)} statuses_known={rrec['statuses_known']}"
                    f" (RSU receptions so far {sum(rsu_rx)}, unique {up_rx})")
                k += 1; next_round += round_s
            # ---- downlink: each due advice to the RSU nearest to the car, which broadcasts it next second
            batches: dict[int, list[str]] = defaultdict(list)
            keep = []
            for m in pending:
                if m.get("send_at_s", m["created_s"]) > t:
                    keep.append(m); continue
                if t > m["created_s"] + float(m.get("validity_s") or 600):
                    expired += 1; reroute_log.append({"vehicle_id": m["vehicle_id"], "sim_time_s": t, "message_id": None, "created_s": m["created_s"], "outcome": "EXPIRED_NO_RSU_IN_REACH"}); continue
                try:
                    x, y = c.vehicle.getPosition(m["vehicle_id"])
                except traci.TraCIException:
                    inapplicable += 1; reroute_log.append({"vehicle_id": m["vehicle_id"], "sim_time_s": t, "message_id": None, "created_s": m["created_s"], "outcome": "VEHICLE_GONE"}); continue
                i, dist = min(((i, math.dist((x, y), tuple(r["sumo_xy"]))) for i, r in enumerate(rsus)), key=lambda z: z[1])
                if dist > rsu_reach_m:
                    no_rsu += 1 if m.get("_waiting") is None else 0; m["_waiting"] = t; keep.append(m); continue
                down_tx += 1; mid = f"adv-{down_tx}"
                handed[mid] = {**{kk: v for kk, v in m.items() if not kk.startswith("_")}, "msg_id": mid, "handed_s": t, "rsu": i, "rsu_distance_m": round(dist, 1)}
                batches[i].append(f"{mid}|{m['vehicle_id']}|{' '.join(m['route'])}")
            pending = keep
            for i, items in batches.items():
                adv_seq[i] += 1
                c.poi.setParameter(f"rsu{i}", "adv", ";".join(items) + ";"); c.poi.setParameter(f"rsu{i}", "adv_seq", str(adv_seq[i]))
            # ---- outcomes reported by the cars (the route change happened inside Veins, on a real reception)
            log = c.poi.getParameter("v2x_log", "log")
            if log:
                c.poi.setParameter("v2x_log", "log", "")
                for line in log.splitlines():
                    outcome, mid, vid, ts, road = line.split("|")
                    h = handed.get(mid, {})
                    entry = {"vehicle_id": vid, "sim_time_s": float(ts), "message_id": mid, "created_s": h.get("created_s"), "handed_to_rsu_s": h.get("handed_s"), "rsu": h.get("rsu"),
                             "latency_ms": round((float(ts) - h["handed_s"]) * 1000, 1) if h else None, "routing_run_id": h.get("routing_run_id"), "forecast_hash": h.get("forecast_hash"), "edge_cost_hash": h.get("edge_cost_hash"),
                             "reason": h.get("reason"), "predicted_saving_s": h.get("predicted_saving_s"), "outcome": outcome, "current_edge": road}
                    reroute_log.append(entry)
                    if outcome == "APPLIED":
                        applied += 1
                    else:
                        inapplicable += 1
            if t % 60 == 0 and t != last_say:
                last_say = t
                say(f"  t={t}s  vehicles {c.vehicle.getIDCount()}  connected {len(present_conn)}  statuses at RSUs {sum(rsu_rx)} (unique to server {up_rx})  advice handed {down_tx} applied {applied} waiting-for-RSU {sum(1 for m in pending if m.get('_waiting'))}  [{time.time() - t0:.0f} s wall]")
        for _ in range(10):                                              # Veins asks for one more step than this loop: keep SUMO moving until Veins closes it at its time limit
            try:
                c.simulationStep()
            except Exception:                                            # noqa: BLE001
                break
      except Exception as e:                                             # noqa: BLE001
        crashed = str(e)[:300]; say(f"  client 2 stopped: {crashed}")
      try:                                                               # Veins leaves at its time limit (its close only removes it: SUMO keeps serving the last client)
        veins.wait(timeout=30 if crashed else 900)
      except subprocess.TimeoutExpired:
        veins.terminate(); crashed = crashed or "Veins did not finish"
      try:
        traci.getConnection(label).close()                               # the last client's close ends the simulation: SUMO writes its outputs in full and exits
      except Exception:                                                  # noqa: BLE001
        pass
      try:
        sumo.wait(timeout=30 if crashed else 600)
      except subprocess.TimeoutExpired:
        sumo.terminate(); crashed = crashed or "SUMO did not finish"
      if not crashed or stepped > 0 or attempt == 5:
        break
      for old in (vdir / "results").glob("*"):
        if old.suffix in (".sca", ".vec", ".vci"):
          old.rename(old.with_name(old.name + f".{int(time.time())}.handshake_failed"))
      port = vl.free_port(port + 1)
      vdir = write_veins(out, cfgf, P, rsus, seed, arm, H, port, gui, int(P["status_period_s"]))
      say(f"  handshake failed before the first step (SUMO 1.21 two-client connect); attempt {attempt + 1} on port {port}")
    vals = vl.read_scalars(vdir / "results"); vs = veins_stats(vals, rsus) if vals else {}
    ok = (out / "tripinfo.xml").exists() and (out / "statistic.xml").exists() and not crashed and stepped > 0
    m: dict = {}
    if ok:
        m = pr.parse_metrics(out, horizon=H); m.update(never_inserted_charge(routes, out / "tripinfo.xml", H))
        m["congestion"] = congestion_metrics(out, net_path, 0, H)
        m["total_vehicle_hours_incl_never_inserted"] = round(m["total_vehicle_hours"] + m["never_inserted_vehicle_hours"], 4)
    m["teleports"] = len(teleports); m["wall_s"] = round(time.time() - t0, 1)
    net_metrics = {"link": LINK, "uplink": {"messages_tx": vs.get("status_sent"), "messages_rx_at_rsus": vs.get("status_received_at_rsus"), "unique_to_server": up_rx, "duplicates_two_rsus": up_dup,
                                            "delivery_ratio_unique": round(up_rx / vs["status_sent"], 4) if vs.get("status_sent") else None},
                   "downlink": {"advice_decided": decided, "still_pending_at_end": len(pending), "handed_to_rsu": down_tx, "broadcast_by_rsus": vs.get("advice_sent_by_rsus"),
                                "received_by_car": vs.get("advice_received"), "applied": vs.get("advice_applied", applied), "inapplicable": vs.get("advice_inapplicable"), "expired_no_rsu_in_reach": expired,
                                "delivery_ratio": round(vs["advice_received"] / down_tx, 4) if down_tx and vs.get("advice_received") is not None else None},
                   "connected_vehicles": len(conn), "penetration_configured": P["penetration"], "rsus": len(rsus), "rsu_reach_m": rsu_reach_m, "reroutes_applied": applied, "veins": vs}
    (out / "reroute_log.jsonl").write_text("".join(json.dumps(e) + "\n" for e in reroute_log))
    (out / "network_metrics.json").write_text(json.dumps(net_metrics, indent=1))
    res = {"simulation_run_id": sim_id, "arm": arm, "seed": seed, "profile": "veins_802.11p", "penetration": P["penetration"], "moment": P["moment"], "config_hash": P["routing_config_hash"], "network_hash": P["network_hash"],
           "sumo": "1.21.0 --num-clients 2 (Veins order 1, this loop order 2)", "fork": None, "warm_up_s": t_begin, "design": PREVE, "information": "gwnet+correction" if server else "baseline",
           "state": "ok" if ok else "crashed", "crash": crashed, "veins_exit": veins.returncode, "metrics": m, "network": net_metrics, "rounds": server.rounds if server else [],
           "routing_run_ids": server.routing_run_ids if server else [], "reroutes_applied": applied, "out_dir": str(out.relative_to(REPO)), "run_utc": datetime.now(timezone.utc).isoformat()}
    (out / "arm_result.json").write_text(json.dumps(res, indent=1, default=str))
    return res


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", default="201", help="an integer, or `clock` = a seed taken from the clock at start (a new demand draw and a new real moment of the METR-LA history every time)")
    ap.add_argument("--minutes", type=int, default=15, help="simulated minutes after the 1 200 s warm-up")
    ap.add_argument("--rsus", type=int, default=20, help="road-side units, at the busiest junctions of a saved baseline run")
    ap.add_argument("--rsu-reach-m", type=float, default=600.0, help="the server hands an advice to an RSU only when the car is this close to it")
    ap.add_argument("--demand-scale", type=float, default=None, help="the protocol's 8.0 by default; lower if Veins is too slow (stated in the results)")
    ap.add_argument("--connected-share", type=float, default=None)
    ap.add_argument("--arms", nargs="+", default=["baseline", ARM], choices=["baseline", ARM])
    ap.add_argument("--edgedata", type=Path, default=None, help="a baseline run's edgedata.xml for choosing the busiest junctions (default: the newest x8 peak arterial baseline of this seed)")
    ap.add_argument("--no-gui", action="store_true")
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args(argv)
    a.seed = (int(time.time()) % 9000) + 1000 if str(a.seed).lower() == "clock" else int(a.seed)
    why = vl.ready()
    if why:
        print(f"STOP: {why}"); return 1
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root = (a.out or (OUT / stamp)).resolve()
    if REPO not in root.parents:
        print(f"STOP: --out must be inside the repository (the loop records paths relative to it); got {root}"); return 1
    root.mkdir(parents=True, exist_ok=True)
    log = open(root / "run.log", "a")

    def say(s: str) -> None:
        print(s, flush=True); log.write(s + "\n"); log.flush()

    say(f"VEINS FORECAST ROUTING {datetime.now(timezone.utc).isoformat()}: LA twin, seed {a.seed}, {a.minutes} min after the warm-up, {a.rsus} RSUs; {LINK}; design {PREVE}")
    pre = prepare(a.seed, a.minutes, root, a.demand_scale, a.connected_share)              # the thesis's own SUMO 1.27 tools draw the demand first
    P = pre["P"]
    from core.simulation.twin.network import net_for
    net = net_for(REPO / P["network"])
    newest = lambda pat: next(iter(sorted((REPO / "results/v2x/closed_loop").glob(pat), key=lambda p: p.stat().st_mtime, reverse=True)), None)
    ed = a.edgedata or newest(f"*_x8_peak_arterial/s{a.seed}/baseline/edgedata.xml") or newest("*_x8_peak_arterial/s*/baseline/edgedata.xml")
    if ed is None:
        say("STOP: no saved baseline edgedata.xml to choose the busiest junctions from (run make run-routing-quick once, or pass --edgedata)"); return 1
    say(f"SEED {a.seed}{' (from the clock)' if 'clock' in sys.argv else ''}; RSU placement from the busiest junctions of {ed.relative_to(REPO)}"
        + (" (a saved baseline of another seed: the placement is a deployment choice, the traffic of this run is its own)" if f"/s{a.seed}/" not in str(ed) else ""))
    x0, y0, x1, y1 = vl.net_bounds(REPO / P["network"])
    rsus = busiest_junctions(net, ed, a.rsus)
    for r in rsus:
        r["veins_xy"] = [round(r["sumo_xy"][0] - x0 + 25, 2), round((y1 - y0) - (r["sumo_xy"][1] - y0) + 25, 2)]
    say(f"  demand {pre['dinfo']['vehicles']} vehicles (hash {pre['dinfo']['demand_hash'][:12]}, scale {pre['dinfo']['demand_scale']}); {int(P['penetration'] * 100)} % connected (Veins's draw);"
        f" RSUs at the {len(rsus)} busiest junctions of {ed.relative_to(REPO)} (entered vehicles {rsus[0]['entered']} … {rsus[-1]['entered']}); METR-LA caps on {len(pre['caps'])} edges")
    (root / "rsus.json").write_text(json.dumps({"edgedata": str(ed.relative_to(REPO)), "rsus": rsus}, indent=1))
    vl.veins_env()                                                                        # from here on: SUMO 1.21's traci (API 21) for the shared simulation
    res = {}
    for arm in a.arms:
        res[arm] = run(arm, a.seed, pre, rsus, pre["sdir"] / arm, not a.no_gui, a.rsu_reach_m, say=say)
        r = res[arm]; m, n = r["metrics"], r["network"]
        say(f"  {arm}: {'veh-h=%.1f arrived=%s tel=%s' % (m['total_vehicle_hours_incl_never_inserted'], m.get('arrived'), m['teleports']) if r['state'] == 'ok' else 'CRASHED: ' + str(r['crash'])}"
            f"  statuses sent {n['uplink']['messages_tx']} received at RSUs {n['uplink']['messages_rx_at_rsus']} (unique {n['uplink']['unique_to_server']})  advice handed {n['downlink']['handed_to_rsu']}"
            f" broadcast {n['downlink']['broadcast_by_rsus']} received {n['downlink']['received_by_car']} applied {n['downlink']['applied']}  [{m['wall_s']} s wall]")
    b, p = res.get("baseline"), res.get(ARM)
    summary = {"generated_utc": datetime.now(timezone.utc).isoformat(), "label": "SIMULATION, LA twin, synthetic peak demand on the real network; METR-LA speeds replayed as caps; network: " + LINK, "design": PREVE,
               "seed": a.seed, "minutes_after_warm_up": a.minutes, "warm_up_s": P["fork_t0_s"], "demand": pre["dinfo"], "rsus": rsus, "rsu_reach_m": a.rsu_reach_m, "penetration": P["penetration"],
               "arms": {k: {"state": v["state"], "metrics": v["metrics"], "network": v["network"], "out_dir": v["out_dir"]} for k, v in res.items()},
               "comparison": {"baseline_vehicle_hours": b["metrics"].get("total_vehicle_hours_incl_never_inserted") if b and b["state"] == "ok" else None,
                              "predictive_vehicle_hours": p["metrics"].get("total_vehicle_hours_incl_never_inserted") if p and p["state"] == "ok" else None} if (b and p) else None}
    if summary["comparison"] and None not in summary["comparison"].values():
        summary["comparison"]["difference_vehicle_hours"] = round(summary["comparison"]["predictive_vehicle_hours"] - summary["comparison"]["baseline_vehicle_hours"], 3)
        say(f"COMPARISON (same seed {a.seed}, same demand, both from 0 s, {a.minutes} min after the warm-up): baseline {summary['comparison']['baseline_vehicle_hours']:.1f} veh-h | predictive + Veins 802.11p"
            f" {summary['comparison']['predictive_vehicle_hours']:.1f} veh-h ({summary['comparison']['difference_vehicle_hours']:+.1f})")
    (root / "summary.json").write_text(json.dumps(summary, indent=1, default=str))
    log.close()
    files = sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file() and (p.name in ("summary.json", "run.log", "arm_result.json", "network_metrics.json", "reroute_log.jsonl", "omnetpp.ini", "sumo.sumocfg", "PROTOCOL.json", "rsus.json") or p.suffix == ".sca"))
    (root / "SHA256SUMS").write_text("".join(f"{hashlib.sha256((root / f).read_bytes()).hexdigest()}  {f}\n" for f in files))
    return 0 if all(r["state"] == "ok" for r in res.values()) else 2


if __name__ == "__main__":
    sys.exit(main())
