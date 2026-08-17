"""P-LIVE tests: reality labels, provider contracts, mock-transport providers,
and the live-state assembler's honest degradation."""
from __future__ import annotations

import json

import pytest

from dhakaflow.common.reality import (Provenance, RealityClass,
                                      assert_single_reality, derive)
from dhakaflow.live.google_providers import (GoogleRoutesProvider,
                                             GoogleWeatherProvider)
from dhakaflow.live.providers import (DHAKA_R1_CORRIDORS, ObservationStore,
                                      TrafficEdgeState, TrafficProvider)
from dhakaflow.services.live_state import PRODUCT_FIELDS, assemble_live_state


def _prov(reality=RealityClass.REAL_LIVE, **kw):
    return Provenance(provider="test", reality=reality,
                      captured_utc="2026-08-16T00:00:00+00:00", **kw)


# ------------------------------------------------------------- reality labels
def test_derived_requires_parents():
    with pytest.raises(ValueError, match="parent reality"):
        Provenance(provider="x", reality=RealityClass.DERIVED,
                   captured_utc="2026-08-16T00:00:00+00:00")


def test_non_derived_must_not_carry_parents():
    with pytest.raises(ValueError, match="only DERIVED"):
        _prov(parent_realities=(RealityClass.SIMULATED,))


def test_mixing_realities_raises():
    with pytest.raises(ValueError, match="REALITY MIX"):
        assert_single_reality([_prov(RealityClass.REAL_LIVE),
                               _prov(RealityClass.SIMULATED)])


def test_explicit_derivation_is_the_legal_mix():
    d = derive("fusion", "2026-08-16T00:00:00+00:00",
               [_prov(RealityClass.REAL_LIVE), _prov(RealityClass.SIMULATED)])
    assert d.reality is RealityClass.DERIVED
    assert set(d.parent_realities) == {RealityClass.REAL_LIVE,
                                       RealityClass.SIMULATED}


def test_unlabelled_observation_cannot_exist():
    with pytest.raises(ValueError, match="provenance"):
        TrafficEdgeState(corridor_id="c", origin_lat=0, origin_lng=0,
                         dest_lat=1, dest_lng=1, duration_s=10,
                         static_duration_s=8, distance_m=100,
                         traffic_delay_s=2)


# ------------------------------------------------------- Google Routes (mock)
ROUTES_PAYLOAD = {"routes": [{
    "duration": "540s", "staticDuration": "380s", "distanceMeters": 2450,
    "polyline": {"encodedPolyline": "abc123xyz"},
    "travelAdvisory": {"speedReadingIntervals": [
        {"startPolylinePointIndex": 0, "endPolylinePointIndex": 12,
         "speed": "SLOW"},
        {"startPolylinePointIndex": 12, "endPolylinePointIndex": 30,
         "speed": "TRAFFIC_JAM"}]}}]}


def test_routes_provider_disabled_without_key(monkeypatch):
    monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)
    p = GoogleRoutesProvider(api_key="")
    assert not p.enabled
    with pytest.raises(RuntimeError, match="READY_NOT_EXECUTED"):
        p.edge_state("c", (23.75, 90.38), (23.74, 90.39))


def test_routes_provider_parses_real_shape(tmp_path):
    captured_headers = {}

    def transport(url, body, headers):
        captured_headers.update(headers)
        assert json.loads(body)["routingPreference"] == "TRAFFIC_AWARE_OPTIMAL"
        return ROUTES_PAYLOAD

    store = ObservationStore(tmp_path)
    p = GoogleRoutesProvider(store=store, api_key="k", transport=transport)
    s = p.edge_state("farmgate_to_shahbagh", (23.7573, 90.3854),
                     (23.7389, 90.3958))

    assert s.duration_s == 540.0 and s.static_duration_s == 380.0
    assert s.traffic_delay_s == 160.0
    assert s.speed_intervals[1][2] == "TRAFFIC_JAM"
    assert s.route_ref and s.route_ref != "abc123xyz"     # hash, not geometry
    assert s.provenance.reality is RealityClass.REAL_LIVE
    assert "EXTERNAL_LIVE_REFERENCE" in s.provenance.metadata["classification"]
    assert "X-Goog-FieldMask" in captured_headers
    assert isinstance(p, TrafficProvider)


def test_runtime_reference_mode_persists_no_google_content(tmp_path):
    """Default GOOGLE_DATA_MODE=RUNTIME_REFERENCE: metadata + derived verdict
    only — no durations, distances, intervals or geometry hit disk."""
    store = ObservationStore(tmp_path)
    p = GoogleRoutesProvider(store=store, api_key="k",
                             transport=lambda u, b, h: ROUTES_PAYLOAD)
    s = p.edge_state("c", (23.75, 90.38), (23.74, 90.39))
    assert s.duration_s == 540.0                     # transient runtime value OK

    assert not list(store.raw_dir.glob("*.jsonl"))   # no raw payloads
    files = list(store.norm_dir.glob("*.jsonl"))
    assert len(files) == 1 and "runtime_reference" in files[0].name
    rec = json.loads(files[0].read_text().strip())
    assert rec["congestion_state"] == "SLOW"         # 540/380 = 1.42 -> SLOW
    assert rec["google_data_mode"] == "RUNTIME_REFERENCE"
    for banned in ("540", "380", "2450", "duration", "distance"):
        assert banned not in json.dumps({k: v for k, v in rec.items()
                                         if k != "captured_utc"})


def test_non_default_google_flags_require_permission_basis():
    from dhakaflow.live.google_providers import GoogleDataPolicy
    with pytest.raises(ValueError, match="permission_basis"):
        GoogleDataPolicy(ml_training_allowed=True)
    ok = GoogleDataPolicy(persist_google_route_content=True,
                          permission_basis="Google contract #X clause Y (reviewed)")
    assert ok.persist_google_route_content


def test_congestion_buckets():
    from dhakaflow.live.google_providers import GoogleDataPolicy
    pol = GoogleDataPolicy()
    assert pol.congestion_bucket(100, 95) == "FREE_FLOW"
    assert pol.congestion_bucket(540, 380) == "SLOW"
    assert pol.congestion_bucket(700, 380) == "CONGESTED"
    assert pol.congestion_bucket(900, 380) == "SEVERE"


# ------------------------------------------------------ Google Weather (mock)
WEATHER_PAYLOAD = {
    "temperature": {"degrees": 31.4}, "relativeHumidity": 78,
    "precipitation": {"qpf": {"quantity": 2.5},
                      "probability": {"percent": 80, "type": "RAIN"}},
    "visibility": {"distance": 6.0},
    "wind": {"speed": {"value": 14.0}, "direction": {"degrees": 120}},
    "cloudCover": 90, "weatherCondition": {"type": "RAIN"},
}


def test_weather_provider_parses_and_labels(tmp_path):
    p = GoogleWeatherProvider(store=ObservationStore(tmp_path), api_key="k",
                              transport=lambda u, b, h: WEATHER_PAYLOAD)
    w = p.current(23.75, 90.39)
    assert w.temperature_c == 31.4 and w.precipitation_probability_pct == 80
    assert w.precipitation_type == "RAIN" and w.cloud_cover_pct == 90
    assert w.provenance.reality is RealityClass.REAL_LIVE
    assert "ablation" in w.provenance.metadata["role"]


# ------------------------------------------------------- live-state assembler
def test_assembler_degrades_honestly_with_no_providers():
    state = assemble_live_state()
    assert state.fields == {}
    assert "GOOGLE_MAPS_API_KEY" in state.unavailable["current_traffic"]
    # every declared product field is present as UNAVAILABLE with its gate
    for name in PRODUCT_FIELDS:
        assert name in state.unavailable
    assert "P4" in state.unavailable["forecast_5_15_30"]


def test_assembler_with_mock_traffic_provider():
    p = GoogleRoutesProvider(api_key="k",
                             transport=lambda u, b, h: ROUTES_PAYLOAD)
    state = assemble_live_state(traffic=p, corridors=DHAKA_R1_CORRIDORS[:2])
    rows = state.fields["current_traffic"]["corridors"]
    assert len(rows) == 2
    assert all(r["reality"] == "REAL_LIVE" for r in rows)
    assert state.fields["current_traffic"]["classification"] == \
        "EXTERNAL_LIVE_REFERENCE"
    # unqualified subsystems still honestly absent
    assert "detector_counts" in state.unavailable


def test_provider_failure_degrades_not_crashes():
    class Failing:
        name, enabled = "boom", True

        def edge_state(self, *a):
            raise RuntimeError("provider outage")

    state = assemble_live_state(traffic=Failing(), corridors=DHAKA_R1_CORRIDORS[:1])
    assert "provider outage" in state.unavailable["current_traffic"]
