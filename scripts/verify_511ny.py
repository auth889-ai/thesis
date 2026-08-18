#!/usr/bin/env python3
"""Isolated 511NY activation check — run this once the developer key arrives.

Usage:
    export NY511_API_KEY=...        # (or put NY511_API_KEY=... in dhakaflow/.env)
    python scripts/verify_511ny.py

Without a key it reports PENDING_EXTERNAL_APPROVAL and exits 0 — the project
is explicitly NOT blocked on this key. With a key it performs one live
getcameras call, captures the response schema VERBATIM as evidence, filters a
Manhattan test bbox, and writes an activation-evidence JSON. Success upgrades
the provider from PENDING_EXTERNAL_APPROVAL to VERIFIED_LIVE in the evidence
file; the classification stays PROVIDER_INTEGRATION_VALIDATION — never a Dhaka
claim.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dhakaflow.live.ny511_provider import (CLASSIFICATION,
                                           FORBIDDEN_CLASSIFICATION,
                                           NY511_KEY_STATUS,
                                           NY511CameraProvider,
                                           load_ny511_key)
from dhakaflow.live.providers import ObservationStore

# Lower Manhattan / midtown — dense camera coverage, good activation probe.
MANHATTAN_BBOX = (40.70, 40.80, -74.02, -73.93)

EVIDENCE = Path(__file__).resolve().parents[1] / "artifacts" / "live_511ny"


def main() -> int:
    key = load_ny511_key()
    if not key:
        print("511NY_CAMERAS =", NY511_KEY_STATUS)
        print()
        print("No key found (env NY511_API_KEY or dhakaflow/.env). This does")
        print("NOT block the project. Operator steps when the key arrives:")
        print("  1. export NY511_API_KEY=<the approved key>")
        print("  2. python scripts/verify_511ny.py")
        print("  3. review artifacts/live_511ny/activation_evidence.json")
        return 0

    store = ObservationStore(EVIDENCE)
    provider = NY511CameraProvider(store=store)
    print(f"Key present ({len(key)} chars) — executing one live getcameras call…")

    all_cams = provider.list_cameras((-90.0, 90.0, -180.0, 180.0))
    in_bbox = [c for c in all_cams
               if MANHATTAN_BBOX[0] <= c.lat <= MANHATTAN_BBOX[1]
               and MANHATTAN_BBOX[2] <= c.lng <= MANHATTAN_BBOX[3]]
    streaming = [c for c in in_bbox if c.has_stream]

    raw_file = EVIDENCE / "raw" / "ny511_cameras.jsonl"
    schema_keys: list[str] = []
    if raw_file.exists():
        first = json.loads(raw_file.read_text().splitlines()[0])
        cams = first.get("payload", {}).get("cameras", [])
        if cams:
            schema_keys = sorted(cams[0].keys())

    evidence = {
        "provider": provider.name,
        "verified_utc": datetime.now(timezone.utc).isoformat(),
        "status": "VERIFIED_LIVE",
        "previous_status": NY511_KEY_STATUS,
        "classification": CLASSIFICATION,
        "never_classified_as": FORBIDDEN_CLASSIFICATION,
        "total_cameras": len(all_cams),
        "manhattan_bbox_cameras": len(in_bbox),
        "manhattan_bbox_streaming": len(streaming),
        "response_schema_keys_verbatim": schema_keys,
    }
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    out = EVIDENCE / "activation_evidence.json"
    out.write_text(json.dumps(evidence, indent=2))

    print(json.dumps(evidence, indent=2))
    print(f"\nEvidence written: {out}")
    print("Next: scripts/run_live_stream_demo.py (ingestion demonstration) —")
    print("classification stays PROVIDER_INTEGRATION_VALIDATION.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
