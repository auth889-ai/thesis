#!/usr/bin/env python3
"""Build the reproducibility asset manifest.

The manifest records small-to-medium artifacts needed for the active rebuild
evidence path. It intentionally excludes bulky regenerable run XML/FCD outputs.

    python results/build_asset_manifest.py
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_OUT = REPO / "docs/ASSET_MANIFEST.json"

EXACT_FILES = [
    "paper_labs/02_dhaka_osm/outputs/lab02_v2/network/dhaka_r1.net.xml",
    "results/artifacts/due_dso_stats/v200/DUE/003/trips_003.rou.xml.gz",
    "data/forecasting/dhaka_twin/MANIFEST.json",
    "data/forecasting/dhaka_twin/data.npz",
    "data/forecasting/dhaka_twin/sensor_graph_data.npz",
    "data/forecasting/dhaka_twin/adj_mx.pkl",
    "data/forecasting/dhaka_twin/sensor_nodes.json",
    "data/forecasting/dhaka_twin/basicts_legacy/data.dat",
    "data/forecasting/dhaka_twin/basicts_legacy/desc.json",
    "data/forecasting/dhaka_twin/basicts_legacy/adj_mx.pkl",
    "data/forecasting/dhaka_twin/basicts_v1/DESC.json",
    "data/forecasting/dhaka_twin/basicts_v1/adj_mx.npy",
    "data/forecasting/dhaka_twin/basicts_v1/train_data.npy",
    "data/forecasting/dhaka_twin/basicts_v1/train_timestamps.npy",
    "data/forecasting/dhaka_twin/basicts_v1/val_data.npy",
    "data/forecasting/dhaka_twin/basicts_v1/val_timestamps.npy",
    "data/forecasting/dhaka_twin/basicts_v1/test_data.npy",
    "data/forecasting/dhaka_twin/basicts_v1/test_timestamps.npy",
    "results/forecasting/twin_floors.json",
    "results/forecasting/twin_floors.md",
    "results/routing/arms_h7200.json",
    "results/routing/stats.json",
    "results/routing/stats.md",
    "results/routing/decision_guard.json",
    "results/routing/decision_guard.md",
    "results/networking/penetration.csv",
    "results/networking/penetration.md",
    "results/networking/latency.csv",
    "results/networking/latency.md",
    "results/nlp/classifier.json",
    "results/nlp/classifier.md",
    "results/nlp/events.jsonl",
    "results/artifacts/p_live/live_reference_summary.json",
    "results/artifacts/p_live/live_reference_summary.md",
    "results/artifacts/p_live/normalized/google_routes_runtime_reference.jsonl",
]

GLOB_FILES = [
    "results/networking/penetration_p*_s*.json",
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def category(rel: str) -> str:
    if rel.startswith("paper_labs/"):
        return "frozen-network"
    if rel.startswith("results/artifacts/due_dso_stats/"):
        return "demand"
    if rel.startswith("data/forecasting/"):
        return "prediction-data"
    if rel.startswith("results/forecasting/"):
        return "prediction-results"
    if rel.startswith("results/routing/"):
        return "routing-results"
    if rel.startswith("results/networking/"):
        return "networking-results"
    if rel.startswith("results/nlp/"):
        return "nlp-results"
    if rel.startswith("results/artifacts/p_live/"):
        return "live-reference"
    if rel.startswith("results/"):
        return "evidence-index"
    return "misc"


def iter_manifest_paths(repo: Path) -> list[Path]:
    paths = [repo / rel for rel in EXACT_FILES]
    for pattern in GLOB_FILES:
        paths.extend(sorted(repo.glob(pattern)))
    return sorted(set(paths), key=lambda p: str(p.relative_to(repo)))


def build_manifest(repo: Path) -> dict:
    assets = []
    missing = []
    for path in iter_manifest_paths(repo):
        rel = str(path.relative_to(repo))
        if not path.exists():
            missing.append(rel)
            continue
        assets.append({
            "path": rel,
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
            "category": category(rel),
            "required_for": "make results / active rebuild demo",
        })
    return {
        "schema": "dhakaflow.asset-manifest.v1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "asset_root_hint": "Set DHAKAFLOW_ASSET_ROOT to a Drive/S3/GCS-exported local folder that mirrors these relative paths.",
        "excludes": [
            "results/routing/*/tripinfo.xml",
            "results/routing/*/edgedata.xml",
            "results/routing/*/statistic.xml",
            "large model checkpoints",
            "raw datasets",
            "API keys or .env files",
        ],
        "assets": assets,
        "missing_when_manifest_built": missing,
    }


def write_markdown(path: Path, manifest: dict) -> None:
    md = path.with_suffix(".md")
    lines = [
        "# Asset Manifest",
        "",
        f"Generated UTC: `{manifest['generated_utc']}`.",
        "",
        "This manifest covers the active rebuild evidence path only. It excludes bulky SUMO XML outputs, raw datasets, model weights, and secrets.",
        "",
        "| category | files | bytes |",
        "|---|---:|---:|",
    ]
    by_cat: dict[str, list[dict]] = {}
    for asset in manifest["assets"]:
        by_cat.setdefault(asset["category"], []).append(asset)
    for cat in sorted(by_cat):
        rows = by_cat[cat]
        lines.append(f"| {cat} | {len(rows)} | {sum(r['bytes'] for r in rows)} |")
    if manifest["missing_when_manifest_built"]:
        lines += ["", "Missing when built:", ""]
        lines.extend(f"- `{p}`" for p in manifest["missing_when_manifest_built"])
    lines += [
        "",
        "Restore/check command:",
        "",
        "```bash",
        "DHAKAFLOW_ASSET_ROOT=/path/to/DhakaFlow-assets bash download_assets.sh",
        "```",
        "",
    ]
    md.write_text("\n".join(lines))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", type=Path, default=REPO)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()

    manifest = build_manifest(args.repo.resolve())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(manifest, indent=1))
    write_markdown(args.out, manifest)
    print(json.dumps({
        "assets": len(manifest["assets"]),
        "missing": len(manifest["missing_when_manifest_built"]),
        "artifact": str(args.out),
    }, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
