"""Single source of truth for where evidence lives and how to regenerate it."""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
FRONTEND = REPO / "dashboard/frontend"

# (file, command that produces it). A panel with no file renders its recipe, never an empty chart.
EVIDENCE: dict[str, tuple[str, str]] = {
    "live_series":   ("predict/data/live_dhaka/series.npz", "python predict/live_state.py"),
    "live_map":      ("predict/data/live_dhaka/corridor_edges.json", "python predict/live_to_edges.py --map"),
    "live_manifest": ("predict/data/live_dhaka/MANIFEST.json", "python predict/live_state.py"),
    "recorder":      ("artifacts/live_dhaka/RECORDER_MANIFEST.json", "python predict/record_live.py --live --yes"),
    "trained":       ("predict/results/trained_results.json", "python predict/record_results.py"),
    "floors":        ("predict/results/benchmark_floors.json", "python predict/benchmark_floors.py"),
    "comparison":    ("predict/results/phase1_comparison.json", "python predict/comparison_table.py"),
    "routing":       ("route/results/stats.json", "python route/stats.py --horizon 7200"),
    "live_chain":    ("route/results/live_chain.json", "python route/live_chain.py --seeds 11,12,13"),
    "incident":      ("route/results/incident.json", "python route/incident_scenario.py"),
    "penetration":   ("network/results/penetration.csv", "python network/penetration_sweep.py --all"),
    "latency":       ("network/results/latency.csv", "python network/latency_injection.py"),
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
