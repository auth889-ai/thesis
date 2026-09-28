#!/usr/bin/env python3
"""Forecast model -> routing: the trained model's predictions steer trips on the twin it was tested on.

    python -m app.protocols.chains.model_in_loop --model STID --compliance 0.1
    python -m app.protocols.chains.model_in_loop --model GWNet --horizons 15,60 --compliance 0.05,0.1

The twin dataset's test split is the tail of seed --seed's 8-h SUMO run (rows -> sim time via data.npz).
This script re-simulates exactly that run (same tiled routes, scale and seed as data/forecasting/dhaka_twin/
MANIFEST.json) and compares, for the trips DEPARTING INSIDE THE TEST WINDOW, pre-departure route choice
(duarouter --weight-files, no mid-trip swaps, equipped share = --compliance) driven by four weight tables
that all cover the SAME 250 sensor edges (other edges free-flow):

  static       nobody reroutes (the tiled DUE routes)                                   baseline
  oracle       the run's own measured 5-min edge times (upper bound)
  persistence  last measured 5-min value carried forward (no model)
  model@H      the trained model's H-minute-ahead predicted speed -> traveltime = length / speed
               (results/forecasting/twin_models/<model>_test_results.npz via forecast_to_weights --source model)

Outputs results/routing/model_in_loop/<model>/ (runs) and results/routing/model_in_loop_<model>.md/.json.
Labels: DHAKA_SIMULATED_SENSOR_GRAPH; one seed unless --seed is varied (the test split is one seed by design).
"""
from __future__ import annotations

import argparse
import gzip
import json
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

from app.paths import REPO
sys.path.insert(0, str(REPO))
from app.twin import runtime as pr  # noqa: E402
from app.protocols.chains.predeparture_arm import VEH_RE, read_routes  # noqa: E402
from app.protocols.chains.run_arms import shift_weights  # noqa: E402

TWIN = REPO / "data/forecasting/dhaka_twin"
OUT = REPO / "results/routing/model_in_loop"


def test_window(npz: Path, seed: int) -> tuple[float, float, int]:
    """(t0 of the first 1-step target bin, end of the last target bin, n windows) in sim seconds of `seed`'s run."""
    d = np.load(TWIN / "data.npz")
    n_win = np.load(npz)["prediction"].shape[0]
    T = d["data"].shape[0]
    first_target = T - n_win - 12 + 1            # windows: inputs [s, s+12), targets [s+12, s+24); last s = T-24
    rows = np.where(d["seed_index"] == np.unique(d["seed_index"])[list(np.unique(d["seed_index"])).index(d["seed_index"][first_target])])[0]
    assert d["seed_index"][first_target] == d["seed_index"][T - 1], "test split must lie inside one seed"
    t0 = float(d["sim_time_s"][first_target])
    t_end = float(d["sim_time_s"][T - 1]) + 300.0
    return t0, t_end, n_win


def filter_to_sensors(src: Path, dst: Path, sensor_edges: set) -> Path:
    root = ET.parse(src).getroot()
    for iv in root.iter("interval"):
        for ed in list(iv):
            if ed.get("id") not in sensor_edges:
                iv.remove(ed)
    ET.ElementTree(root).write(dst)
    return dst


def simulate(a, routes: Path, out: Path, tag: str) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    ns = argparse.Namespace(net=str(pr.DEFAULT_NET), routes=str(routes), seed=a.seed, scale=a.scale, horizon=a.horizon,
                            edgedata_period=300, time_to_teleport=300, sumo_binary="sumo")
    subprocess.run(pr.base_cmd(ns, out), check=True)
    return window_metrics(out, a.t0, a.t_end, a.compliance_now, a.horizon)


def window_metrics(out: Path, t0: float, t_end: float, compliance: float, horizon: float) -> dict:
    d_all, d_eq, unf, tele_all = [], [], 0, None
    for ti in ET.parse(out / "tripinfo.xml").getroot().iter("tripinfo"):
        dep = float(ti.get("depart"))
        if not (t0 <= dep < t_end):
            continue
        arr = float(ti.get("arrival", -1))
        dur = float(ti.get("duration")) if arr >= 0 else horizon - dep
        unf += arr < 0
        d_all.append(dur)
        if pr.equipped(ti.get("id"), compliance):
            d_eq.append(dur)
    st = ET.parse(out / "statistic.xml").getroot().find("teleports")
    return {"window_trips": len(d_all), "window_vehicle_hours": sum(d_all) / 3600, "window_mean_tt_s": float(np.mean(d_all)) if d_all else None,
            "window_p95_tt_s": float(np.percentile(d_all, 95)) if d_all else None, "equipped_mean_tt_s": float(np.mean(d_eq)) if d_eq else None,
            "window_unfinished": unf, "teleports_total_run": int(st.get("total")) if st is not None else None}


def reroute_pre_departure(a, weights: Path, out: Path) -> tuple[Path, int]:
    vehicles = read_routes(Path(a.routes))
    eq = [(v, d, r) for v, d, r in vehicles if pr.equipped(v, a.compliance_now) and a.t0 <= float(d) < a.t_end]
    trips = out / "trips_equipped.xml"
    trips.write_text("<routes>\n" + "".join(f'  <trip id="{v}" depart="{d}" from="{r.split()[0]}" to="{r.split()[-1]}"/>\n' for v, d, r in eq) + "</routes>\n")
    alt = out / "routes_equipped.rou.xml"
    subprocess.run(["duarouter", "--net-file", str(pr.DEFAULT_NET), "--route-files", str(trips), "--weight-files", str(weights),
                    "--weight-attribute", "traveltime", "--output-file", str(alt), "--ignore-errors", "--no-warnings", "--no-step-log",
                    "--seed", str(a.seed), "--routing-threads", "4"], check=True, capture_output=True)
    new = {v: r for v, d, r in VEH_RE.findall(alt.read_text())}
    merged = out / "routes_merged.rou.xml"
    changed = 0
    with open(merged, "w") as fh:
        fh.write('<routes xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/routes_file.xsd">\n')
        for v, d, r in vehicles:
            nr = new.get(v, r); changed += nr != r
            fh.write(f'    <vehicle id="{v}" depart="{d}">\n        <route edges="{nr}" />\n    </vehicle>\n')
        fh.write("</routes>\n")
    return merged, changed


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default="STID")
    ap.add_argument("--pred", type=Path, help="test_results.npz (default results/forecasting/twin_models/<model>_test_results.npz)")
    ap.add_argument("--horizons", default="15,60", help="model lead times (min) to route on")
    ap.add_argument("--compliance", default="0.1", help="comma list of equipped shares")
    ap.add_argument("--seed", type=int, default=None, help="twin seed whose run holds the test split (default: from data.npz)")
    a = ap.parse_args()
    man = json.loads((TWIN / "MANIFEST.json").read_text())
    cfg = man.get("config", {})
    a.routes = str(REPO / cfg["routes_file"]); a.scale = float(cfg["demand_scale"]); a.horizon = int(cfg["hours_per_seed"] * 3600)
    pred = a.pred or REPO / f"results/forecasting/twin_models/{a.model}_test_results.npz"
    d = np.load(TWIN / "data.npz")
    last = int(d["seed_index"][-1])
    a.seed = a.seed or (last if last > 5 else int(man["seeds"][last]))     # seed_index is an index into MANIFEST.seeds
    a.t0, a.t_end, n_win = test_window(pred, a.seed)
    sensors = {n["edge_id"] for n in json.loads((TWIN / "sensor_nodes.json").read_text())}
    print(f"[model_in_loop] model={a.model} seed={a.seed} scale={a.scale} run={a.horizon}s test window [{a.t0:.0f}, {a.t_end:.0f}) s, {n_win} windows, {len(sensors)} sensor edges", flush=True)
    base = OUT / a.model; base.mkdir(parents=True, exist_ok=True)
    comps = [float(x) for x in a.compliance.split(",")]
    a.compliance_now = comps[0]
    t_start = time.time()
    static_dir = base / "static"
    res = {"static": simulate(a, Path(a.routes), static_dir, "static")}
    # weight tables, all restricted to the sensor edges
    w = {"oracle": filter_to_sensors(static_dir / "edgedata.xml", base / "w_oracle.xml", sensors),
         "persistence": filter_to_sensors(shift_weights(static_dir / "edgedata.xml", base / "w_persist_raw.xml", 300), base / "w_persistence.xml", sensors)}
    for h in (int(x) for x in a.horizons.split(",")):
        wf = base / f"w_model{h}.xml"
        subprocess.run([sys.executable, "-m", "app.routing.forecast_to_weights", "--source", "model", "--pred", str(pred),
                        "--sensor-nodes", str(TWIN / "sensor_nodes.json"), "--horizon-min", str(h), "--t0", str(a.t0), "--period", "300",
                        "--out", str(wf)], check=True, capture_output=True)
        w[f"model@{h}"] = wf
    for c in comps:
        a.compliance_now = c
        for name, wf in w.items():
            out = base / f"{name}_c{c:g}"; out.mkdir(exist_ok=True)
            merged, changed = reroute_pre_departure(a, wf, out)
            m = simulate(a, merged, out, name)
            m["routes_changed"] = changed
            res[f"{name}_c{c:g}"] = m
            print(f"[model_in_loop] {name:12s} c={c:g} changed={changed} window veh-h={m['window_vehicle_hours']:.1f} mean_tt={m['window_mean_tt_s']:.0f} eq_tt={m['equipped_mean_tt_s']} tele={m['teleports_total_run']}", flush=True)
    s = res["static"]
    cols = ["window_vehicle_hours", "window_mean_tt_s", "window_p95_tt_s", "equipped_mean_tt_s", "window_unfinished", "teleports_total_run"]
    lines = [f"# Model in the loop — {a.model} forecasts steering pre-departure route choice on the Dhaka twin\n",
             f"Twin run: seed {a.seed}, scale {a.scale}, {a.horizon}s; test window [{a.t0:.0f}, {a.t_end:.0f}) s = {n_win} forecast windows; "
             f"{s['window_trips']} trips depart in the window. All weight tables cover the same {len(sensors)} sensor edges. Label DHAKA_SIMULATED_SENSOR_GRAPH; single seed (the test split).\n",
             "| arm | " + " | ".join(cols) + " | routes changed | Δ veh-h vs static | Δ equipped TT vs static |", "|---|" + "---|" * (len(cols) + 3)]
    for name, m in res.items():
        dv = f"{100 * (m['window_vehicle_hours'] / s['window_vehicle_hours'] - 1):+.1f} %" if name != "static" else "–"
        de = f"{100 * (m['equipped_mean_tt_s'] / s['equipped_mean_tt_s'] - 1):+.1f} %" if name != "static" and m.get("equipped_mean_tt_s") and s.get("equipped_mean_tt_s") else "–"
        lines.append(f"| {name} | " + " | ".join(f"{m[c]:.1f}" if isinstance(m[c], float) else str(m[c]) for c in cols) + f" | {m.get('routes_changed', 0)} | {dv} | {de} |")
    lines += ["", f"Regenerate: `python -m app.protocols.chains.model_in_loop --model {a.model} --horizons {a.horizons} --compliance {a.compliance}` (wall {time.time() - t_start:.0f} s)."]
    (REPO / f"results/routing/model_in_loop_{a.model}.md").write_text("\n".join(lines) + "\n")
    (REPO / f"results/routing/model_in_loop_{a.model}.json").write_text(json.dumps({"config": {k: v for k, v in vars(a).items() if k != "pred"} | {"pred": str(pred)}, "results": res}, indent=1, default=str))
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
