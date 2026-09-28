"""The record of one sweep point, with every definition written into it, and the small-log
housekeeping that lets the travel-time split be recomputed later."""
from __future__ import annotations

import json
import math
import shutil
import statistics
import sys
from pathlib import Path

from app.paths import REPO

from .parsers import (equipped_from_mapping_log, parse_id_map, parse_mapping, parse_mosaic_log, parse_navigation,
                      parse_summary, parse_tripinfo, parse_visualizer, pct)
from .scenario import NS, RESULTS, SCEN_ROOT, point_name, ptag

HAZARD = {"lat_min": 23.7500, "lat_max": 23.7555, "lon_min": 90.3915, "lon_max": 90.3975}

DEFINITIONS = {
    "equipped": "VEHICLE_REGISTRATION rows whose application list contains WeatherWarningApp",
    "delivery_ratio_veh": "distinct DENM receivers / equipped vehicles",
    "receptions_per_denm": "V2X_MESSAGE_RECEPTION rows / V2X_MESSAGE_TRANSMISSION rows",
    "latency": "reception time - transmission time of the same MessageId (SNS ad-hoc ITS-G5, multi-hop)",
    "route_switches": "CentralNavigationComponent 'Change to route' lines in Navigation.log",
    "travel_time": "SUMO tripinfo (finished trips only; unfinished counted separately)",
}
TTH_MODEL = ("analytic: straight-line distance from the vehicle's position at its FIRST DENM reception to the hazard "
             "rectangle boundary, divided by max(current speed, 0.3*mean trip speed, 1 m/s); vehicles = those that actually switched route")


def dist_to_hazard_m(lat, lon):
    """Straight-line distance (m) from a point to the hazard rectangle (0 if inside)."""
    dlat = max(HAZARD["lat_min"] - lat, 0, lat - HAZARD["lat_max"])
    dlon = max(HAZARD["lon_min"] - lon, 0, lon - HAZARD["lon_max"])
    return math.hypot(dlat * 111_320.0, dlon * 111_320.0 * math.cos(math.radians(lat)))


def time_to_hazard(vis, switches):
    """Per rerouting vehicle: state at the moment of its FIRST DENM reception ->
    distance to hazard zone / current speed = time budget the advisory had (analytic)."""
    rows = []
    for veh in {v for v, _ in switches}:
        first = vis["rx_first"].get(veh)
        tr = vis["traj"].get(veh)
        if not first or not tr:
            continue
        t_rx = first[0] / NS
        cand = [s for s in tr if s[0] <= t_rx] or tr[:1]      # nearest sample at or before t_rx (2 s grid), else first after
        t, lat, lon, spd, edge = cand[-1]
        d = dist_to_hazard_m(lat, lon)
        speeds = [s[3] for s in tr if s[3] > 0.5]
        v_mean = statistics.fmean(speeds) if speeds else 5.0
        v_eff = max(spd, 0.3 * v_mean, 1.0)
        rows.append({"veh": veh, "t_rx_s": round(t_rx, 3), "t_sample_s": t, "dist_m": round(d, 1),
                     "speed_m_s": round(spd, 2), "v_mean_m_s": round(v_mean, 2), "tth_s": round(d / v_eff, 1), "edge": edge})
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
    registered, equipped = len(vis["registered"]), len(vis["equipped"])
    receivers = set(vis["rx_first"])
    n_rx, n_tx = sum(vis["rx_count"].values()), len(vis["tx"])
    first_tx = min((t for t, _ in vis["tx"].values()), default=None)
    switched = {v for v, _ in switches}
    tth_sorted = sorted(r["tth_s"] for r in tth)
    res = {
        "point": {"p": p, "seed": seed, "duration_s": duration, "scenario": str(scenario.relative_to(REPO)), "log_dir": str(log_dir)},
        "wall_s": wall_log if wall_log is not None else wall_s,      # MOSAIC SequentialTimeManagement duration
        "wall_total_s": wall_s,                                       # whole mosaic.sh process incl. JVM/SUMO start-up
        "sim_ended_s": ended[0] if ended else None,
        "vehicles": {"registered": registered, "equipped": equipped, "unequipped": registered - equipped,
                     "equipped_fraction": (equipped / registered) if registered else None,
                     "mapping_log_total": map_total, "mapping_log_with_wwa": map_wwa},
        "v2x": {"denm_sent": n_tx, "message_types": dict(vis["denm_types"]), "senders": len(vis["senders"]),
                "first_denm_s": (first_tx / NS) if first_tx is not None else None,
                "receptions": n_rx, "receivers": len(receivers), "receivers_equipped": len(receivers & vis["equipped"]),
                "delivery_ratio_veh": (len(receivers) / equipped) if equipped else None,
                "receptions_per_denm": (n_rx / n_tx) if n_tx else None,
                "receptions_per_receiver": (n_rx / len(receivers)) if receivers else None,
                "latency": vis["latency"]},
        "routing": {"route_switches": len(switches), "vehicles_switched": len(switched),
                    "switch_fraction_of_receivers": (len(switched) / len(receivers)) if receivers else None,
                    "switch_fraction_of_equipped": (len(switched) / equipped) if equipped else None},
        "sumo": {"tripinfo": trip, "summary": summ},
        "time_to_hazard": {"model": TTH_MODEL, "n": len(tth),
                           "tth_zero_fraction": (sum(1 for r in tth if r["tth_s"] <= 0) / len(tth)) if tth else None,
                           "tth_s_p10": pct(tth_sorted, .10) if tth else None, "tth_s_p50": pct(tth_sorted, .50) if tth else None,
                           "tth_s_p90": pct(tth_sorted, .90) if tth else None, "rows": tth},
        "definitions": DEFINITIONS,
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
    from .report import aggregate
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
