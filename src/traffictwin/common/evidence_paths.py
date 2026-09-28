"""Single source of truth for where evidence lives and how to regenerate it."""
from __future__ import annotations

from pathlib import Path

from traffictwin.paths import REPO
FRONTEND = REPO / "frontend"

# (file, command that produces it). A panel with no file renders its recipe, never an empty chart.
EVIDENCE: dict[str, tuple[str, str]] = {
    "live_series":   ("data/forecasting/live_dhaka/series.npz", "python -m traffictwin.forecasting.live.live_state"),
    "live_map":      ("data/forecasting/live_dhaka/corridor_edges.json", "python -m traffictwin.forecasting.live.live_to_edges --map"),
    "live_manifest": ("data/forecasting/live_dhaka/MANIFEST.json", "python -m traffictwin.forecasting.live.live_state"),
    "recorder":      ("results/artifacts/live_dhaka/RECORDER_MANIFEST.json", "python -m traffictwin.forecasting.live.record_live --live --yes"),
    "trained":       ("results/forecasting/trained_results.json", "python -m traffictwin.forecasting.evaluation.record_results"),
    "floors":        ("results/forecasting/benchmark_floors.json", "python -m traffictwin.forecasting.evaluation.benchmark_floors"),
    "comparison":    ("results/forecasting/phase1_comparison.json", "python -m traffictwin.forecasting.evaluation.comparison_table"),
    "routing":       ("results/routing/stats.json", "python -m traffictwin.protocols.statistics --horizon 7200"),
    "live_chain":    ("results/routing/live_chain.json", "python -m traffictwin.protocols.chains.live_chain --seeds 11,12,13"),
    "incident":      ("results/routing/incident.json", "python -m traffictwin.protocols.chains.incident_scenario"),
    "penetration":   ("results/networking/penetration.csv", "python -m traffictwin.networking.mosaic.penetration_sweep --all"),
    "latency":       ("results/networking/latency.csv", "python -m traffictwin.networking.mosaic.latency_injection"),
    "results_md":    ("results/RESULTS.md", "python results/build_results.py"),
}

SSE_INTERVAL_S = 5
LEVELS = ["FREE_FLOW", "SLOW", "CONGESTED", "SEVERE"]


def path(key: str) -> Path:
    return REPO / EVIDENCE[key][0]


def command(key: str) -> str:
    return EVIDENCE[key][1]


def exists(key: str) -> bool:
    return path(key).exists()
