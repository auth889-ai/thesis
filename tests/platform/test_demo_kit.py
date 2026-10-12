"""Supervisor demo kit (scripts/demo/): the check names a fix for what is missing; the figures show the saved numbers only."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def load(name: str):
    spec = importlib.util.spec_from_file_location(f"demo_{name}", REPO / f"scripts/demo/{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_check_names_a_fix_for_a_missing_file(tmp_path):
    rows = load("check").checks(repo=tmp_path)                 # an empty folder: every data file is missing
    missing = [r for r in rows if "rq1/summary.json" in r[0]]
    assert missing and not missing[0][1] and "make fetch-data" in missing[0][2]
    assert all(fix for _, ok, fix, _ in rows if not ok)


def test_forecast_figure_uses_the_summary_numbers():
    s = json.loads((REPO / "results/forecasting/rq1/summary.json").read_text())
    d = load("forecast").series(s)
    la = s["lab"]["METR-LA"]
    assert d["Los Angeles, best trained (D2STGNN)"][2] == la["D2STGNN"]["60"]["mae"] / la["persistence"]["60"]["mae"]
    dhaka = next(v for k, v in d.items() if k.startswith("Dhaka"))
    best15 = min(s["dhaka"][m]["15"]["mae"] for m in ("chronos", "chronos2", "timesfm"))
    assert dhaka[0] == best15 / s["dhaka"]["persistence"]["15"]["mae"]
    assert d["_stop_and_go"]["Dhaka BM"] == s["character"]["DhaTraX"]["sites"]["BM"]["stop_and_go_share"]


def test_phone_subset_is_fixed_by_the_seed_and_renumbered():
    spec = importlib.util.spec_from_file_location("demo_mesh_subset", REPO / "scripts/demo/mesh.py")
    src = spec.loader.get_source("demo_mesh_subset")
    ns: dict = {}
    exec(src[src.index("def subset"):src.index("def run(")], {"random": __import__("random")}, ns)   # pons lives in the mesh venv only
    moves = [(t, i, float(i), 0.0, 0) for t in range(3) for i in range(17)]
    a, b = ns["subset"](moves, 17, 4, 1), ns["subset"](moves, 17, 4, 1)
    assert a == b and {m[1] for m in a} == {0, 1, 2, 3}
    assert ns["subset"](moves, 17, 17, 1) == moves               # all phones = the study's own trace, unchanged
