#!/usr/bin/env python3
"""Execute the first live Google capture: 6 Dhaka R1 corridors + 1 weather.

Runs under GOOGLE_DATA_MODE=RUNTIME_REFERENCE (the only shipped mode):
raw persistence OFF, Google route content persistence OFF, ML use FORBIDDEN.
Persisted to disk: request metadata + DERIVED congestion verdicts only.
The full field values are printed to the terminal (transient runtime use)
and summarised in the mandated report.

Usage:
    export GOOGLE_MAPS_API_KEY=...   # restricted key: Routes API + Weather API
    python -m core.ml.forecasting.live.run_live_capture
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.common.data.live_providers.google_providers import (GoogleRoutesProvider,
                                             GoogleWeatherProvider)
from core.common.data.live_providers.providers import DHAKA_R1_CORRIDORS, ObservationStore
from core.common.credentials import load_credential


def load_key() -> str:
    return load_credential("GOOGLE_MAPS_API_KEY")


def main() -> int:
    key = load_key()
    report = {
        "stage": "P-LIVE_FIRST_CAPTURE",
        "google_data_mode": "RUNTIME_REFERENCE",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "billing_skus": {
            "routes": "Routes API: Compute Routes Advanced "
                      "(TRAFFIC_AWARE_OPTIMAL + TRAFFIC_ON_POLYLINE "
                      "triggers the Advanced SKU)",
            "weather": "Weather API: Current Conditions",
        },
    }

    if not key:
        report["status"] = "BLOCKED_NO_KEY"
        report["operator_steps"] = [
            "console.cloud.google.com -> APIs & Services -> enable 'Routes API'",
            "enable 'Weather API'",
            "Credentials -> Create API key -> restrict to Routes API + Weather API",
            "put GOOGLE_MAPS_API_KEY=<key> in the root .env (gitignored) or environment",
            "rerun: python -m core.ml.forecasting.live.run_live_capture",
        ]
        print(json.dumps(report, indent=2))
        return 1

    store = ObservationStore(Path("results/artifacts/p_live"))
    routes = GoogleRoutesProvider(store=store, api_key=key)   # default policy
    weather = GoogleWeatherProvider(store=None, api_key=key)  # transient only

    # --- 6 predeclared corridors ------------------------------------------
    corridor_rows, errors = [], []
    for c in DHAKA_R1_CORRIDORS:
        try:
            s = routes.edge_state(c["corridor_id"], c["origin"], c["dest"])
            corridor_rows.append({
                "corridor": s.corridor_id,
                "duration_s": s.duration_s,
                "static_duration_s": s.static_duration_s,
                "traffic_delay_s": s.traffic_delay_s,
                "distance_m": s.distance_m,
                "speed_intervals": [list(i) for i in s.speed_intervals],
                "congestion_state": routes.policy.congestion_bucket(
                    s.duration_s, s.static_duration_s),
                "request_latency_ms": s.provenance.request_latency_ms,
                "reality": s.provenance.reality.value,
                "captured_utc": s.provenance.captured_utc,
            })
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{c['corridor_id']}: {type(exc).__name__}: {exc}")

    # --- 1 weather observation (R1 centroid: Karwan Bazar) ----------------
    weather_row = None
    try:
        w = weather.current(23.7508, 90.3928)
        weather_row = {k: v for k, v in w.__dict__.items() if k != "provenance"}
        weather_row.update({
            "request_latency_ms": w.provenance.request_latency_ms,
            "reality": w.provenance.reality.value,
            "captured_utc": w.provenance.captured_utc,
        })
    except Exception as exc:  # noqa: BLE001
        errors.append(f"weather: {type(exc).__name__}: {exc}")

    report.update({
        "status": "EXECUTED" if corridor_rows else "ALL_REQUESTS_FAILED",
        "corridors_requested": len(DHAKA_R1_CORRIDORS),
        "corridors_captured": len(corridor_rows),
        "corridors": corridor_rows,
        "weather": weather_row,
        "errors": errors,
        "persistence_note": (
            "Disk holds runtime-reference records only (metadata + derived "
            "congestion verdicts). Field values above are transient runtime "
            "output per GOOGLE_DATA_MODE=RUNTIME_REFERENCE."),
    })

    # The report file itself contains Google field values -> keep it out of the
    # durable evidence tree; print to terminal, persist only the compliant log.
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
