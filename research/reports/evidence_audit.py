#!/usr/bin/env python3
"""Audit the rebuild evidence contract.

This is intentionally lightweight: it does not call APIs, run SUMO, or train a
model. It only reads the artifacts that the pipelines have already produced and
labels each part as PASS, FAIL, or PENDING.

    python research/reports/evidence_audit.py
"""
from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
DEFAULT_JSON = REPO / "results/evidence_audit.json"
DEFAULT_MD = REPO / "results/evidence_audit.md"


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text())


def row(name: str, status: str, artifact: Path, check: str, details: str) -> dict[str, str]:
    return {
        "name": name,
        "status": status,
        "artifact": str(artifact),
        "check": check,
        "details": details,
    }


def audit_twin(repo: Path) -> dict[str, str]:
    path = repo / "data/forecasting/dhaka_twin/MANIFEST.json"
    manifest = load_json(path)
    if not manifest:
        return row("Dhaka twin prediction data", "PENDING", path, "manifest exists", "dataset not generated")
    verdict = manifest.get("acceptance", {}).get("verdict")
    label = manifest.get("label") or manifest.get("evidence_domain")
    seeds = manifest.get("seeds", [])
    shape = manifest.get("data_npz", {}).get("data_shape") or manifest.get("shape")
    ok = verdict == "PASS" and label == "DHAKA_SIMULATED_SENSOR_GRAPH" and len(seeds) >= 3
    status = "PASS" if ok else "FAIL"
    details = f"label={label}; acceptance={verdict}; seeds={len(seeds)}; shape={shape}"
    return row("Dhaka twin prediction data", status, path, "PASS manifest, labelled simulated, >=3 seeds", details)


def audit_twin_floors(repo: Path) -> dict[str, str]:
    path = repo / "results/forecasting/twin_floors.json"
    rep = load_json(path)
    if not rep:
        return row("Prediction floors", "PENDING", path, "baseline forecast file exists", "not produced")
    models = sorted(rep.get("models", {}).keys())
    horizons = rep.get("horizons_min", [])
    ok = {"persistence", "historical_average"}.issubset(models) and len(horizons) >= 4
    status = "PASS" if ok else "FAIL"
    return row("Prediction floors", status, path, "persistence and historical-average at 4 horizons",
               f"models={models}; horizons_min={horizons}")


def audit_colab_benchmark(repo: Path) -> dict[str, str]:
    csv_path = repo / "results/forecasting/benchmark.csv"
    md_path = repo / "results/forecasting/benchmark.md"
    if not csv_path.exists() and not md_path.exists():
        return row("Colab BasicTS benchmark", "PENDING", csv_path,
                   "real benchmark table copied from Drive", "run the Colab notebook, then pull results")
    if csv_path.exists():
        with csv_path.open(newline="") as fh:
            rows = list(csv.DictReader(fh))
        models = {r.get("model", "") for r in rows}
        datasets = {r.get("dataset", "") for r in rows}
        status = "PASS" if rows and models and datasets else "FAIL"
        return row("Colab BasicTS benchmark", status, csv_path,
                   "non-empty model x dataset table", f"rows={len(rows)}; models={sorted(models)}; datasets={sorted(datasets)}")
    return row("Colab BasicTS benchmark", "PASS", md_path, "benchmark markdown exists",
               "CSV not present; markdown will be shown in RESULTS")


def audit_routing(repo: Path) -> dict[str, str]:
    path = repo / "results/routing/decision_guard.json"
    decision = load_json(path)
    if not decision:
        return row("Routing decision guard", "PENDING", path, "decision artifact exists", "run make route")
    evals = decision.get("deployable_evaluations", [])
    accepted = [ev for ev in evals if ev.get("accepted")]
    honest_block = decision.get("decision") == "NO_SAFE_ROUTING_ACTION" and bool(evals)
    status = "PASS" if (decision.get("decision") == "ACT" and accepted) or honest_block else "FAIL"
    details = (
        f"decision={decision.get('decision')}; selected={decision.get('selected_arm')}; "
        f"benefit_total_vehicle_hours={decision.get('selected_mean_total_vehicle_hours_benefit_pct')}"
    )
    return row("Routing decision guard", status, path,
               "appendix simulation either selects a safe arm or honestly blocks unsafe action", details)


def audit_live_reference(repo: Path) -> dict[str, str]:
    path = repo / "results/artifacts/p_live/live_reference_summary.json"
    summary = load_json(path)
    if not summary:
        return row("Live Google reference", "PENDING", path, "runtime reference summary exists",
                   "run make live-summary or make live-capture")
    latest = summary.get("latest", [])
    no_content = all(not rec.get("route_content_persisted") for rec in latest)
    ok = (
        summary.get("honesty_label") == "EXTERNAL_LIVE_REFERENCE_NOT_TRAINING_DATA"
        and summary.get("latest_corridors", 0) > 0
        and no_content
    )
    status = "PASS" if ok else "FAIL"
    details = (
        f"corridors={summary.get('latest_corridors')}; states={summary.get('state_counts')}; "
        f"route_content_persisted={not no_content}"
    )
    return row("Live Google reference", status, path,
               "live/reference only, no Google route content persisted", details)


def audit_live_route_advice(repo: Path) -> dict[str, str]:
    path = repo / "live/results/route_advice.jsonl"
    if not path.exists():
        return row("Real route advisor", "PENDING", path, "live advisory metadata exists",
                   "run python live/route_advisor.py --live --yes --corridor farmgate_to_shahbagh")
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    banned = {"duration_s", "static_duration_s", "distance_m", "polyline", "encodedPolyline"}
    real_rows = [r for r in rows if r.get("reality") == "REAL_LIVE"]
    no_content = all(
        r.get("google_data_mode") == "RUNTIME_REFERENCE"
        and r.get("route_content_persisted") is False
        and not (set(r) & banned)
        for r in rows
    )
    status = "PASS" if real_rows and no_content else "FAIL"
    details = f"rows={len(rows)}; real_rows={len(real_rows)}; route_content_persisted={not no_content}"
    return row("Real route advisor", status, path,
               "real live advisory exists and stores no Google route content", details)


def audit_user_pilot(repo: Path) -> dict[str, str]:
    path = repo / "live/results/pilot_metrics.json"
    summary = load_json(path)
    if not summary:
        return row("Real user pilot", "PENDING", path, "completed trip metrics exist",
                   "run live/user_trip_logger.py start/complete for the 3 users")
    ok = (
        summary.get("honesty_label") == "REAL_USER_PILOT_SMALL_SAMPLE_NO_GOOGLE_ROUTE_CONTENT_STORED"
        and summary.get("route_content_persisted") is False
        and summary.get("completed_trips", 0) > 0
    )
    status = "PASS" if ok else "FAIL"
    details = (
        f"completed_trips={summary.get('completed_trips')}; "
        f"participants={summary.get('participants')}; "
        f"mean_actual_elapsed_s={summary.get('mean_actual_elapsed_s')}"
    )
    return row("Real user pilot", status, path,
               "real user trip timestamps, no fixed seeds", details)


def audit_asset_manifest(repo: Path) -> dict[str, str]:
    path = repo / "docs/ASSET_MANIFEST.json"
    manifest = load_json(path)
    if not manifest:
        return row("Asset bootstrap manifest", "PENDING", path, "asset manifest exists",
                   "run python research/reports/build_asset_manifest.py")
    assets = manifest.get("assets", [])
    missing = manifest.get("missing_when_manifest_built", [])
    ok = manifest.get("schema") == "dhakaflow.asset-manifest.v1" and assets and not missing
    status = "PASS" if ok else "FAIL"
    details = f"assets={len(assets)}; missing_when_built={len(missing)}"
    return row("Asset bootstrap manifest", status, path, "manifest has assets and no missing entries", details)


def audit_network(repo: Path) -> dict[str, str]:
    path = repo / "results/networking/penetration.csv"
    if not path.exists():
        return row("V2X networking sweep", "PENDING", path, "penetration sweep CSV exists", "run make network")
    lines = [ln for ln in path.read_text().splitlines() if ln.strip()]
    status = "PASS" if len(lines) > 1 else "FAIL"
    return row("V2X networking sweep", status, path, "non-empty penetration table", f"rows={max(len(lines) - 1, 0)}")


def audit_nlp(repo: Path) -> dict[str, str]:
    path = repo / "results/nlp/classifier.json"
    rep = load_json(path)
    if not rep:
        return row("NLP incident classifier", "PENDING", path, "classifier result exists", "run make nlp")
    status = "PASS" if rep else "FAIL"
    metric_keys = sorted(k for k in rep.keys() if "f1" in k.lower() or "accuracy" in k.lower())
    return row("NLP incident classifier", status, path, "classifier metrics JSON exists",
               f"metric_keys={metric_keys or sorted(rep.keys())[:6]}")


def overall_status(rows: list[dict[str, str]]) -> str:
    statuses = {r["status"] for r in rows}
    if "FAIL" in statuses:
        return "FAIL"
    if "PENDING" in statuses:
        return "PASS_WITH_PENDING_ITEMS"
    return "PASS"


def write_markdown(path: Path, report: dict[str, Any], repo: Path) -> None:
    lines = [
        "# Evidence Audit",
        "",
        f"Generated UTC: `{report['generated_utc']}`.",
        f"Overall status: **{report['overall_status']}**.",
        "",
        "| area | status | artifact | check | details |",
        "|---|---|---|---|---|",
    ]
    for r in report["rows"]:
        artifact = Path(r["artifact"])
        rel = artifact.relative_to(repo) if artifact.is_absolute() and artifact.is_relative_to(repo) else artifact
        details = r["details"].replace("|", "\\|")
        lines.append(f"| {r['name']} | {r['status']} | `{rel}` | {r['check']} | {details} |")
    lines += [
        "",
        "Reality rule: live Google data is used only as runtime/reference evidence, "
        "not as cached training data. Dhaka twin sensor data is simulated on the real frozen R1 topology "
        "and must not be described as real sensor measurements.",
        "The `live/` route-advisor and user-pilot path is the no-fixed-seed real-world evidence path.",
        "",
    ]
    path.write_text("\n".join(lines))


def build_report(repo: Path) -> dict[str, Any]:
    rows = [
        audit_twin(repo),
        audit_twin_floors(repo),
        audit_colab_benchmark(repo),
        audit_routing(repo),
        audit_live_reference(repo),
        audit_live_route_advice(repo),
        audit_user_pilot(repo),
        audit_asset_manifest(repo),
        audit_network(repo),
        audit_nlp(repo),
    ]
    return {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "overall_status": overall_status(rows),
        "rows": rows,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", type=Path, default=REPO)
    ap.add_argument("--out-json", type=Path, default=DEFAULT_JSON)
    ap.add_argument("--out-md", type=Path, default=DEFAULT_MD)
    args = ap.parse_args()

    repo = args.repo.resolve()
    report = build_report(repo)
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(report, indent=1))
    write_markdown(args.out_md, report, repo)
    print(json.dumps({"overall_status": report["overall_status"], "artifact": str(args.out_md)}, indent=1))
    return 1 if report["overall_status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
