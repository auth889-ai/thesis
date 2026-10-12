"""The offline mesh table: the report's formulas, honest refusals, per-city tables, and the feed line."""
from __future__ import annotations

import ast
import json
import statistics
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from core.common import tag
from app.main import app
from core.networking.mesh import results

TRACE = "a" * 64


def _run(folder: Path, city: str, router: str, seed: int, delivered: int, created: int = 300, relayed: int = 100, latency: float = 50.0, trace: str = TRACE) -> None:
    (folder / "runs").mkdir(parents=True, exist_ok=True)
    (folder / "runs" / f"{router}_seed{seed}.json").write_text(json.dumps({
        "label": "SIMULATED", "city": city, "router": router, "seed": seed, "nodes": 4, "duration_s": 300, "pons_version": "pons-dtn 0.2.1",
        "radio": {"name": "BT_10m", "range_m": 10, "source": "test"}, "messages": {"interval_s": 1, "size_bytes": 100, "ttl_s": 300}, "ns2_trace_sha256": trace,
        "routing_stats": {"created": created, "delivered": delivered, "dropped": 0, "started": relayed, "relayed": relayed, "removed": 0, "aborted": 0, "dups": 0,
                          "latency_avg": latency if delivered else 0.0, "delivery_prob": delivered / created, "hops_avg": 1.0,
                          "overhead_ratio": (relayed - delivered) / delivered if delivered else 0.0}}))


def _movement(folder: Path, city: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "movement.json").write_text(json.dumps({"city": city, "network": "net.xml.gz", "network_sha256_uncompressed_in_city_config": "n" * 64,
                                                       "demand": {"kind": "SYNTHETIC randomTrips, UNCALIBRATED", "seed": 11, "period_s": 2.0, "horizon_s": 1800},
                                                       "sumo_version": "Eclipse SUMO sumo 1.27.1", "window_s": [900, 1200], "window_steps": 300, "vehicles_seen_in_window": 9,
                                                       "vehicles_kept_present_whole_window": 4, "routes_sha256": "r" * 64, "ns2_trace": "x.tcl", "ns2_trace_sha256": TRACE}))


def _configs(folder: Path, city: str, routers: list[str], seeds: list[int]) -> Path:
    c = folder / "configs"
    c.mkdir(exist_ok=True)
    (c / f"{city}.yaml").write_text(yaml.safe_dump({"city_id": city, "routers": routers, "seeds": seeds}))
    return c


def test_the_table_uses_the_report_formulas_and_leaves_seeds_without_deliveries_out_of_the_delay(tmp_path):
    ev, city = tmp_path / "ev", "c"
    _movement(ev, city)
    for seed, delivered, latency in ((1, 6, 40.0), (2, 0, 0.0), (3, 12, 80.0)):
        _run(ev, city, "epidemic", seed, delivered, latency=latency)
    for seed in (1, 2, 3):
        _run(ev, city, "prophet", seed, 3, relayed=3)
    cfg = _configs(tmp_path, city, ["epidemic", "prophet"], [1, 2, 3])
    out = results.build(city, runs=ev, root=tmp_path / "res", evidence=tmp_path / "evidence", configs=cfg)
    assert out["available"] and out["label"] == "SIMULATED" and out["city_id"] == city
    epi = out["rows"][0]
    ratios = [6 / 300, 0.0, 12 / 300]
    assert epi["delivery_ratio"] == {"mean": round(statistics.fmean(ratios), 3), "sd": round(statistics.stdev(ratios), 3), "min": 0.0, "max": 0.04, "n": 3}
    assert epi["delay_s"] == {"mean": 60.0, "sd": round(statistics.stdev([40.0, 80.0]), 1), "min": 40.0, "max": 80.0, "n": 2} and epi["seeds_without_delivery"] == 1
    assert epi["copies_per_message"]["mean"] == round(100 / 300, 2)
    assert out["rows"][1]["router"] == "prophet" and out["rows"][1]["overhead_ratio"]["mean"] == 0.0
    assert set(out["run_sha256"]) == {f"{r}_seed{s}.json" for r in ("epidemic", "prophet") for s in (1, 2, 3)}
    assert out["scope"]["vehicles_simulated"] == 4 and out["dataset"]["demand"]["kind"].startswith("SYNTHETIC")
    assert (tmp_path / "res" / city / "summary.json").exists() and (tmp_path / "evidence" / city / "results.json").exists()
    assert results.read(city, root=tmp_path / "res")["rows"][0]["name"] == "Epidemic"


def test_a_run_on_another_movement_trace_is_refused_and_a_city_without_runs_has_no_table(tmp_path):
    ev, city = tmp_path / "ev", "c"
    _movement(ev, city)
    _run(ev, city, "epidemic", 1, 3)
    _run(ev, city, "epidemic", 2, 3, trace="b" * 64)
    cfg = _configs(tmp_path, city, ["epidemic"], [1, 2])
    with pytest.raises(ValueError, match="movement trace"):
        results.build(city, runs=ev, root=tmp_path / "res", evidence=None, configs=cfg)
    other = results.build("elsewhere", runs=ev, root=tmp_path / "res", evidence=None, configs=cfg)
    assert other["available"] is False and "no data for this city" in other["reason"] and other["rows"] == []
    assert results.read("elsewhere", root=tmp_path / "res")["available"] is False


def test_the_endpoint_is_per_city_labelled_and_honest_about_missing_data():
    client = TestClient(app)
    r = client.get("/api/mesh/results/no_such_city")
    assert r.status_code == 200
    body = r.json()
    assert body["label"] == "SIMULATED" and body["city_id"] == "no_such_city"
    assert body["table"]["available"] is False and "no data for this city" in body["table"]["reason"]
    dhaka = client.get("/api/mesh/results/dhaka").json()["table"]
    if dhaka["available"]:                                                  # the checked-in Dhaka result, when it has been built
        assert dhaka["city_id"] == "dhaka" and dhaka["label"] == "SIMULATED" and all(r["delivery_ratio"]["n"] == 5 for r in dhaka["rows"])


def test_the_feed_line_carries_a_tag_and_belongs_to_one_city(monkeypatch, tmp_path):
    from app.alerts import service
    ev, city = tmp_path / "ev", "c"
    _movement(ev, city)
    for seed in (1, 2):
        _run(ev, city, "epidemic", seed, 6)
    cfg = _configs(tmp_path, city, ["epidemic"], [1, 2])
    results.build(city, runs=ev, root=tmp_path / "res", evidence=None, configs=cfg)
    monkeypatch.setattr(results, "RESULTS", tmp_path / "res")
    items = service.mesh_items(city)
    assert [(i["kind"], i["stamp"], i["tag"]["kind"], i["tag"]["calibrated_to"]) for i in items] == [("mesh", "SIMULATED", "simulated", "uncalibrated")]
    assert items[0]["values"]["ratio_pct"] == 2.0 and items[0]["values"]["vehicles"] == 4 and tag.untagged(items) == []
    assert service.mesh_items("elsewhere") == []
    assert service.FEED_KINDS["mesh"] is True


def test_the_mesh_package_sends_nothing_anywhere():
    banned = {"requests", "httpx", "urllib", "smtplib", "boto3", "socket", "twilio", "app.plan"}
    for f in (Path(results.__file__).parent).glob("*.py"):
        for node in ast.walk(ast.parse(f.read_text())):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""] if isinstance(node, ast.ImportFrom) else []
            assert not any(n.split(".")[0] in banned or n in banned for n in names), (f.name, names)


def test_the_plain_sentence_numbers_come_from_the_same_rows_as_the_table(tmp_path):
    """CLAUDE.md, plain language rule 5."""
    ev, city = tmp_path / "ev", "c"
    _movement(ev, city)
    for seed in (1, 2):
        _run(ev, city, "epidemic", seed, 6, latency=40.0)          # 2 %
        _run(ev, city, "prophet", seed, 9, latency=70.0)           # 3 %, the best
    cfg = _configs(tmp_path, city, ["epidemic", "prophet"], [1, 2])
    out = results.build(city, runs=ev, root=tmp_path / "res", evidence=None, configs=cfg)
    assert out["plain"] == {"vehicles": 4, "reached_pct": 3.0, "delay_s": 70, "router": "prophet"}
    best = max(out["rows"], key=lambda r: r["delivery_ratio"]["mean"])
    assert out["plain"]["reached_pct"] == round(100 * best["delivery_ratio"]["mean"], 1)
    dhaka = results.read("dhaka")
    if dhaka.get("available"):
        assert dhaka["plain"] == results.plain_numbers(dhaka["rows"], dhaka["scope"]["vehicles_simulated"])
