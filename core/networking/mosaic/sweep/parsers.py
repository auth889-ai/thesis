"""Parsers for one MOSAIC run: the file-output ambassador's visualizer.csv (registrations, V2X
transmissions and receptions, trajectories), Navigation.log, Mapping.log, Traffic.log, MOSAIC.log,
and SUMO's tripinfo.xml and summary.xml."""
from __future__ import annotations

import math
import re
import statistics
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

from core.networking.mosaic.sweep.scenario import NS, WWA


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
    lat_sum_ns = lat_n = lat_max = 0
    lat_min = None
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
                        traj[parts[2]].append((t / NS, float(parts[3]), float(parts[4]), float(parts[5]), parts[6] if len(parts) > 6 else ""))
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


def _matches(path: Path, pattern: str):
    if not path.exists():
        return
    rx = re.compile(pattern)
    for line in path.read_text(errors="replace").splitlines():
        m = rx.search(line)
        if m:
            yield m


def parse_navigation(path: Path):
    """(vehicle, route) for every 'Change to route X for vehicle Y' line (CentralNavigationComponent)."""
    return [(m.group(2), m.group(1)) for m in _matches(path, r"Change to route (\S+) for vehicle (\S+)\.")]


def parse_id_map(traffic_log: Path) -> dict:
    """SUMO vehicle id -> MOSAIC unit name (Traffic.log: Assigned unit MOSAIC-ID: "veh_0" to external unit: "od000_0")."""
    return {m.group(2): m.group(1) for m in _matches(traffic_log, r'Assigned unit MOSAIC-ID: "([^"]+)" to external unit: "([^"]+)"')}


def equipped_from_mapping_log(path: Path) -> set:
    return {m.group(1) for m in _matches(path, r"Mapping Scenario Vehicle\. time=\d+, name=(\S+), type=\S+, apps=\[([^\]]*)\]") if WWA in m.group(2)}


def parse_mapping(path: Path):
    n_total = n_wwa = 0
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


def _trip_stats(rows):
    if not rows:
        return {"n": 0}
    dur = sorted(r[0] for r in rows); tl = sorted(r[1] for r in rows); wt = sorted(r[2] for r in rows); rl = [r[3] for r in rows]
    return {"n": len(rows),
            "duration_mean_s": statistics.fmean(dur), "duration_p50_s": pct(dur, .5), "duration_p95_s": pct(dur, .95),
            "timeLoss_mean_s": statistics.fmean(tl), "timeLoss_p95_s": pct(tl, .95),
            "waitingTime_mean_s": statistics.fmean(wt), "routeLength_mean_m": statistics.fmean(rl)}


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
        rec = (float(el.get("duration")), float(el.get("timeLoss", "nan")), float(el.get("waitingTime", "nan")), float(el.get("routeLength", "nan")))
        fin["all"].append(rec)
        fin["equipped" if idmap.get(el.get("id"), el.get("id")) in equipped else "unequipped"].append(rec)
        el.clear()
    out.update({"finished": _trip_stats(fin["all"]), "finished_equipped": _trip_stats(fin["equipped"]),
                "finished_unequipped": _trip_stats(fin["unequipped"]), "unfinished": unfinished})
    return out


def parse_summary(path: Path):
    if not path.exists():
        return {"available": False}
    last = None
    n_steps = 0
    mean_speed_sum = halting_sum = 0.0
    for _, el in ET.iterparse(path, events=("end",)):
        if el.tag == "step":
            last = dict(el.attrib)
            n_steps += 1
            mean_speed_sum += float(el.get("meanSpeed", "0") or 0)
            halting_sum += float(el.get("halting", "0") or 0)
            el.clear()
    if last is None:
        return {"available": False}
    return {"available": True, "final_step": last, "meanSpeed_avg_over_steps_m_s": mean_speed_sum / n_steps, "halting_avg_over_steps": halting_sum / n_steps}
