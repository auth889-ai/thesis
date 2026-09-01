#!/usr/bin/env python3
"""Summarize compliant live/reference traffic captures.

The Google live-capture path persists only request metadata and our derived
congestion bucket, not route durations, geometry, speed intervals, or other
Google route content. This script keeps that boundary and emits a small summary
for the thesis results index.

    python predict/summarize_live_reference.py
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = REPO / "artifacts/p_live/normalized/google_routes_runtime_reference.jsonl"
DEFAULT_JSON = REPO / "artifacts/p_live/live_reference_summary.json"
DEFAULT_MD = REPO / "artifacts/p_live/live_reference_summary.md"


def load_records(path: Path) -> list[dict]:
    if not path.exists():
        return []
    records = []
    for line in path.read_text().splitlines():
        if line.strip():
            records.append(json.loads(line))
    records.sort(key=lambda r: r.get("captured_utc", ""))
    return records


def latest_unique_corridors(records: list[dict]) -> list[dict]:
    latest: dict[str, dict] = {}
    for rec in records:
        cid = rec.get("corridor_id")
        if cid:
            latest[cid] = rec
    return sorted(latest.values(), key=lambda r: r.get("corridor_id", ""))


def write_markdown(path: Path, summary: dict) -> None:
    lines = [
        "# Live Reference Summary",
        "",
        f"Source: `{summary['source']}`.",
        f"Generated UTC: `{summary['generated_utc']}`.",
        f"Google data mode: `{summary['google_data_mode']}`.",
        "",
        "This summary stores only request metadata and derived congestion states.",
        "It does not store Google route geometry, route durations, speed intervals, or training data.",
        "",
        f"Latest captured corridors: **{summary['latest_corridors']}**.",
        f"Latest congested/severe corridors: **{summary['latest_congested_or_severe']}**.",
        "",
        "| corridor | captured UTC | state | latency ms | route content persisted |",
        "|---|---|---|---:|---|",
    ]
    for row in summary["latest"]:
        lines.append(
            f"| {row['corridor_id']} | {row['captured_utc']} | "
            f"{row['congestion_state']} | {row['request_latency_ms']} | "
            f"{row['route_content_persisted']} |"
        )
    lines += ["", "State counts: " + json.dumps(summary["state_counts"], sort_keys=True), ""]
    path.write_text("\n".join(lines))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    ap.add_argument("--out-json", type=Path, default=DEFAULT_JSON)
    ap.add_argument("--out-md", type=Path, default=DEFAULT_MD)
    args = ap.parse_args()

    records = load_records(args.source)
    latest = latest_unique_corridors(records)
    counts = Counter(row.get("congestion_state", "UNKNOWN") for row in latest)
    congested = sum(counts[s] for s in ("CONGESTED", "SEVERE"))
    summary = {
        "stage": "LIVE_REFERENCE_SUMMARY",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "source": str(args.source),
        "total_reference_rows": len(records),
        "latest_corridors": len(latest),
        "latest_congested_or_severe": congested,
        "state_counts": dict(sorted(counts.items())),
        "google_data_mode": "RUNTIME_REFERENCE",
        "honesty_label": "EXTERNAL_LIVE_REFERENCE_NOT_TRAINING_DATA",
        "latest": latest,
    }
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(summary, indent=1))
    write_markdown(args.out_md, summary)
    print(json.dumps({
        "latest_corridors": summary["latest_corridors"],
        "latest_congested_or_severe": summary["latest_congested_or_severe"],
        "state_counts": summary["state_counts"],
        "artifact": str(args.out_md),
    }, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
