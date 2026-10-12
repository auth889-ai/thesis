"""Fit a city's generated demand to recorded counts with SUMO's own routeSampler, and report how well it matches.

    PYTHONPATH=backend python -m core.simulation.twin.calibration --city dhaka

What is fitted, and what is not. The city's config names a recorded dataset and a clock window. Each located site of
that dataset measures one road section in one direction; routeSampler (SUMO tools/routeSampler.py, used as released)
chooses routes from a pool of randomTrips routes so that the vehicles entering each of those sections in each
interval match the counts. routeSampler only places vehicles on routes that pass a counted section, so the demand
written here is: the sampled traffic through the counted sections, plus the city's ordinary generated traffic on
routes that touch none of them. THAT SECOND PART IS UNCALIBRATED, and so is every section that is not counted.

The report gives, per site and interval, the count observed, the count routeSampler placed, and the count an actual
SUMO run produced (several seeds), each with its GEH. A miss is written as a miss.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

from core.common.data import city_config, real_speeds
from core.common.paths import REPO
from core.simulation.twin import city_pipeline, scenario_builder as sb

EVIDENCE_DIR = city_pipeline.EVIDENCE_DIR
GEH_OK = 5.0                 # the usual acceptance threshold for hourly volumes; here applied to each interval scaled to an hour
CHECK_SEEDS = (11, 12, 13, 14, 15)


def geh(simulated: float, observed: float, interval_s: int) -> float:
    """GEH on hourly rates (the statistic is defined for vehicles per hour)."""
    m, c = simulated * 3600 / interval_s, observed * 3600 / interval_s
    return 0.0 if m + c == 0 else math.sqrt(2 * (m - c) ** 2 / (m + c))


def site_counts(cfg: city_config.CityConfig, net) -> list[dict]:
    """The located sites of the calibration dataset with the section each measures and its counts per interval."""
    cal, out = cfg.calibration, []
    reader = real_speeds._readers()[cal.dataset]
    h, m = (int(x) for x in cal.window_start.split(":"))
    for src in real_speeds.recorded_sources(cfg.city_id, net, cfg.bounding_box.tuple):
        if src["dataset"] != reader.NAME:
            continue
        for st in src["sites"]:
            if not st.get("section"):
                continue                                # a site with no stated place, or no road section near it, constrains nothing
            per = reader.counts().get(st["site"], {})
            counts = []
            for k in range(cal.duration_s // cal.interval_s):
                minute = h * 60 + m + k * cal.interval_s // 60
                counts.append(per.get(f"{minute // 60:02d}:{minute % 60:02d}"))      # None: that interval was not completely recorded
            out.append({"site": st["site"], "day": st["day"], "section": st["section"], "section_distance_m": st["section_distance_m"],
                        "bearing_deg": st["bearing_deg"], "counts": counts})
    return out


def write_counts(sites: list[dict], interval_s: int, path: Path) -> None:
    root = ET.Element("data")
    for k in range(len(sites[0]["counts"])):
        iv = ET.SubElement(root, "interval", id="recorded", begin=str(k * interval_s), end=str((k + 1) * interval_s))
        for s in sites:
            if s["counts"][k] is not None:
                ET.SubElement(iv, "edge", id=s["section"], entered=str(s["counts"][k]))
    ET.ElementTree(root).write(path)


def _vehicles(path: Path) -> tuple[list, list]:
    root = ET.parse(path).getroot()
    return root.findall("vType"), [v for v in root.findall("vehicle") if v.find("route") is not None]


def merge(sampled: Path, background: Path, counted: set[str], out: Path) -> dict:
    """Sampled vehicles, plus the background vehicles whose route touches no counted section, in order of departure."""
    _, cal = _vehicles(sampled)
    types, bg = _vehicles(background)
    kept = [v for v in bg if not counted & set(v.find("route").get("edges").split())]
    for v in cal:
        v.set("departLane", "best")
    root = ET.Element("routes")
    root.extend(types)
    root.extend(sorted(cal + kept, key=lambda v: float(v.get("depart"))))
    tree = ET.ElementTree(root)
    ET.indent(tree)
    tree.write(out, encoding="UTF-8", xml_declaration=True)
    return {"sampled_through_counted_sections": len(cal), "background_uncalibrated": len(kept), "background_dropped_for_touching_a_counted_section": len(bg) - len(kept)}


def entered(edgedata: Path, sections: list[str], intervals: int, interval_s: int) -> dict:
    got = {s: [0] * intervals for s in sections}
    for iv in ET.parse(edgedata).getroot().iter("interval"):
        k = int(float(iv.get("begin")) // interval_s)
        for e in iv.iter("edge"):
            if e.get("id") in got and k < intervals:
                got[e.get("id")][k] = int(float(e.get("entered", 0)))
    return got


def simulate(net: Path, routes: Path, sections: list[str], cal, seed: int, work: Path, sumo_extra: list[str]) -> dict:
    add, ed = work / f"add_{seed}.xml", work / f"edgedata_{seed}.xml"
    add.write_text(f'<additional><edgeData id="cal" file="{ed}" freq="{cal.interval_s}"/></additional>')
    stat = work / f"stat_{seed}.xml"
    subprocess.run(["sumo", "--net-file", str(net), "--route-files", str(routes), "--additional-files", str(add), "--seed", str(seed), "--end", str(cal.duration_s),
                    "--statistic-output", str(stat), "--no-step-log", "--no-warnings", "--ignore-route-errors", "--time-to-teleport", "300"] + sumo_extra,
                   check=True, capture_output=True, text=True)
    st = ET.parse(stat).getroot()
    return {"entered": entered(ed, sections, cal.duration_s // cal.interval_s, cal.interval_s), "teleports": int(st.find("teleports").get("total")),
            "inserted": int(st.find("vehicles").get("inserted")), "waiting_to_insert_at_end": int(st.find("vehicles").get("waiting"))}


def report(sites: list[dict], placed: dict, runs: dict, cal) -> dict:
    """Per site: observed, placed by the sampler, and simulated (mean and spread over seeds), with GEH per interval."""
    out, all_geh_sampler, all_geh_sim = [], [], []
    for s in sites:
        rows = []
        for k, obs in enumerate(s["counts"]):
            if obs is None:
                continue
            sims = [r["entered"][s["section"]][k] for r in runs.values()]
            g1, g2 = geh(placed[s["section"]][k], obs, cal.interval_s), geh(statistics.fmean(sims), obs, cal.interval_s)
            all_geh_sampler.append(g1)
            all_geh_sim.append(g2)
            rows.append({"interval": k, "observed": obs, "sampler": placed[s["section"]][k], "geh_sampler": round(g1, 2),
                         "simulated_mean": round(statistics.fmean(sims), 1), "simulated_sd": round(statistics.stdev(sims), 1) if len(sims) > 1 else None, "geh_simulated": round(g2, 2)})
        obs_total, sim_totals = sum(r["observed"] for r in rows), [sum(run["entered"][s["section"]][r["interval"]] for r in rows) for run in runs.values()]
        out.append({**{k: s[k] for k in ("site", "day", "section", "section_distance_m", "bearing_deg")}, "intervals_counted": len(rows),
                    "observed_total": obs_total, "sampler_total": sum(r["sampler"] for r in rows),
                    "simulated_total_mean": round(statistics.fmean(sim_totals), 1), "simulated_total_sd": round(statistics.stdev(sim_totals), 1) if len(sim_totals) > 1 else None,
                    "simulated_over_observed_pct": round(100 * statistics.fmean(sim_totals) / obs_total, 1) if obs_total else None,
                    "intervals_within_geh_5_simulated": sum(r["geh_simulated"] <= GEH_OK for r in rows), "intervals": rows})
    share = lambda g: round(100 * sum(x <= GEH_OK for x in g) / len(g), 1) if g else None
    return {"sites": out, "overall": {"site_intervals": len(all_geh_sim), "within_geh_5_sampler_pct": share(all_geh_sampler), "within_geh_5_simulated_pct": share(all_geh_sim),
                                      "geh_definition": "GEH on hourly rates, each interval's count scaled to an hour; 5 is the usual acceptance threshold"}}


def run(city_id: str, sumo_extra: list[str] | None = None, evidence_dir: Path = EVIDENCE_DIR) -> dict:
    import sumolib
    cfg = city_config.load(city_id)
    cal = cfg.calibration
    if cal is None:
        raise SystemExit(f"{city_id}: no calibration block in its config, so there are no counts to fit; the demand stays uncalibrated")
    man_path = sb.scenario_dir(city_id) / "MANIFEST.json"
    man = json.loads(man_path.read_text())
    net_file = REPO / man["files"]["net"]
    net = sumolib.net.readNet(str(net_file))
    sites = site_counts(cfg, net)
    if not sites:
        raise SystemExit(f"{city_id}: no located site of {cal.dataset} lies on a road section of this network")
    out_dir, log = sb.scenario_dir(city_id), []
    routes = out_dir / f"{city_id}.calibrated.rou.xml"
    sections = [s["section"] for s in sites]
    tools = sb.sumo_tools_dir()
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        write_counts(sites, cal.interval_s, work / "counts.xml")
        pool_opts = sb.run_random_trips(net_file, work / "pool.trips.xml", work / "pool.rou.xml", cal.seed, cal.pool_period_s, cal.duration_s, cal.pool_fringe_factor)
        sb.run_random_trips(net_file, work / "bg.trips.xml", work / "bg.rou.xml", cfg.sumo.build.seed, cfg.sumo.build.period_s, cal.duration_s)
        sampler = [sys.executable, str(tools / "routeSampler.py"), "-r", str(work / "pool.rou.xml"), "--edgedata-files", str(work / "counts.xml"), "--edgedata-attribute", "entered",
                   "-o", str(work / "sampled.rou.xml"), "--mismatch-output", str(work / "mismatch.xml"), "--seed", str(cal.seed), "--prefix", "cal"]
        r = subprocess.run(sampler, capture_output=True, text=True)
        if r.returncode != 0:
            raise SystemExit("routeSampler.py failed: " + (r.stderr or r.stdout)[-800:])
        log += ["randomTrips.py (pool) " + " ".join(o for o in pool_opts if not o.startswith("/")), "routeSampler.py " + " ".join(Path(o).name if o.startswith("/") else o for o in sampler[2:]),
                (r.stdout + r.stderr).strip()]
        pool_routes = len(_vehicles(work / "pool.rou.xml")[1])
        merged = merge(work / "sampled.rou.xml", work / "bg.rou.xml", set(sections), routes)
        placed = {s: [0] * (cal.duration_s // cal.interval_s) for s in sections}
        for v in _vehicles(work / "sampled.rou.xml")[1]:           # what the sampler placed: a vehicle counts in the interval it departs in, as routeSampler counts it
            k = int(float(v.get("depart")) // cal.interval_s)
            for e in set(v.find("route").get("edges").split()) & set(sections):
                placed[e][min(k, len(placed[e]) - 1)] += 1
        mixed = city_pipeline.apply_mix(cfg, routes, net_file, cal.seed, log)
        runs = {seed: simulate(net_file, routes, sections, cal, seed, work, sumo_extra or []) for seed in CHECK_SEEDS}
    rep = report(sites, placed, runs, cal)
    reader = real_speeds._readers()[cal.dataset]
    where = ", ".join(f"{s['site']} on {s['day']}" for s in sites)
    calibrated_to = (f"{reader.NAME} counts at {len(sites)} road sections, one direction each ({where}), {cal.window_start} for {cal.duration_s // 60} min; "
                     f"{rep['overall']['within_geh_5_simulated_pct']} % of {rep['overall']['site_intervals']} site-intervals within GEH 5 in simulation; every other section uncalibrated")
    record = {"city_id": city_id, "generated_utc": datetime.now(timezone.utc).isoformat(), "sumo": city_pipeline._sumo_version(),
              "command": f"PYTHONPATH=backend python -m core.simulation.twin.calibration --city {city_id}" + (f" --sumo-extra \"{' '.join(sumo_extra)}\"" if sumo_extra else ""),
              "what_is_calibrated": f"only the {len(sites)} road sections the located {reader.NAME} sites measure, one direction each, on different days treated as one clock window. "
                                    "Traffic that touches none of them is the city's ordinary generated demand and is uncalibrated. Counts are " + reader.CAVEAT + ".",
              "dataset": {"name": reader.NAME, "version": reader.VERSION, "citation": reader.CITATION, "licence": reader.LICENCE},
              "config": cal.model_dump(), "candidate_routes": pool_routes, "demand": {"file": city_pipeline._rel(routes), "sha256": city_pipeline.sha256(routes), **merged, "vehicle_mix": mixed},
              "sumo_extra": sumo_extra or [], "check_seeds": list(CHECK_SEEDS),
              "simulation_runs": {str(s): {k: v for k, v in r.items() if k != "entered"} for s, r in runs.items()},
              "calibrated_to": calibrated_to, **rep}
    ev = Path(evidence_dir) / city_id
    ev.mkdir(parents=True, exist_ok=True)
    (ev / "calibration.json").write_text(json.dumps(record, indent=1) + "\n")
    (ev / "calibration.log").write_text("\n".join(log) + "\n")
    man["files"]["routes"], man["horizon_s"] = city_pipeline._rel(routes), cal.duration_s
    man["demand_reality"] = man["label"] = "SYNTHETIC_PARTLY_CALIBRATED"
    man["calibrated_to"] = calibrated_to
    man["warning"] = ("The network is real; the demand is generated. Only the road sections measured by recorded counts are fitted to them; "
                      "everything else is uncalibrated. This is a simulation, not a measurement of this city's traffic.")
    man_path.write_text(json.dumps(man, indent=1))
    return record


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--city", required=True)
    ap.add_argument("--sumo-extra", default="", help="SUMO options the check runs use, the same as the experiments that will use this demand")
    a = ap.parse_args()
    rec = run(a.city, a.sumo_extra.split())
    for s in rec["sites"]:
        print(f"{s['site']} ({s['day']}) section {s['section']}: observed {s['observed_total']}, sampler {s['sampler_total']}, simulated {s['simulated_total_mean']} "
              f"± {s['simulated_total_sd']} ({s['simulated_over_observed_pct']} %), {s['intervals_within_geh_5_simulated']} of {s['intervals_counted']} intervals within GEH 5")
    print(rec["overall"], rec["demand"]["sampled_through_counted_sections"], "sampled +", rec["demand"]["background_uncalibrated"], "background")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
