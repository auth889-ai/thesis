#!/usr/bin/env python3
"""Run fixed coverage interventions against the saved Scenario A evaluation states."""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO), str(REPO / "src")]
from pipeline.v2x import closed_loop as cl
from pipeline.routing import edge_costs as ec
from traffictwin.protocols.oracle_gate import sha_file

REFERENCE = "la_c4_central_wide_prepeak_ideal_p30_cfgea08dddedc14_stressA_eval_fork1200_x8_peak_arterial"
ARMS = ("oracle_coverage_limited_v2x", "gwnet_direct_v2x")


def read(p):
    return json.loads(p.read_text())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="results/v2x/coverage_diagnostic/scenarioA_fixed_v1")
    parser.add_argument("--seeds", default="201,202,203,204,205")
    parser.add_argument("--analyze", action="store_true", help="also run the complete same-state audit and assemble the report")
    args = parser.parse_args()
    source = REPO / "results/v2x/closed_loop" / REFERENCE
    report = read(source / "report.json")
    P = dict(report["protocol"])
    cfg = ec.load_config()
    assert P["routing_config_hash"] == cfg["_config_hash"], "routing config changed"
    assert P["controller_config_hash"] == cl.controller_config()["_hash"], "controller changed"
    assert P["network_hash"] == sha_file(REPO / P["network"]), "network changed"
    assert P["mapping_hash"] == sha_file(REPO / P["mapping_file"]), "mapping changed"
    assert P["sumo_version"] == cl.sumo_version(), "SUMO version changed"
    from traffictwin.forecasting import ModelRegistry
    checkpoint = ModelRegistry.metr_la_gwnet()
    checkpoint_sha = hashlib.sha256(Path(checkpoint.checkpoint_path).read_bytes()).hexdigest()
    assert checkpoint_sha.startswith(P["checkpoint_sha256"]), "checkpoint changed"
    assert checkpoint_sha.startswith(checkpoint.checkpoint_sha256), "registry checkpoint evidence changed"
    seeds = [int(s) for s in args.seeds.split(",")]
    assert all(s in report["seeds"] for s in seeds)
    out = REPO / args.output
    out.mkdir(parents=True, exist_ok=True)
    P["run_namespace"] = "coverage_diagnostic_v1"
    manifest = {"frozen_protocol": P, "reference_run": str(source.relative_to(REPO)),
                "reference_report_sha256": hashlib.sha256((source / "report.json").read_bytes()).hexdigest(),
                "seeds": seeds, "arms": list(ARMS), "variants_A_C": "identical current DIRECT+DERIVED GWNet arm; reference results used explicitly",
                "oracle_replacement": "same baseline future window as full Oracle; replaces values only inside GWNet 15-minute coverage, at every existing horizon; no observation means retain original value and log it",
                "bottleneck_definition": "baseline measured edge travel time / free-flow >= 1.3 in the routing window",
                "execution": "new arms execute fresh SUMO runs using the reference saved fork bytes and demand files"}
    mf = out / "PROTOCOL.json"
    if mf.exists():
        assert read(mf) == manifest, "diagnostic protocol changed"
    else:
        mf.write_text(json.dumps(manifest, indent=2))
    for seed in seeds:
        rec = next(r for r in report["per_seed"] if r["seed"] == seed)
        fc = cl.Forecaster(P, seed)
        caps = fc.caps(P["simulation_duration_s"])
        state = REPO / rec["fork"]["state_file"]
        assert cl.state_content_hash(state) == rec["fork"]["state_sha256"]
        routes = REPO / rec["demand"]["demand_file"]
        assert sha_file(routes) == rec["demand"]["demand_hash"]
        for arm in ARMS:
            dest = out / f"s{seed}" / arm
            if (dest / "arm_result.json").exists():
                prior = read(dest / "arm_result.json")
                assert prior["fork"]["state_sha256"] == rec["fork"]["state_sha256"]
                print(f"verified completed diagnostic s{seed} {arm}", flush=True)
                continue
            print(f"START s{seed} {arm}", flush=True)
            result = cl.run_sumo(arm, seed, routes, dest, P, cfg, fc, caps,
                                 (state, rec["fork"]["state_sha256"]), source / f"s{seed}/baseline/edgedata.xml")
            print(f"DONE s{seed} {arm}: vehicle-hours={result['metrics']['total_vehicle_hours_incl_never_inserted']}", flush=True)
    (out / "COMPLETED.json").write_text(json.dumps({"seeds": seeds, "arms": ARMS}))
    if args.analyze:
        if seeds != report["seeds"] or out != REPO / "results/v2x/coverage_diagnostic/scenarioA_fixed_v1":
            raise ValueError("report assembly requires all five frozen seeds and the canonical output directory")
        for script in ("coverage_analysis.py", "coverage_report.py"):
            subprocess.run([sys.executable, str(REPO / "experiments/routing" / script)], cwd=REPO, check=True)


if __name__ == "__main__":
    main()
