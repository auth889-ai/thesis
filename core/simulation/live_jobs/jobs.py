"""The four live jobs. Each calls the same code as its terminal run (scripts/live/run_*.py) and adds only the frames for the map.
A frame is plain JSON: positions as [lon, lat], counts as numbers. The pace (SPEED simulated seconds per real second) applies only while
the action is on screen; the rest runs at full speed."""
from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path

from core.common.paths import REPO
from core.simulation.live_jobs.runner import Job, Stop, live_script, net

SPEED = 8.0
NEAR_M = 600.0
OUT = REPO / "evidence/live_web/runs"
TECHS = ("its_g5", "c_v2x", "cellular_4g")
LEVELS = ("dhaka", "x0.5", "x1", "x2", "x3", "x4")
PROTOCOLS = ("epidemic", "spray_and_wait", "prophet")


def _num(p: dict, key: str, default, lo, hi, kind=float):
    v = kind(p.get(key, default))
    if not lo <= v <= hi:
        raise ValueError(f"{key} must be between {lo} and {hi}")
    return v


def validate(kind: str, p: dict) -> dict:
    """The parameters each job takes, checked; anything else is ignored. Pure."""
    if kind in ("v2x", "sos"):
        tech = p.get("tech", "its_g5")
        if tech not in TECHS:
            raise ValueError(f"tech must be one of {TECHS}")
        out = {"tech": tech, "share": _num(p, "share", 1.0 if kind == "v2x" else 0.5, 0.0, 1.0), "seed": _num(p, "seed", 11, 1, 10_000, int)}
        level = p.get("level", "dhaka")
        if level not in (LEVELS if kind == "v2x" else LEVELS[:5]):
            raise ValueError(f"level must be one of {LEVELS}")
        if kind == "v2x":                                      # live demo input (2026-10-12): demand level and a chosen or random route; defaults = the thesis run
            demand = p.get("demand", "current")
            if demand not in ("current", "dhatrax-peak"):
                raise ValueError("demand must be current or dhatrax-peak")
            if demand == "dhatrax-peak" and level != "dhaka":
                raise ValueError("demand dhatrax-peak needs level dhaka")
            edges = [p.get(k) for k in ("from", "to")]
            if any(edges) and not all(edges):
                raise ValueError("give both from and to (edge ids or random)")
            for e in edges:
                if e is not None and not (isinstance(e, str) and 0 < len(e) <= 64 and (e == "random" or all(c.isalnum() or c in "#_-.:" for c in e))):
                    raise ValueError("from/to must be an edge id or random")
            if demand != "current" or edges[0]:               # only when given: the default parameter set stays exactly the thesis run's
                out |= {"demand": demand, "from": edges[0], "to": edges[1]}
        return out | {"level": level}
    if kind == "mesh":
        proto = p.get("protocol", "prophet")
        if proto not in PROTOCOLS:
            raise ValueError(f"protocol must be one of {PROTOCOLS}")
        return {"protocol": proto, "phones": _num(p, "phones", 17, 2, 17, int), "range": _num(p, "range", 10.0, 1.0, 200.0), "seed": _num(p, "seed", 1, 1, 10_000, int)}
    if kind == "signals":
        level = p.get("level", "dhaka")
        if level not in LEVELS:
            raise ValueError(f"level must be one of {LEVELS}")
        return {"level": level, "seed": _num(p, "seed", 11, 1, 10_000, int)}
    raise ValueError(f"unknown simulation {kind!r}")


def lonlat(n, x: float, y: float) -> list[float]:
    lon, lat = n.convertXY2LonLat(x, y)
    return [round(lon, 6), round(lat, 6)]


# ---------------------------------------------------------------------------------------------------------------------------- v2x
class _Arrived(Exception):
    pass


def v2x(job: Job) -> dict:
    """RQ3: scripts/live/run_v2x.py's two runs (service.run_one, make-way rule v2), the alert run drawn on the map."""
    from core.networking.v2x import model
    from core.simulation.ambulance import service
    rv = live_script("run_v2x")
    p = job.params
    demand, scale = rv.LEVELS[p["level"]]
    if p.get("demand") == "dhatrax-peak":
        scale = 1.0                                            # the corridor at the full recorded DhaTraX counts
    route = None
    if p.get("from"):
        rnd = service.random_route("dhaka", demand, p["seed"]) if "random" in (p["from"], p["to"]) else None
        route = (rnd[0] if p["from"] == "random" else p["from"], rnd[1] if p["to"] == "random" else p["to"])
    cfg = service.settings()
    if cfg["alert"].get("makeway", {}).get("version") != 2:
        raise RuntimeError("configs/ambulance.yaml is not make-way rule v2")
    root = OUT / job.id
    scen = service.scenario("dhaka", demand, route)
    job.say(f"seed {p['seed']}; route {scen['edges'][0]} -> {scen['edges'][-1]} ({scen['length_m']:.0f} m, {len(scen['signals'])} signals); demand {p.get('demand', 'current')} at scale {scale:g}")
    job.say("computing the run without alert (same traffic, same seed)")
    m0 = service.run_one("dhaka", "no_alert", None, 0.0, p["seed"], demand, root=root, scale=scale, route=route)
    t0 = m0["ambulance"]["travel_time_s"]
    job.emit({"t": None, "phase": "no_alert_done", "no_alert_s": t0})
    n = net(str(scen["net"]))
    range_m = model.parameters(p["tech"]).get("range_m")
    job.say(f"the ambulance drives with the alert over {p['tech']}")
    seen: dict = {}

    def hook(conn, t, run):
        job.check_stop()
        seen["run"] = run
        if service.AMBULANCE not in conn.vehicle.getIDList():
            if run.state == "arrived":
                raise _Arrived
            return
        x, y = conn.vehicle.getPosition(service.AMBULANCE)
        cars = []
        for v in conn.vehicle.getIDList():
            if v == service.AMBULANCE:
                continue
            vx, vy = conn.vehicle.getPosition(v)
            if math.hypot(vx - x, vy - y) <= NEAR_M:
                cars.append(lonlat(n, vx, vy) + [1 if v in run.makeway.before else 2 if v in run.alerted else 0])
        m = run.msgs
        job.emit({"t": int(t), "ambulance": lonlat(n, x, y), "range_m": range_m, "cars": cars,
                  "counts": {"sent": m["sent"], "delivered": m["delivered"], "lost": m["lost"], "out_of_range": m["out_of_range"],
                             "alerted": len(run.alerted), "making_way": len(run.makeway.before),
                             "green_now": len(run.preemption.preempted()) if run.preemption else 0}})
        time.sleep(1.0 / SPEED)
        if run.state == "arrived":
            raise _Arrived

    out = root / "dhaka" / demand / rv.run_dir("alert_preemption", p["tech"], p["share"], p["seed"], scale, rv.route_tag(route))
    try:
        service.run_one("dhaka", "alert_preemption", p["tech"], p["share"], p["seed"], demand, root=root, scale=scale, hook=hook, route=route)
    except _Arrived:
        pass
    run = seen.get("run")
    s = run.summary() if run else {}
    t1 = rv.ambulance_time(out)
    msgs, alerted = s.get("messages", {}), s.get("vehicles_alerted")
    s0, s1 = (rv.saved("no_alert", None, 0.0, p["seed"], demand, scale), rv.saved("alert_preemption", p["tech"], p["share"], p["seed"], demand, scale)) if not route else (None, None)
    check = None
    if s0 and s1:
        want = (s0["ambulance"]["travel_time_s"], s1["ambulance"]["travel_time_s"], s1["messages"], s1["vehicles_alerted"])
        check = {"saved": {"no_alert_s": want[0], "alert_s": want[1], "messages": want[2], "alerted": want[3]}, "reproduced": want == (t0, t1, msgs, alerted)}
    return {"label": "SIMULATION", "city": "dhaka", "params": job.params, "scale": scale, "route": [scen["edges"][0], scen["edges"][-1]], "route_m": scen["length_m"],
            "signals_on_route": len(scen["signals"]), "no_alert_s": t0, "alert_s": t1,
            "saved_pct": round(100 * (t0 - t1) / t0, 1) if t0 and t1 else None, "messages": msgs, "alerted": alerted,
            "junctions_green": len(s.get("junctions_preempted", [])), "check": check,
            "check_text": ("REPRODUCED" if check["reproduced"] else "DIFFERENT") if check else "new: the thesis has no saved run with these settings"}


# ---------------------------------------------------------------------------------------------------------------------------- sos
def sos(job: Job) -> dict:
    """Crash SOS car to car: scripts/live/run_sos_v2v.py (the SOS rule re-check, the warned run drawn, then the same seed without)."""
    rs = live_script("run_sos_v2v")
    from types import SimpleNamespace
    from core.simulation.ambulance import service
    p = job.params
    ok, lines = rs.rule_check()
    a = SimpleNamespace(tech=p["tech"], share=p["share"], seed=p["seed"], level=p["level"], crash_at=600.0, after=300.0, speed=SPEED, no_gui=True)
    demand, _ = rs.LEVELS[p["level"]]
    n = net(str(service.scenario("dhaka", demand)["net"]))
    job.say("warming the traffic up to the crash (600 s)")

    def on_step(c, t, crashed, warned, rerouted, msgs):
        job.check_stop()
        if crashed is None:
            return
        cx, cy = c.vehicle.getPosition(crashed) if crashed in c.vehicle.getIDList() else (None, None)
        if cx is None:
            return
        cars = []
        for v in c.vehicle.getIDList():
            if v == crashed:
                continue
            vx, vy = c.vehicle.getPosition(v)
            if math.hypot(vx - cx, vy - cy) <= 2 * NEAR_M:
                cars.append(lonlat(n, vx, vy) + [2 if v in rerouted else 1 if v in warned else 0])
        job.emit({"t": int(t - a.crash_at), "crashed": lonlat(n, cx, cy), "cars": cars,
                  "counts": {"warned": max(len(warned) - 1, 0), "rerouted": len(rerouted), "broadcasts": msgs["broadcasts"], "received": msgs["delivered"], "lost": msgs["lost"]}})
        time.sleep(1.0 / SPEED)

    job.say("a car crashes; its warning spreads car to car")
    w = rs.simulate(a, warn=True, gui=False, on_step=on_step)
    job.say("the same seed without any warning (for comparison)")
    nw = rs.simulate(a, warn=False, gui=False)
    inr = w["messages"]["delivered"] + w["messages"]["lost"]
    return {"label": "SIMULATION", "params": job.params, "rule_reproduced": ok, "rule_lines": [l.strip() for l in lines], "with_warning": w, "without_warning": nw,
            "delivery_in_range": round(w["messages"]["delivered"] / inr, 3) if inr else None,
            "check_text": ("REPRODUCED (the SOS rule on the thesis traces)" if ok else "DIFFERENT (the SOS rule)") + "; car-to-car numbers are new: no thesis number"}


# ---------------------------------------------------------------------------------------------------------------------------- mesh
MESH_PY = REPO / "research/mesh_pons/.venv/bin/python"


def mesh(job: Job) -> dict:
    """RQ4: PONS through scripts/live/mesh_frames.py in the mesh venv (the same set-up as run_mesh.py), frames in lon/lat."""
    if not MESH_PY.exists():
        raise RuntimeError("the mesh simulator (PONS) is not installed on this server: it runs on the research machine")
    p = job.params
    mv = json.loads((REPO / "research/mesh_pons/evidence/movement.json").read_text())
    n = net(str(REPO / mv["network"]))
    cmd = [str(MESH_PY), "-W", "ignore", str(REPO / "scripts/live/mesh_frames.py"), "--protocol", p["protocol"], "--phones", str(p["phones"]),
           "--range", str(p["range"]), "--seed", str(p["seed"])]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=REPO)
    rows, summary = [], None
    job.say(f"{p['phones']} phones, {p['protocol']}, {p['range']:g} m: PONS computing")
    try:
        for line in proc.stdout:
            job.check_stop()
            d = json.loads(line)
            if "frame" in d:
                f = d["frame"]
                job.emit({"t": f["t"], "phones": [lonlat(n, x, y) for x, y in f["pos"]], "links": f["links"], "counts": f["counts"]})
                time.sleep(1.0 / (SPEED * 4))                  # 300 s of movement in about 10 s
            elif "row" in d:
                rows.append(d["row"]); job.say(f"seed {d['row']['seed']} done")
            elif "summary" in d:
                summary = d["summary"]
    except Stop:
        proc.kill()
        raise
    proc.wait()
    if summary is None:
        raise RuntimeError("PONS ended without a result: " + proc.stderr.read()[-300:])
    return {"label": "SIMULATION", "params": p, "rows": rows, **summary}


# ---------------------------------------------------------------------------------------------------------------------------- signals
def signals(job: Job) -> dict:
    """RQ3 signals: scripts/live/run_signals.py's two sides in parallel (fixed time; sumo-rl Q-learning in its venv), live halting counts."""
    rsig = live_script("run_signals")
    if not rsig.RL_PY.exists():
        raise RuntimeError("sumo-rl is not installed on this server: the signals comparison runs on the research machine")
    import sumo
    p = job.params
    work = OUT / job.id
    work.mkdir(parents=True, exist_ok=True)
    env = os.environ | {"PYTHONPATH": f"{REPO}:{REPO / 'backend'}", "SUMO_HOME": os.path.dirname(sumo.__file__), "DHAKAFLOW_NO_OBSERVATORY": "1"}
    procs, files = {}, {}
    for side, py in (("fixed", sys.executable), ("rl", str(rsig.RL_PY))):
        files[side] = work / f"frames_{side}.jsonl"
        procs[side] = subprocess.Popen([py, str(REPO / "scripts/live/run_signals.py"), "--level", p["level"], "--seed", str(p["seed"]), "--speed", str(SPEED),
                                        "--no-gui", "--side", side, "--frames", str(files[side])], env=env, cwd=REPO, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    job.say("two runs in parallel: fixed-time signals and Q-learning signals")
    pos = {s: 0 for s in files}
    last = {s: None for s in files}
    try:
        while any(pr.poll() is None for pr in procs.values()):
            job.check_stop()
            for s, f in files.items():
                if f.exists():
                    with f.open() as fh:
                        fh.seek(pos[s]); chunk = fh.read(); pos[s] = fh.tell()
                    for line in chunk.splitlines():
                        if line.strip():
                            last[s] = json.loads(line)
            if last["fixed"] or last["rl"]:
                job.emit({"t": max((last[s] or {}).get("t", 0) for s in last), "fixed": last["fixed"], "rl": last["rl"]})
            time.sleep(0.25)
    except Stop:
        for pr in procs.values():
            pr.kill()
        raise
    got = {}
    for s in ("fixed", "rl"):
        f = rsig.OUT / f"last_{s}.json"
        if procs[s].returncode or not f.exists():
            raise RuntimeError(f"the {s} run did not finish: " + procs[s].stderr.read()[-300:])
        got[s] = json.loads(f.read_text())
    demand, scale = rsig.LEVELS[p["level"]]
    checks = {}
    for s in ("fixed", "rl"):
        w = rsig.saved(s, p["seed"], demand, scale)
        checks[s] = None if w is None else all(w[k] == got[s][k] for k in rsig.KEYS)
    text = "new: the thesis has no saved run with these settings" if all(v is None for v in checks.values()) else (
        "REPRODUCED" if all(v for v in checks.values() if v is not None) else "DIFFERENT")
    return {"label": "SIMULATION", "params": p, "fixed": got["fixed"], "rl": got["rl"], "checks": checks, "check_text": text}
