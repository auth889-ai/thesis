"""Single source of truth for where evidence lives and how to regenerate it."""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
FRONTEND = REPO / "dashboard/frontend"

# (file, command that produces it). A panel with no file renders its recipe, never an empty chart.
EVIDENCE: dict[str, tuple[str, str]] = {
    "live_series":   ("data/forecasting/live_dhaka/series.npz", "python pipeline/forecasting/live_state.py"),
    "live_map":      ("data/forecasting/live_dhaka/corridor_edges.json", "python pipeline/forecasting/live_to_edges.py --map"),
    "live_manifest": ("data/forecasting/live_dhaka/MANIFEST.json", "python pipeline/forecasting/live_state.py"),
    "recorder":      ("artifacts/live_dhaka/RECORDER_MANIFEST.json", "python pipeline/forecasting/record_live.py --live --yes"),
    "trained":       ("results/forecasting/trained_results.json", "python pipeline/forecasting/record_results.py"),
    "floors":        ("results/forecasting/benchmark_floors.json", "python pipeline/forecasting/benchmark_floors.py"),
    "comparison":    ("results/forecasting/phase1_comparison.json", "python pipeline/forecasting/comparison_table.py"),
    "routing":       ("results/routing/stats.json", "python pipeline/routing/stats.py --horizon 7200"),
    "live_chain":    ("results/routing/live_chain.json", "python pipeline/routing/live_chain.py --seeds 11,12,13"),
    "incident":      ("results/routing/incident.json", "python pipeline/routing/incident_scenario.py"),
    "penetration":   ("results/networking/penetration.csv", "python pipeline/networking/penetration_sweep.py --all"),
    "latency":       ("results/networking/latency.csv", "python pipeline/networking/latency_injection.py"),
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
