"""RQ2b: the ambulance study at Dhaka's recorded density (docs/PAPER_MAP.md, RQ2). The density-gap check found the main cause of the
gap is supply: generated trips do not load the INT section and the network gridlocks elsewhere first. Here:
  1. a corridor network: the edges within BUFFER_M of the ambulance's route, cut with SUMO's netconvert (--keep-edges.input-file);
  2. demand from DhaTraX's recorded counts on the INT and BM sections at the recorded morning hour, with core.simulation.twin.calibration's own
     chain (site_counts, write_counts, randomTrips pool, SUMO's routeSampler, merge with a corridor background, apply_mix), and the
     density-gap check's tighter lateral gaps for two-wheelers, rickshaws and CNGs; SUMO's sublane model as in every RQ2 run;
  3. the density reached on the INT section, against the recorded value, whatever it is.

    python -m core.simulation.ambulance.corridor build      # corridor net + routes + evidence/ambulance_rq2/dhaka_density/calibration.json
    python -m core.simulation.ambulance.corridor density    # the INT density reached, seeds 11-20, no ambulance -> .../density.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import statistics
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from core.common.paths import REPO

BUFFER_M = 300.0
OUT_DIR = REPO / "data/cities/dhaka/sumo/corridor"
NET = OUT_DIR / "dhaka_corridor.net.xml.gz"
ROUTES = OUT_DIR / "dhaka_density.rou.xml"
EVIDENCE = REPO / "evidence/ambulance_rq2/dhaka_density"
INT, BM = "691209729#5", "235293033#10"
DENSITY_SEEDS = range(11, 21)
TIGHT = {"Motor_Cycle": {"minGapLat": "0.1", "latAlignment": "arbitrary", "minGap": "1.0"}, "Bicycle": {"minGapLat": "0.1", "latAlignment": "arbitrary"},
         "Rickshaw": {"minGapLat": "0.15", "latAlignment": "arbitrary"}, "CNG": {"minGapLat": "0.2", "latAlignment": "arbitrary", "minGap": "1.5"}}


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def keep_edges(net, route_edges: list[str], buffer_m: float = BUFFER_M) -> list[str]:
    """Edges with any shape point within `buffer_m` of the route's shape, plus the route's own edges. Tested."""
    pts = [p for e in route_edges for p in net.getEdge(e).getShape()]
    keep = {e.getID() for e in net.getEdges() if any(math.dist(a, b) <= buffer_m for a in e.getShape() for b in pts)}
    return sorted(keep | set(route_edges))


def tighten(text: str, tight: dict = TIGHT) -> str:
    """Add the tighter lateral settings to those vTypes only (the RQ2 density-gap check's values). Tested."""
    for vid, attrs in tight.items():
        extra = " ".join(f'{k}="{v}"' for k, v in attrs.items())
        text = re.sub(rf'<vType id="{vid}"([^>]*?)(/?)>', lambda m: f'<vType id="{vid}"{m.group(1)} {extra}{m.group(2)}>', text)
    return text


def match(scales=(0.4, 0.5, 0.6, 0.7, 0.72, 0.75, 0.78, 0.8), seeds=range(11, 16)) -> dict:
    """The recorded counts overload the INT section (density above DhaTraX's recorded range, throughput below it). The demand is
    scaled down until the section's median density sits inside the recorded 07:00-08:00 interquartile range, closest to the
    recorded median; that scale is the "Dhaka density" level. Every scale tried is kept."""
    tried = [density(seeds, scale=s) for s in scales]
    rec = tried[0]["recorded_07_08"]["INT"]
    inside = [t for t in tried if t["within_recorded_iqr"]]
    best = min(inside, key=lambda t: abs(t["INT_density_median_over_seeds"] - rec["density_median"])) if inside else None
    body = {"tried": [{k: t[k] for k in ("scale", "INT_density_median_over_seeds", "INT_entered_median", "within_recorded_iqr")} for t in tried],
            "recorded_INT": rec, "chosen_scale": best and best["scale"], "chosen_density": best and best["INT_density_median_over_seeds"],
            "rule": "median INT density over seeds inside the recorded 07:00-08:00 interquartile range, closest to the recorded median"}
    (EVIDENCE / "match.json").write_text(json.dumps(body, indent=1))
    return body


def build() -> dict:
    import sumolib
    from core.common.data import city_config
    from core.simulation.ambulance import service
    from core.simulation.twin import calibration as cal_mod
    from core.simulation.twin import city_pipeline
    from core.simulation.twin import scenario_builder as sb
    scen = service.scenario("dhaka", "generated")
    full = sumolib.net.readNet(str(scen["net"]), withPrograms=True)
    keep = keep_edges(full, scen["edges"])
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "keep_edges.txt").write_text("\n".join(keep) + "\n")
    r = subprocess.run(["netconvert", "--sumo-net-file", str(scen["net"]), "--keep-edges.input-file", str(OUT_DIR / "keep_edges.txt"),
                        "--output-file", str(NET), "--no-warnings"], capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit("netconvert failed: " + (r.stderr or r.stdout)[-600:])
    cnet = sumolib.net.readNet(str(NET), withPrograms=True)
    have = {e.getID() for e in cnet.getEdges()}
    missing = [e for e in scen["edges"] + [INT, BM] if e not in have]
    if missing:
        raise SystemExit(f"the corridor lost route or camera edges: {missing}")
    signals = []
    for s in scen["signals"]:
        a, b = full.getTLSSecure(s["tls"]), cnet.getTLSSecure(s["tls"])
        pa = [(p.duration, p.state) for prog in a.getPrograms().values() for p in prog.getPhases()]
        pb = [(p.duration, p.state) for prog in b.getPrograms().values() for p in prog.getPhases()]
        if not pa:
            raise SystemExit(f"no signal programme read for {s['tls']}: the comparison would mean nothing")
        signals.append({"tls": s["tls"], "same_programme": pa == pb, "phases_full": len(pa), "phases_corridor": len(pb)})
    cfg = city_config.load("dhaka")
    c = cfg.calibration
    sites = [s for s in cal_mod.site_counts(cfg, cnet) if s["section"] in (INT, BM)]
    log: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        cal_mod.write_counts(sites, c.interval_s, work / "counts.xml")
        sb.run_random_trips(NET, work / "pool.trips.xml", work / "pool.rou.xml", c.seed, c.pool_period_s, c.duration_s, c.pool_fringe_factor)
        sb.run_random_trips(NET, work / "bg.trips.xml", work / "bg.rou.xml", cfg.sumo.build.seed, cfg.sumo.build.period_s, c.duration_s)
        sampler = [sys.executable, str(sb.sumo_tools_dir() / "routeSampler.py"), "-r", str(work / "pool.rou.xml"), "--edgedata-files", str(work / "counts.xml"),
                   "--edgedata-attribute", "entered", "-o", str(work / "sampled.rou.xml"), "--mismatch-output", str(work / "mismatch.xml"), "--seed", str(c.seed), "--prefix", "cal"]
        rr = subprocess.run(sampler, capture_output=True, text=True)
        if rr.returncode != 0:
            raise SystemExit("routeSampler.py failed: " + (rr.stderr or rr.stdout)[-800:])
        log.append((rr.stdout + rr.stderr).strip()[-2000:])
        merged = cal_mod.merge(work / "sampled.rou.xml", work / "bg.rou.xml", {INT, BM}, ROUTES)
        mixed = city_pipeline.apply_mix(cfg, ROUTES, NET, c.seed, log)
    ROUTES.write_text(tighten(ROUTES.read_text()))
    rec = {"generated_utc": datetime.now(timezone.utc).isoformat(), "buffer_m": BUFFER_M, "edges_kept": len(keep), "edges_full": len(full.getEdges()),
           "net": {"file": str(NET.relative_to(REPO)), "sha256": _sha(NET)}, "routes": {"file": str(ROUTES.relative_to(REPO)), "sha256": _sha(ROUTES)},
           "route_signals_after_cut": signals, "sites": [{k: s[k] for k in ("site", "day", "section", "counts")} for s in sites],
           "window": f"{c.window_start}, {c.duration_s} s in {c.interval_s} s intervals; BM and INT were recorded on different days, treated as one clock window",
           "demand": {**merged, "vehicle_mix": mixed}, "tight_lateral": TIGHT, "routesampler_log_tail": log[0][-1200:] if log else None,
           "commands": ["netconvert --sumo-net-file <dhaka_r1> --keep-edges.input-file keep_edges.txt --output-file dhaka_corridor.net.xml.gz", "randomTrips.py (pool, background)",
                        "routeSampler.py -r pool.rou.xml --edgedata-files counts.xml --edgedata-attribute entered"]}
    (EVIDENCE / "calibration.json").write_text(json.dumps(rec, indent=1))
    return rec


def density(seeds=DENSITY_SEEDS, horizon: int = 3600, scale: float = 1.0) -> dict:
    """No ambulance: the INT section's density every second (vehicles on the edge / its length, all classes, all lanes, as DhaTraX)
    and the vehicles entering it, per seed; BM's too."""
    import traci
    import pandas as pd
    out = []
    for seed in seeds:
        cmd = ["sumo", "--net-file", str(NET), "--route-files", str(ROUTES), "--seed", str(seed), "--scale", str(scale), "--end", str(horizon), "--lateral-resolution", "0.8",
               "--time-to-teleport", "300", "--no-step-log", "--no-warnings", "--ignore-route-errors"]
        label = f"dens{seed}_{scale}"
        traci.start(cmd, label=label)
        c = traci.getConnection(label)
        L = {e: c.lane.getLength(f"{e}_0") / 1000 for e in (INT, BM)}
        dens, seen, entered = {INT: [], BM: []}, {INT: set(), BM: set()}, {INT: 0, BM: 0}
        t = 0
        while t < horizon:
            c.simulationStep()
            t = c.simulation.getTime()
            for e in (INT, BM):
                ids = set(c.edge.getLastStepVehicleIDs(e))
                entered[e] += len(ids - seen[e])
                seen[e] |= ids
                dens[e].append(len(ids) / L[e])
        tele = c.simulation.getEndingTeleportNumber()
        c.close()
        out.append({"seed": seed, **{f"{k}_density_mean": round(statistics.fmean(v[300:]), 2) for k, v in (("INT", dens[INT]), ("BM", dens[BM]))},
                    "INT_density_peak": round(max(dens[INT]), 1), "INT_entered_per_hour": entered[INT], "BM_entered_per_hour": entered[BM]})
        print(out[-1], flush=True)
    d = pd.read_csv(REPO / "data/recorded/dhatrax/Traffic_Analysis/combined_traffic_5min.csv")
    rec = {}
    for site in ("INT", "BM"):
        x = d[(d.site == site) & (d.interval_start.str[11:13] == "07")]
        rec[site] = {"density_median": round(float(x.density_veh_per_km.median()), 1), "density_q25": round(float(x.density_veh_per_km.quantile(.25)), 1),
                     "density_q75": round(float(x.density_veh_per_km.quantile(.75)), 1), "flow_veh_h_median": round(float(x.flow_rate_veh_per_hour.median()))}
    m = statistics.median([r["INT_density_mean"] for r in out])
    body = {"generated_utc": datetime.now(timezone.utc).isoformat(), "scale": scale, "runs": out, "recorded_07_08": rec,
            "INT_density_median_over_seeds": round(m, 2), "INT_entered_median": statistics.median([r["INT_entered_per_hour"] for r in out]),
            "share_of_recorded_density": round(m / rec["INT"]["density_median"], 3),
            "within_recorded_iqr": rec["INT"]["density_q25"] <= m <= rec["INT"]["density_q75"],
            "label": "Dhaka density" if rec["INT"]["density_q25"] <= m <= rec["INT"]["density_q75"] else f"corridor at recorded counts ({round(m, 1)} veh/km at INT)"}
    p = EVIDENCE / ("density.json" if scale == 1.0 else f"density_x{scale:g}.json")
    p.write_text(json.dumps(body, indent=1))
    p.with_suffix(".sha256").write_text(_sha(p) + f"  {p.name}\n")
    return body


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["build", "density", "match"])
    a = ap.parse_args()
    r = build() if a.cmd == "build" else density() if a.cmd == "density" else match()
    print(json.dumps({k: v for k, v in r.items() if k not in ("runs", "routesampler_log_tail", "sites")}, indent=1)[:3000])
