#!/usr/bin/env python3
"""Record a LIVE Dhaka congestion time series — the head of the live chain.

    python -m core.ml.forecasting.live.record_live --dry-run                 # fixture transport, no API calls, no cost
    python -m core.ml.forecasting.live.record_live --live --interval 300     # real capture, ~$X/day (printed first)
    touch results/artifacts/live_dhaka/STOP                               # stop a running recorder

Why this exists: an ML forecaster needs HISTORY, and history accrues by wall clock — an hour
not recorded today is data that never exists. This recorder polls the 6 predeclared Dhaka R1
corridors every --interval seconds (default 300 s = the METR-LA bin width) and appends one row
per corridor per tick, so `src/pipeline/forecasting/` can later build a real (not simulated) Dhaka dataset.

COMPLIANCE — this is the part that makes the data usable in a thesis.
Google Maps Platform terms forbid storing Maps Content and forbid training models on it. This
recorder therefore runs under the repository's shipped `GoogleDataPolicy` (RUNTIME_REFERENCE):
what lands on disk is request metadata plus the DERIVED congestion verdict that the policy
documents as ours to keep — never durations, distances, speed intervals or geometry. That means:

  * the recorded series is a sequence of congestion CLASSES (FREE_FLOW / SLOW / CONGESTED /
    SEVERE) per corridor per tick, not Google travel times;
  * it is honest to forecast that class series and to use it as a live state signal;
  * it is NOT a substitute for a licensed speed/flow feed. For real-valued speeds with a licence
    that permits storage, add a TomTom/HERE provider implementing `dhakaflow.live.providers
    .TrafficProvider` and pass `--provider tomtom|here` (see PROVIDERS below).

Cost: --live is required for real calls (the repo convention, cf. verify_keys.py --live); the
estimated request count and spend are printed and must be confirmed with --yes for long runs.
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from core.common.paths import REPO
sys.path.insert(0, str(REPO))

from core.common.data.live_providers.google_providers import GoogleDataPolicy, GoogleRoutesProvider  # noqa: E402
from core.common.data.live_providers.providers import DHAKA_R1_CORRIDORS, ObservationStore  # noqa: E402

DEFAULT_OUT = REPO / "results/artifacts/live_dhaka"
# Google Routes "Compute Routes Advanced" (TRAFFIC_AWARE_OPTIMAL + speed intervals) list price.
# Printed for budgeting only; verify against your billing console before a long run.
USD_PER_1000_REQUESTS = 10.0
PROVIDERS = {"google": "GoogleRoutesProvider (RUNTIME_REFERENCE: derived verdicts only)"}


def rel(p: Path) -> str:
    """Repo-relative when inside the repo, absolute otherwise (--out may point anywhere)."""
    try:
        return str(p.relative_to(REPO))
    except ValueError:
        return str(p)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def fixture_transport(url: str, body: bytes | None, headers: dict) -> dict:
    """Deterministic stand-in for the Routes endpoint: --dry-run makes no network call.

    Returns a shape the provider parses, with a duration that varies by request so the
    recorder's plumbing (bucketing, rotation, manifest counting) is exercised end to end.
    Rows produced this way are labelled reality=FIXTURE and are never thesis evidence.
    """
    import hashlib
    n = int(hashlib.md5(body or b"").hexdigest()[:8], 16)
    ratio = 1.0 + (n % 7) * 0.18                       # 1.00 .. 2.08 -> covers every bucket
    static_s = 600.0
    return {"routes": [{"duration": f"{static_s * ratio:.0f}s",
                        "staticDuration": f"{static_s:.0f}s",
                        "distanceMeters": 3200,
                        "polyline": {"encodedPolyline": "fixture"},
                        "travelAdvisory": {"speedReadingIntervals": []}}]}


def tick(provider, corridors, store: ObservationStore, reality: str) -> list[dict]:
    """One sweep over every corridor. A failing corridor is logged, never fabricated."""
    rows = []
    for c in corridors:
        try:
            provider.edge_state(c["corridor_id"], c["origin"], c["dest"])
            rows.append({"corridor_id": c["corridor_id"], "ok": True})
        except Exception as ex:                        # src/pipeline/networking/quota/HTTP — keep recording
            err = {"corridor_id": c["corridor_id"], "captured_utc": _now(), "ok": False,
                   "error": f"{type(ex).__name__}: {ex}"[:300], "reality": reality}
            store.append_runtime_reference("recorder_errors", err)
            rows.append(err)
    return rows


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--provider", default="google", choices=sorted(PROVIDERS))
    p.add_argument("--interval", type=int, default=300, help="seconds between sweeps (300 = METR-LA bin)")
    p.add_argument("--hours", type=float, default=None, help="stop after this many hours (default: until STOP file)")
    p.add_argument("--out", default=str(DEFAULT_OUT))
    p.add_argument("--live", action="store_true", help="make REAL API calls (spends credit); omit for --dry-run")
    p.add_argument("--dry-run", action="store_true", help="fixture transport: no network, no cost")
    p.add_argument("--yes", action="store_true", help="skip the cost confirmation for --live runs")
    p.add_argument("--ticks", type=int, default=None, help="stop after N sweeps (testing)")
    a = p.parse_args()

    if not (a.live or a.dry_run):
        p.error("choose --live (real capture, spends credit) or --dry-run (fixtures, free)")
    if a.live and a.dry_run:
        p.error("--live and --dry-run are mutually exclusive")

    out = Path(a.out)
    store = ObservationStore(out)
    corridors = list(DHAKA_R1_CORRIDORS)
    reality = "REAL_LIVE" if a.live else "FIXTURE"

    per_hour = len(corridors) * 3600 / a.interval
    if a.live:
        print(f"[cost] {len(corridors)} corridors every {a.interval}s = {per_hour:.0f} requests/hour "
              f"= {per_hour * 24:.0f}/day ~= ${per_hour * 24 * USD_PER_1000_REQUESTS / 1000:.2f}/day "
              f"at ${USD_PER_1000_REQUESTS:.0f}/1000 (verify in your billing console)")
        if not a.yes:
            print("[cost] re-run with --yes to start the live recorder"); return 2
        if not os.environ.get("GOOGLE_MAPS_API_KEY"):
            print("[error] GOOGLE_MAPS_API_KEY not set — nothing recorded, nothing fabricated"); return 3

    provider = GoogleRoutesProvider(store=store, policy=GoogleDataPolicy(),
                                    transport=None if a.live else fixture_transport,
                                    api_key=None if a.live else "FIXTURE_KEY")

    stop_file = out / "STOP"
    stop_file.unlink(missing_ok=True)
    manifest = out / "RECORDER_MANIFEST.json"
    started = _now()
    man = {"started_utc": started, "provider": a.provider, "provider_impl": PROVIDERS[a.provider],
           "reality": reality, "interval_s": a.interval, "corridors": [c["corridor_id"] for c in corridors],
           "google_data_mode": GoogleDataPolicy.MODE,
           "persisted_fields": ["corridor_id", "captured_utc", "request_latency_ms", "congestion_state",
                                "google_data_mode", "route_content_persisted"],
           "never_persisted": ["duration", "staticDuration", "distanceMeters", "speedReadingIntervals", "polyline"],
           "series_file": rel(out / "normalized/google_routes_runtime_reference.jsonl"),
           "ticks": 0, "rows_ok": 0, "rows_failed": 0, "stop_file": rel(stop_file)}
    manifest.write_text(json.dumps(man, indent=1))

    stopping = {"now": False}
    signal.signal(signal.SIGINT, lambda *_: stopping.update(now=True))
    signal.signal(signal.SIGTERM, lambda *_: stopping.update(now=True))

    print(f"[recorder] {reality} start {started} interval={a.interval}s corridors={len(corridors)} -> {out}")
    print(f"[recorder] stop with: touch {stop_file}")
    t_end = time.time() + a.hours * 3600 if a.hours else None
    n = 0
    while not stopping["now"]:
        t0 = time.time()
        rows = tick(provider, corridors, store, reality)
        n += 1
        man["ticks"] = n
        man["rows_ok"] += sum(r.get("ok") is True for r in rows)
        man["rows_failed"] += sum(r.get("ok") is False for r in rows)
        man["last_tick_utc"] = _now()
        manifest.write_text(json.dumps(man, indent=1))
        print(f"[recorder] tick {n} ok={sum(r.get('ok') is True for r in rows)}/{len(rows)} "
              f"({time.time() - t0:.1f}s)", flush=True)
        if a.ticks and n >= a.ticks:
            break
        if stop_file.exists() or (t_end and time.time() >= t_end):
            break
        slept = 0.0
        while slept < a.interval - (time.time() - t0) and not stopping["now"] and not stop_file.exists():
            time.sleep(min(1.0, a.interval))
            slept += 1.0
    man["finished_utc"] = _now()
    manifest.write_text(json.dumps(man, indent=1))
    print(f"[recorder] stopped after {n} ticks; {man['rows_ok']} rows ok, {man['rows_failed']} failed")
    print(f"[recorder] manifest {manifest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
