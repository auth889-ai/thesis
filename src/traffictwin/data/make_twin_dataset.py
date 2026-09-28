#!/usr/bin/env python3
"""METR-LA-shaped Dhaka twin sensor dataset on the frozen R1 network.

    python src/pipeline/forecasting/make_twin_dataset.py --seeds 11 --hours 2                 # smoke
    python src/pipeline/forecasting/make_twin_dataset.py --seeds 11,12,13 --hours 8 --scale 0.15 --place-by-flow

Wraps the existing (unchanged) sensor-graph pipeline in research/twin/sensor_graph.py:
250 virtual sensors = SUMO edgeData aggregates at 5-min bins on the frozen network
(sha256 checked), adjacency = DCRNN gaussian-kernel recipe on directed road distances.

Demand = the SAME scenario the routing arms use (src/pipeline/routing/predictive_routing.py): the
audited DUE pulse results/artifacts/due_dso_stats/v200/DUE/003/trips_003.rou.xml.gz tiled every
600 s by research/twin/demand.make_repeating_routes (routes_repeat_1h is cycles=8 of it),
run at --scale 0.15 for the 8-hour sensor replay. The routing experiments use the separate
2-hour route scale from results/routing/SCALE_CHOICE.json; using that route scale for 8-hour
sensor generation gridlocks R1 (see REJECTED_RUNS / MANIFEST "scale_sweep_note"). The gate
(every seed: insertion >= 0.95,
teleports <= --max-teleport-frac of inserted) marks the run PASS/FAIL in MANIFEST.json and
exits 2 on FAIL. --place-by-flow puts the 250 sensors on the top-250 edges by vehicle count
in the longest complete results/routing/static_s11_h*/edgedata.xml (coverage ~100% instead of
~30% for the rank/grid placement); the DCRNN adjacency recipe is unchanged. Each seed is
an independent replay of the same H-hour window (a "day"); seeds are concatenated in
time order, and `seed_index` / `sim_time_s` in data.npz mark the boundaries.

Outputs (data/forecasting/dhaka_twin/):
  data.npz           data (T,N,C) float32, C = [speed_ms, flow_veh, occupancy_pct,
                     tod_fraction, dow_fraction]; mask (T,N) bool (speed NaN where no
                     vehicle sampled -> mask False, never silently 0); seed_index (T,);
                     sim_time_s (T,); adjacency (N,N); distances_m (N,N)
  adj_mx.pkl         pickled (N,N) float32 adjacency (BasicTS load_adj format)
  sensor_nodes.json  edge_id, length_m, speed_limit_ms, num_lanes, x, y per sensor
  sensor_graph_data.npz  the pipeline's native bundle (speed, density, occupancy, flow)
  MANIFEST.json      DHAKA_SIMULATED_SENSOR_GRAPH label, sha256 of every file, per-seed
                     wall time / teleports / coverage, demand provenance
  basicts_legacy/    data.dat + desc.json + adj_mx.pkl (BasicTS @ 4c3e2d3 benchmark layout)
  basicts_v1/        train/val/test_data.npy + DESC.json (BasicTS v1.0 layout)

Everything here is SIMULATED on the real frozen topology; never described as a real
measurement.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pickle
import subprocess
import sys
import time
from pathlib import Path

from traffictwin.paths import REPO
sys.path.insert(0, str(REPO))

import numpy as np

from traffictwin.optimization.graph_router import NetworkGraph
from traffictwin.forecasting.training.basicts_adapter import (export_basicts_dataset,
                                                  export_basicts_legacy_dataset)
from traffictwin.digital_twin.demand import make_repeating_routes
from traffictwin.digital_twin.sensor_graph import (CHANNELS, EVIDENCE_DOMAIN,
                                        SENSOR_PERIOD_S, SensorNode, largest_scc,
                                        gaussian_kernel_adjacency,
                                        node_list_sha256, parse_edgedata,
                                        road_distances, save_dataset,
                                        select_sensor_edges,
                                        write_sensor_additional)

DEFAULT_NET = REPO / "paper_labs/02_dhaka_osm/outputs/lab02_v2/network/dhaka_r1.net.xml"
FROZEN_NET_SHA256 = "06194df039740fa2ceb0bcb2c438444efd755f26e0f863327f0e1d6524775dcb"
DUE_PULSE = REPO / "results/artifacts/due_dso_stats/v200/DUE/003/trips_003.rou.xml.gz"
PULSE_PERIOD_S = 600.0            # routes_repeat_1h = this pulse x 8 cycles
DEFAULT_SCALE = 0.15              # accepted 8-hour sensor-data scale; the route harness has its own
                                  # 2-hour calibrated scale in results/routing/SCALE_CHOICE.json
DEFAULT_OUT = REPO / "data/forecasting/dhaka_twin"
OUT_CHANNELS = ("speed_ms", "flow_veh", "occupancy_pct", "tod_fraction", "dow_fraction")

# Acceptance gate: a seed whose demand cannot be inserted is a boundary queue, not
# traffic, and its sensors record gridlock. Both must hold for every seed.
MIN_INSERTION_RATE = 0.95         # inserted / (inserted + waiting at end)
MAX_TELEPORT_FRAC = 0.01          # teleports / inserted — unified with results/routing/SCALE_CHOICE.json
                                  # (routing agent's criterion: teleports <= 1% at h7200); 0.005 was the
                                  # first gate, under which 0.15 was the largest passing scale
# Evidence that the calibrated ROUTING scale is not a usable SENSOR-DATA scale
# (measured 2026-09-01 with this script, seed 11, 4 h): recorded in every manifest.
REJECTED_RUNS = {
    "finding": "the calibrated ROUTING scale 0.584 (TWIN_SYNC_PASS, 1-h window) is NOT a "
               "usable SENSOR-DATA scale: the DUE pulse (3000 veh / 600 s before scaling) "
               "gridlocks R1 at every scale >= 0.2 over 2-4 h; 0.15 is the largest scale "
               "in the sweep that passes the gate (insertion 1.00, 0 teleports)",
    "insertion_rate": "inserted / (inserted + waiting_to_insert_at_end)",
    "runs_seed11": [
        {"scale": 0.584, "hours": 4, "inserted": 20366, "waiting": 21682, "insertion_rate": 0.484,
         "teleports": 2965, "teleport_frac": 0.146, "coverage_pct": 36.0, "wall_s": 258.7, "verdict": "FAIL"},
        {"scale": 0.5, "hours": 2, "inserted": 11146, "waiting": 6854, "insertion_rate": 0.619,
         "teleports": 681, "teleport_frac": 0.061, "coverage_pct": 35.8, "wall_s": 71.0, "verdict": "FAIL"},
        {"scale": 0.4, "hours": 2, "inserted": 7565, "waiting": 6835, "insertion_rate": 0.525,
         "teleports": 710, "teleport_frac": 0.094, "coverage_pct": 15.5, "wall_s": 57.9, "verdict": "FAIL"},
        {"scale": 0.3, "hours": 2, "inserted": 8275, "waiting": 2525, "insertion_rate": 0.766,
         "teleports": 567, "teleport_frac": 0.069, "coverage_pct": 28.7, "wall_s": 47.7, "verdict": "FAIL"},
        {"scale": 0.25, "hours": 2, "inserted": 9000, "waiting": 0, "insertion_rate": 1.0,
         "teleports": 62, "teleport_frac": 0.0069, "coverage_pct": 38.1, "wall_s": 34.8, "verdict": "FAIL (teleports > 0.5%)"},
        {"scale": 0.2, "hours": 2, "inserted": 5230, "waiting": 1970, "insertion_rate": 0.726,
         "teleports": 109, "teleport_frac": 0.021, "coverage_pct": 13.3, "wall_s": 26.8, "verdict": "FAIL"},
        {"scale": 0.15, "hours": 2, "inserted": 5400, "waiting": 0, "insertion_rate": 1.0,
         "teleports": 0, "teleport_frac": 0.0, "coverage_pct": 29.4, "wall_s": 16.1, "verdict": "PASS"},
        {"scale": 0.1, "hours": 2, "inserted": 3600, "waiting": 0, "insertion_rate": 1.0,
         "teleports": 0, "teleport_frac": 0.0, "coverage_pct": 13.4, "wall_s": 10.9, "verdict": "PASS"}],
    "measured": "2026-09-01, src/pipeline/forecasting/make_twin_dataset.py, sumo 1.27.1, seed 11, time-to-teleport 300"}


def _xml_closed(p: Path) -> bool:
    with open(p, "rb") as fh:
        fh.seek(max(0, p.stat().st_size - 256))
        return b"</meandata>" in fh.read()


def find_longest_static_edgedata(seed: int = 11) -> Path | None:
    """results/routing/static_s{seed}_h*/edgedata.xml with the largest horizon, if any."""
    cands = []
    for d in (REPO / "results/routing").glob(f"static_s{seed}_h*"):
        p = d / "edgedata.xml"
        if p.exists() and _xml_closed(p):        # skip runs still being written / killed
            try:
                cands.append((int(d.name.rsplit("_h", 1)[1]), p))
            except ValueError:
                pass
    return max(cands)[1] if cands else None


def select_sensor_edges_by_flow(net_path: Path, edgedata: Path, n_target: int = 250,
                                min_length_m: float = 50.0) -> tuple[list[SensorNode], dict]:
    """Top-`n_target` candidate edges by sampled vehicle count in a static routing run.

    Candidates are the same population the rank-based placement uses (passenger edges
    in the largest SCC, length >= min_length_m); score = sum of edgeData `entered` over
    all intervals, tie-break sampledSeconds, then the existing (lanes, speed, length, id)
    rank. Adjacency recipe is untouched (still road_distances + gaussian kernel).
    """
    import sumolib
    import xml.etree.ElementTree as ET

    net = sumolib.net.readNet(str(net_path))
    passenger = [e for e in net.getEdges()
                 if not e.getID().startswith(":") and e.allows("passenger")]
    succ = {e.getID(): [o.getID() for o in e.getOutgoing() if o.allows("passenger")]
            for e in passenger}
    core = largest_scc([e.getID() for e in passenger], succ)

    entered: dict[str, float] = {}
    sampled: dict[str, float] = {}
    n_iv = 0
    for _, el in ET.iterparse(str(edgedata)):
        if el.tag == "interval":
            n_iv += 1
            for ed in el.iter("edge"):
                eid = ed.get("id")
                entered[eid] = entered.get(eid, 0.0) + float(ed.get("entered", 0.0))
                sampled[eid] = sampled.get(eid, 0.0) + float(ed.get("sampledSeconds", 0.0))
            el.clear()

    cands = []
    for e in passenger:
        eid = e.getID()
        if eid not in core or float(e.getLength()) < min_length_m:
            continue
        shape = e.getShape()
        mid = shape[len(shape) // 2]
        cands.append(SensorNode(edge_id=eid, length_m=float(e.getLength()),
                                speed_limit_ms=float(e.getSpeed()), num_lanes=len(e.getLanes()),
                                x=float(mid[0]), y=float(mid[1])))
    ranked = sorted(cands, key=lambda c: (-entered.get(c.edge_id, 0.0),
                                          -sampled.get(c.edge_id, 0.0),
                                          -c.num_lanes, -c.speed_limit_ms, -c.length_m, c.edge_id))
    chosen = ranked[:n_target]
    if len(chosen) < n_target:
        raise ValueError(f"only {len(chosen)} candidates for {n_target} sensors")
    info = {"policy": "top-N by summed edgeData `entered` (tie: sampledSeconds, then "
                      "lanes/speed/length/id rank) over passenger edges in the largest SCC",
            "source_edgedata": str(edgedata.relative_to(REPO) if edgedata.is_relative_to(REPO) else edgedata),
            "source_edgedata_sha256": sha256_file(edgedata), "source_intervals": n_iv,
            "candidates": len(cands), "edges_with_traffic_in_source": len(entered),
            "min_entered_selected": entered.get(chosen[-1].edge_id, 0.0),
            "max_entered_selected": entered.get(chosen[0].edge_id, 0.0)}
    return sorted(chosen, key=lambda c: c.edge_id), info


def acceptance(rec: dict, max_teleport_frac: float = MAX_TELEPORT_FRAC) -> dict:
    """SUMO's `loaded` counts vehicles BEFORE --scale thinning, so the demand that
    actually tried to enter is inserted + waiting_to_insert_at_end (= loaded x scale)."""
    demand = (rec.get("inserted") or 0) + (rec.get("waiting_to_insert_at_end") or 0)
    ins = rec["inserted"] / demand if demand else 0.0
    tel = rec["teleports"] / rec["inserted"] if rec.get("inserted") else 1.0
    ok = ins >= MIN_INSERTION_RATE and tel <= max_teleport_frac
    return {"demand_after_scale": int(demand), "insertion_rate": round(ins, 4),
            "teleport_frac": round(tel, 5), "pass": bool(ok)}


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_int_list(s: str) -> list[int]:
    return [int(x) for x in s.replace(" ", "").split(",") if x]


def run_sumo(a, net: Path, routes: Path, add: Path, seed: int, end_s: float,
             log: Path) -> dict:
    """Same processing options as src/pipeline/routing/predictive_routing.base_cmd, plus a stats file."""
    stats = log.with_suffix(".statistic.xml")
    cmd = [a.sumo_binary, "--net-file", str(net), "--route-files", str(routes),
           "--additional-files", str(add), "--seed", str(seed),
           "--scale", str(a.scale), "--end", str(end_s),
           "--statistic-output", str(stats),
           "--no-step-log", "--no-warnings", "--ignore-route-errors",
           "--time-to-teleport", str(a.time_to_teleport),
           "--device.rerouting.probability", "0"]
    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True)
    wall = time.time() - t0
    log.write_text(" ".join(cmd) + "\n\n" + r.stdout[-4000:] + "\n" + r.stderr[-4000:])
    if r.returncode != 0:
        raise RuntimeError(f"SUMO failed (seed {seed}): {r.stderr[-1500:]}")
    import xml.etree.ElementTree as ET
    st = ET.parse(stats).getroot()
    veh, tele = st.find("vehicles"), st.find("teleports")
    return {"wall_s": round(wall, 1),
            "inserted": int(veh.get("inserted")) if veh is not None else None,
            "loaded": int(veh.get("loaded")) if veh is not None else None,
            "running_at_end": int(veh.get("running")) if veh is not None else None,
            "waiting_to_insert_at_end": int(veh.get("waiting")) if veh is not None else None,
            "teleports": int(tele.get("total")) if tele is not None else None}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seeds", default="11,12,13", help="comma list, e.g. 11,12,13")
    ap.add_argument("--hours", type=float, default=4.0, help="simulated hours per seed")
    ap.add_argument("--scale", type=float, default=DEFAULT_SCALE)
    ap.add_argument("--n-sensors", type=int, default=250)
    ap.add_argument("--start-hour", type=float, default=8.0,
                    help="clock hour the simulated window starts at (tod channel only)")
    ap.add_argument("--net", type=Path, default=DEFAULT_NET)
    ap.add_argument("--pulse", type=Path, default=DUE_PULSE,
                    help="route pulse to tile (default: the audited DUE pulse)")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--time-to-teleport", type=int, default=300)
    ap.add_argument("--sumo-binary", default="sumo")
    ap.add_argument("--keep-raw", action="store_true", help="keep per-seed edgedata XML")
    ap.add_argument("--place-by-flow", nargs="?", const="auto", default=None, metavar="EDGEDATA_XML",
                    help="place sensors on the top-N edges by sampled vehicle count in a static "
                         "routing run's edgedata.xml ('auto' = longest results/routing/static_s11_h*)")
    ap.add_argument("--max-teleport-frac", type=float, default=MAX_TELEPORT_FRAC,
                    help="acceptance gate: teleports / inserted (default %(default)s)")
    a = ap.parse_args()

    seeds = parse_int_list(a.seeds)
    end_s = a.hours * 3600.0
    bins_per_seed = int(round(end_s / SENSOR_PERIOD_S))
    out = a.out.resolve()               # SUMO resolves edgeData paths relative to the additional file
    raw = out / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    t_start = time.time()

    net_sha = sha256_file(a.net)
    if net_sha != FROZEN_NET_SHA256:
        raise RuntimeError(f"network sha256 {net_sha[:16]} != frozen R1 {FROZEN_NET_SHA256[:16]}")
    print(f"[twin] net {a.net.name} sha256 ok | seeds={seeds} hours={a.hours} "
          f"scale={a.scale} sensors={a.n_sensors} bins/seed={bins_per_seed}")

    # --- sensors (deterministic on the frozen net) -----------------------------
    if a.place_by_flow:
        src = (find_longest_static_edgedata() if a.place_by_flow == "auto" else Path(a.place_by_flow))
        if src is None or not src.exists():
            raise FileNotFoundError("--place-by-flow: no complete static edgedata.xml found")
        if not _xml_closed(src):
            raise ValueError(f"--place-by-flow: {src} is truncated (run still writing or killed)")
        nodes, placement = select_sensor_edges_by_flow(a.net, src, n_target=a.n_sensors)
        print(f"[twin] placement by flow from {placement['source_edgedata']} "
              f"({placement['source_intervals']} intervals; entered range "
              f"{placement['min_entered_selected']:.0f}-{placement['max_entered_selected']:.0f})")
    else:
        nodes = select_sensor_edges(a.net, n_target=a.n_sensors)
        placement = {"policy": "rank (lanes, speed limit, length) under a 12x12 spatial grid quota "
                               "[research/twin/sensor_graph.select_sensor_edges]"}
    edge_ids = [n.edge_id for n in nodes]
    print(f"[twin] {len(nodes)} sensors, node_list_sha256={node_list_sha256(nodes)[:16]}...")

    # --- demand: the routing scenario's pulse tiled for H hours ---------------
    cycles = int(np.ceil(end_s / PULSE_PERIOD_S))
    routes = make_repeating_routes(a.pulse, raw / f"routes_{cycles}x{int(PULSE_PERIOD_S)}s.rou.xml.gz",
                                   cycles=cycles, period_s=PULSE_PERIOD_S)
    print(f"[twin] routes: {routes.name} ({cycles} cycles of {a.pulse.name}, "
          f"sha256 {sha256_file(routes)[:16]}...)")

    # --- simulate each seed ------------------------------------------------------
    all_data, all_mask, per_seed = [], [], []
    for seed in seeds:
        edgedata = raw / f"edgedata_s{seed}.xml"
        add = write_sensor_additional(nodes, raw / f"sensors_s{seed}.add.xml", edgedata)
        print(f"[twin] seed {seed}: running SUMO for {end_s:.0f}s ...", flush=True)
        stats = run_sumo(a, a.net, routes, add, seed, end_s, raw / f"sumo_s{seed}.log")
        data, mask = parse_edgedata(edgedata, edge_ids)
        if data.shape[0] != bins_per_seed:
            print(f"[twin] WARNING seed {seed}: {data.shape[0]} bins, expected {bins_per_seed}")
        all_data.append(data)
        all_mask.append(mask)
        rec = {"seed": seed, "timesteps": int(data.shape[0]),
               "coverage_pct": round(100.0 * float(mask.mean()), 1),
               "mean_speed_ms": round(float(np.nanmean(data[..., 0])), 3),
               "mean_flow_veh_per_bin": round(float(np.nanmean(data[..., 3])), 2),
               **stats}
        rec.update(acceptance(rec, a.max_teleport_frac))
        per_seed.append(rec)
        print(f"[twin] seed {seed}: {rec['timesteps']} bins, coverage {rec['coverage_pct']}%, "
              f"inserted {rec['inserted']}/{rec['loaded']} ({rec['insertion_rate']:.3f}), "
              f"teleports {rec['teleports']} ({rec['teleport_frac']:.4f}), "
              f"wall {rec['wall_s']}s -> {'PASS' if rec['pass'] else 'FAIL'}", flush=True)
        if not a.keep_raw:
            edgedata.unlink(missing_ok=True)

    native = np.concatenate(all_data)           # (T, N, 4) = CHANNELS order
    mask = np.concatenate(all_mask)
    seed_index = np.concatenate([np.full(d.shape[0], k) for k, d in enumerate(all_data)])
    sim_time = np.concatenate([np.arange(d.shape[0]) * SENSOR_PERIOD_S for d in all_data])

    # --- adjacency (DCRNN recipe, unchanged code) --------------------------------
    print("[twin] road distances + gaussian-kernel adjacency ...", flush=True)
    graph = NetworkGraph.from_sumo_net(a.net)
    dist = road_distances(graph, edge_ids)
    adj = gaussian_kernel_adjacency(dist)

    # --- native bundle + MANIFEST via the pipeline's own writer ------------------
    wall_total = round(time.time() - t_start, 1)
    save_dataset(out, native, mask, adj, dist, nodes,
                 network_sha256=net_sha, seeds=seeds,
                 config={"hours_per_seed": a.hours, "bins_per_seed": bins_per_seed,
                         "demand_scale": a.scale, "start_hour": a.start_hour,
                         "demand_provenance": "CALIBRATED_ROUTING_SCENARIO: DUE pulse "
                                              f"{a.pulse.relative_to(REPO) if a.pulse.is_relative_to(REPO) else a.pulse} "
                                              f"tiled every {PULSE_PERIOD_S:g}s x {cycles} "
                                              f"(same generator as results/artifacts/gates/routes_repeat_1h), "
                                              f"sumo --scale {a.scale}",
                         "routes_file": str(routes.relative_to(REPO)),
                         "routes_sha256": sha256_file(routes),
                         "pulse_sha256": sha256_file(a.pulse),
                         "time_to_teleport_s": a.time_to_teleport,
                         "seed_boundaries_timesteps": [d.shape[0] for d in all_data],
                         "per_seed": per_seed, "wall_s_total": wall_total,
                         "sumo": subprocess.run([a.sumo_binary, "--version"], capture_output=True,
                                                text=True).stdout.split("\n")[0]})

    # --- METR-LA-shaped export ----------------------------------------------------
    n = len(nodes)
    tod = ((a.start_hour * 3600.0 + sim_time) % 86400.0) / 86400.0
    dow = (seed_index % 7) / 7.0
    ch = {name: native[..., CHANNELS.index(name)] for name in ("speed_ms", "occupancy_pct", "flow_veh")}
    arr = np.stack([ch["speed_ms"], ch["flow_veh"], ch["occupancy_pct"],
                    np.repeat(tod[:, None], n, axis=1),
                    np.repeat(dow[:, None], n, axis=1)], axis=2).astype(np.float32)
    np.savez_compressed(out / "data.npz", data=arr, mask=mask, seed_index=seed_index,
                        sim_time_s=sim_time, adjacency=adj.astype(np.float32),
                        distances_m=dist, channels=np.array(OUT_CHANNELS),
                        sensor_edges=np.array(edge_ids))
    with open(out / "adj_mx.pkl", "wb") as fh:
        pickle.dump(adj.astype(np.float32), fh)

    # BasicTS exports through the existing adapters. period_steps=bins_per_seed makes
    # their tod = fraction of the simulated window and day = seed index (each seed is an
    # independent replay of the same window), so no clock value overflows an embedding.
    export_basicts_legacy_dataset(out, out / "basicts_legacy", period_steps=bins_per_seed)
    export_basicts_dataset(out, out / "basicts_v1", period_steps=bins_per_seed)

    # --- manifest: label + sha256 of everything ------------------------------------
    m = json.loads((out / "MANIFEST.json").read_text())
    files = sorted(p for p in out.rglob("*") if p.is_file() and p.name != "MANIFEST.json"
                   and "raw" not in p.relative_to(out).parts)
    verdict = "PASS" if all(r["pass"] for r in per_seed) else "FAIL"
    m.update({
        "label": EVIDENCE_DOMAIN,
        "acceptance": {"verdict": verdict,
                       "rule": f"every seed: insertion_rate >= {MIN_INSERTION_RATE} and "
                               f"teleports/inserted <= {a.max_teleport_frac}",
                       "per_seed": [{k: r[k] for k in ("seed", "insertion_rate", "teleport_frac", "pass")}
                                    for r in per_seed]},
        "sensor_placement": placement,
        "scale_sweep_note": REJECTED_RUNS,
        "dataset": "dhaka_twin (METR-LA-shaped)",
        "data_npz": {"data_shape": list(arr.shape), "channels": list(OUT_CHANNELS),
                     "speed_missing": "NaN where no vehicle sampled; mask False",
                     "tod": f"fraction of 24h clock, window starts at {a.start_hour:g}:00",
                     "dow": "seed_index % 7 / 7 (each seed = one simulated day)"},
        "basicts_clock_convention": "period_steps=bins_per_seed: tod = fraction of the "
                                    "simulated window, day = seed index",
        "files_sha256": {str(p.relative_to(out)): sha256_file(p) for p in files},
        "generator": "src/pipeline/forecasting/make_twin_dataset.py",
        "args": vars(a) | {"net": str(a.net), "pulse": str(a.pulse), "out": str(a.out)},
    })
    (out / "MANIFEST.json").write_text(json.dumps(m, indent=2))

    print(f"\n[twin] data.npz: T={arr.shape[0]} x N={arr.shape[1]} x C={arr.shape[2]} | "
          f"mask coverage {100.0 * float(mask.mean()):.1f}% | adjacency nnz "
          f"{100.0 * float((adj > 0).mean()):.1f}% | total wall {wall_total}s")
    print(f"[twin] acceptance {verdict} | label {EVIDENCE_DOMAIN} -> {out / 'MANIFEST.json'}")
    return 0 if verdict == "PASS" else 2


if __name__ == "__main__":
    sys.exit(main())
