"""Fast tests for the rebuild tree (src/pipeline/forecasting/ src/pipeline/routing/ src/pipeline/nlp/ results/). No GPU, no network, no long SUMO runs."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from pipeline.routing import predictive_routing as pr  # noqa: E402
from traffictwin.protocols.chains import incident_scenario as inc  # noqa: E402

SMOKE_EDGEDATA = REPO / "results/routing/static_s11_h900/edgedata.xml"
PY = sys.executable

needs_nlp_model = pytest.mark.skipif(not (REPO / "results/nlp/tfidf_lr.joblib").exists(), reason="trained classifier is git-ignored; absent on CI")


def _tripinfo(tmp: Path, rows):
    tmp.mkdir(parents=True, exist_ok=True)
    body = "".join(f'<tripinfo id="v{i}" depart="{d}" arrival="{a}" duration="{du}" waitingTime="{w}" timeLoss="{tl}" departDelay="0" rerouteNo="{r}"/>'
                   for i, (d, a, du, w, tl, r) in enumerate(rows))
    (tmp / "tripinfo.xml").write_text(f"<tripinfos>{body}</tripinfos>")
    (tmp / "statistic.xml").write_text('<statistic><vehicles loaded="5" inserted="4" running="1" waiting="1"/><teleports total="2"/></statistic>')


def test_parse_metrics_arithmetic(tmp_path):
    #             depart arrival duration waiting timeLoss reroute
    _tripinfo(tmp_path, [(0, 100, 100, 10, 20, 0), (0, 300, 300, 30, 40, 1), (0, -1, 0, 0, 0, 0)])
    m = pr.parse_metrics(tmp_path, horizon=1000)
    assert m["arrived"] == 2 and m["unfinished"] == 1
    assert m["mean_travel_time_s"] == 200 and m["p95_travel_time_s"] == 300
    assert m["total_waiting_s"] == 40 and m["teleports"] == 2 and m["inserted"] == 4
    # vehicle-hours charges the unfinished trip up to the horizon: (100 + 300 + 1000) / 3600
    assert abs(m["total_vehicle_hours"] - 1400 / 3600) < 1e-9
    assert abs(m["mean_travel_time_all"] - 1400 / 3) < 1e-9
    assert m["vehicles_rerouted_at_least_once"] == 1


def test_equipped_is_deterministic_and_calibrated():
    ids = [f"od{i:04d}_{j}_c0" for i in range(200) for j in range(50)]
    frac = sum(pr.equipped(v, 0.3) for v in ids) / len(ids)
    assert abs(frac - 0.3) < 0.02
    assert [pr.equipped(v, 0.3) for v in ids[:500]] == [pr.equipped(v, 0.3) for v in ids[:500]]
    assert not any(pr.equipped(v, 0.0) for v in ids[:1000]) and all(pr.equipped(v, 1.0) for v in ids[:1000])


@pytest.mark.skipif(not SMOKE_EDGEDATA.exists(), reason="needs a static smoke run")
def test_load_weights_and_forecast_to_weights_sources(tmp_path):
    rows = pr.load_weights(SMOKE_EDGEDATA)
    assert rows and all(len(r) == 4 and r[3] > 0 for r in rows)
    intervals = sorted({(b, e) for b, e, _, _ in rows})
    assert intervals[0][0] == 0.0 and intervals[0][1] == 300.0
    for src in ("oracle", "persistence"):
        out = tmp_path / f"{src}.xml"
        r = subprocess.run([PY, str(REPO / "src/pipeline/forecasting/forecast_to_weights.py"), "--source", src, "--edgedata", str(SMOKE_EDGEDATA),
                            "--out", str(out)], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr[-800:]
        got = pr.load_weights(out)
        if src == "oracle":
            assert sorted(got) == sorted(rows)
        else:  # persistence: interval [b,e) carries the source's [b-300, e-300)
            src_map = {(b, e, edge): tt for b, e, edge, tt in rows}
            shifted = [(b, e, edge, tt) for b, e, edge, tt in got if b >= 300]
            assert shifted and all(abs(src_map[(b - 300, e - 300, edge)] - tt) < 1e-6 for b, e, edge, tt in shifted)


def test_incident_helpers():
    assert inc.pct(100, 80) == -20.0 and inc.pct(0, 5) is None
    lo, hi = inc.boot_ci([-10.0, -12.0, -8.0])
    assert lo <= -10.0 <= hi and lo >= -12.0 and hi <= -8.0
    ev = inc.load_event(REPO / "results/nlp/events_karwan_bazar.jsonl")
    assert ev["edges"] and ev["factor"] >= 3 and ev["label"] in ("incident", "congestion")


@needs_nlp_model
def test_event_feed_maps_karwan_bazar_to_r1_edges(tmp_path):
    out = tmp_path / "ev.jsonl"
    r = subprocess.run([PY, str(REPO / "src/pipeline/nlp/event_feed.py"), "--text", "Heavy jam at Karwan Bazar after a bus breakdown", "--out", str(out)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-800:]
    ev = [json.loads(l) for l in out.read_text().splitlines() if l.strip()]
    assert ev and ev[0]["place"] and ev[0]["place"].lower().startswith("karwan") and ev[0]["edges"]
    assert ev[0]["label"] in ("incident", "congestion") and ev[0]["factor"] > 1


def test_gazetteer_all_inside_or_labelled():
    g = json.loads((REPO / "src/pipeline/nlp/gazetteer.json").read_text())
    places = g if isinstance(g, list) else g.get("places", list(g.values()))
    assert len(places) >= 25
    for p in places:
        assert "lat" in p and "lon" in p and 23.6 < float(p["lat"]) < 23.95 and 90.3 < float(p["lon"]) < 90.5


def test_build_results_marks_missing(tmp_path, monkeypatch):
    r = subprocess.run([PY, str(REPO / "results/build_results.py")], capture_output=True, text=True, cwd=REPO)
    assert r.returncode == 0, r.stderr[-500:]
    txt = (REPO / "results/RESULTS.md").read_text()
    assert "Traceback" not in txt and "## Routing" in txt


@pytest.mark.slow
def test_static_and_predictive_smoke(tmp_path):
    for arm, extra in (("static", []), ("predictive", ["--weights", str(SMOKE_EDGEDATA), "--compliance", "0.3"])):
        out = tmp_path / arm
        r = subprocess.run([PY, str(REPO / "src/pipeline/routing/predictive_routing.py"), "--arm", arm, "--seed", "11", "--horizon", "300", "--out", str(out)] + extra,
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stderr[-800:]
        m = json.loads((out / "metrics.json").read_text())["metrics"]
        assert {"arrived", "total_vehicle_hours", "teleports"} <= set(m)
