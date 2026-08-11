#!/usr/bin/env python3
"""Lab 02 end-to-end orchestrator (config-driven; heavy execution = Colab).

Usage: python scripts/run_lab02.py --config configs/smoke.yaml --output-root <dir> [--osm-file existing.osm]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402

from src.osm.download import download_osm, sha256_file  # noqa: E402
from src.network.build import build_network  # noqa: E402
from src.validation.network_checks import validate_network, representative_routes  # noqa: E402
from src.demand.generate import generate_and_route, run_simulation  # noqa: E402
from src.metrics.summarize import summarize_tripinfo, summarize_run  # noqa: E402
from src.visualization.plot_net import plot_network  # noqa: E402


def main() -> dict:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(ROOT / "configs/smoke.yaml"))
    ap.add_argument("--output-root", default=None)
    ap.add_argument("--osm-file", default=None,
                    help="reuse an existing OSM extract instead of downloading")
    args = ap.parse_args()
    cfg = yaml.safe_load(open(args.config))
    out = Path(args.output_root) if args.output_root else ROOT / "outputs" / cfg["experiment_name"]
    out.mkdir(parents=True, exist_ok=True)
    gate: dict = {"config": cfg, "config_path": str(Path(args.config).resolve())}

    # 1. OSM acquisition
    osm_file = Path(args.osm_file) if args.osm_file else out / "osm" / "dhaka_extract.osm"
    if args.osm_file and osm_file.exists():
        gate["osm"] = {"reused_existing": str(osm_file), "sha256": sha256_file(osm_file),
                       "bytes": osm_file.stat().st_size}
    else:
        gate["osm"] = download_osm(cfg["bbox"], osm_file, out / "osm" / "osm_manifest.json")
    gate["OSM_SOURCE"] = "PASS" if osm_file.stat().st_size > 10_000 else "FAIL"

    # 2. netconvert
    net_file = out / "network" / "dhaka.net.xml"
    rec = build_network(osm_file, net_file, out / "network")
    gate["netconvert"] = {k: rec[k] for k in ("returncode", "net_sha256", "net_bytes")}
    gate["netconvert_warnings"] = rec["warnings"]["counts"]
    gate["OSM_TO_SUMO"] = "PASS" if rec["returncode"] == 0 else "FAIL"

    # 3. network validation
    val = validate_network(net_file, out / "validation")
    gate["network_validation"] = val
    gate["NETWORK_VALIDATION"] = "PASS" if val["n_edges"] > cfg["min_edges"] else "FAIL"
    gate["CONNECTIVITY"] = "PASS" if val["scc_edge_fraction"] >= cfg["min_scc_fraction"] else "FAIL"
    tls_ok = (val["n_tls"] >= cfg["min_tls"] and val["tls_all_have_yellow"]
              and not val["tls_any_all_green"])
    gate["SIGNAL_VALIDATION"] = "PASS" if tls_ok else "FAIL"

    # 4. representative routes
    rep = representative_routes(net_file, out / "validation")
    gate["representative_routes"] = {"n_ok": rep["n_ok"], "n_total": rep["n_total"]}
    gate["REPRESENTATIVE_ROUTES"] = "PASS" if rep["n_ok"] == rep["n_total"] else "FAIL"

    # 5-6. demand + deterministic run + metrics
    dem = generate_and_route(net_file, out / "demand", cfg["seed"],
                             cfg["sim_end"], cfg["trip_period"])
    gate["demand"] = {k: dem[k] for k in ("n_trips", "n_routed", "unroutable_fraction")}
    sim = run_simulation(net_file, Path(dem["routes_file"]), out / "sim",
                         cfg["seed"], cfg["sim_end"])
    gate["sim"] = {k: sim[k] for k in ("returncode", "teleports", "collisions",
                                       "emergency_braking")}
    trips = summarize_tripinfo(out / "sim" / "tripinfo.xml", out / "metrics" / "trip_metrics.json")
    runsum = summarize_run(out / "sim" / "summary.xml")
    (out / "metrics" / "run_summary.json").write_text(json.dumps(runsum, indent=2))
    gate["trip_metrics"] = trips
    gate["run_summary"] = runsum
    demand_ok = (dem["unroutable_fraction"] is not None
                 and dem["unroutable_fraction"] <= cfg["max_unroutable_fraction"]
                 and sim["returncode"] == 0 and sim["collisions"] == 0)
    gate["DEMAND_RUN"] = "PASS" if demand_ok else "FAIL"
    gate["METRICS"] = "PASS" if trips["n_arrived_trips"] > 0 else "FAIL"

    # 7. figures
    figs = plot_network(net_file, out / "figures" / "dhaka_network.png",
                        title=f"Dhaka OSM network — {cfg['experiment_name']}")
    gate["figures"] = figs

    (out / "gate_record.json").write_text(json.dumps(gate, indent=2, default=str))
    print(json.dumps({k: v for k, v in gate.items()
                      if k.isupper() or k in ("trip_metrics", "run_summary", "sim")},
                     indent=2, default=str))
    return gate


if __name__ == "__main__":
    main()
