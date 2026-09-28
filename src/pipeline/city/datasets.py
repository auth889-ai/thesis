"""The research datasets this project actually has, and what each one licenses us to claim.

The audit found the research datasets and the runtime dashboard were disconnected: METR-LA,
PEMS-BAY, PEMS07M, TrafficSH and the rest existed as files and results with no way for a reader to
see they existed at all. This catalog is the join.

The arrays themselves stay on Drive/S3 and are never vendored into git — but their EXISTENCE,
scale and provenance become visible, and a city can inherit a dataset's evidence to earn a
capability.

The field that decides the most here is `in_opencity_pretraining`. A dataset inside OpenCity's
pre-training corpus can never support a zero-shot claim about it, no matter how good the number is,
and this is the single place that fact is recorded so nothing downstream has to remember it.
"""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]

# From the commented-out `dataset_use` line in OpenCity's own conf/general_conf/pretrain.conf.
OPENCITY_PRETRAINING = {
    "CAD4-1", "CAD4-2", "CAD4-3", "CAD4-4", "CAD7-1", "CAD7-2", "CAD7-3", "CAD8-1", "CAD8-2",
    "CAD12-1", "CAD12-2", "PEMS08", "PEMS04", "PEMS_BAY", "METR_LA", "NYC_TAXI",
    "TrafficHZ", "TrafficZZ", "TrafficCD", "TrafficJN",
}

CATALOG: dict[str, dict] = {
    "METR-LA": {
        "dataset": "METR-LA", "city": "Los Angeles", "country": "USA", "reality": "REAL",
        "target": "speed (mph)", "nodes": 207, "timesteps": 34272, "interval_min": 5,
        "source": "DCRNN release (Li et al., ICLR 2018)",
        "in_opencity_pretraining": True,
        "storage": "Google Drive / S3 — not vendored into git",
    },
    "PEMS-BAY": {
        "dataset": "PEMS-BAY", "city": "Bay Area", "country": "USA", "reality": "REAL",
        "target": "speed (mph)", "nodes": 325, "timesteps": 52116, "interval_min": 5,
        "source": "DCRNN release (Li et al., ICLR 2018)",
        "in_opencity_pretraining": True,
        "storage": "Google Drive / S3 — not vendored into git",
    },
    "PEMS04": {"dataset": "PEMS04", "city": "California D4", "country": "USA", "reality": "REAL",
               "target": "flow", "nodes": 307, "timesteps": None, "interval_min": 5,
               "source": "PEMS release", "in_opencity_pretraining": True,
               "storage": "Google Drive / S3"},
    "PEMS08": {"dataset": "PEMS08", "city": "California D8", "country": "USA", "reality": "REAL",
               "target": "flow", "nodes": 170, "timesteps": None, "interval_min": 5,
               "source": "PEMS release", "in_opencity_pretraining": True,
               "storage": "Google Drive / S3"},
    "PEMS07M": {"dataset": "PEMS07M", "city": "California D7 (metro)", "country": "USA",
                "reality": "REAL", "target": "speed", "nodes": 228, "timesteps": 12672,
                "interval_min": 5, "source": "OpenCity release (hkuds/OpenCity-dataset)",
                "in_opencity_pretraining": False,
                "storage": "HuggingFace hkuds/OpenCity-dataset"},
    "TrafficSH": {"dataset": "TrafficSH", "city": "Shanghai", "country": "China", "reality": "REAL",
                  "target": "traffic index", "nodes": 896, "timesteps": 1403, "interval_min": 5,
                  "source": "OpenCity release", "in_opencity_pretraining": False,
                  "storage": "HuggingFace hkuds/OpenCity-dataset"},
    "TrafficNJ": {"dataset": "TrafficNJ", "city": "Nanjing", "country": "China", "reality": "REAL",
                  "target": "traffic index", "nodes": None, "timesteps": None, "interval_min": 5,
                  "source": "OpenCity release", "in_opencity_pretraining": False,
                  "storage": "HuggingFace hkuds/OpenCity-dataset"},
    "TrafficTJ": {"dataset": "TrafficTJ", "city": "Tianjin", "country": "China", "reality": "REAL",
                  "target": "traffic index", "nodes": None, "timesteps": None, "interval_min": 5,
                  "source": "OpenCity release", "in_opencity_pretraining": False,
                  "storage": "HuggingFace hkuds/OpenCity-dataset"},
    "DHAKA-LIVE": {
        "dataset": "DHAKA-LIVE", "city": "Dhaka", "country": "Bangladesh",
        "reality": "REAL_LIVE (derived)", "target": "congestion class / derived speed",
        "nodes": 12, "timesteps": None, "interval_min": 5,
        "source": "Google Routes API, RUNTIME_REFERENCE mode — derived verdicts only",
        "in_opencity_pretraining": False,
        "storage": "in-memory rolling buffer; route content is never written to disk",
        "caveat": ("12 API-derived corridors, not a sensor network. Below every threshold a "
                   "spatio-temporal model needs; see dhaka_opencity_schema.py --check"),
    },
}


def _load(path: Path) -> object:
    try:
        return json.loads((REPO / path).read_text())
    except (OSError, json.JSONDecodeError):
        return None


def enrich() -> dict[str, dict]:
    """Attach the results this project actually produced to each dataset entry.

    Everything here is read from an evidence file, so the catalog cannot drift from the results it
    advertises. A dataset with no results simply shows none.
    """
    cat = {k: dict(v) for k, v in CATALOG.items()}

    trained = _load(Path("results/forecasting/trained_results.json")) or {}
    for r in (trained.get("runs") or []):
        e = cat.get(r.get("dataset"))
        if not e:
            continue
        m = (r.get("metrics_by_horizon_min") or {}).get("15") or {}
        e.setdefault("city_specific_models", [])
        e.setdefault("model_results", [])
        if r["model"] not in e["city_specific_models"]:
            e["city_specific_models"].append(r["model"])
        e["model_results"].append({"model": r["model"], "mae@15min": m.get("mae"),
                                   "rmse@15min": m.get("rmse"), "protocol": "DCRNN 15-min"})

    oc = _load(Path("results/forecasting/opencity_crosscity.json")) or []
    for r in oc:
        e = cat.get(r.get("dataset"))
        if not e:
            continue
        avg = (r.get("metrics") or {}).get("average") or {}
        e["opencity_verdict"] = r.get("verdict")
        e["opencity_zero_shot"] = {"mae": avg.get("mae"), "rmse": avg.get("rmse"),
                                   "mape": avg.get("mape"),
                                   "published": (r.get("published") or {}).get("mae"),
                                   "protocol": "OpenCity 288-step horizon, authors' split"}
        e["exposure"] = r.get("exposure")

    # A dataset can be held out AND still be unusable. OpenCity's input window is 288 steps over
    # a graph of hundreds of nodes; a 12-corridor series satisfies neither. Being absent from the
    # pre-training corpus is necessary for a zero-shot claim, never sufficient.
    for k, e in cat.items():
        nodes, steps = e.get("nodes"), e.get("timesteps")
        reasons = []
        if nodes is not None and nodes < 20:
            reasons.append(f"only {nodes} nodes; OpenCity's graphs hold hundreds")
        if steps is not None and steps < 288:
            reasons.append(f"only {steps} steps; its input window is 288")
        e["opencity_schema_ok"] = not reasons if (nodes or steps) else None
        e["opencity_schema_blocking"] = reasons

    for k, e in cat.items():
        e.setdefault("exposure", "SEEN_IN_PRETRAINING" if e.get("in_opencity_pretraining")
                     else ("HELD_OUT_ZERO_SHOT" if e.get("in_opencity_pretraining") is False else None))
        e["comparable_protocols"] = (
            "OpenCity metrics use a 288-step horizon on the authors' split; city-specific models "
            "use 15-minute horizons under the DCRNN protocol. The two must not be compared "
            "directly.")
    return cat


def catalog() -> dict[str, dict]:
    return enrich()
