"""Single source of truth for where evidence lives and how to regenerate it."""
from __future__ import annotations

from pathlib import Path

from app.paths import REPO
FRONTEND = (REPO / "frontend/dist") if (REPO / "frontend/dist/index.html").exists() else REPO / "frontend"   # built app when `npm run build` ran, else the sources

# (file, command that produces it). A panel with no file renders its recipe, never an empty chart.
EVIDENCE: dict[str, tuple[str, str]] = {
    "live_series":   ("data/forecasting/live_dhaka/series.npz", "python -m app.forecasting.live.live_state"),
    "live_map":      ("data/forecasting/live_dhaka/corridor_edges.json", "python -m app.forecasting.live.live_to_edges --map"),
    "live_manifest": ("data/forecasting/live_dhaka/MANIFEST.json", "python -m app.forecasting.live.live_state"),
    "recorder":      ("results/artifacts/live_dhaka/RECORDER_MANIFEST.json", "python -m app.forecasting.live.record_live --live --yes"),
    "trained":       ("results/forecasting/trained_results.json", "python -m app.forecasting.evaluation.record_results"),
    "floors":        ("results/forecasting/benchmark_floors.json", "python -m app.forecasting.evaluation.benchmark_floors"),
    "comparison":    ("results/forecasting/phase1_comparison.json", "python -m app.forecasting.evaluation.comparison_table"),
    "routing":       ("results/routing/stats.json", "python -m app.protocols.statistics --horizon 7200"),
    "live_chain":    ("results/routing/live_chain.json", "python -m app.protocols.chains.live_chain --seeds 11,12,13"),
    "incident":      ("results/routing/incident.json", "python -m app.protocols.chains.incident_scenario"),
    "penetration":   ("results/networking/penetration.csv", "python -m app.networking.mosaic.penetration_sweep --all"),
    "latency":       ("results/networking/latency.csv", "python -m app.networking.mosaic.latency_injection"),
    "results_md":    ("results/RESULTS.md", "python research/reports/build_results.py"),
}

SSE_INTERVAL_S = 5
LEVELS = ["FREE_FLOW", "SLOW", "CONGESTED", "SEVERE"]


def path(key: str) -> Path:
    return REPO / EVIDENCE[key][0]


def command(key: str) -> str:
    return EVIDENCE[key][1]


def exists(key: str) -> bool:
    return path(key).exists()
