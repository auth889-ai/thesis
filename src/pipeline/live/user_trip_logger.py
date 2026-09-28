#!/usr/bin/env python3
"""Log a small real-user pilot trip without fixed seeds.

The logger stores user-owned trip timestamps and advice metadata. It does not
store Google route durations, distances, route geometry, or private raw
coordinates. Use the route advisor first, then start/complete a trip:

    python live/route_advisor.py --live --yes --corridor farmgate_to_shahbagh
    python live/user_trip_logger.py start --participant p1 --advice-id <id> --corridor farmgate_to_shahbagh
    python live/user_trip_logger.py complete --trip-id <id>
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from pipeline.core.live.providers import DHAKA_R1_CORRIDORS  # noqa: E402
from pipeline.live.schemas import append_jsonl, assert_no_google_content, coord_ref, load_jsonl, now_utc, parse_lat_lng, stable_ref  # noqa: E402

DEFAULT_LOG = REPO / "results/live/pilot_trips.jsonl"
DEFAULT_JSON = REPO / "results/live/pilot_metrics.json"
DEFAULT_MD = REPO / "results/live/pilot_metrics.md"


def utc_parse(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def corridor_coords(corridor_id: str) -> tuple[tuple[float, float], tuple[float, float]]:
    by_id = {c["corridor_id"]: c for c in DHAKA_R1_CORRIDORS}
    if corridor_id not in by_id:
        raise SystemExit(f"unknown corridor {corridor_id!r}; choices: {', '.join(sorted(by_id))}")
    c = by_id[corridor_id]
    return c["origin"], c["dest"]


def refs(args: argparse.Namespace) -> tuple[str, str, str]:
    if args.corridor:
        origin, dest = corridor_coords(args.corridor)
        return coord_ref(*origin), coord_ref(*dest), args.corridor
    if not args.origin or not args.dest:
        raise SystemExit("provide --corridor or both --origin lat,lng and --dest lat,lng")
    origin = parse_lat_lng(args.origin)
    dest = parse_lat_lng(args.dest)
    return coord_ref(*origin), coord_ref(*dest), args.label or "custom"


def start(args: argparse.Namespace) -> int:
    started = args.started_utc or now_utc()
    origin_ref, dest_ref, label = refs(args)
    participant_ref = stable_ref(args.participant)
    trip_id = stable_ref("|".join([participant_ref, args.advice_id, started, origin_ref, dest_ref]))
    row = {
        "event": "start",
        "trip_id": trip_id,
        "participant_ref": participant_ref,
        "advice_id": args.advice_id,
        "started_utc": started,
        "query_label": label,
        "origin_ref": origin_ref,
        "dest_ref": dest_ref,
        "chosen_option_rank": args.chosen_option_rank,
        "reality": "REAL_USER_PILOT",
        "google_data_mode": "RUNTIME_REFERENCE",
        "route_content_persisted": False,
    }
    assert_no_google_content(row)
    append_jsonl(args.log, row)
    print(json.dumps({"status": "TRIP_STARTED", "trip_id": trip_id, "log": str(args.log)}, indent=1))
    return 0


def complete(args: argparse.Namespace) -> int:
    rows = load_jsonl(args.log)
    starts = [r for r in rows if r.get("event") == "start" and r.get("trip_id") == args.trip_id]
    if not starts:
        raise SystemExit(f"no start event found for trip {args.trip_id}")
    start_row = starts[-1]
    arrived = args.arrived_utc or now_utc()
    elapsed_s = max((utc_parse(arrived) - utc_parse(start_row["started_utc"])).total_seconds(), 0.0)
    row = {
        "event": "complete",
        "trip_id": args.trip_id,
        "arrived_utc": arrived,
        "actual_elapsed_s": round(elapsed_s, 1),
        "actual_elapsed_source": "USER_REPORTED_TIMESTAMP",
        "completed": True,
        "notes": (args.notes or "")[:180],
        "reality": "REAL_USER_PILOT",
        "google_data_mode": "RUNTIME_REFERENCE",
        "route_content_persisted": False,
    }
    assert_no_google_content(row)
    append_jsonl(args.log, row)
    write_summary(args.log, args.out_json, args.out_md)
    print(json.dumps({"status": "TRIP_COMPLETED", "trip_id": args.trip_id,
                      "actual_elapsed_s": row["actual_elapsed_s"]}, indent=1))
    return 0


def matched_trips(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    starts = {r["trip_id"]: r for r in rows if r.get("event") == "start"}
    trips = []
    for row in rows:
        if row.get("event") != "complete" or row.get("trip_id") not in starts:
            continue
        trips.append({**starts[row["trip_id"]], **row})
    return trips


def write_summary(log: Path, out_json: Path, out_md: Path) -> dict[str, Any]:
    rows = load_jsonl(log)
    trips = matched_trips(rows)
    elapsed = [float(t["actual_elapsed_s"]) for t in trips]
    summary = {
        "stage": "REAL_USER_PILOT",
        "generated_utc": now_utc(),
        "source": str(log),
        "started_trips": sum(1 for r in rows if r.get("event") == "start"),
        "completed_trips": len(trips),
        "participants": len({t.get("participant_ref") for t in trips}),
        "mean_actual_elapsed_s": round(sum(elapsed) / len(elapsed), 1) if elapsed else None,
        "google_data_mode": "RUNTIME_REFERENCE",
        "route_content_persisted": False,
        "honesty_label": "REAL_USER_PILOT_SMALL_SAMPLE_NO_GOOGLE_ROUTE_CONTENT_STORED",
    }
    assert_no_google_content(summary)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(summary, indent=1))
    lines = [
        "# Real User Pilot",
        "",
        f"Generated UTC: `{summary['generated_utc']}`.",
        f"Started trips: **{summary['started_trips']}**.",
        f"Completed trips: **{summary['completed_trips']}**.",
        f"Participants: **{summary['participants']}**.",
        f"Mean actual elapsed time: **{summary['mean_actual_elapsed_s']} s**.",
        "",
        "This is real user-pilot evidence, not fixed-seed simulation. It stores user-owned timestamps and hashed OD refs only.",
        "It does not store Google route durations, distances, or geometry.",
        "",
    ]
    out_md.write_text("\n".join(lines))
    return summary


def summarize(args: argparse.Namespace) -> int:
    summary = write_summary(args.log, args.out_json, args.out_md)
    print(json.dumps(summary, indent=1))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p_start = sub.add_parser("start")
    p_start.add_argument("--participant", required=True, help="pseudonym; stored only as hash")
    p_start.add_argument("--advice-id", required=True)
    p_start.add_argument("--chosen-option-rank", type=int, default=0)
    p_start.add_argument("--corridor")
    p_start.add_argument("--origin")
    p_start.add_argument("--dest")
    p_start.add_argument("--label", default="custom")
    p_start.add_argument("--started-utc")
    p_start.add_argument("--log", type=Path, default=DEFAULT_LOG)
    p_start.set_defaults(func=start)

    p_complete = sub.add_parser("complete")
    p_complete.add_argument("--trip-id", required=True)
    p_complete.add_argument("--arrived-utc")
    p_complete.add_argument("--notes", default="")
    p_complete.add_argument("--log", type=Path, default=DEFAULT_LOG)
    p_complete.add_argument("--out-json", type=Path, default=DEFAULT_JSON)
    p_complete.add_argument("--out-md", type=Path, default=DEFAULT_MD)
    p_complete.set_defaults(func=complete)

    p_summary = sub.add_parser("summarize")
    p_summary.add_argument("--log", type=Path, default=DEFAULT_LOG)
    p_summary.add_argument("--out-json", type=Path, default=DEFAULT_JSON)
    p_summary.add_argument("--out-md", type=Path, default=DEFAULT_MD)
    p_summary.set_defaults(func=summarize)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
