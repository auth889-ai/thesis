"""Tiny synthetic test of the Lab 00 notebook's core SQL logic.

Runs the notebook's code cells (minus Colab-only mount/install/download cells)
against a ~2000-row synthetic UTD19-shaped CSV. No real data, no heavy compute —
this validates SQL syntax, validation-rule arithmetic, city selection, and the
manual-verification assertions before anything runs in Colab.

Run:  python3 tests/test_notebook_sql_synthetic.py
"""
import csv, json, pathlib, random, sys, tempfile

random.seed(42)
TMP = pathlib.Path(tempfile.mkdtemp(prefix="lab00_synth_"))

# ---- synthetic utd19_u.csv: 2 cities, known-planted defects ----
rows = []
for city, ndet, fmt in [("synthcity", 6, "%Y-%m-%d"), ("othercity", 2, "%d.%m.%Y")]:
    for det in range(ndet):
        for day in (["2017-05-0%d" % d for d in range(1, 4)] if fmt == "%Y-%m-%d"
                    else ["0%d.05.2017" % d for d in range(1, 3)]):
            for t in range(0, 86400, 3600):  # hourly to stay tiny
                flow = round(random.uniform(100, 900), 1)
                occ = round(random.uniform(0.01, 0.6), 4)
                speed = round(random.uniform(10, 60), 1) if city == "synthcity" else ""
                rows.append([day, t, f"{city}_det{det}", flow, occ, "", city, speed])
# planted defects (known counts)
rows.append(["2017-05-01", 0, "synthcity_det0", -5.0, 0.1, "", "synthcity", 30])     # V4 x1
rows.append(["2017-05-01", 3600, "synthcity_det0", 500.0, 0.0, "", "synthcity", 30]) # V7 x1
rows.append(["2017-05-01", 7200, "synthcity_det0", 500.0, 1.7, "", "synthcity", 30]) # V5 x1
rows.append(["bad-date", 7200, "synthcity_det1", 100.0, 0.1, "", "synthcity", 30])   # V1 x1
rows.append(rows[0])                                                                  # V2 x1 dup
rows.append(["2017-05-01", 10800, "synthcity_det2", "", 0.1, "e1", "synthcity", 30]) # V3+V10
U = TMP / "utd19_u.csv"
with open(U, "w", newline="") as f:
    w = csv.writer(f); w.writerow(["day", "interval", "detid", "flow", "occ", "error", "city", "speed"])
    w.writerows(rows)

D = TMP / "detectors.csv"
with open(D, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["detid", "length", "pos", "fclass", "road", "limit", "lanes", "linkid", "long", "lat", "citycode"])
    for city, ndet in [("synthcity", 6), ("othercity", 2)]:
        for det in range(ndet):
            if city == "synthcity" and det == 5:
                continue  # planted V8 orphan
            w.writerow([f"{city}_det{det}", 0.01, 0.005, "primary", "Main St", 50, 2, det, 90.4, 23.8, city])
(TMP / "links.csv").write_text("linkid,order\n1,1\n")

# ---- execute notebook code cells with Colab-only cells stubbed ----
NB = pathlib.Path(__file__).resolve().parent.parent / "notebooks" / "Lab00_UTD19_Colab.ipynb"
nb = json.load(open(NB))
code_cells = [c["source"] if isinstance(c["source"], str) else "".join(c["source"])
              for c in nb["cells"] if c["cell_type"] == "code"]

import os as _os
_os.environ["MPLBACKEND"] = "Agg"  # headless plotting for the tiny test
import pathlib as _p, numpy as _np, pandas as _pd

ns = {}
SKIP_MARKERS = ["drive.mount", "eth_discover()", "%pip", "shutil.make_archive"]
ROOT = TMP / "drive_root"
for d in ["raw", "processed", "outputs/audit", "outputs/figures", "outputs/manifest", "repo_artifacts"]:
    (ROOT / d).mkdir(parents=True, exist_ok=True)
import shutil as _sh
for name in ["utd19_u.csv", "detectors.csv", "links.csv"]:
    _sh.copy2(TMP / name, ROOT / "raw" / name)

# pre-seed names normally created by the Colab-only (skipped) cells
ns.update({"os": _os, "pathlib": _p, "pd": _pd, "np": _np,
           "ROOT": ROOT, "ENV": {"synthetic": True}})

executed = skipped = 0
for i, src in enumerate(code_cells):
    if src.startswith("# ============================== CONFIG"):
        exec(compile(src, f"cell{i}", "exec"), ns)
        ns["CONFIG"]["drive_root"] = str(ROOT)
        ns["CONFIG"]["duckdb_temp_dir"] = str(TMP / "ddb_tmp")
        ns["CONFIG"]["select"] = {"min_speed_nonnull_frac": 0.5, "min_rows": 100,
                                  "max_rows": 10**9, "min_detectors": 3, "min_days": 2,
                                  "max_error_rate": 0.10}
        ns["CONFIG"]["smoke_days"] = 2
        ns["CONFIG"]["mfd_min_detectors"] = 3
        executed += 1
        continue
    if any(m in src for m in SKIP_MARKERS):
        skipped += 1
        continue
    exec(compile(src, f"cell{i}", "exec"), ns)
    executed += 1

# ---- assertions on planted defects ----
rep = ns["rep"].set_index("rule")
CITY = ns["CITY"]
assert CITY == "synthcity", CITY
# V2 = 5: the V4/V5/V7/V3 planted rows reuse (detid, day, interval) keys that the
# base loop already emitted, plus the one explicit duplicate row → 5 key collisions.
checks = {"V4_negative_flow": 1, "V7_flow_without_occ": 1, "V5_occ_out_of_range": 1,
          "V1_bad_timestamp": 1, "V2_duplicate_key": 5, "V10_error_flagged": 1,
          "V8_detid_missing_metadata": 1}
for rule, expected in checks.items():
    got = int(rep.loc[rule, "flagged"])
    assert got == expected, f"{rule}: expected {expected}, got {got}"
assert int(rep.loc["V3_missing_flow_or_occ", "flagged"]) == 1
assert ns["MODAL_STEP"] == 3600
assert len(ns["days"]) == 2
print(f"executed {executed} cells, skipped {skipped} Colab-only cells")
print("ALL SYNTHETIC TESTS PASSED — planted defect counts all recovered exactly")
