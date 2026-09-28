"""Aggregate congestion measurements from a completed SUMO execution."""
import statistics
import sumolib
from pathlib import Path

def congestion_metrics(out: Path, net_path: Path, t0: float, H: float) -> dict:
    """How congested the twin actually was: per edge and 300 s interval, utilisation = entered vehicles /
    (lanes × 1800 veh/h/lane × interval); distribution over major roads at the busiest interval, mean
    occupancy, standing queue (summary `halting`), mean speed, spillback proxy (share of major edges with
    occupancy ≥ 80 % in any interval). Read from SUMO's own edgeData and summary outputs."""
    import xml.etree.ElementTree as ET
    from pipeline.city.sensor_map import MAJOR
    net = sumolib.net.readNet(str(net_path))
    lanes = {e.getID(): e.getLaneNumber() for e in net.getEdges()}
    major = {e.getID() for e in net.getEdges() if (e.getType() or "") in MAJOR}
    util_by_iv, occ, spill = {}, [], set()
    for iv in ET.parse(out / "edgedata.xml").getroot().iter("interval"):
        b, e = float(iv.get("begin")), float(iv.get("end")); dur = max(e - b, 1.0)
        if e <= t0:
            continue
        us = []
        for ed in iv.iter("edge"):
            eid = ed.get("id")
            if eid not in major:
                continue
            ent = float(ed.get("entered") or 0); u = ent / (lanes.get(eid, 1) * 1800.0 * dur / 3600.0)
            us.append(u); o = float(ed.get("occupancy") or 0); occ.append(o)
            if o >= 80.0:
                spill.add(eid)
        if us:
            util_by_iv[b] = sorted(us)
    busiest = max(util_by_iv.items(), key=lambda kv: statistics.fmean(kv[1]))[1] if util_by_iv else []
    q = lambda xs, p: (xs[min(len(xs) - 1, int(p * len(xs)))] if xs else None)
    halting, speeds, running, steps = [], [], [], []
    for st in ET.parse(out / "summary.xml").getroot().iter("step"):
        if float(st.get("time")) >= t0:
            halting.append(int(st.get("halting"))); running.append(int(st.get("running"))); steps.append((float(st.get("time")), int(st.get("running")), int(st.get("halting")), float(st.get("meanSpeed") or -1)))
            ms = st.get("meanSpeed")
            if ms not in (None, "-1.00", "-1"):
                speeds.append(float(ms))
    # the loaded network: steps where at least a quarter of the peak number of vehicles is running (the first
    # and last minutes, with a handful of vehicles, say nothing about congestion)
    peak_run = max(running) if running else 0
    loaded = [x for x in steps if x[1] >= 0.25 * peak_run and x[3] >= 0]
    loaded_speed = [x[3] for x in loaded]; loaded_halt = [x[2] / max(x[1], 1) for x in loaded]
    reasons = {}
    st_file = out / "statistic.xml"
    if st_file.exists():
        tp = ET.parse(st_file).getroot().find(".//teleports")
        if tp is not None:
            reasons = {k: int(v) for k, v in tp.attrib.items()}
    return {"major_edges": len(major), "teleport_reasons": reasons, "busiest_interval_utilisation": {"p50": round(q(busiest, .5), 3) if busiest else None, "p90": round(q(busiest, .9), 3) if busiest else None, "max": round(busiest[-1], 3) if busiest else None,
                                                                      "share_ge_0.5": round(sum(1 for u in busiest if u >= 0.5) / len(busiest), 3) if busiest else None, "share_ge_0.7": round(sum(1 for u in busiest if u >= 0.7) / len(busiest), 3) if busiest else None,
                                                                      "share_ge_0.9": round(sum(1 for u in busiest if u >= 0.9) / len(busiest), 3) if busiest else None},
            "mean_occupancy_pct_major": round(statistics.fmean(occ), 2) if occ else None, "spillback_major_edges_occ_ge_80": len(spill), "spillback_share": round(len(spill) / len(major), 4) if major else None,
            "max_running_vehicles": max(running) if running else None, "max_halting_vehicles": max(halting) if halting else None, "mean_halting_vehicles": round(statistics.fmean(halting), 1) if halting else None,
            "mean_speed_mps": round(statistics.fmean(speeds), 2) if speeds else None, "min_mean_speed_mps": round(min(speeds), 2) if speeds else None,
            "loaded_mean_speed_mps": round(statistics.fmean(loaded_speed), 2) if loaded_speed else None, "loaded_min_speed_mps": round(min(loaded_speed), 2) if loaded_speed else None,
            "loaded_mean_halting_share": round(statistics.fmean(loaded_halt), 3) if loaded_halt else None, "loaded_max_halting_share": round(max(loaded_halt), 3) if loaded_halt else None, "loaded_steps": len(loaded)}

