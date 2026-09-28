#!/usr/bin/env python3
"""Paired-seed driver for every routing arm on the Dhaka R1 network.

    python src/pipeline/routing/run_arms.py --seeds 11,12,13 --horizon 1800 --jobs 3
    python src/pipeline/routing/stats.py --horizon 1800            # then the statistics

For every seed the same net, demand (routes_repeat_1h, --scale 0.584), horizon and
compliance are used; only the routing rule differs.  Static is run FIRST for each seed
because its edgedata.xml (5-min mean edge travel times) is the ground truth that the two
predictive arms consume:

  static                  B1  pre-computed shortest routes, no rerouting
  reactive                B2  equipped vehicles reroute on CURRENT travel times every 60 s
  predictive_oracle       P+  predictive arm fed the static run's OWN edgedata (perfect forecast)
  predictive_persistence  P0  predictive arm fed the same table shifted by one interval, i.e. each
                              5-min slot carries the PREVIOUS slot's measured times ("persistence"
                              = the no-forecast-model baseline; see shift_weights())
  due                     B3  SUMO's official duaIterate.py (Gawron DUE) on trips derived from the
                              route file (first/last edge, same id and depart, depart < horizon),
                              capped at --due-iterations; the last iteration's routes are then
                              simulated with the exact static command and parsed by
                              predictive_routing.parse_metrics.  Its metrics.json carries a
                              `due_status` field (ok / failed / timeout) and the assignment wall time.

Each arm is a subprocess call of src/pipeline/routing/predictive_routing.py (so the SUMO command line is
identical to the single-run harness); runs execute in a --jobs-wide thread pool, phase 1 =
all static runs, phase 2 = every other (arm, seed).  Output:

  results/routing/<arm>_s<seed>_h<H>/metrics.json      per run (arm 'due' also keeps dua/, trips.xml)
  results/routing/arms_h<H>.json                       {arm: {seed: per-run record}}
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from multiprocessing.pool import ThreadPool
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from pipeline.routing import predictive_routing as pr  # noqa: E402

ALL_ARMS = ["static", "reactive", "predictive_oracle", "predictive_persistence", "due"]


def run_dir(arm: str, seed: int, horizon: int, results: Path) -> Path:
    return results / f"{arm}_s{seed}_h{horizon}"


def sumo_home() -> Path:
    """SUMO_HOME if set, else the `sumo` package dir shipped by the eclipse-sumo wheel."""
    if os.environ.get("SUMO_HOME") and (Path(os.environ["SUMO_HOME"]) / "tools/assign/duaIterate.py").exists():
        return Path(os.environ["SUMO_HOME"])
    import sumolib
    for parent in Path(sumolib.__file__).resolve().parents:
        cand = parent / "sumo"
        if (cand / "tools/assign/duaIterate.py").exists():
            return cand
    raise RuntimeError("duaIterate.py not found; set SUMO_HOME")


# ----------------------------------------------------------------------------- weights
def shift_weights(path: Path, out: Path, lag_s: int = 300) -> Path:
    """Persistence forecast: interval [b, e) gets the edge travel times measured in
    [b-lag, e-lag).  The first interval has no predecessor and is written empty, so SUMO
    falls back to free-flow costs there (same fallback the predictive arm uses for any
    edge/interval missing from the table)."""
    root = ET.parse(path).getroot()
    ivs = list(root.iter("interval"))
    by_begin = {round(float(iv.get("begin"))): iv for iv in ivs}
    new = ET.Element("meandata")
    for iv in ivs:
        b = round(float(iv.get("begin")))
        dst = ET.SubElement(new, "interval", {"id": iv.get("id", "ed"), "begin": iv.get("begin"), "end": iv.get("end")})
        src = by_begin.get(b - lag_s)
        if src is not None:
            for ed in src.iter("edge"):
                if ed.get("traveltime") is not None:
                    ET.SubElement(dst, "edge", {"id": ed.get("id"), "traveltime": ed.get("traveltime")})
    ET.ElementTree(new).write(out, xml_declaration=True, encoding="UTF-8")
    return out


# ----------------------------------------------------------------------------- DUE
def write_trips(routes: Path, out: Path, horizon: int) -> tuple[Path, int]:
    """<trip id depart from to/> per vehicle of the route file departing before `horizon`
    (later vehicles never enter a --end horizon simulation anyway)."""
    opener = gzip.open if str(routes).endswith(".gz") else open
    with opener(routes, "rb") as fh:
        root = ET.parse(fh).getroot()
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<routes>"]
    n = 0
    for veh in root.iter("vehicle"):
        dep = float(veh.get("depart"))
        if dep >= horizon:
            continue
        edges = veh.find("route").get("edges").split()
        lines.append(f'    <trip id="{veh.get("id")}" depart="{dep:.2f}" from="{edges[0]}" to="{edges[-1]}"/>')
        n += 1
    lines.append("</routes>")
    out.write_text("\n".join(lines) + "\n")
    return out, n


def run_due(a, seed: int, out: Path, log: Path) -> dict:
    """duaIterate.py -> final route file -> static simulation of it -> metrics."""
    out.mkdir(parents=True, exist_ok=True)
    work = out / "dua"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir()
    trips, n_trips = write_trips(Path(a.routes), out / "trips.xml", a.horizon)
    home = sumo_home()
    cmd = [sys.executable, str(home / "tools/assign/duaIterate.py"),
           "-n", str(a.net), "-t", str(trips), "-l", str(a.due_iterations),
           "-b", "0", "-e", str(a.horizon), "-a", str(a.edgedata_period),
           "--continue-on-unbuild", "--time-to-teleport", str(a.time_to_teleport),
           "duarouter--routing-threads", "2",
           "sumo--seed", str(seed), "sumo--scale", str(a.scale), "sumo--ignore-route-errors"]
    rec = {"arm": "due", "seed": seed, "horizon_s": a.horizon, "due_iterations": a.due_iterations,
           "due_trips": n_trips, "due_command": " ".join(cmd), "sumo_home": str(home)}
    t0 = time.time()
    with open(log, "w") as lf:
        try:
            proc = subprocess.run(cmd, cwd=work, stdout=lf, stderr=subprocess.STDOUT, text=True,
                                  env=dict(os.environ, SUMO_HOME=str(home)), timeout=a.due_timeout)
            rc = proc.returncode
        except subprocess.TimeoutExpired:
            rc = "timeout"
    rec["due_wall_s"] = round(time.time() - t0, 1)
    # last completed iteration dir: NNN/ with *.rou.xml(.gz) that is not the .alt. set
    rou = None
    for it in sorted((d for d in work.iterdir() if d.is_dir() and d.name.isdigit()), key=lambda d: int(d.name), reverse=True):
        found = [f for f in it.glob("*.rou.xml*") if ".alt." not in f.name and f.suffix in (".gz", ".xml")]
        if found:
            rou, rec["due_last_iteration"] = found[0], int(it.name)
            break
    if rou is None:
        rec.update({"due_status": "failed" if rc != "timeout" else "timeout", "due_rc": rc, "metrics": None})
        (out / "metrics.json").write_text(json.dumps(rec, indent=1))
        return rec
    rec["due_status"] = "ok" if rc == 0 else f"partial({rc})"   # partial = timeout/error but an iteration finished
    rec["due_route_file"] = str(rou)
    # simulate the DUE routes with the exact static command (same seed/scale/horizon/outputs)
    sub = run_pr(a, "static", seed, out, log.with_name(log.stem + "_sim.log"), extra=["--routes", str(rou)])
    sub.update(rec)
    (out / "metrics.json").write_text(json.dumps(sub, indent=1))
    return sub


# ----------------------------------------------------------------------------- arms
def run_pr(a, arm: str, seed: int, out: Path, log: Path, extra: list[str] = ()) -> dict:
    cmd = [sys.executable, str(ROUTE / "predictive_routing.py"), "--arm", arm, "--seed", str(seed),
           "--horizon", str(a.horizon), "--scale", str(a.scale), "--compliance", str(a.compliance),
           "--period", str(a.period), "--net", str(a.net), "--routes", str(a.routes),
           "--edgedata-period", str(a.edgedata_period), "--time-to-teleport", str(a.time_to_teleport),
           "--sumo-binary", a.sumo_binary, "--out", str(out), *extra]
    with open(log, "w") as lf:
        subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT, text=True, check=True)
    return json.loads((out / "metrics.json").read_text())


def run_one(a, arm: str, seed: int) -> tuple[str, int, dict]:
    out = run_dir(arm, seed, a.horizon, a.results)
    out.mkdir(parents=True, exist_ok=True)
    log = a.log_dir / f"{arm}_s{seed}_h{a.horizon}.log"
    static_ed = run_dir("static", seed, a.horizon, a.results) / "edgedata.xml"
    t0 = time.time()
    print(f"[run_arms] start {arm} seed={seed}", flush=True)
    if arm == "static":
        rec = run_pr(a, "static", seed, out, log)
    elif arm == "reactive":
        rec = run_pr(a, "reactive", seed, out, log)
    elif arm == "predictive_oracle":
        rec = run_pr(a, "predictive", seed, out, log, ["--weights", str(static_ed)])
    elif arm == "predictive_persistence":
        w = shift_weights(static_ed, out / "weights_persistence.xml", a.lag)
        rec = run_pr(a, "predictive", seed, out, log, ["--weights", str(w)])
    elif arm == "due":
        rec = run_due(a, seed, out, log)
    else:
        raise ValueError(arm)
    rec["arm"] = arm
    rec["driver_wall_s"] = round(time.time() - t0, 1)
    (out / "metrics.json").write_text(json.dumps(rec, indent=1))
    m = rec.get("metrics") or {}
    print(f"[run_arms] done  {arm} seed={seed} wall={rec['driver_wall_s']}s "
          f"mean_tt={m.get('mean_travel_time_s')} arrived={m.get('arrived')} status={rec.get('due_status', '-')}", flush=True)
    return arm, seed, rec


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--arms", default=",".join(ALL_ARMS))
    p.add_argument("--seeds", default="11,12,13")
    p.add_argument("--horizon", type=int, default=3600)
    p.add_argument("--compliance", type=float, default=0.3)
    p.add_argument("--period", type=int, default=60)
    p.add_argument("--jobs", type=int, default=3)
    p.add_argument("--scale", type=float, default=pr.DEFAULT_SCALE)
    p.add_argument("--net", default=str(pr.DEFAULT_NET))
    p.add_argument("--routes", default=str(pr.DEFAULT_ROUTES))
    p.add_argument("--edgedata-period", type=int, default=300)
    p.add_argument("--lag", type=int, default=300, help="persistence lag (s) = one edgedata interval")
    p.add_argument("--time-to-teleport", type=int, default=300)
    p.add_argument("--sumo-binary", default="sumo")
    p.add_argument("--due-iterations", type=int, default=8)
    p.add_argument("--due-timeout", type=int, default=3600, help="wall cap for duaIterate (s)")
    p.add_argument("--results", default=str(ROUTE / "results"))
    p.add_argument("--log-dir", default=str(ROUTE / "results" / "logs"))
    a = p.parse_args()
    a.results, a.log_dir = Path(a.results), Path(a.log_dir)
    a.results.mkdir(parents=True, exist_ok=True)
    a.log_dir.mkdir(parents=True, exist_ok=True)
    arms = [x.strip() for x in a.arms.split(",") if x.strip()]
    seeds = [int(s) for s in a.seeds.split(",")]
    bad = set(arms) - set(ALL_ARMS)
    if bad:
        p.error(f"unknown arms {bad}; choose from {ALL_ARMS}")

    t0 = time.time()
    agg_path = a.results / f"arms_h{a.horizon}.json"
    agg = json.loads(agg_path.read_text()) if agg_path.exists() else {}
    with ThreadPool(a.jobs) as pool:
        phases = []
        if "static" in arms or any(x != "static" for x in arms):
            phases.append([("static", s) for s in seeds])         # dependency of the predictive arms
        rest = [(x, s) for x in arms if x != "static" for s in seeds]
        if rest:
            phases.append(rest)
        for jobs in phases:
            for arm, seed, rec in pool.starmap(run_one, [(a, x, s) for x, s in jobs]):
                agg.setdefault(arm, {})[str(seed)] = rec
                agg_path.write_text(json.dumps(agg, indent=1))
    print(f"[run_arms] all done in {time.time() - t0:.0f}s -> {agg_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
