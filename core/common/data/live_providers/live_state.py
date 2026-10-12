"""Live-state API — the product view over whatever is actually available.

Assembles one `LiveState` document from the enabled providers. Every field
carries its reality label and provenance; a field with no enabled provider is
reported as UNAVAILABLE with the reason — the API never fills a gap with a
plausible number.

Serves the mandated product surface incrementally: fields whose subsystems are
not yet qualified (detector counts before P1 winner, forecasts before P4,
PREVENT/REACT before the control gate) are declared in the schema now and
report UNAVAILABLE until their subsystem passes its gate — the API shape is
stable from day one, the data arrives as science permits.

`build_app()` wraps the assembler in FastAPI when installed; the assembler is
plain Python so it is testable and usable without any web dependency.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from core.common.reality import RealityClass
from core.common.data.live_providers.providers import (CameraProvider, DHAKA_R1_CORRIDORS,
                              TrafficProvider, WeatherProvider)

UNAVAILABLE = "UNAVAILABLE"

# The full product surface, declared up front. Each entry maps to the gate that
# must pass before the field can carry data.
PRODUCT_FIELDS = {
    "current_traffic": "P-LIVE (Google Routes key)",
    "current_weather": "P-LIVE (Google Routes key)",
    "camera_freshness": "P-LIVE (camera provider qualification)",
    "detector_counts": "P1 winner + P2 tracking",
    "tracker_state": "P2",
    "forecast_5_15_30": "P4 forecasting gate",
    "prevent_react_state": "P5/P6 control gate",
    "candidate_routing_intervention": "routing gate (validated, frozen)",
    "candidate_signal_intervention": "P5/P6",
    "sumo_counterfactual": "twin gate",
    "network_wide_expected_improvement": "joint routing+control gate",
}


@dataclass
class LiveState:
    generated_utc: str
    city_id: str
    fields: dict = field(default_factory=dict)         # name -> value+provenance
    unavailable: dict = field(default_factory=dict)    # name -> reason

    def to_dict(self) -> dict:
        return asdict(self)


def _unavailable(reason: str) -> dict:
    return {"status": UNAVAILABLE, "reason": reason}


def assemble_live_state(
    city_id: str = "dhaka_r1",
    traffic: TrafficProvider | None = None,
    weather: WeatherProvider | None = None,
    camera: CameraProvider | None = None,
    corridors: Sequence[Mapping[str, Any]] = DHAKA_R1_CORRIDORS,
    extra: Mapping[str, Any] | None = None,
) -> LiveState:
    """One consistent snapshot. Providers that fail degrade to UNAVAILABLE."""
    state = LiveState(generated_utc=datetime.now(timezone.utc).isoformat(),
                      city_id=city_id)

    # --- current traffic --------------------------------------------------
    if traffic is not None and traffic.enabled:
        rows, errors = [], []
        for c in corridors:
            try:
                s = traffic.edge_state(c["corridor_id"], c["origin"], c["dest"])
                rows.append({
                    "corridor": s.corridor_id,
                    "duration_s": s.duration_s,
                    "static_duration_s": s.static_duration_s,
                    "traffic_delay_s": s.traffic_delay_s,
                    "reality": s.provenance.reality.value,
                    "captured_utc": s.provenance.captured_utc,
                    "provider": s.provenance.provider,
                })
            except Exception as exc:  # noqa: BLE001 — degraded, not crashed
                errors.append(f"{c['corridor_id']}: {exc}")
        state.fields["current_traffic"] = {
            "classification": "EXTERNAL_LIVE_REFERENCE",
            "corridors": rows, "errors": errors}
        if not rows:
            state.unavailable["current_traffic"] = "; ".join(errors) or "no corridors"
    else:
        state.unavailable["current_traffic"] = _unavailable(
            "no enabled TrafficProvider (GOOGLE_MAPS_API_KEY unset)")["reason"]

    # --- current weather --------------------------------------------------
    if weather is not None and weather.enabled:
        try:
            mid = corridors[0]
            w = weather.current(*mid["origin"])
            state.fields["current_weather"] = {
                **{k: v for k, v in asdict(w).items() if k != "provenance"},
                "reality": w.provenance.reality.value,
                "captured_utc": w.provenance.captured_utc,
                "provider": w.provenance.provider,
                "claim_status": "exogenous candidate — no forecasting benefit "
                                "claimed until ablation passes",
            }
        except Exception as exc:  # noqa: BLE001
            state.unavailable["current_weather"] = str(exc)
    else:
        state.unavailable["current_weather"] = "no enabled WeatherProvider"

    # --- camera freshness -------------------------------------------------
    if camera is not None and camera.enabled:
        try:
            cams = camera.list_cameras((23.723, 90.372, 23.762, 90.408))
            state.fields["camera_freshness"] = [
                {"camera_id": c.camera_id, "provider": c.provider,
                 "has_stream": c.has_stream, "freshness_s": c.freshness_s,
                 "reality": c.provenance.reality.value}
                for c in cams]
        except Exception as exc:  # noqa: BLE001
            state.unavailable["camera_freshness"] = str(exc)
    else:
        state.unavailable["camera_freshness"] = (
            "no qualified camera provider (INRIX/TrafficLand qualification in "
            "progress; Vizzion: no confirmed Dhaka coverage)")

    # --- gated subsystem fields ------------------------------------------
    for name, gate in PRODUCT_FIELDS.items():
        if name in state.fields or name in state.unavailable:
            continue
        state.unavailable[name] = f"gated on: {gate}"

    if extra:
        state.fields.update(dict(extra))

    return state


def build_app(**providers):
    """FastAPI wrapper — optional; the assembler above needs no web framework."""
    from fastapi import FastAPI

    app = FastAPI(title="DhakaFlow Live State",
                  description="Every field carries a reality label; absent data "
                              "is UNAVAILABLE with a reason, never fabricated.")

    @app.get("/live/state")
    def live_state():
        return assemble_live_state(**providers).to_dict()

    @app.get("/live/health")
    def health():
        return {p: getattr(v, "enabled", False)
                for p, v in providers.items() if v is not None}

    return app
