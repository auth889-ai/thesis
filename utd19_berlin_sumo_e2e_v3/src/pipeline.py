from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable

from .utils import StepContext, ensure_dirs, load_config, read_json, workspace

PROJECT = Path(__file__).resolve().parents[1]


def module(name: str, *args: object) -> list[str]:
    return [sys.executable, "-m", f"src.{name}", *[str(x) for x in args]]


def call(ctx: StepContext, cmd: list[str]) -> None:
    from .utils import run
    run(cmd, cwd=PROJECT, log=ctx.log)


def add_optional(cmd: list[str], flag: str, value) -> None:
    if value is not None:
        cmd += [flag, str(value)]


def step_demo_data(ctx: StepContext, accept_auto: bool) -> dict:
    if ctx.cfg["mode"] != "demo":
        return {"skipped": "not demo"}
    call(ctx, module("create_demo_data", "--output-dir", ctx.root / "raw", "--seed", ctx.cfg["seed"]))
    return {"raw": str(ctx.root / "raw")}


def step_download_utd19(ctx: StepContext, accept_auto: bool) -> dict:
    if ctx.cfg["mode"] == "demo":
        return {"skipped": "demo data"}
    call(ctx, module("download_utd19", "--output-dir", ctx.dirs["raw/utd19"]))
    return {"measurements": str(ctx.dirs["raw/utd19"] / "utd19_u.csv")}


def step_preprocess_utd19(ctx: StepContext, accept_auto: bool) -> dict:
    cfg = ctx.cfg["utd19"]
    raw = ctx.dirs["raw/utd19"]
    cmd = module(
        "preprocess_utd19", "--measurements", raw / "utd19_u.csv",
        "--detectors", raw / "detectors.csv", "--links", raw / "links.csv",
        "--output-dir", ctx.dirs["processed/utd19"],
        "--target-mode", cfg["target_mode"], "--aggregation", cfg["hourly_aggregation"],
        "--threads", 2, "--memory-limit", "8GB",
    )
    if cfg.get("strict_error_filter", True):
        cmd += ["--strict-error-filter"]
    city_features = raw / "city_features.csv"
    if cfg.get("include_city_features") and city_features.exists():
        cmd += ["--city-features", str(city_features)]
    call(ctx, cmd)
    return {"model_table": str(ctx.dirs["processed/utd19"] / "utd19_model_table.parquet")}


def step_train(ctx: StepContext, accept_auto: bool) -> dict:
    cfg = ctx.cfg["utd19"]
    cmd = module(
        "train_models", "--data", ctx.dirs["processed/utd19"] / "utd19_model_table.parquet",
        "--output-dir", ctx.dirs["models"], "--seed", ctx.cfg["seed"],
        "--polynomial-max-rows", cfg.get("polynomial_max_rows", 500000),
        "--linear-svm-max-rows", cfg.get("linear_svm_max_rows"),
        "--random-forest-trees", cfg.get("random_forest_trees", 200),
    )
    add_optional(cmd, "--base-max-rows", cfg.get("model_max_rows"))
    add_optional(cmd, "--random-forest-max-rows", cfg.get("random_forest_max_rows"))
    call(ctx, cmd)
    return {"random_forest": str(ctx.dirs["models"] / "random_forest_for_berlin.joblib")}


def step_download_berlin(ctx: StepContext, accept_auto: bool) -> dict:
    if ctx.cfg["mode"] == "demo":
        return {"skipped": "demo data"}
    cfg = ctx.cfg["berlin"]
    call(ctx, module(
        "download_berlin", "--output-dir", ctx.dirs["raw/berlin"],
        "--year", cfg["year"], "--month", cfg["month"],
        "--branch-regex", cfg["archive_branch_regex"],
    ))
    return {"raw": str(ctx.dirs["raw/berlin"])}


def step_preprocess_berlin(ctx: StepContext, accept_auto: bool) -> dict:
    cfg = ctx.cfg["berlin"]
    cmd = module(
        "preprocess_berlin", "--raw-dir", ctx.dirs["raw/berlin"],
        "--locations", ctx.dirs["raw/berlin"] / "teu_standorte.json",
        "--output-dir", ctx.dirs["processed/berlin"],
        "--year", cfg["year"], "--month", cfg["month"],
        "--actual-dates", *cfg.get("actual_dates", []),
        "--valid-quality", *cfg.get("quality_valid_values", [1]),
        "--minimum-id-match-ratio", cfg.get("minimum_id_match_ratio", 0.5),
    )
    add_optional(cmd, "--max-detectors", cfg.get("max_detectors"))
    if cfg.get("detector_ids"):
        cmd += ["--detector-ids", *[str(x) for x in cfg["detector_ids"]]]
    call(ctx, cmd)
    return {"actual": str(ctx.dirs["processed/berlin"] / "berlin_actual.parquet")}


def step_download_osm(ctx: StepContext, accept_auto: bool) -> dict:
    if ctx.cfg["mode"] == "demo":
        return {"skipped": "demo network"}
    call(ctx, module(
        "download_osm", "--url", ctx.cfg["osm"]["source_url"],
        "--output", ctx.dirs["raw/osm"] / "berlin-latest.osm.pbf",
    ))
    return {"pbf": str(ctx.dirs["raw/osm"] / "berlin-latest.osm.pbf")}


def step_network(ctx: StepContext, accept_auto: bool) -> dict:
    cmd = module(
        "build_network", "--pbf", ctx.dirs["raw/osm"] / "berlin-latest.osm.pbf",
        "--output-dir", ctx.dirs["sumo/network"],
    )
    if ctx.cfg["mode"] == "demo":
        cmd += ["--demo-nodes", PROJECT / "demo/demo.nod.xml", "--demo-edges", PROJECT / "demo/demo.edg.xml"]
    elif ctx.cfg["osm"].get("clip_to_detector_bbox"):
        cmd += [
            "--clip", "--locations", ctx.dirs["processed/berlin"] / "berlin_locations.csv",
            "--buffer-km", ctx.cfg["osm"].get("detector_bbox_buffer_km", 4),
        ]
    call(ctx, cmd)
    call(ctx, module(
        "network_stats", "--net", ctx.dirs["sumo/network"] / "berlin.net.xml",
        "--output", ctx.dirs["sumo/network"] / "network_stats.json",
    ))
    return {
        "network": str(ctx.dirs["sumo/network"] / "berlin.net.xml"),
        "stats": str(ctx.dirs["sumo/network"] / "network_stats.json"),
    }


def step_mapping(ctx: StepContext, accept_auto: bool) -> dict:
    out = ctx.dirs["sumo/mapping"]
    accepted = out / "mapping_accepted.csv"
    if ctx.cfg["mode"] == "demo":
        shutil.copy2(PROJECT / "demo/demo_mapping.csv", accepted)
        return {"mapping": str(accepted), "mode": "bundled demo mapping"}
    cfg = ctx.cfg["mapping"]
    cmd = module(
        "map_detectors", "--net", ctx.dirs["sumo/network"] / "berlin.net.xml",
        "--locations", ctx.dirs["processed/berlin"] / "berlin_locations.csv",
        "--output-dir", out, "--radius", cfg["search_radius_m"],
        "--max-candidates", cfg["max_candidates"],
        "--distance-weight", cfg["distance_weight"],
        "--direction-weight", cfg["direction_weight"], "--name-weight", cfg["name_weight"],
    )
    if accept_auto:
        cmd += ["--accept-auto"]
    call(ctx, cmd)
    if not accepted.exists():
        raise RuntimeError(
            f"Manual mapping gate reached. Open {out / 'mapping_review.html'}, edit/copy "
            f"{out / 'mapping_review_template.csv'} to {accepted}, then rerun from mapping. "
            "For an unreviewed automated run, add --accept-auto-mapping."
        )
    call(ctx, module(
        "validate_mapping", "--net", ctx.dirs["sumo/network"] / "berlin.net.xml",
        "--mapping", accepted, "--output-dir", out,
    ))
    return {"mapping": str(accepted), "validation": str(out / "mapping_validation_summary.json")}


def step_features(ctx: StepContext, accept_auto: bool) -> dict:
    end_hour = min(24, int(ctx.cfg["simulation"]["end"]) // 3600)
    call(ctx, module(
        "build_berlin_features", "--mapping", ctx.dirs["sumo/mapping"] / "mapping_accepted.csv",
        "--prediction-date", ctx.cfg["berlin"]["prediction_date"],
        "--output-dir", ctx.dirs["processed/berlin"], "--begin-hour", 0, "--end-hour", end_hour,
    ))
    return {"features": str(ctx.dirs["processed/berlin"] / "berlin_features.parquet")}


def step_predict(ctx: StepContext, accept_auto: bool) -> dict:
    call(ctx, module(
        "predict_berlin", "--model", ctx.dirs["models"] / "random_forest_for_berlin.joblib",
        "--protocol", ctx.dirs["models"] / "training_protocol.json",
        "--features", ctx.dirs["processed/berlin"] / "berlin_features.parquet",
        "--actual", ctx.dirs["processed/berlin"] / "berlin_actual.parquet",
        "--output-dir", ctx.dirs["processed/berlin"],
    ))
    return {"predictions": str(ctx.dirs["processed/berlin"] / "berlin_predictions.csv")}


def step_taz(ctx: StepContext, accept_auto: bool) -> dict:
    call(ctx, module(
        "create_taz", "--net", ctx.dirs["sumo/network"] / "berlin.net.xml",
        "--output-dir", ctx.dirs["sumo/candidates"],
        "--grid-m", ctx.cfg["candidates"]["taz_grid_m"],
    ))
    return {"taz": str(ctx.dirs["sumo/candidates"] / "berlin.taz.xml")}


def step_candidates(ctx: StepContext, accept_auto: bool) -> dict:
    cfg = ctx.cfg["candidates"]
    call(ctx, module(
        "generate_candidates", "--net", ctx.dirs["sumo/network"] / "berlin.net.xml",
        "--mapping", ctx.dirs["sumo/mapping"] / "mapping_accepted.csv",
        "--taz", ctx.dirs["sumo/candidates"] / "berlin.taz.xml",
        "--edge-to-taz", ctx.dirs["sumo/candidates"] / "edge_to_taz.csv",
        "--output-dir", ctx.dirs["sumo/candidates"],
        "--random-count", cfg["random_route_count"], "--taz-count", cfg["taz_route_count"],
        "--coverage-per-detector", cfg["coverage_routes_per_detector"],
        "--begin", ctx.cfg["simulation"]["begin"], "--end", ctx.cfg["simulation"]["end"],
        "--seed", ctx.cfg["seed"], "--random-factor", cfg["routing_random_factor"],
    ))
    return {"candidate_manifest": str(ctx.dirs["sumo/candidates"] / "candidate_manifest.json")}


def candidate_routes(ctx: StepContext) -> list[str]:
    manifest = read_json(ctx.dirs["sumo/candidates"] / "candidate_manifest.json", {})
    return manifest.get("route_files", [
        str(ctx.dirs["sumo/candidates"] / "random.routes.xml"),
        str(ctx.dirs["sumo/candidates"] / "taz.routes.xml"),
        str(ctx.dirs["sumo/candidates"] / "coverage.routes.xml"),
    ])


def step_coverage(ctx: StepContext, accept_auto: bool) -> dict:
    call(ctx, module(
        "coverage_audit", "--mapping", ctx.dirs["sumo/mapping"] / "mapping_accepted.csv",
        "--route-files", *candidate_routes(ctx), "--output-dir", ctx.dirs["sumo/candidates"],
        "--require-complete",
    ))
    return {"coverage": str(ctx.dirs["sumo/candidates"] / "candidate_coverage_summary.json")}


def step_counts(ctx: StepContext, accept_auto: bool) -> dict:
    call(ctx, module(
        "counts_to_edgedata", "--predictions", ctx.dirs["processed/berlin"] / "berlin_predictions.csv",
        "--mapping", ctx.dirs["sumo/mapping"] / "mapping_accepted.csv",
        "--output-dir", ctx.dirs["sumo/calibration"],
        "--merge", ctx.cfg["route_sampler"]["merge_same_edge"],
        "--scale-counts", ctx.cfg["simulation"]["scale_counts"],
        "--begin", ctx.cfg["simulation"]["begin"], "--end", ctx.cfg["simulation"]["end"],
    ))
    return {"counts": str(ctx.dirs["sumo/calibration"] / "predicted_edge_counts.xml")}


def step_calibrate(ctx: StepContext, accept_auto: bool) -> dict:
    cfg = ctx.cfg["route_sampler"]
    cmd = module(
        "calibrate", "--route-files", *candidate_routes(ctx),
        "--counts", ctx.dirs["sumo/calibration"] / "predicted_edge_counts.xml",
        "--output-dir", ctx.dirs["sumo/calibration"],
        "--optimize", cfg["optimize"], "--threads", cfg["threads"],
        "--seed", ctx.cfg["seed"], "--begin", ctx.cfg["simulation"]["begin"],
        "--end", ctx.cfg["simulation"]["end"], "--interval", 3600,
    )
    if cfg.get("write_flows"):
        cmd += ["--write-flows", cfg["write_flows"]]
    call(ctx, cmd)
    call(ctx, module(
        "parse_route_sampler_log", "--log", ctx.dirs["sumo/calibration"] / "route_sampler.log",
        "--output-dir", ctx.dirs["sumo/calibration"],
    ))
    return {
        "routes": str(ctx.dirs["sumo/calibration"] / "calibrated.rou.xml"),
        "route_sampler_summary": str(ctx.dirs["sumo/calibration"] / "route_sampler_summary.json"),
    }


def step_build_sim(ctx: StepContext, accept_auto: bool) -> dict:
    cfg = ctx.cfg["simulation"]
    call(ctx, module(
        "build_simulation", "--net", ctx.dirs["sumo/network"] / "berlin.net.xml",
        "--routes", ctx.dirs["sumo/calibration"] / "calibrated.rou.xml",
        "--mapping", ctx.dirs["sumo/mapping"] / "mapping_accepted.csv",
        "--output-dir", ctx.dirs["sumo/simulation"],
        "--begin", cfg["begin"], "--end", cfg["end"], "--step-length", cfg["step_length"],
        "--time-to-teleport", cfg["time_to_teleport"], "--seed", ctx.cfg["seed"],
        "--gui-delay-ms", cfg["gui_delay_ms"],
    ))
    return {"config": str(ctx.dirs["sumo/simulation"] / "berlin.sumocfg")}


def step_run_sim(ctx: StepContext, accept_auto: bool) -> dict:
    call(ctx, module(
        "run_simulation", "--config", ctx.dirs["sumo/simulation"] / "berlin.sumocfg",
        "--output-dir", ctx.dirs["sumo/simulation"],
    ))
    return {"summary": str(ctx.dirs["sumo/simulation"] / "summary.xml")}


def step_extract(ctx: StepContext, accept_auto: bool) -> dict:
    call(ctx, module(
        "extract_simulated_counts", "--edge-data", ctx.dirs["sumo/simulation"] / "simulated_edge_counts.xml",
        "--mapping", ctx.dirs["sumo/mapping"] / "mapping_accepted.csv",
        "--summary", ctx.dirs["sumo/simulation"] / "summary.xml",
        "--statistics", ctx.dirs["sumo/simulation"] / "statistics.xml",
        "--output-dir", ctx.dirs["reports"],
    ))
    return {"simulated_counts": str(ctx.dirs["reports"] / "simulated_edge_counts.csv")}


def step_evaluate(ctx: StepContext, accept_auto: bool) -> dict:
    cmd = module(
        "evaluate", "--predictions", ctx.dirs["processed/berlin"] / "berlin_predictions.csv",
        "--edge-predictions", ctx.dirs["sumo/calibration"] / "edge_predictions.csv",
        "--actual", ctx.dirs["processed/berlin"] / "berlin_actual.parquet",
        "--simulated-edge", ctx.dirs["reports"] / "simulated_edge_counts.csv",
        "--simulated-detector", ctx.dirs["reports"] / "simulated_detector_counts.csv",
        "--output-dir", ctx.dirs["reports"],
    )
    network = ctx.dirs["reports"] / "network_hourly_summary.csv"
    if network.exists():
        cmd += ["--network-summary", network]
    cmd += [
        "--network-stats", ctx.dirs["sumo/network"] / "network_stats.json",
        "--extraction-audit", ctx.dirs["reports"] / "extraction_audit.json",
        "--route-sampler-summary", ctx.dirs["sumo/calibration"] / "route_sampler_summary.json",
    ]
    call(ctx, cmd)
    return {"evaluation": str(ctx.dirs["reports"] / "final_evaluation.json")}


def step_bundle(ctx: StepContext, accept_auto: bool) -> dict:
    call(ctx, module(
        "package_gui", "--simulation-dir", ctx.dirs["sumo/simulation"],
        "--reports-dir", ctx.dirs["reports"], "--output-dir", ctx.dirs["gui_bundle"],
    ))
    return {"gui_zip": str(ctx.dirs["gui_bundle"]) + ".zip"}


STEPS: list[tuple[str, Callable[[StepContext, bool], dict]]] = [
    ("00_demo_data", step_demo_data),
    ("01_download_utd19", step_download_utd19),
    ("02_preprocess_utd19", step_preprocess_utd19),
    ("03_train_models", step_train),
    ("04_download_berlin", step_download_berlin),
    ("05_preprocess_berlin", step_preprocess_berlin),
    ("06_download_osm", step_download_osm),
    ("07_build_network", step_network),
    ("08_map_detectors", step_mapping),
    ("09_build_berlin_features", step_features),
    ("10_predict_berlin", step_predict),
    ("11_create_taz", step_taz),
    ("12_generate_candidates", step_candidates),
    ("13_coverage_audit", step_coverage),
    ("14_predicted_counts", step_counts),
    ("15_route_sampler", step_calibrate),
    ("16_build_simulation", step_build_sim),
    ("17_run_simulation", step_run_sim),
    ("18_extract_outputs", step_extract),
    ("19_evaluate", step_evaluate),
    ("20_package_gui", step_bundle),
]


def main() -> None:
    parser = argparse.ArgumentParser(description="End-to-end paper-faithful UTD19→Berlin→SUMO pipeline")
    parser.add_argument("--config", required=True)
    parser.add_argument("--from-step")
    parser.add_argument("--to-step")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--accept-auto-mapping", action="store_true")
    parser.add_argument("--list-steps", action="store_true")
    args = parser.parse_args()

    if args.list_steps:
        for name, _ in STEPS:
            print(name)
        return
    cfg = load_config(args.config)
    root = workspace(cfg)
    dirs = ensure_dirs(root)
    names = [name for name, _ in STEPS]
    start = names.index(args.from_step) if args.from_step else 0
    end = names.index(args.to_step) if args.to_step else len(STEPS) - 1
    if start > end:
        raise ValueError("--from-step comes after --to-step")

    print(f"Project: {PROJECT}\nWorkspace: {root}\nMode: {cfg['mode']}")
    for index, (name, function) in enumerate(STEPS):
        if index < start or index > end:
            continue
        ctx = StepContext(cfg=cfg, root=root, dirs=dirs, step=name)
        if cfg.get("resume", True) and ctx.done() and not args.force:
            print(f"[SKIP] {name} (checkpoint exists)")
            continue
        print(f"\n===== {name} =====")
        outputs = function(ctx, args.accept_auto_mapping)
        ctx.mark_done(outputs)
        print(f"[DONE] {name}: {outputs}")
    print(f"\nPipeline finished through: {names[end]}")


if __name__ == "__main__":
    main()
