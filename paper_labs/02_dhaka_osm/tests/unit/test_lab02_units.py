"""SUMO-free unit tests for Lab 02 building blocks."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.osm.download import overpass_query  # noqa: E402
from src.network.build import classify_warnings  # noqa: E402
from src.validation.network_checks import _kosaraju_largest_scc  # noqa: E402
from src.metrics.summarize import percentile  # noqa: E402


def test_overpass_query_contains_bbox_and_highway_filter():
    q = overpass_query({"south": 23.723, "west": 90.372, "north": 23.762, "east": 90.408})
    assert "23.723,90.372,23.762,90.408" in q
    assert 'way["highway"]' in q and "out body" in q


def test_warning_classifier_buckets_and_flags_unknown():
    log = ("Warning: Removed 42 geometry nodes\n"
           "Warning: Joining junctions cluster_1\n"
           "Warning: The mysterious frobnicator failed\n"
           "Info: irrelevant line\n")
    r = classify_warnings(log)
    assert r["counts"]["removed_geometry_node"] == 1
    assert r["counts"]["junction_join"] == 1
    assert r["counts"]["unclassified"] == 1
    assert "frobnicator" in r["unclassified_samples"][0]


def test_kosaraju_finds_largest_scc():
    # a<->b<->c cycle plus dangling d (a->d only)
    fwd = {"a": {"b", "d"}, "b": {"c"}, "c": {"a"}, "d": set()}
    scc = _kosaraju_largest_scc(fwd)
    assert scc == {"a", "b", "c"}


def test_kosaraju_disconnected_components():
    fwd = {"a": {"b"}, "b": {"a"}, "x": {"y"}, "y": {"z"}, "z": {"x"}}
    assert _kosaraju_largest_scc(fwd) == {"x", "y", "z"}


def test_percentile_matches_linear_interpolation():
    assert percentile([1, 2, 3, 4, 5], 50) == 3
    assert percentile([1, 2, 3, 4, 5], 100) == 5
    assert abs(percentile([1, 2, 3, 4], 50) - 2.5) < 1e-9
