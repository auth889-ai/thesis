"""RQ2b: why the alert to every vehicle makes the ambulance slower at the Dhaka-density level. Re-runs chosen seeds (siren only and
alert, ITS-G5, 100 %) with a per-second log of every second the ambulance stands (speed < 0.5 m/s): where it is, the vehicle
directly ahead (from SUMO's own getLeader), whether that vehicle was alerted, whether it is inside a junction, whether it waits at
the end of a lane with no link to the next road on its route (it needs a lane change it is not making), and every teleport.
The runs go to results/emergency/dhaka/rq2/inspect/ (never the result folders); the log to evidence/ambulance_rq2/inspect/dhaka/.

    cd backend && DHAKAFLOW_NO_OBSERVATORY=1 python ../research/ambulance_rq2/scripts/inspect_dhaka_slow.py --seeds 12 15 19 21
    ... --variant near50 | nojunction | strategic --arms alert      # the same log for a make-way variant (alert_overrides in service.run_one)
    ~/.dhakaflow/venvs/sumo-rl-np1/bin/python ... --seeds 14 18 19 21 23 --arms no_alert rl_signals --tag rq2c   # Q-learning signals (NumPy-1 venv)
"""
import argparse
import json
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))
OUT = ROOT / "evidence/ambulance_rq2/inspect/dhaka"
RUNS = ROOT / "results/emergency/dhaka/rq2/inspect"
SCALE = json.loads((ROOT / "evidence/ambulance_rq2/dhaka_density/match.json").read_text())["chosen_scale"]
V1 = {"makeway": {"version": 1}}                 # RQ2b's logs were made with make-way v1; since RQ2c the default is v2 (configs/ambulance.yaml)
DEEP = "--deep" in sys.argv
ROUTE_EDGES: set = set()
VARIANTS = {None: V1, "near50": {**V1, "makeway_m": 50.0}, "nojunction": {**V1, "no_makeway_in_junctions": True},
            "strategic": {**V1, "keep_strategic": True},
            "v2d50": {"keep_strategic": True, "makeway_m": 50.0}, "v2d100": {"keep_strategic": True, "makeway_m": 100.0}}   # RQ2c: the two candidate rules       # diagnostic: alerted vehicles keep their own route lane changes (lcStrategic not set to -1)


def needs_change(conn, vid: str) -> bool:
    """At the end of its lane with no link from this lane to the next road on its route."""
    v = conn.vehicle
    lane, road = v.getLaneID(vid), v.getRoadID(vid)
    if road.startswith(":"):
        return False
    route, i = v.getRoute(vid), v.getRouteIndex(vid)
    if i + 1 >= len(route) or conn.lane.getLength(lane) - v.getLanePosition(vid) > 10:
        return False
    return not any(l[0].rsplit("_", 1)[0] == route[i + 1] for l in conn.lane.getLinks(lane))


def one(args) -> dict:
    arm, seed, variant = args
    from core.simulation.ambulance import service
    rows, tele = [], []

    def hook(conn, t, run):
        v = conn.vehicle
        if not ROUTE_EDGES:
            ROUTE_EDGES.update(run.scen["edges"])
        for vid in conn.simulation.getStartingTeleportIDList():
            tele.append({"t": t, "vehicle": vid, "alerted": vid in run.alerted, "making_way": vid in run.makeway.before})
        if run.state != "driving" or service.AMBULANCE not in v.getIDList() or v.getSpeed(service.AMBULANCE) >= 0.5:
            return
        a = service.AMBULANCE
        lead = v.getLeader(a, 100.0)
        row = {"t": t, "road": v.getRoadID(a), "lane": v.getLaneIndex(a), "pos": round(v.getLanePosition(a), 1), "lat": round(v.getLateralLanePosition(a), 2),
               "in_junction": v.getRoadID(a).startswith(":"), "leader": None}
        nx = v.getNextTLS(a)                                              # the next traffic light on the ambulance's route: id, metres to it, its state for the ambulance's link
        row["next_tls"] = {"id": nx[0][0], "dist": round(nx[0][2], 1), "state": nx[0][3]} if nx else None
        if lead and lead[0]:
            l, gap = lead
            row["leader"] = {"id": l, "gap": round(gap, 1), "speed": round(v.getSpeed(l), 2), "road": v.getRoadID(l), "in_junction": v.getRoadID(l).startswith(":"),
                             "alerted": l in run.alerted, "making_way": l in run.makeway.before, "needs_lane_change": needs_change(conn, l),
                             "lat": round(v.getLateralLanePosition(l), 2), "type": v.getTypeID(l), "waiting_s": round(v.getWaitingTime(l), 1)}
        chain, cur = [], lead[0] if lead and lead[0] else None          # what holds the leader: the next vehicles ahead of it, three deep
        while cur and len(chain) < 3:
            nxt = v.getLeader(cur, 50.0)
            if not nxt or not nxt[0]:
                break
            cur = nxt[0]
            chain.append({"id": cur, "gap": round(nxt[1], 1), "speed": round(v.getSpeed(cur), 2), "making_way": cur in run.makeway.before,
                          "needs_lane_change": needs_change(conn, cur), "in_junction": v.getRoadID(cur).startswith(":"), "waiting_s": round(v.getWaitingTime(cur), 1)})
        row["ahead_of_leader"] = chain
        if DEEP and lead and lead[0]:                                     # --deep: follow the queue to its head (up to 80 vehicles): who holds it, and is that a light?
            cur, n = lead[0], 0
            while n < 80:
                nxt = v.getLeader(cur, 30.0)
                if not nxt or not nxt[0] or v.getSpeed(nxt[0]) > 2.0:
                    break
                cur, n = nxt[0], n + 1
            tl = v.getNextTLS(cur)
            row["queue_head"] = {"id": cur, "behind_it": n, "road": v.getRoadID(cur), "speed": round(v.getSpeed(cur), 2), "needs_lane_change": needs_change(conn, cur),
                                 "next_tls": {"id": tl[0][0], "dist": round(tl[0][2], 1), "state": tl[0][3]} if tl else None,
                                 "on_route": v.getRoadID(cur) in ROUTE_EDGES}
        side = []                                                         # the vehicles beside / ahead in the next lanes, i.e. where the rescue lane should open
        for mode in (2, 3):                                               # SUMO getNeighbors: bit 0 right, bit 1 leaders -> 2 left leaders, 3 right leaders
            for nid, gap in v.getNeighbors(a, mode):
                side.append({"id": nid, "side": "left" if mode == 2 else "right", "gap": round(gap, 1), "speed": round(v.getSpeed(nid), 2),
                             "making_way": nid in run.makeway.before, "lat": round(v.getLateralLanePosition(nid), 2)})
        row["beside"] = side
        rows.append(row)

    if arm == "rl_signals":                                           # Q-learning signals, no alert: run in the NumPy-1 venv (rq2.NP1), frozen Q-tables
        from core.simulation.ambulance import rl_signals
        m = rl_signals.run(SCALE, seed, "rl_signals", 0.0, root=RUNS, demand="dhaka_density", inspect=hook)
        return {"arm": arm, "seed": seed, "variant": None, "state": m.get("state"), "travel_time_s": m["ambulance"].get("travel_time_s"),
                "stood_s": len(rows), "summary": summarise(rows, tele), "teleports_near": tele, "stood": rows}
    m = service.run_one("dhaka", arm, None if arm == "no_alert" else "its_g5", 0.0 if arm == "no_alert" else 1.0, seed, "dhaka_density", root=RUNS, scale=SCALE,
                        observe=True, alert_overrides=VARIANTS.get(variant), tag=variant or "", hook=hook)
    return {"arm": arm, "seed": seed, "variant": variant, "state": m.get("state"), "travel_time_s": m["ambulance"].get("travel_time_s"),
            "stood_s": len(rows), "summary": summarise(rows, tele), "teleports_near": tele, "stood": rows}


def summarise(rows: list[dict], tele: list[dict]) -> dict:
    """Seconds stood, by what was directly ahead. Pure."""
    c = Counter()
    for r in rows:
        L = r["leader"]
        if r["in_junction"]:
            c["ambulance inside a junction"] += 1
        if L is None:
            c["nothing within 100 m ahead"] += 1
            continue
        c["leader alerted (moving aside)" if L["making_way"] else "leader not alerted"] += 1
        if L["needs_lane_change"]:
            c["leader waits at a lane end it cannot leave" + (" (alerted)" if L["making_way"] else " (not alerted)")] += 1
        if L["in_junction"]:
            c["leader inside a junction" + (" (alerted)" if L["making_way"] else "")] += 1
        if L["speed"] < 0.1:
            c["leader stopped"] += 1
    leaders = Counter(r["leader"]["id"] for r in rows if r["leader"])
    return {"seconds": dict(c), "top_leaders": leaders.most_common(5), "teleports_total": len(tele),
            "teleports_of_alerted": sum(x["alerted"] for x in tele), "teleported_while_making_way": sum(x["making_way"] for x in tele),
            "top_leaders_teleported": [lid for lid, _ in leaders.most_common(5) if any(x["vehicle"] == lid for x in tele)]}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+", required=True)
    ap.add_argument("--variant", choices=sorted(k for k in VARIANTS if k))
    ap.add_argument("--arms", nargs="+", default=["no_alert", "alert"])
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--deep", action="store_true", help="also follow the queue ahead to its head")
    ap.add_argument("--tag", default="", help="suffix for the log names, so earlier logs of the same seeds are kept")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    jobs = [(arm, s, a.variant if arm != "no_alert" else None) for s in a.seeds for arm in a.arms]
    with ProcessPoolExecutor(a.jobs) as ex:
        for r in ex.map(one, jobs):
            name = f"{r['arm']}_s{r['seed']}" + (f"_{r['variant']}" if r["variant"] else "") + (f"_{a.tag}" if a.tag else "")
            (OUT / f"{name}.json").write_text(json.dumps(r, indent=1))
            print(name, r["state"], r["travel_time_s"], "stood", r["stood_s"], json.dumps(r["summary"])[:600], flush=True)
