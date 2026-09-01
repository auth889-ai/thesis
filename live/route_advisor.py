#!/usr/bin/env python3
"""Real-time route advisor for the no-fixed-seed pilot path.

The CLI can run in fixture mode without API cost, or in live mode with an
explicit `--yes`. Google route durations and geometry are used only in memory
to choose an option. The evidence JSONL stores privacy-preserving request refs,
derived congestion state, recommendation rank, and compliance metadata only.

Examples:
    python live/route_advisor.py --dry-run --corridor farmgate_to_shahbagh
    python live/route_advisor.py --live --yes --origin 23.7573,90.3854 --dest 23.7389,90.3958
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path
from typing import Callable

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from dhakaflow.live.google_providers import GoogleDataPolicy, ROUTES_ENDPOINT  # noqa: E402
from dhakaflow.live.providers import DHAKA_R1_CORRIDORS  # noqa: E402
from live.schemas import AdviceRecord, RuntimeRouteOption, RouteQuery, append_jsonl, now_utc, parse_lat_lng, stable_ref  # noqa: E402

DEFAULT_OUT = REPO / "live/results/route_advice.jsonl"
USD_PER_1000_REQUESTS = 10.0
FIELD_MASK = ",".join([
    "routes.duration",
    "routes.staticDuration",
    "routes.distanceMeters",
    "routes.polyline.encodedPolyline",
])


def load_key() -> str:
    key = os.environ.get("GOOGLE_MAPS_API_KEY", "")
    envf = REPO / "dhakaflow/.env"
    if not key and envf.exists():
        for line in envf.read_text().splitlines():
            m = re.match(r'\s*(?:export\s+)?GOOGLE_MAPS_API_KEY\s*=\s*["\']?([^"\'\s]+)', line)
            if m:
                return m.group(1)
    return key


def parse_duration(value: str | None) -> float:
    return float((value or "0s").rstrip("s"))


def default_transport(url: str, body: bytes, headers: dict) -> dict:
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read())


def fixture_transport(url: str, body: bytes, headers: dict) -> dict:
    n = int(hashlib.sha256(body).hexdigest()[:8], 16)
    base = 540 + (n % 7) * 20
    ratios = [1.28, 1.10, 1.55]
    routes = []
    for idx, ratio in enumerate(ratios):
        static = base + idx * 45
        routes.append({
            "duration": f"{static * ratio:.0f}s",
            "staticDuration": f"{static:.0f}s",
            "distanceMeters": 2400 + idx * 180,
            "polyline": {"encodedPolyline": f"fixture-{n}-{idx}"},
        })
    return {"routes": routes}


def query_from_args(args: argparse.Namespace) -> RouteQuery:
    if args.corridor:
        by_id = {c["corridor_id"]: c for c in DHAKA_R1_CORRIDORS}
        if args.corridor not in by_id:
            raise SystemExit(f"unknown corridor {args.corridor!r}; choices: {', '.join(sorted(by_id))}")
        c = by_id[args.corridor]
        return RouteQuery(origin=c["origin"], dest=c["dest"], label=c["corridor_id"])
    if not args.origin or not args.dest:
        raise SystemExit("provide --corridor or both --origin lat,lng and --dest lat,lng")
    return RouteQuery(origin=parse_lat_lng(args.origin), dest=parse_lat_lng(args.dest), label=args.label or "custom")


def compute_options(query: RouteQuery, api_key: str, transport: Callable[[str, bytes, dict], dict]) -> list[RuntimeRouteOption]:
    body = json.dumps({
        "origin": {"location": {"latLng": {"latitude": query.origin[0], "longitude": query.origin[1]}}},
        "destination": {"location": {"latLng": {"latitude": query.dest[0], "longitude": query.dest[1]}}},
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_AWARE_OPTIMAL",
        "computeAlternativeRoutes": True,
    }).encode()
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": FIELD_MASK,
    }
    payload = transport(ROUTES_ENDPOINT, body, headers)
    routes = payload.get("routes") or []
    if not routes:
        raise RuntimeError("route provider returned no routes")
    policy = GoogleDataPolicy()
    options: list[RuntimeRouteOption] = []
    for idx, route in enumerate(routes):
        duration = parse_duration(route.get("duration"))
        static = parse_duration(route.get("staticDuration"))
        poly = (route.get("polyline") or {}).get("encodedPolyline", "")
        options.append(RuntimeRouteOption(
            rank=idx,
            duration_s=duration,
            static_duration_s=static,
            distance_m=float(route["distanceMeters"]) if "distanceMeters" in route else None,
            route_ref=stable_ref(poly) if poly else "",
            congestion_state=policy.congestion_bucket(duration, static),
        ))
    return options


def recommend(options: list[RuntimeRouteOption]) -> RuntimeRouteOption:
    penalty = {"FREE_FLOW": 0, "SLOW": 30, "CONGESTED": 120, "SEVERE": 240, "UNKNOWN": 60}
    return min(options, key=lambda r: r.duration_s + penalty.get(r.congestion_state, 60))


def persist_advice(path: Path, query: RouteQuery, options: list[RuntimeRouteOption], selected: RuntimeRouteOption,
                   provider: str, reality: str) -> AdviceRecord:
    captured = now_utc()
    advice_id = stable_ref("|".join([
        captured,
        query.origin_ref,
        query.dest_ref,
        str(selected.rank),
        reality,
    ]))
    record = AdviceRecord(
        advice_id=advice_id,
        captured_utc=captured,
        provider=provider,
        reality=reality,
        query_label=query.label,
        origin_ref=query.origin_ref,
        dest_ref=query.dest_ref,
        route_count=len(options),
        recommended_rank=selected.rank,
        recommended_congestion_state=selected.congestion_state,
        scoring_policy="minimum provider ETA with congestion-bucket penalty; provider values are runtime-only",
    )
    append_jsonl(path, record.persistable())
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--corridor", help="one of the predefined public Dhaka R1 corridors")
    parser.add_argument("--origin", help="lat,lng; used only in memory, persisted as a hash")
    parser.add_argument("--dest", help="lat,lng; used only in memory, persisted as a hash")
    parser.add_argument("--label", default="custom")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--dry-run", action="store_true", help="fixture routes, no network, no cost")
    parser.add_argument("--live", action="store_true", help="real Google Routes call, spends credit")
    parser.add_argument("--yes", action="store_true", help="required with --live")
    args = parser.parse_args()

    if args.live == args.dry_run:
        parser.error("choose exactly one: --dry-run or --live")
    if args.live and not args.yes:
        print(f"[cost] one advisory call ~= ${USD_PER_1000_REQUESTS / 1000:.3f}; re-run with --yes")
        return 2

    query = query_from_args(args)
    key = load_key() if args.live else "FIXTURE_KEY"
    if args.live and not key:
        print("[error] GOOGLE_MAPS_API_KEY not set; no route advice fabricated")
        return 3

    t0 = time.monotonic()
    options = compute_options(query, key, default_transport if args.live else fixture_transport)
    selected = recommend(options)
    record = persist_advice(args.out, query, options, selected, "google_routes", "REAL_LIVE" if args.live else "FIXTURE")
    print(json.dumps({
        "status": "ADVICE_WRITTEN",
        "advice_id": record.advice_id,
        "reality": record.reality,
        "query_label": record.query_label,
        "route_count": len(options),
        "recommended_rank": selected.rank,
        "recommended_congestion_state": selected.congestion_state,
        "wall_ms": round((time.monotonic() - t0) * 1000, 1),
        "persisted": str(args.out),
        "persistence_note": "durations/distances/geometry were runtime-only and were not written",
    }, indent=1))
    print("runtime_options_not_persisted:")
    for opt in options:
        print(f"  rank={opt.rank} duration_min={opt.duration_s / 60:.1f} "
              f"static_min={opt.static_duration_s / 60:.1f} state={opt.congestion_state}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
