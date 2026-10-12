"""make run-sos-v2v: a crash on the Dhaka corridor, detected by the SOS rule, and the warning spread car to car, computed live.

    python scripts/live/run_sos_v2v.py [--tech its_g5|c_v2x|cellular_4g] [--share 0.5] [--seed 11] [--level dhaka|x1|x2|...]
                                       [--crash-at 600] [--after 600] [--speed 8] [--no-gui]

1. The SOS rule (core/safety/sos.py, WreckWatch: 4 g at driving speed) is run again on the thesis's three synthetic traces and must
   give the thesis's answers (evidence/sos/results.json).
2. SUMO (Dhaka corridor, generated demand at the chosen level): at --crash-at one car on the corridor stops (red). Its phone's rule fires
   on the crash trace and the warning goes out over the chosen technology through the thesis's V2X delivery model
   (core/networking/v2x/model.deliver, the same function as RQ3). Every warned, equipped car repeats it once a second (a flood, as in
   Veins' TraCIDemo11p). Warned cars turn blue; a warned car whose route still crosses the crash edge reroutes the way TraCIDemo11p does
   (that edge's travel time set very high, then reroute) and turns green.
3. The same seed is run again without any warning, and the cars that were heading for the crash are compared.
There is no thesis number for car-to-car SOS: the delivery and travel-time results are new, and the script says so.
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
import time
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO), str(REPO / "backend")]

from core.networking.v2x import model  # noqa: E402
from core.safety import sos  # noqa: E402
from core.simulation.ambulance import service  # noqa: E402
from core.simulation.twin import runtime as pr  # noqa: E402

OUT = REPO / "evidence/live_runs/sos_v2v"
LEVELS = {"dhaka": ("dhaka_density", 0.78), "x0.5": ("generated", 0.5), "x1": ("generated", 1.0), "x2": ("generated", 2.0), "x3": ("generated", 3.0)}
RED, BLUE, GREEN = (230, 20, 20, 255), (40, 110, 255, 255), (20, 170, 60, 255)
YELLOW = (255, 220, 0, 255)          # --gui-colours: warned (alerted) cars yellow, rerouted cars blue (display only)
REACH_M = 1000              # receivers considered per sender (beyond every technology's range except cellular)


def say(*lines: str) -> None:
    print("\n".join(lines), flush=True)


def rule_check() -> tuple[bool, list[str]]:
    """The SOS rule on the thesis traces, against the thesis results."""
    want = {r["kind"]: r for r in sos.read()["rows"]}
    ok, lines = True, []
    for kind in sos.KINDS:
        tr = sos.trace(kind)
        got = sos.detect(tr["samples"])
        w = want[kind]
        same = (got["detected"], got.get("at_s"), round(got["peak_g"], 2)) == (w["detected"], w["at_s"], round(w["peak_g"], 2))
        ok &= same
        lines.append(f"    {kind}: peak {got['peak_g']:.2f} g, alarm {'yes at ' + str(got['at_s']) + ' s' if got['detected'] else 'no'}"
                     f"  (thesis: {'yes at ' + str(w['at_s']) + ' s' if w['detected'] else 'no'}) -> {'same' if same else 'DIFFERENT'}")
    return ok, lines


COLLIDE_VS_VEINS = """  How make run-sos-collide differs from Veins's TraCIDemo11p (vendored, read: src/veins/modules/application/traci/TraCIDemo11p.cc):
    1. Their "accident" is a car told to stop (TraCIMobility accidentStart/accidentDuration); here SUMO detects a real contact: one car
       stops obeying the safe-speed rules (speedMode 0, no lane change) and drives into the car ahead (--collision.action warn).
    2. Their trigger is "stood still for 10 s" (lastDroveAt), so queues warn too; here the trigger is SUMO's own collision list.
    3. Their warning carries the road id and receivers call changeRoute(road, 9999); here delivery goes through the thesis's V2X model
       (range, loss, delay) and receivers reroute the same way (adapted travel time 9999, rerouteTraveltime).
    4. They rebroadcast once with a random delay; here every warned car rebroadcasts every interval while in reach (a flood).
    5. SUMO's own record of the contact (collisions.xml: collider, victim, lane, position, time) is kept in last_run.json."""


def simulate(a, warn: bool, gui: bool, on_step=None) -> dict:
    colours = bool(getattr(a, "gui_colours", False))                     # display only; the web job's settings have no such flag
    collide = bool(getattr(a, "collide", False))                         # make run-sos-collide: a real collision detected by SUMO itself (off by default)
    """`on_step(conn, t, crashed, warned, rerouted, messages)` after each second: the web app's live frames (core/simulation/live_jobs); display only."""
    import traci
    demand, scale = LEVELS[a.level]
    scen = service.scenario("dhaka", demand)
    out = OUT / "runs" / f"{'warn' if warn else 'nowarn'}_{a.tech}_p{int(a.share * 100):03d}_s{a.seed}_{a.level}"
    out.mkdir(parents=True, exist_ok=True)
    ns = SimpleNamespace(sumo_binary="sumo-gui" if gui else "sumo", net=scen["net"], routes=scen["routes"], seed=a.seed, scale=scale,
                         horizon=a.crash_at + a.after, edgedata_period=300, time_to_teleport=300,
                         sumo_extra=["--lateral-resolution", "0.8"] + (["--start", "--quit-on-end", "--window-size", "1600,1000", "--delay", "0",
                                                                        "--gui-settings-file", str(OUT / "view.xml")] if gui else [])
                         # SUMO's own collision handling (docs Simulation/Safety): the colliding vehicles stop for stoptime, then continue (warn);
                         # every collision is written to collisions.xml (collider, victim, lane, position, time)
                         + (["--collision.action", "warn", "--collision.stoptime", str(max(10, int(a.after) - 10)), "--collision-output", str(out / "collisions.xml")] if collide else []))
    label = f"sos-{time.time_ns()}"
    traci.start(pr.base_cmd(ns, out), port=pr.free_port(), label=label)
    c = traci.getConnection(label)
    rng = random.Random(f"{a.seed}|{a.tech}|{a.share}|sos")
    p = model.parameters(a.tech)
    edges = scen["edges"]
    crash_edge = edges[len(edges) // 2]
    crashed, warned, rerouted, no_alt = None, {}, set(), 0
    rammer, collision, announced = None, None, False
    msgs = {"broadcasts": 0, "sent": 0, "delivered": 0, "lost": 0, "out_of_range": 0}
    affected, arrived_at, teleported = set(), {}, set()
    last_send: dict[str, float] = {}
    t = 0.0
    try:
        while t < ns.horizon:
            c.simulationStep()
            t = c.simulation.getTime()
            for v in c.simulation.getArrivedIDList():
                arrived_at[v] = t
            teleported.update(c.simulation.getStartingTeleportIDList())
            if collide and rammer is None and t >= a.crash_at:
                # a real collision: one car on the crash road that has a car ahead stops obeying SUMO's safe-speed rules (speedMode 0,
                # no lane change) and drives at 20 m/s into it; SUMO detects the contact itself (simulation.getCollidingVehiclesIDList)
                for v in c.edge.getLastStepVehicleIDs(crash_edge):
                    if c.vehicle.getLeader(v, 150.0):
                        rammer = v
                        c.vehicle.setSpeedMode(v, 0); c.vehicle.setLaneChangeMode(v, 0); c.vehicle.setSpeed(v, 20.0)
                        break
            if collide and crashed is None and rammer is not None:
                hit = [v for v in c.simulation.getCollidingVehiclesIDList() if v in c.vehicle.getIDList()]
                if hit:
                    crashed = rammer if rammer in hit else hit[0]
                    collision = {"t": t, "vehicles": sorted(set(hit)), "rammer": rammer, "lane": c.vehicle.getLaneID(crashed), "pos_m": round(c.vehicle.getLanePosition(crashed), 1)}
                    c.vehicle.setSpeed(rammer, 0); c.vehicle.setSpeedMode(rammer, 31)         # back to SUMO's rules once it has crashed
                    for v in hit:
                        c.vehicle.setLaneChangeMode(v, 0); c.vehicle.setColor(v, RED)
            if not collide and crashed is None and t >= a.crash_at:
                on = c.edge.getLastStepVehicleIDs(crash_edge)
                if on:
                    crashed = on[0]
                    c.vehicle.setSpeed(crashed, 0); c.vehicle.setLaneChangeMode(crashed, 0); c.vehicle.setColor(crashed, RED)
            if crashed is not None and not announced:
                    announced = True
                    for v in c.vehicle.getIDList():                        # who was heading for the crash
                        r = c.vehicle.getRoute(v)
                        i = c.vehicle.getRouteIndex(v)
                        if v != crashed and crash_edge in r[max(i, 0):]:
                            affected.add(v)
                    if warn:
                        warned[crashed] = t
                    if gui:
                        c.gui.trackVehicle("View #0", crashed); c.gui.setZoom("View #0", 700)
                        x, y = c.vehicle.getPosition(crashed)
                        c.poi.add("hud", x, y + 150, (0, 0, 0, 0))
            if warn and crashed is not None:
                ids = set(c.vehicle.getIDList())
                pos = {v: c.vehicle.getPosition(v) for v in ids}
                equipped = [v for v in ids if v not in warned and pr.equipped(v, a.share)]
                for s in [v for v in warned if v in ids or v == crashed]:
                    if t - last_send.get(s, -1e9) < p["interval_s"] or s not in pos:
                        continue
                    last_send[s] = t
                    msgs["broadcasts"] += 1
                    sx, sy = pos[s]
                    for r in equipped:
                        if r in warned or abs(pos[r][0] - sx) > REACH_M or abs(pos[r][1] - sy) > REACH_M:
                            continue
                        d = model.deliver(model.Station(s, sx, sy), model.Station(r, *pos[r]), t, a.tech, rng)
                        msgs["sent"] += 1
                        msgs["delivered" if d.delivered else "out_of_range" if d.reason == model.OUT_OF_RANGE else "lost"] += 1
                        if d.delivered:
                            warned[r] = t
                            if gui:
                                c.vehicle.setColor(r, YELLOW if colours else BLUE)
                            route, i = c.vehicle.getRoute(r), c.vehicle.getRouteIndex(r)
                            if crash_edge in route[max(i, 0) + 1:]:
                                c.vehicle.setAdaptedTraveltime(r, crash_edge, 9999.0)     # TraCIDemo11p: changeRoute(roadId, 9999)
                                c.vehicle.rerouteTraveltime(r, False)
                                if crash_edge in c.vehicle.getRoute(r)[c.vehicle.getRouteIndex(r) + 1:]:
                                    no_alt += 1
                                else:
                                    rerouted.add(r)
                                    if gui:
                                        c.vehicle.setColor(r, BLUE if colours else GREEN)
                if gui and crashed in ids:
                    x, y = pos[crashed]
                    c.poi.setPosition("hud", x, y + 150)
                    c.poi.setParameter("hud", "label", (f"alerted {len(warned) - 1}  |  rerouted {len(rerouted)}  |  ambulance delay: no ambulance in this run"
                                                        f"  |  received {msgs['delivered']} of {msgs['sent']}") if colours else
                                       (f"CRASH  |  warned {len(warned) - 1}  rerouted {len(rerouted)}  |  broadcasts {msgs['broadcasts']}"
                                        f"  received {msgs['delivered']}  lost in range {msgs['lost']}"))
            if on_step:
                on_step(c, t, crashed, warned, rerouted, msgs)
            if gui and crashed is not None:
                time.sleep(1.0 / a.speed)
                if int(t) % 30 == 0:
                    say(f"    t={int(t - a.crash_at)} s after the crash: warned {max(len(warned) - 1, 0)}, rerouted {len(rerouted)}")
    finally:
        try:
            c.close()
        except Exception:                                            # noqa: BLE001
            pass
    reached = [arrived_at[v] - a.crash_at for v in affected if v in arrived_at]
    first_warn = sorted(w - a.crash_at for v, w in warned.items() if v != crashed)
    if collide and collision is not None and (out / "collisions.xml").exists():          # SUMO's own record of the contact
        import xml.etree.ElementTree as ET2
        collision["sumo_collision_output"] = [dict(e.attrib) for e in ET2.parse(out / "collisions.xml").getroot().iter("collision")][:5]
    return {"warn": warn, "crashed": crashed, "crash_edge": crash_edge, "collision": collision, "affected": len(affected), "affected_arrived": len(reached),
            "affected_mean_s_to_arrive": round(statistics.fmean(reached), 1) if reached else None, "teleports": len(teleported),
            "warned": max(len(warned) - 1, 0) if warn else 0, "rerouted": len(rerouted), "no_alternative": no_alt, "messages": msgs,
            "half_warned_by_s": first_warn[len(first_warn) // 2] if first_warn else None}


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--veins" in argv:                                          # the second view: Veins (OMNeT++, 802.11p) on the same corridor (scripts/live/run_veins.py)
        sys.path.insert(0, str(REPO / "scripts/live"))
        import run_veins
        keep, out, skip = {"--share", "--seed", "--txpower", "--window", "--makeway", "--crash-at"}, [], False
        for i, x in enumerate(argv):
            if skip:
                skip = False
            elif x in keep:
                out += [x, argv[i + 1]]; skip = True
            elif x in ("--no-gui", "--sumo-gui"):
                out.append(x)
            elif x.startswith("--") and x != "--veins" and i + 1 < len(argv) and not argv[i + 1].startswith("--"):
                skip = True                                        # a thesis-view option Veins does not take (e.g. --tech: Veins is 802.11p only)
        return run_veins.main(["sos"] + out)
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tech", default="its_g5", choices=["its_g5", "c_v2x", "cellular_4g"])
    ap.add_argument("--share", type=float, default=0.5, help="share of cars with the app (0..1)")
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--level", default="dhaka", choices=list(LEVELS))
    ap.add_argument("--crash-at", type=float, default=600.0)
    ap.add_argument("--after", type=float, default=600.0, help="simulated seconds after the crash")
    ap.add_argument("--speed", type=float, default=8.0)
    ap.add_argument("--no-gui", action="store_true")
    ap.add_argument("--gui-colours", action="store_true", help="display only: warned cars yellow, rerouted cars blue, a live counter (alerted / rerouted)")
    ap.add_argument("--collide", action="store_true", help="make run-sos-collide: a real collision inside SUMO (one car ignores the safe-speed rules and hits the car ahead), detected by SUMO itself, then the same warning path")
    a = ap.parse_args(argv)
    p = model.parameters(a.tech)
    say("LIVE RUN (crash SOS car to car, Dhaka corridor, SIMULATION): a car crashes; its phone's SOS rule fires; the warning hops",
        f"  car to car over {a.tech} ({'range ' + str(p['range_m']) + ' m' if p.get('range_m') else 'no range limit'}, delivery {p['delivery_ratio_in_range']}),"
        f" {int(a.share * 100)} % of cars have the app; warned cars heading for the crash reroute.",
        "SOFTWARE: Eclipse SUMO 1.27.1 + TraCI; our SOS rule (WreckWatch, White et al. 2011); our V2X delivery model (as RQ3);",
        "  warning and reroute logic as in Veins' TraCIDemo11p (Sommer et al.). Traffic: generated, uncalibrated.", "")
    say("1/3 The SOS rule on the thesis traces (computed now):")
    ok, lines = rule_check()
    say(*lines, "    THESIS CHECK: " + ("REPRODUCED (evidence/sos/results.json)." if ok else "DIFFERENT."), "")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "view.xml").write_text((REPO / "scripts/live/run_v2x.py").read_text().split('VIEW = """')[1].split('"""')[0])
    say(f"2/3 Crash with car-to-car warning ({'no window' if a.no_gui else 'SUMO window: red = crashed, blue = warned, green = rerouted'}) ...")
    if a.collide:
        say(COLLIDE_VS_VEINS)
    w = simulate(a, warn=True, gui=not a.no_gui)
    trace_note = None
    if a.collide and w.get("collision") and w["collision"].get("sumo_collision_output"):          # R1 (2026-10-11): the crash sensor's trace from SUMO's own record
        from core.safety import sos
        recs = w["collision"]["sumo_collision_output"]
        rec = next((r for r in recs if r.get("collider") == w["collision"].get("rammer") or r.get("victim") == w["collision"].get("rammer")), recs[0])
        phone = "victim" if rec.get("victim") == w.get("crashed") else "collider"                # the car whose phone runs the rule: the one the story calls crashed
        tr = sos.from_collision(float(rec["colliderSpeed"]), float(rec["victimSpeed"]),
                                {"run": "scripts/live/run_sos_v2v.py --collide", "args": {k: vars(a)[k] for k in ("seed", "level", "tech", "share", "crash_at")},
                                 "record": {k: rec.get(k) for k in ("time", "lane", "pos", "collider", "victim", "colliderType", "victimType", "colliderSpeed", "victimSpeed")},
                                 "phone_in": {"vehicle": rec.get(phone), "type": rec.get(f"{phone}Type"), "sumo_role": phone}},
                                phone_speed_mps=float(rec[f"{phone}Speed"]))
        sha = sos.write_collision_trace(tr)
        d = tr["detection"]
        c = tr["collision"]
        trace_note = {"file": str(sos.COLLISION_TRACE.relative_to(REPO)), "sha256": sha, "closing_speed_mps": c["closing_speed_mps"], "pulse_peak_g": c["pulse_peak_g"],
                      "speed_kmh": d["speed_kmh"], "detected": d["detected"], "at_s": d["at_s"], "at_g": d["at_g"], "peak_g": d["peak_g"]}
        say("", f"  CRASH SENSOR from SUMO's record (collisions.xml, t={rec.get('time')} s): collider {rec.get('colliderType')} {rec.get('collider')} at {rec.get('colliderSpeed')} m/s, victim {rec.get('victimType')} {rec.get('victim')} at {rec.get('victimSpeed')} m/s",
            f"    closing speed {c['closing_speed_mps']} m/s as a {int(c['pulse_s'] * 1000)} ms pulse (ASSUMED length) = {c['pulse_peak_g']} g; the phone is in {rec.get(phone)} (SUMO's {phone}) at {d['speed_kmh']} km/h (floor {sos.MIN_SPEED_KMH})",
            f"    the rule (4 g, White et al. 2011): " + (f"countdown starts at {d['at_s']} s ({d['at_g']} g)" if d["detected"] else f"no countdown (peak {d['peak_g']} g)")
            + f"; trace written to {trace_note['file']} (Emergency page chip, present step 7)")
    say("3/3 Same seed, crash without any warning (no window) ...")
    n = simulate(a, warn=False, gui=False)
    inr = w["messages"]["delivered"] + w["messages"]["lost"]
    ratio = round(w["messages"]["delivered"] / inr, 3) if inr else None
    say("", f"RESULT of this run (seed {a.seed}, level {a.level}, {a.tech}, {int(a.share * 100)} % with the app):",
        (f"  SUMO's collision: {json.dumps(w.get('collision'))}\n" if a.collide else "") +
        f"  warning: cars warned {w['warned']} (half of them within {w['half_warned_by_s']} s), rerouted {w['rerouted']}, no other road {w['no_alternative']}",
        f"  messages: {w['messages']['broadcasts']} broadcasts; to cars in range: {inr}, received {w['messages']['delivered']}, lost {w['messages']['lost']}"
        f" (delivery ratio in range {ratio}; the model's is {p['delivery_ratio_in_range']})",
        f"  cars heading for the crash: {w['affected']}; arrived within {int(a.after)} s: {w['affected_arrived']} with the warning, {n['affected_arrived']} without",
        f"  their mean time from the crash to arrival: {w['affected_mean_s_to_arrive']} s with, {n['affected_mean_s_to_arrive']} s without; teleports {w['teleports']} vs {n['teleports']}",
        "  THESIS CHECK: the rule part is checked above; car-to-car SOS has no thesis number, so these delivery and travel figures are new.")
    (OUT / "last_run.json").write_text(json.dumps({"args": vars(a), "rule_reproduced": ok, "with_warning": w, "without_warning": n, "collision_trace": trace_note}, indent=1) + "\n")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
