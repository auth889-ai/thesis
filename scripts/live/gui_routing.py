"""make gui-routing / make demo-routing (Part D, 2026-10-12): RQ2's forecast routing loop LIVE in sumo-gui on the Los Angeles twin, the loop unchanged.

    PYTHONPATH=.:backend python scripts/live/gui_routing.py [--minutes 15] [--delay 40] [--seed 201] [--profile ideal|its-g5|c-v2x|4g] [--no-gui]
                                                            [--arm predictive_corrected_v2x|baseline] [--demo] [--window-pos X,Y] [--window-size W,H] [--title TEXT]

The run is the saved RQ2 protocol (scripts/live/run_routing_quick.SETTINGS: la_c4_central_wide, prepeak, 30 % connected, 8x peak demand on the
arterials, fork state at 1 200 s, Graph WaveNet forecast + residual correction + the decision rules every 300 s) executed by
core.simulation.closed_loop.control.closed_loop.run_sumo with reuse off, for `--minutes` of simulated time after the fork. This script adds
ONLY display and printouts through the loop's own hooks (event_hook, control_hook, trace_hook) and never changes a decision:
  * connected cars (30 %) yellow, the others white; a car flashes green for a second when its uplink status is DELIVERED;
  * blue for the rest of the run once a delivered reroute is APPLIED; a red flash when a downlink to it is DROPPED (lost);
  * each 300 s round: translucent red polygons on the edges whose corrected forecast speed is below 50 % of the speed limit (the round's own
    edge_cost_table.json), the previous round's cleared;
  * one terminal line per round and the same text on a label in the window: sim time, round, uplink delivered / lost, the forecast's error at
    15 min against the recorded METR-LA values (mean absolute error in mph over the mapped sensors, computed from the loop's forecaster and
    data), the decisions as the loop counted them, downlink delivered / lost, total reroutes applied.
`--demo` (make demo-routing, 2026-10-12 08:40) adds, on top: a cellular base-station POI; short-lived lines, uplink RED (a status being sent,
one in every UPLINK_LINE_EVERY shown) and downlink GREEN (an advice received), a grey X where a downlink was lost (colour convention of
Eclipse MOSAIC's and Veins' visualisers: red/green message lines, the rerouted car kept blue); every priced edge coloured by corrected
forecast speed / limit (green >= 70 %, orange 40-70 %, red < 40 %); a matplotlib window per round with forecast vs corrected vs the real
METR-LA speeds for the three busiest mapped sensors and their MAE; narrated phase lines with live counts. `--arm baseline` shows the same
traffic from the same fork with no server (the loop's own baseline arm).
Profiles: ideal (the saved protocol), its-g5, c-v2x and 4g (registered at run time from the thesis's radio model: latency, loss, lifetime; 4g is
the cellular V2N one, server <-> car; scripts/routing/run_profile.py). Every number comes from the running loop or its files; nothing is typed in.
Output: evidence/live_runs/gui_routing/<stamp>/ (the loop's own run folder + gui_routing_run[_<arm>].json with the counters and the loop's own log counts).
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO), str(REPO / "backend")]

OUT = REPO / "evidence/live_runs/gui_routing"
ARM = "predictive_corrected_v2x"
WHITE, YELLOW, BLUE, GREEN, RED = (255, 255, 255, 255), (255, 220, 0, 255), (40, 90, 255, 255), (0, 230, 80, 255), (255, 40, 40, 255)
RED_FILL = (255, 0, 0, 90)
BAND = {"green": (0, 170, 60, 110), "orange": (255, 140, 0, 130), "red": (230, 0, 0, 140)}
GREY = (120, 120, 120, 255)
MPH = 2.23694
UPLINK_LINE_EVERY = 25                                         # one uplink line drawn per 25 statuses (about 60 statuses a second would hide the map)
VIEW = """<viewsettings>
  <scheme name="live">
    <background backgroundColor="white" showGrid="0"/>
    <edges laneEdgeMode="0" laneShowBorders="1" showLinkDecals="1" showRails="1" hideConnectors="0"/>
    <vehicles vehicleMode="0" vehicleQuality="2" vehicle_minSize="1" vehicle_exaggeration="4" showBlinker="1"/>
    <pois poi_minSize="0" poi_exaggeration="1" poiName_show="0" poiText_show="1" poiTextParam="label" poiText_size="140" poiText_color="20,20,20"/>
    <polys poly_exaggeration="1"/>
  </scheme>
</viewsettings>
"""
GROUPS = {"REROUTE": ("REROUTE",), "KEEP": ("KEEP_CURRENT_BELOW_THRESHOLD", "COOLDOWN", "REJECTED_COOLDOWN", "DEFERRED_BUDGET", "REJECTED_SHARE"),
          "NO_ALTERNATIVE": ("NO_ALTERNATIVE", "NO_REAL_ALTERNATIVE", "NO_ROUTE", "NO_SAFE_ROUTING_ACTION"), "REJECTED_CAPACITY": ("REJECTED_CAPACITY", "REJECTED_ROUTE_CAPACITY", "ROUTE_CAPACITY")}


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def grouped(decisions: dict) -> dict:
    """The loop's own decision counts, grouped for one line; anything unlisted is kept under its own name."""
    out = {g: 0 for g in GROUPS}
    for name, n in (decisions or {}).items():
        g = next((g for g, names in GROUPS.items() if name in names), name)
        out[g] = out.get(g, 0) + int(n)
    return out


def forecast_vs_real(fc, as_of: int) -> dict:
    """Graph WaveNet's 12-step forecast from the loop's forecaster against the recorded METR-LA values that follow `as_of` (the held-out split
    the loop reads), for the mapped sensors; mph, as the dataset is. MAE at 15 min (step 3) over all mapped sensors, and per sensor over 12 steps."""
    import numpy as np
    out = fc.service.predict(as_of)
    pred, now = np.asarray(out["prediction"]), np.asarray(out["now"])
    j = [int(s[1:]) for s in fc.cmap]
    T = fc.vals.shape[0]
    truth = np.stack([fc.vals[min(as_of + h, T - 1)] for h in range(1, 13)])          # (12, sensors)
    t3, p3 = truth[2, j], pred[2, j]; ok = t3 > 0
    mae15 = float(np.mean(np.abs(p3[ok] - t3[ok]))) if ok.any() else None
    per = {s: float(np.mean(np.abs(pred[:, int(s[1:])] - truth[:, int(s[1:])]))) for s in fc.cmap if (truth[:, int(s[1:])] > 0).all()}
    return {"pred": pred, "now": now, "truth": truth, "mae15": mae15, "per_sensor_mae": per, "as_of": as_of}


def prepare(a, root: Path):
    """Protocol, demand draw and the ONE fork state of this seed under `root` (reused by every arm started under the same root)."""
    rp = _load(REPO / "scripts/routing/run_profile.py", "run_profile")
    reg = rp.register_profiles()
    S = rp.settings()
    from core.simulation.closed_loop.control import closed_loop as cl
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    duration = int(S["fork_t0"] + a.minutes * 60)
    ns = argparse.Namespace(city=S["city"], seeds=[a.seed], profile=a.profile, penetration=getattr(a, "connected_share", None) or S["penetration"], moment=S["moment"], round_s=S["round_s"], horizon_min=S["horizon_min"],
                            status_period_s=S["status_period_s"], duration_s=duration, tag=f"gui{stamp}", incident=[], fuse_observed=False, fork_t0=S["fork_t0"],
                            demand_scale=S["demand_scale"], demand_profile=S["demand_profile"], od_rule=S["od_rule"])
    cfg = cl.ec.load_config(); P = cl.protocol(ns, cfg)
    (root / "PROTOCOL.json").write_text(json.dumps(P, indent=1))
    sdir = root / f"s{a.seed}"; sdir.mkdir(parents=True, exist_ok=True)
    routes, dinfo = cl.demand_for_seed(P, a.seed, sdir)
    fc = cl.Forecaster(P, a.seed); caps = fc.caps(P["simulation_duration_s"])
    fork = cl.save_fork_state(a.seed, routes, sdir / "fork", P, caps)
    return {"cl": cl, "reg": reg, "S": S, "P": P, "cfg": cfg, "routes": routes, "dinfo": dinfo, "fc": fc, "caps": caps, "fork": fork, "sdir": sdir, "duration": duration}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--minutes", type=int, default=15, help="simulated minutes after the fork state")
    ap.add_argument("--delay", type=float, default=40.0, help="sumo-gui delay per step, ms")
    ap.add_argument("--seed", type=int, default=201)
    ap.add_argument("--profile", default="ideal", choices=["ideal", "its-g5", "c-v2x", "4g"], help="ideal = the saved protocol; its-g5 / c-v2x = direct radio; 4g = cellular server <-> car (V2N), registered from the radio model")
    ap.add_argument("--connected-share", type=float, default=None, help="share of connected cars (default: the saved protocol's 0.30)")
    ap.add_argument("--arm", default=ARM, choices=[ARM, "baseline"], help="baseline = the same traffic from the same fork, no server, no rerouting")
    ap.add_argument("--demo", action="store_true", help="the richer display of make demo-routing (base station, message lines, three speed bands, matplotlib window, narration)")
    ap.add_argument("--window-pos", default=None, help="sumo-gui window position X,Y")
    ap.add_argument("--window-size", default="1600,1000")
    ap.add_argument("--title", default=None, help="text shown before the window label")
    ap.add_argument("--no-gui", action="store_true")
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args(argv)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root = (a.out or (OUT / stamp)).resolve()
    if REPO not in root.parents:
        print(f"STOP: --out must be inside the repository (the loop records paths relative to it); got {root}"); return 1
    root.mkdir(parents=True, exist_ok=True)
    arm = a.arm
    pre = prepare(a, root)
    cl, reg, S, P, cfg, routes, dinfo, fc, caps, fork, sdir, duration = (pre[k] for k in ("cl", "reg", "S", "P", "cfg", "routes", "dinfo", "fc", "caps", "fork", "sdir", "duration"))
    from core.simulation.twin import runner
    import sumolib
    tag = a.title or ("BASELINE: no rerouting" if arm == "baseline" else f"PREDICTIVE + {a.profile}")
    print(f"LIVE RUN (RQ2 forecast routing, Los Angeles twin, SIMULATION) [{tag}]: seed {a.seed}, profile {a.profile} {reg.get(a.profile, '(the saved protocol: no latency, no loss)')},"
          f" {int(P['penetration'] * 100)} % connected, {S['demand_scale']:g}x {S['demand_profile']} demand ({dinfo['vehicles']} vehicles, draw {dinfo['demand_hash'][:12]}…), fork at {S['fork_t0']} s, {a.minutes} min after it;"
          f" Graph WaveNet checkpoint {P['checkpoint_sha256'][:12]}…, rounds every {P['round_s']} s. The loop is core.simulation.closed_loop (unchanged); this script only colours and prints.", flush=True)
    net = sumolib.net.readNet(str(REPO / P["network"]))
    bx = net.getBoundary(); hud_xy = ((bx[0] + bx[2]) / 2, bx[3] - 50); bs_xy = ((bx[0] + bx[2]) / 2, (bx[1] + bx[3]) / 2)
    gui = not a.no_gui

    # ---- display only: sumo-gui instead of sumo, through the runner's own command builder ----
    base_cmd = runner.pr.base_cmd
    view = root / "view.xml"; view.write_text(VIEW)

    def gui_cmd(ns_, out_):
        cmd = base_cmd(ns_, out_)
        if not gui:
            return cmd
        cmd[0] = "sumo-gui"
        cmd += ["--start", "--quit-on-end", "--delay", str(a.delay), "--window-size", a.window_size, "--gui-settings-file", str(view)]
        if a.window_pos:
            cmd += ["--window-pos", a.window_pos]
        return cmd
    runner.pr.base_cmd = gui_cmd

    import traci
    C = {"uplink_tx": 0, "uplink_delivered": 0, "uplink_lost": 0, "downlink_tx": 0, "downlink_delivered": 0, "downlink_lost": 0, "reroutes_applied": 0, "rounds": 0, "polygons": 0}
    base: dict[str, tuple] = {}; flash: dict[str, float] = {}; polys: list[str] = []; lines: list[str] = []; rounds_out: list[dict] = []
    seen_rx: set[str] = set()                                  # a message deferred on a junction is re-queued and delivered again: count each message once, as the loop does
    st = {"t": 0, "shapes": 0, "last_phase_line": -1, "sensors": None}
    temp: dict[str, float] = {}                                # short-lived shapes -> remove at
    plot = {"fig": None}

    def colour(vid, c):
        if not gui:
            return
        try:
            traci.vehicle.setColor(vid, c)
        except traci.TraCIException:
            pass

    def shape(points, col, until, width=2.0):
        if not gui:
            return
        st["shapes"] += 1; pid = f"msg{st['shapes']}"
        try:
            traci.polygon.add(pid, [tuple(p) for p in points], col, fill=False, layer=6, lineWidth=width); temp[pid] = until
        except traci.TraCIException:
            pass

    def car_xy(vid):
        try:
            return traci.vehicle.getPosition(vid)
        except traci.TraCIException:
            return None

    def trace_hook(ev: dict):
        kind, ch, vid, status = ev.get("type"), ev.get("channel"), ev.get("vehicle_id"), ev.get("status")
        if kind == "V2X_TX":
            C[f"{ch}_tx"] += 1
            if status == "DROPPED":
                C[f"{ch}_lost"] += 1
                if ch == "downlink" and vid:
                    colour(vid, RED); flash[vid] = st["t"] + 2
                    if a.demo and (xy := car_xy(vid)):
                        d = 25.0
                        shape([(xy[0] - d, xy[1] - d), (xy[0] + d, xy[1] + d)], GREY, st["t"] + 3, 4.0); shape([(xy[0] - d, xy[1] + d), (xy[0] + d, xy[1] - d)], GREY, st["t"] + 3, 4.0)
            elif a.demo and ch == "uplink" and vid and C["uplink_tx"] % UPLINK_LINE_EVERY == 0 and (xy := car_xy(vid)):
                shape([xy, bs_xy], RED, st["t"] + 1, 1.5)
        elif kind == "V2X_RX":
            if ev.get("msg_id") in seen_rx:
                return
            seen_rx.add(ev.get("msg_id"))
            C[f"{ch}_delivered"] += 1
            if ch == "uplink" and vid:
                colour(vid, GREEN); flash[vid] = st["t"] + 1
            elif a.demo and ch == "downlink" and vid and (xy := car_xy(vid)):
                shape([bs_xy, xy], GREEN, st["t"] + 2, 3.0)
        elif kind == "TRACI_ROUTE_RESULT" and ev.get("outcome") == "APPLIED":
            C["reroutes_applied"] += 1
            if vid:
                base[vid] = BLUE; colour(vid, BLUE); flash.pop(vid, None)
            if a.demo and C["reroutes_applied"] <= 3:
                print(f"    PHASE 3 ADVICE APPLIED: t={st['t']}s car {vid} took the advised route ({len(ev.get('affected_edges') or [])} edges differ); reroutes applied so far {C['reroutes_applied']}", flush=True)

    def control_hook(t: int):
        st["t"] = t
        if gui:
            for vid in traci.vehicle.getIDList():
                if vid not in base:
                    base[vid] = YELLOW if runner.connected(vid, P["penetration"], a.seed) else WHITE
                    colour(vid, base[vid])
            for vid, until in list(flash.items()):
                if t >= until:
                    colour(vid, base.get(vid, WHITE)); flash.pop(vid, None)
            for pid, until in list(temp.items()):
                if t >= until:
                    try:
                        traci.polygon.remove(pid)
                    except traci.TraCIException:
                        pass
                    temp.pop(pid, None)
            if a.demo and not st.get("bs") and arm != "baseline":
                try:
                    traci.poi.add("basestation", bs_xy[0], bs_xy[1], (60, 60, 60, 255), poiType="base_station", layer=7, width=60, height=60)
                    pr_ = reg.get(a.profile)
                    traci.poi.setParameter("basestation", "label", f"cellular base station [{a.profile}]: " + (f"latency {pr_['latency_ms']:g} ms, loss {pr_['loss'] * 100:g} %, lifetime {pr_['ttl_s']:g} s" if pr_ else "ideal link"))
                    r = 120.0; ring = [(bs_xy[0] + r * math.cos(k * math.pi / 12), bs_xy[1] + r * math.sin(k * math.pi / 12)) for k in range(25)]
                    traci.polygon.add("basestation_ring", ring, (60, 60, 60, 255), fill=False, layer=7, lineWidth=4)
                except traci.TraCIException:
                    pass
                st["bs"] = True
        if a.demo and t % 60 == 0 and t != st["last_phase_line"] and arm != "baseline":
            st["last_phase_line"] = t
            print(f"    PHASE 1 REPORTING t={t}s: statuses {C['uplink_delivered']} delivered / {C['uplink_lost']} lost; advice {C['downlink_delivered']} received / {C['downlink_lost']} lost; cars rerouted {C['reroutes_applied']}; vehicles on the road {traci.vehicle.getIDCount()}", flush=True)
        elif a.demo and t % 60 == 0 and t != st["last_phase_line"]:
            st["last_phase_line"] = t
            print(f"    BASELINE t={t}s: vehicles on the road {traci.vehicle.getIDCount()}, no server, no rerouting", flush=True)
        return []

    def band_of(ratio: float) -> str:
        return "green" if ratio >= 0.7 else "orange" if ratio >= 0.4 else "red"

    def draw_plot(fr: dict, k: int, t: int, corrected: dict):
        """A matplotlib window per round: forecast vs corrected vs the real METR-LA speeds for the three busiest mapped sensors."""
        import numpy as np
        if st["sensors"] is None:                               # chosen once, in the first round: the three lowest current speeds among the mapped sensors WITH readings
            valid = [s for s in fc.cmap if s in fr["per_sensor_mae"] and fr["now"][int(s[1:])] > 0]    # METR-LA stores a missing reading as 0
            st["sensors"] = sorted(valid or list(fc.cmap), key=lambda s: fr["now"][int(s[1:])])[:3]
        import matplotlib
        import matplotlib.pyplot as plt
        if plot["fig"] is None:
            plt.ion(); plot["fig"], plot["ax"] = plt.subplots(1, 3, figsize=(12, 3.6)); plot["fig"].canvas.manager.set_window_title("forecast vs corrected vs real METR-LA")
        fig, axes = plot["fig"], plot["ax"]
        x = [5 * h for h in range(1, 13)]
        for ax, s in zip(axes, st["sensors"]):
            ax.clear(); j = int(s[1:]); edge = fc.cmap[s]["edges"][0]
            ax.plot(x, fr["pred"][:, j], color="#1f77b4", lw=1.8, label="Graph WaveNet forecast")
            ax.plot(x, fr["truth"][:, j], color="#2ca02c", lw=1.8, label="real METR-LA (recorded)")
            row = corrected.get(edge) or {}
            if row.get("bounded_speed_mps"):
                ax.plot([15], [row["bounded_speed_mps"] * MPH], marker="o", color="#d62728", ms=8, ls="none", label="corrected @15 min")
            ax.axhline(fr["now"][j], color="grey", lw=0.8, ls="--", label="now")
            ax.set_title(f"sensor {fc.cmap[s]['sensor_id']} (edge {edge[:10]}): MAE {fr['per_sensor_mae'].get(s, float('nan')):.1f} mph", fontsize=9)
            ax.set_xlabel("minutes ahead"); ax.set_ylabel("mph"); ax.set_ylim(0, 75)
        axes[0].legend(fontsize=7, loc="lower left")
        fig.suptitle(f"round {k} at t={t}s, METR-LA as_of index {fr['as_of']} (2012, 5-min bins); MAE@15min over all mapped sensors {fr['mae15']:.2f} mph", fontsize=9)
        fig.tight_layout(); fig.canvas.draw_idle(); plt.pause(0.05)
        fig.savefig(root / f"forecast_round_{k}.png", dpi=110)

    def event_hook(ev: dict):
        if ev.get("type") != "forecast_and_routing":
            return
        r = ev["round"]; k = r["round"]; t = r["sim_time_s"]; C["rounds"] += 1
        table = sdir / arm / f"routing_round_{k}" / "edge_cost_table.json"
        edges = json.loads(table.read_text()).get("edges") or {} if table.exists() else {}
        rated = {e: row["bounded_speed_mps"] / row["speed_limit_mps"] for e, row in edges.items() if row.get("bounded_speed_mps") and row.get("speed_limit_mps")}
        slow = [e for e, ratio in rated.items() if ratio < 0.5]
        bands = {b: sum(1 for ratio in rated.values() if band_of(ratio) == b) for b in BAND}
        if gui:
            for pid in polys:
                try:
                    traci.polygon.remove(pid)
                except traci.TraCIException:
                    pass
            polys.clear()
            for e, ratio in rated.items():
                if not a.demo and ratio >= 0.5:
                    continue
                try:
                    sh = net.getEdge(e).getShape()
                    if len(sh) >= 2:
                        pid = f"slow_{k}_{e}"
                        traci.polygon.add(pid, [tuple(p) for p in sh] + [tuple(sh[0])], BAND[band_of(ratio)] if a.demo else RED_FILL, fill=False, layer=4, lineWidth=10 if a.demo else 12); polys.append(pid)
                except (KeyError, traci.TraCIException):
                    pass
            C["polygons"] = len(polys)
        fr = forecast_vs_real(fc, int(r["as_of_index"])); mae = fr["mae15"]
        g = grouped(r.get("decisions_after_budget") or r.get("decisions"))
        line = (f"t={t}s round {k}: uplink {C['uplink_delivered']} delivered / {C['uplink_lost']} lost | forecast MAE@15min {mae:.2f} mph vs METR-LA | "
                f"REROUTE {g['REROUTE']} KEEP {g['KEEP']} NO_ALTERNATIVE {g['NO_ALTERNATIVE']} REJECTED_CAPACITY {g['REJECTED_CAPACITY']} | "
                f"downlink {C['downlink_delivered']} delivered / {C['downlink_lost']} lost | reroutes applied {C['reroutes_applied']} | edges below 50 % of limit {len(slow)}")
        if a.demo:
            print(f"    PHASE 2 FORECAST round {k} at t={t}s: Graph WaveNet ran on the 12 recorded METR-LA bins before index {r['as_of_index']}; correction from the cars' reports touched {(r.get('correction') or {}).get('corrected_edges', '?')} edges;"
                  f" priced edges {len(rated)}: {bands['green']} green (>= 70 % of limit), {bands['orange']} orange (40-70 %), {bands['red']} red (< 40 %); decisions REROUTE {g['REROUTE']} KEEP {g['KEEP']} NO_ALTERNATIVE {g['NO_ALTERNATIVE']} REJECTED_CAPACITY {g['REJECTED_CAPACITY']}; advice sent {r.get('recommendations_sent')}", flush=True)
        print("  " + line, flush=True); lines.append(line)
        rounds_out.append({"round": k, "sim_time_s": t, "as_of_index": r["as_of_index"], "forecast_mae_mph_15min": mae, "per_sensor_mae": fr["per_sensor_mae"], "decisions": r.get("decisions_after_budget"), "grouped": g,
                           "slow_edges": len(slow), "bands": bands, "counters": dict(C)})
        if gui:
            try:
                if not st.get("hud"):
                    traci.poi.add("hud", hud_xy[0], hud_xy[1], (0, 0, 0, 0)); st["hud"] = True
                traci.poi.setParameter("hud", "label", f"{tag} | " + line)
            except traci.TraCIException:
                pass
            if a.demo:
                try:
                    draw_plot(fr, k, t, edges)
                except Exception as exc:                        # noqa: BLE001 - the plot window is display only
                    print(f"    (plot window: {exc})", flush=True)

    def baseline_hook(ev: dict):
        if ev.get("type") == "simulation" and gui and not st.get("hud"):
            try:
                traci.poi.add("hud", hud_xy[0], hud_xy[1], (0, 0, 0, 0)); st["hud"] = True
                traci.poi.setParameter("hud", "label", f"{tag}: same traffic, same fork, no server")
            except traci.TraCIException:
                pass

    t0 = time.time()
    try:
        r = cl.run_sumo(arm, a.seed, routes, sdir / arm, P, cfg, fc, caps, fork, None, event_hook=event_hook if arm != "baseline" else baseline_hook, control_hook=control_hook, trace_hook=trace_hook)
    finally:
        runner.pr.base_cmd = base_cmd
    n = r["network"]; m = r["metrics"]
    loop = {"uplink_tx": n["uplink"]["messages_tx"], "uplink_delivered": n["uplink"]["messages_rx"], "downlink_tx": n["downlink"]["messages_tx"], "downlink_delivered": n["downlink"]["messages_rx"],
            "reroutes_applied": r["reroutes_applied"]}
    same = all(C[k] == loop[k] for k in loop)
    print(f"RESULT [{tag}] ({a.minutes} min after the fork, seed {a.seed}, profile {a.profile}): vehicle-hours {m['total_vehicle_hours_incl_never_inserted']:.1f}, arrived {m['arrived']}, teleports {m['teleports']};"
          f" uplink {loop['uplink_delivered']}/{loop['uplink_tx']} delivered, downlink {loop['downlink_delivered']}/{loop['downlink_tx']} delivered, reroutes applied {loop['reroutes_applied']}, rounds {C['rounds']}; wall {time.time() - t0:.0f} s",
          flush=True)
    print(f"  CHECK: the screen counters equal the loop's own message log and reroute count -> {'SAME' if same else 'DIFFERENT'}", flush=True)
    rec = {"args": {k: (str(v) if isinstance(v, Path) else v) for k, v in vars(a).items()}, "arm": arm, "profile_params": reg.get(a.profile), "duration_s": duration, "penetration": P["penetration"],
           "counters": C, "loop": loop, "same": same, "rounds": rounds_out, "lines": lines, "metrics": {k: m[k] for k in ("total_vehicle_hours_incl_never_inserted", "arrived", "teleports")},
           "run_dir": str(sdir.relative_to(REPO)), "wall_s": round(time.time() - t0)}
    (root / f"gui_routing_run_{arm}.json").write_text(json.dumps(rec, indent=1, default=str))
    if arm == ARM:
        (root / "gui_routing_run.json").write_text(json.dumps(rec, indent=1, default=str))
    if plot["fig"] is not None:
        try:
            import matplotlib.pyplot as plt
            plt.close(plot["fig"])
        except Exception:                                      # noqa: BLE001
            pass
    return 0 if same else 2


if __name__ == "__main__":
    sys.exit(main())
