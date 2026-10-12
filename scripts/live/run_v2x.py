"""make run-v2x: the RQ3 ambulance study run live in SUMO's window, with the parameters you choose.

    python scripts/live/run_v2x.py [--tech its_g5|c_v2x|cellular_4g] [--share 1.0] [--seed N|clock (default 11)] [--level dhaka|x0.5|x1|x2|x3|x4]
                                   [--demand current|dhatrax-peak] [--from EDGE|random --to EDGE|random] [--arm alert_preemption|alert] [--speed 8] [--no-gui] [--record DIR]
    make run-v2x-live SEED=<n> FROM=<edge|random> TO=<edge|random> [DEMAND=dhatrax-peak]     # 2026-10-12: seed, route and demand level chosen by the viewer

Nothing is replayed: both runs (no alert, then the chosen alert) are computed now by the study's own code
(core/simulation/ambulance/service.py run_one, make-way rule v2 from configs/ambulance.yaml, the V2X delivery model of
core/networking/v2x). On the map: the ambulance (white, green cross), the radio range of the chosen technology around it (blue),
cars making way now (orange), and a live label with packets sent / delivered, cars alerted and junctions turned green.
At the end it prints the measured results and, when the study saved a run with exactly these settings, checks they are equal.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO), str(REPO / "backend")]

from core.networking.v2x import model  # noqa: E402
from core.simulation.ambulance import service  # noqa: E402

CITY = "dhaka"
SAVED = REPO / "results/emergency/dhaka/rq2"
OUT = REPO / "evidence/live_runs/v2x"
ORANGE, GREY, BLUE = (255, 150, 0, 255), (200, 200, 200, 255), (30, 90, 255, 255)
YELLOW, AMB_GREEN = (255, 220, 0, 255), (0, 190, 70, 255)          # --gui-colours: alerted cars yellow, the ambulance green (display only)
MATCH = REPO / "evidence/ambulance_rq2/dhaka_density/match.json"     # corridor.match(): the scale at which the INT section sits inside DhaTraX's recorded density range
CALIBRATION = REPO / "evidence/ambulance_rq2/dhaka_density/calibration.json"


def dhaka_scale(path: Path = MATCH) -> float:
    """The "Dhaka density" scale, read from the computed match (never typed)."""
    return float(json.loads(path.read_text())["chosen_scale"])


def recorded_counts(path: Path = CALIBRATION) -> dict:
    """The hourly DhaTraX counts the corridor demand was fitted to: the 12 five-minute counts per site, summed."""
    cal = json.loads(path.read_text())
    return {s["site"]: {"section": s["section"], "day": s["day"], "vehicles_per_hour": int(sum(s["counts"]))} for s in cal["sites"]}


LEVELS = {"dhaka": ("dhaka_density", dhaka_scale()), "x0.5": ("generated", 0.5), "x1": ("generated", 1.0), "x2": ("generated", 2.0),
          "x3": ("generated", 3.0), "x4": ("generated", 4.0)}
DEMANDS = ("current", "dhatrax-peak")      # current = the level as chosen; dhatrax-peak = the corridor at the FULL recorded counts (scale 1.0 of the fitted routes)


def sumo_version() -> str:
    import subprocess
    try:
        return subprocess.run(["sumo", "--version"], capture_output=True, text=True, timeout=20).stdout.splitlines()[0].strip()
    except Exception:                                          # noqa: BLE001 - display only
        return "SUMO (version not read)"
VIEW = """<viewsettings>
  <scheme name="live">
    <background backgroundColor="white" showGrid="0"/>
    <edges laneEdgeMode="0" laneShowBorders="1" showLinkDecals="1" showRails="1" hideConnectors="0"/>
    <vehicles vehicleMode="0" vehicleQuality="2" vehicle_minSize="1" vehicle_exaggeration="5" showBlinker="1" vehicleColor="200,200,200"/>
    <junctions junctionMode="0" drawLinkTLIndex_show="0" drawLinkJunctionIndex_show="0" showLane2Lane="0"/>
    <pois poi_minSize="0" poi_exaggeration="1" poiName_show="0" poiText_show="1" poiTextParam="label" poiText_size="110" poiText_color="20,20,20"/>
    <polys poly_exaggeration="1"/>
  </scheme>
</viewsettings>
"""


class Arrived(Exception):
    pass


def say(*lines: str) -> None:
    print("\n".join(lines), flush=True)


def run_dir(arm: str, tech, share: float, seed: int, scale: float, tag: str = "") -> str:
    return service.run_name(arm, tech, share, seed) + (f"_x{scale:g}" if scale != 1.0 else "") + (f"_{tag}" if tag else "")


def route_tag(route: tuple[str, str] | None) -> str:
    import hashlib
    return "r" + hashlib.sha1("|".join(route).encode()).hexdigest()[:8] if route else ""


def saved(arm: str, tech, share: float, seed: int, demand: str, scale: float) -> dict | None:
    """The study's saved run with exactly these settings, if it made one (no alert: runs/, alert arms with make-way v2: runs_v2/)."""
    f = SAVED / ("runs" if arm == "no_alert" else "runs_v2") / CITY / demand / run_dir(arm, tech, share, seed, scale) / "metrics.json"
    return json.loads(f.read_text()) if f.exists() else None


def ambulance_time(out: Path) -> float | None:
    f = out / "tripinfo.xml"
    if not f.exists():
        return None
    try:
        root = ET.parse(f).getroot()
    except ET.ParseError:                                      # SUMO died mid-run (its bluelight segfault): the file is cut short
        return None
    for t in root.iter("tripinfo"):
        if t.get("id") == service.AMBULANCE:
            return float(t.get("duration"))
    return None


def crashed(out: Path) -> float | None:
    """The simulated second at which SUMO itself died in this run folder, or None (run_one records it in metrics.json)."""
    f = out / "metrics.json"
    if not f.exists():
        return None
    m = json.loads(f.read_text())
    return m.get("crashed_after_s") if m.get("state") == "sumo_crashed" else None


def circle(x: float, y: float, r: float, n: int = 36) -> list[tuple[float, float]]:
    """A polygon approximating the radio range around (x, y). Pure."""
    return [(x + r * math.cos(2 * math.pi * k / n), y + r * math.sin(2 * math.pi * k / n)) for k in range(n)]


def gui_hook(record: Path | None, depart_s: float, range_m: float | None, speed: float, captured: dict, colours: bool = False):
    """Display only (colours, range circle, label, pace); the run's own logic is untouched. Stops when the ambulance arrives."""
    painted: set[str] = set()
    st = {"slow": False, "frame": 0, "drawn": False}

    def hook(conn, t, run):
        captured["run"] = run
        if not st["slow"] and t >= depart_s - 20:
            st["slow"] = True
        if st["slow"] and not record:
            time.sleep(1.0 / speed)
        if service.AMBULANCE in conn.vehicle.getIDList():
            x, y = conn.vehicle.getPosition(service.AMBULANCE)
            if not st["drawn"]:
                conn.gui.trackVehicle("View #0", service.AMBULANCE)
                conn.gui.setZoom("View #0", 600 if range_m and range_m < 500 else 450 if range_m else 1400)
                if range_m:
                    conn.polygon.add("radio", circle(x, y, range_m) + [circle(x, y, range_m)[0]], BLUE, fill=False, layer=5, lineWidth=4)
                conn.poi.add("hud", x, y + 140, (0, 0, 0, 0))
                st["drawn"] = True
            if range_m:
                conn.polygon.setShape("radio", circle(x, y, range_m) + [circle(x, y, range_m)[0]])
            m = run.msgs
            pre = len(run.preemption.preempted()) if run.preemption else 0
            conn.poi.setPosition("hud", x, y + 140)
            if colours:                                        # --gui-colours: every car ever alerted yellow, the ambulance green, a live counter
                conn.vehicle.setColor(service.AMBULANCE, AMB_GREEN)
                ids = set(conn.vehicle.getIDList())
                for v in run.alerted - painted:
                    if v in ids:
                        conn.vehicle.setColor(v, YELLOW)
                painted.update(run.alerted)
                delay = conn.vehicle.getTimeLoss(service.AMBULANCE)
                conn.poi.setParameter("hud", "label", f"alerted {len(run.alerted)}  |  ambulance delay {delay:.0f} s"
                                                      f"  |  delivered {m['delivered']} of {m['sent']}  |  green now {pre}")
                if int(t) % 15 == 0:
                    say(f"    t={int(t)} s  alerted {len(run.alerted)}  ambulance delay {delay:.0f} s  delivered {m['delivered']} of {m['sent']}")
                if record and st["slow"]:
                    conn.gui.screenshot("View #0", str(record / f"f{st['frame']:05d}.png"))
                    st["frame"] += 1
                if run.state == "arrived":
                    raise Arrived
                return
            conn.poi.setParameter("hud", "label", f"sent {m['sent']}  delivered {m['delivered']}  lost {m['lost']}  out of range {m['out_of_range']}"
                                                  f"  |  cars alerted {len(run.alerted)}  making way {len(run.makeway.before)}  |  green now {pre}")
            now = set(run.makeway.before)
            for v in now - painted:
                conn.vehicle.setColor(v, ORANGE)
            for v in painted - now:
                if v in conn.vehicle.getIDList():
                    conn.vehicle.setColor(v, GREY)
            painted.clear(); painted.update(now)
            if int(t) % 15 == 0:
                say(f"    t={int(t)} s  sent {m['sent']} delivered {m['delivered']}  cars alerted {len(run.alerted)}  junctions green now {pre}")
        if record and st["slow"]:
            conn.gui.screenshot("View #0", str(record / f"f{st['frame']:05d}.png"))
            st["frame"] += 1
        if run.state == "arrived":
            raise Arrived
    return hook


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
        return run_veins.main(["v2x"] + out)
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tech", default="its_g5", choices=["its_g5", "c_v2x", "cellular_4g"])
    ap.add_argument("--share", type=float, default=1.0, help="share of cars that can receive the alert (0..1)")
    ap.add_argument("--seed", default="11", help="random seed (default 11, the thesis's; make present depends on it) or 'clock' = from the clock, printed on screen (make run-v2x-live)")
    ap.add_argument("--level", default="dhaka", choices=list(LEVELS), help=f"traffic: dhaka = the corridor at Dhaka's recorded density (x{LEVELS['dhaka'][1]:g}, evidence/ambulance_rq2/dhaka_density/match.json)")
    ap.add_argument("--demand", default="current", choices=DEMANDS, help="dhatrax-peak = the corridor demand at the FULL recorded DhaTraX 07:00-08:00 counts (scale 1.0), heavier than the thesis level")
    ap.add_argument("--from", dest="from_edge", default=None, help="ambulance start edge id on the network, or 'random' (drawn by the seed); default: the city config's trip")
    ap.add_argument("--to", dest="to_edge", default=None, help="ambulance end edge id, or 'random'")
    ap.add_argument("--arm", default="alert_preemption", choices=["alert_preemption", "alert"], help="alert and green signals, or the alert only")
    ap.add_argument("--speed", type=float, default=8.0, help="simulated seconds per real second while the ambulance drives")
    ap.add_argument("--no-gui", action="store_true")
    ap.add_argument("--record", type=Path)
    ap.add_argument("--gui-colours", action="store_true", help="display only: alerted cars yellow, the ambulance green, a live counter (alerted / rerouted / ambulance delay)")
    a = ap.parse_args(argv)
    seed_source = "the clock" if str(a.seed) == "clock" else "given"
    a.seed = int(time.time()) % 100_000 if str(a.seed) == "clock" else int(a.seed)
    demand, scale = LEVELS[a.level]
    if a.demand == "dhatrax-peak":
        if demand != "dhaka_density":
            say("STOP: --demand dhatrax-peak needs --level dhaka (the corridor fitted to the DhaTraX counts)."); return 1
        scale = 1.0
    route = None
    if (a.from_edge is None) != (a.to_edge is None):
        say("STOP: give both --from and --to (edge ids or 'random')."); return 1
    if a.from_edge is not None:
        if a.from_edge == "random" or a.to_edge == "random":
            rnd = service.random_route(CITY, demand, a.seed)
            route = (rnd[0] if a.from_edge == "random" else a.from_edge, rnd[1] if a.to_edge == "random" else a.to_edge)
        else:
            route = (a.from_edge, a.to_edge)
    try:
        scen = service.scenario(CITY, demand, route)
    except service.Refused as exc:
        say(f"STOP: {exc}"); return 1
    p = model.parameters(a.tech)
    cfg = service.settings()
    counts = recorded_counts() if demand == "dhaka_density" else None
    demand_text = (f"the corridor fitted to DhaTraX's 07:00-08:00 counts (" + ", ".join(f"{k} {v['vehicles_per_hour']} veh/h on {v['day']}" for k, v in counts.items()) + f") at scale {scale:g}"
                   + (" = the FULL recorded counts" if scale == 1.0 else f" = the thesis's 'Dhaka density' level (match.json)")) if counts else f"generated city demand at scale {scale:g}"
    say(f"LIVE RUN (RQ3, Dhaka corridor, SIMULATION): an ambulance crosses twice in the same traffic, first with no alert, then with",
        f"  {'the alert and green signals' if a.arm == 'alert_preemption' else 'the alert only'} over {a.tech}"
        f" ({'range ' + str(p['range_m']) + ' m' if p.get('range_m') else 'no range limit'}, delivery {p['delivery_ratio_in_range']}, {int(a.share * 100)} % of cars equipped).",
        f"  SEED {a.seed} (from {seed_source})",
        f"  ROUTE {scen['edges'][0]} -> {scen['edges'][-1]}: {len(scen['edges'])} edges, {scen['length_m']:.0f} m, {len(scen['signals'])} signals on it"
        + (" (edges chosen for this run)" if route else " (the city config's trip, as in the thesis)"),
        f"  DEMAND {a.demand}: {demand_text}",
        f"SOFTWARE: {sumo_version()} + TraCI; make-way rule v2 (SUMO bluelight settings; the {cfg['alert']['makeway']['distance_m']:g} m alert distance is our choice, configs/ambulance.yaml);",
        "  our V2X delivery model (core/networking/v2x, parameters sourced in configs/network_model.yaml); pre-emption adapted from atsc-rl.", "")
    if cfg["alert"].get("makeway", {}).get("version") != 2:
        say("STOP: configs/ambulance.yaml is not make-way rule v2."); return 1
    root = OUT / "runs"
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "view.xml").write_text(VIEW)
    say("1/2 No alert (computed now, no window) ...")
    m0 = service.run_one(CITY, "no_alert", None, 0.0, a.seed, demand, root=root, scale=scale, route=route)
    t0 = m0["ambulance"]["travel_time_s"]
    if m0.get("state") == "sumo_crashed":
        say(f"    SUMO itself crashed at {m0.get('crashed_after_s')} s (its bluelight device, evidence/emergency/dhaka/sumo_bluelight_crash.json): try another seed."); return 3
    say(f"    ambulance travel time, no alert: {t0} s", "")
    say(f"2/2 With {a.arm.replace('_', ' ')} ({'no window' if a.no_gui else 'SUMO window: blue = radio range, orange = making way, label = packets'}) ...")
    if a.record:
        a.record.mkdir(parents=True, exist_ok=True)
    out = root / CITY / demand / run_dir(a.arm, a.tech, a.share, a.seed, scale, route_tag(route))
    captured: dict = {}
    try:
        if a.no_gui:
            m1 = service.run_one(CITY, a.arm, a.tech, a.share, a.seed, demand, root=root, scale=scale, route=route)
            msgs, alerted, junctions = m1["messages"], m1["vehicles_alerted"], m1.get("junctions_preempted", [])
        else:
            service.run_one(CITY, a.arm, a.tech, a.share, a.seed, demand, root=root, scale=scale, route=route, sumo_binary="sumo-gui",
                            gui_options=("--start", "--quit-on-end", "--window-size", "1600,1000", "--delay", "0", "--gui-settings-file", str(OUT / "view.xml")),
                            hook=gui_hook(a.record, cfg["ambulance"]["depart_s"], p.get("range_m"), a.speed, captured, a.gui_colours))
    except Arrived:
        pass                                                   # run_one closed SUMO, which wrote the ambulance's trip
    if not a.no_gui:
        r = captured.get("run")
        s = r.summary() if r else {}
        msgs, alerted, junctions = s.get("messages", {}), s.get("vehicles_alerted"), s.get("junctions_preempted", [])
    if crashed(out) is not None:
        say(f"    SUMO itself crashed at {crashed(out)} s in the alert run (its bluelight device, evidence/emergency/dhaka/sumo_bluelight_crash.json): no result; try another seed."); return 3
    t1 = ambulance_time(out)
    pct = round(100 * (t0 - t1) / t0, 1) if t0 and t1 else None
    ratio = round(msgs.get("delivered", 0) / msgs["sent"], 3) if msgs.get("sent") else None
    say("", f"RESULT of this run (Dhaka corridor, SIMULATION, seed {a.seed} from {seed_source}, demand {a.demand} at scale {scale:g}, route {scen['edges'][0]} -> {scen['edges'][-1]} ({scen['length_m']:.0f} m), {a.tech}, {int(a.share * 100)} % equipped):",
        f"  ambulance travel time: no alert {t0} s, {a.arm.replace('_', ' ')} {t1} s" + (f" -> {pct:+.1f} % ({'sooner' if pct > 0 else 'later'})" if pct is not None else ""),
        f"  messages: sent {msgs.get('sent')}, delivered {msgs.get('delivered')} (delivery ratio {ratio}), lost {msgs.get('lost')}, out of range {msgs.get('out_of_range')}",
        f"  cars alerted {alerted}; junctions turned green {len(junctions)}")
    s0, s1 = (saved("no_alert", None, 0.0, a.seed, demand, scale), saved(a.arm, a.tech, a.share, a.seed, demand, scale)) if not route else (None, None)
    check = None
    if s0 and s1:
        want = (s0["ambulance"]["travel_time_s"], s1["ambulance"]["travel_time_s"], s1["messages"], s1["vehicles_alerted"])
        got = (t0, t1, msgs, alerted)
        check = want == got
        say(f"  THESIS CHECK: the study saved a run with exactly these settings: no alert {want[0]} s, {a.arm} {want[1]} s, messages {want[2]},"
            f" cars alerted {want[3]} -> " + ("REPRODUCED exactly." if check else "DIFFERENT (see above)."))
    else:
        say("  THESIS CHECK: the study has no saved run with exactly these settings; this result is new (not a thesis number).")
    rec = {"args": vars(a) | {"record": str(a.record) if a.record else None}, "seed_source": seed_source, "scale": scale, "route": list(scen["edges"][:1] + scen["edges"][-1:]),
           "route_given": list(route) if route else None, "route_m": scen["length_m"], "signals_on_route": len(scen["signals"]), "recorded_counts": counts,
           "no_alert_s": t0, "with_s": t1, "pct": pct, "messages": msgs,
           "vehicles_alerted": alerted, "junctions_preempted": junctions, "thesis_check": check}
    (OUT / "last_run.json").write_text(json.dumps(rec, indent=1) + "\n")
    return 0 if check is not False else 2


if __name__ == "__main__":
    sys.exit(main())
