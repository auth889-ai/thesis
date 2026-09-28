#!/usr/bin/env python3
"""Predictive routing applied BEFORE departure (no mid-trip route changes).

    python -m traffictwin.protocols.chains.predeparture_arm --source oracle      --seeds 11,12,13 --horizon 7200
    python -m traffictwin.protocols.chains.predeparture_arm --source persistence --seeds 11,12,13 --horizon 7200

Motivation (results/routing/stats.md, 10 seeds): every en-route arm raises teleports 3-5x versus
static -> mid-trip route swaps near junctions create lane conflicts that eat the routing gain.
Here the forecast is used the way a navigation app uses it at trip start: the equipped share
(--compliance, same md5 rule as every other arm) gets its route from SUMO's official
`duarouter --weight-files <forecast meanData XML> --weight-attribute traveltime` (time-dependent
Dijkstra over the interval table), the rest keep the static routes; the merged route file is
then simulated with the exact static command (predictive_routing.base_cmd).
Weights: oracle = that seed's static edgedata (upper bound), persistence = lag-300 s table.
Outputs results/routing/predeparture_{source}_s{seed}_h{H}/metrics.json and merges the arm into
results/routing/arms_h{H}.json as `predeparture_{source}` so stats.py / decision_guard.py see it.
"""
from __future__ import annotations

import argparse
import gzip
import json
import re
import subprocess
import sys
import time
from pathlib import Path

from traffictwin.paths import REPO
sys.path.insert(0, str(REPO))
from traffictwin.digital_twin import runtime as pr  # noqa: E402
from traffictwin.protocols.chains.run_arms import shift_weights  # noqa: E402

RESULTS = REPO / "results/routing"   # overridden by --results
VEH_RE = re.compile(r'<vehicle id="([^"]+)" depart="([^"]+)">\s*<route edges="([^"]+)"\s*/>\s*</vehicle>', re.S)


def read_routes(path: Path) -> list[tuple[str, str, str]]:
    txt = gzip.open(path, "rt").read() if str(path).endswith(".gz") else path.read_text()
    return VEH_RE.findall(txt)


def run(a, seed: int) -> dict:
    out = RESULTS / f"predeparture_{a.source}_c{a.compliance:g}_s{seed}_h{a.horizon}"
    out.mkdir(parents=True, exist_ok=True)
    static_ed = RESULTS / f"static_s{seed}_h{a.horizon}/edgedata.xml"
    if not static_ed.exists():
        raise SystemExit(f"missing {static_ed} — run the static arm for seed {seed} first")
    weights = static_ed if a.source == "oracle" else shift_weights(static_ed, out / "weights_persistence.xml", lag_s=a.lag)
    vehicles = read_routes(Path(a.routes))
    eq = [(v, d, r) for v, d, r in vehicles if pr.equipped(v, a.compliance) and float(d) < a.horizon]
    trips = out / "trips_equipped.xml"
    trips.write_text("<routes>\n" + "".join(f'  <trip id="{v}" depart="{d}" from="{r.split()[0]}" to="{r.split()[-1]}"/>\n' for v, d, r in eq) + "</routes>\n")
    alt = out / "routes_equipped.rou.xml"
    cmd = [a.duarouter, "--net-file", str(a.net), "--route-files", str(trips), "--weight-files", str(weights),
           "--weight-attribute", "traveltime", "--output-file", str(alt), "--ignore-errors", "--no-warnings", "--no-step-log",
           "--seed", str(seed), "--routing-threads", "4"]
    t0 = time.time()
    subprocess.run(cmd, check=True, capture_output=True)
    new = {v: r for v, d, r in VEH_RE.findall(alt.read_text())}
    merged = out / "routes_merged.rou.xml"
    with open(merged, "w") as fh:
        fh.write('<routes xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/routes_file.xsd">\n')
        changed = 0
        for v, d, r in vehicles:
            nr = new.get(v, r)
            changed += nr != r
            fh.write(f'    <vehicle id="{v}" depart="{d}">\n        <route edges="{nr}" />\n    </vehicle>\n')
        fh.write("</routes>\n")
    a.seed, a.routes_run = seed, str(merged)
    ns = argparse.Namespace(**vars(a)); ns.routes = str(merged)
    subprocess.run(pr.base_cmd(ns, out), check=True)
    m = pr.parse_metrics(out, horizon=a.horizon)
    rec = {"arm": f"predeparture_{a.source}_c{a.compliance:g}", "seed": seed, "horizon_s": a.horizon, "scale": a.scale, "compliance": a.compliance,
           "weights": str(weights), "equipped_trips": len(eq), "routes_changed": changed, "duarouter": " ".join(cmd),
           "wall_s": round(time.time() - t0, 1), "metrics": m}
    (out / "metrics.json").write_text(json.dumps(rec, indent=1))
    print(f"[predeparture_{a.source}_c{a.compliance:g}] seed={seed} equipped={len(eq)} changed={changed} veh-h={m['total_vehicle_hours']:.1f} "
          f"arrived={m['arrived']} teleports={m['teleports']} wall={rec['wall_s']}s", flush=True)
    return rec


def main() -> int:
    global RESULTS
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--source", choices=["oracle", "persistence"], default="oracle")
    p.add_argument("--seeds", default="11,12,13")
    p.add_argument("--horizon", type=int, default=7200)
    sc = RESULTS / "SCALE_CHOICE.json"
    p.add_argument("--scale", type=float, default=json.loads(sc.read_text()).get("scale", 0.25) if sc.exists() else 0.25)
    p.add_argument("--compliance", type=float, default=0.3)
    p.add_argument("--lag", type=int, default=300)
    p.add_argument("--net", default=str(pr.DEFAULT_NET))
    p.add_argument("--routes", default=str(pr.DEFAULT_ROUTES))
    p.add_argument("--edgedata-period", type=int, default=300)
    p.add_argument("--time-to-teleport", type=int, default=300)
    p.add_argument("--sumo-binary", default="sumo")
    p.add_argument("--duarouter", default="duarouter")
    p.add_argument("--results", default=str(RESULTS))
    a = p.parse_args()
    RESULTS = Path(a.results)
    agg_path = RESULTS / f"arms_h{a.horizon}.json"
    agg = json.loads(agg_path.read_text()) if agg_path.exists() else {}
    for s in (int(x) for x in a.seeds.split(",")):
        rec = run(a, s)
        agg.setdefault(rec["arm"], {})[str(s)] = rec
        agg_path.write_text(json.dumps(agg, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
