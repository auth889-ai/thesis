"""The tag that travels with every traffic value from the backend to the page (docs/ARCHITECTURE_PLAN.md, rule 18).

    real        someone measured it: who (`source`), the time it refers to (`as_of`), the dataset or station
    simulated   a model of the world produced it: what it is calibrated to, or "uncalibrated", and on what basis
    forecast    a model's statement about a time that has not come: the model, when it was issued, the real data it
                rests on, and how its uncertainty is given

A forecast is neither a measurement nor a simulation, so it has its own word instead of borrowing one of the two.
A value is sent as `{"value", "unit", "tag"}`; a page does not show a value that arrives without a tag.

Map attributes (a road section's length, its speed limit, its shape) are not traffic values. They are described once
per response by its `network` block and are listed in STRUCTURAL, which the test for untagged numbers reads.
"""
from __future__ import annotations

UNCALIBRATED = "uncalibrated"
STRUCTURAL = {"geometry", "length_m", "limit_kmh", "heading_deg", "lat", "lon", "horizons_min", "bbox", "bearing_deg", "section_distance_m", "window_s"}


def real(source: str, as_of: str, dataset: str | None = None, **more) -> dict:
    return {"kind": "real", "source": source, "as_of": as_of, "dataset": dataset, **more}


def simulated(basis: str, calibrated_to: str | None = None, **more) -> dict:
    return {"kind": "simulated", "calibrated_to": calibrated_to or UNCALIBRATED, "basis": basis, **more}


def forecast(model: str, issued_at: str, based_on: str, uncertainty: str, **more) -> dict:
    return {"kind": "forecast", "model": model, "issued_at": issued_at, "based_on": based_on, "uncertainty": uncertainty, **more}


def tagged(value: float, unit: str, tag: dict, **more) -> dict:
    return {"value": value, "unit": unit, "tag": tag, **more}


def untagged(obj, path: str = "") -> list[str]:
    """Paths of the numbers in a response that carry no tag and are not map attributes."""
    if isinstance(obj, dict):
        if "tag" in obj and "value" in obj:
            return [] if isinstance(obj["tag"], dict) and obj["tag"].get("kind") in ("real", "simulated", "forecast") else [path or "."]
        return [p for k, v in obj.items() if k not in STRUCTURAL for p in untagged(v, f"{path}.{k}")]
    if isinstance(obj, (list, tuple)):
        return [p for i, v in enumerate(obj) for p in untagged(v, f"{path}[{i}]")]
    return [path] if isinstance(obj, (int, float)) and not isinstance(obj, bool) else []
