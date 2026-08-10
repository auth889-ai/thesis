"""Synthetic recovery test for the Stage-1 (paper-faithful) notebook.

Generates ~40 fake detectors whose (occ, flow, speed) obey a KNOWN triangular
fundamental diagram (vf=50 km/h, capacity q_c=1800 veh/h/lane at k*=36,
jam kappa=150 veh/km/lane), with occupancy stored on a 0-100 percent scale and
noise + planted defects. Runs the notebook's real cells (Colab-only cells
stubbed) and asserts the estimated critical point recovers the planted one.

Run:  python3 tests/test_stage1_synthetic.py   (~30 s, tiny data)
"""
import json, os, pathlib, tempfile
import numpy as np

os.environ["MPLBACKEND"] = "Agg"
import pandas as pd

rng = np.random.default_rng(7)
TMP = pathlib.Path(tempfile.mkdtemp(prefix="lab00_s1_"))
(TMP / "raw").mkdir()
for d in ["stage1/figures", "stage1/tables"]:
    (TMP / d).mkdir(parents=True)

# ---- ground truth triangular FD (per lane) ----
VF, KC, QC, KAPPA = 50.0, 36.0, 1800.0, 150.0   # q* = VF*KC = 1800
W = QC / (KAPPA - KC)                             # backward wave ~15.8 km/h

def q_of_k(k):
    return np.where(k <= KC, VF * k, W * (KAPPA - k))

# ---- synthesize measurements: 40 detectors x 5 days x 288 intervals ----
DET_LEN = 1.0 / 120.0  # effective (veh+det) length km -> occ_frac = k * DET_LEN
rows = []
for det in range(40):
    for day in range(1, 6):
        # demand profile: two peaks pushing some intervals past critical density
        t = np.arange(0, 86400, 300)
        base = 0.25 + 0.75 * (np.exp(-((t/3600 - 8.5) / 1.8) ** 2) +
                              np.exp(-((t/3600 - 18.0) / 2.2) ** 2))
        k = np.clip(base * (KC * 1.9) * rng.uniform(0.85, 1.15, len(t)), 0.3, KAPPA * 0.95)
        q = q_of_k(k) * rng.normal(1.0, 0.05, len(t))
        occ_pct = np.clip(k * DET_LEN * 100.0, 0.05, 99.0)   # percent scale!
        v = q / k
        for ti, qi, oi, vi in zip(t, q, occ_pct, v):
            rows.append([f"2017-06-0{day}", ti, f"synthdet{det:03d}", round(max(qi, 0), 1),
                         round(oi, 3), "", "synthcity", round(vi, 1)])
# planted defects: error-flagged, negative flow, dup
rows.append(["2017-06-01", 0, "synthdet000", 500.0, 5.0, "err1", "synthcity", 30])
rows.append(["2017-06-01", 300, "synthdet000", -9.0, 5.0, "", "synthcity", 30])
rows.append(rows[0])

pd.DataFrame(rows, columns=["day", "interval", "detid", "flow", "occ", "error", "city", "speed"]) \
  .to_csv(TMP / "raw/utd19_u.csv", index=False)
print(f"synthetic file: {len(rows):,} rows")

# ---- execute the notebook cells ----
NB = pathlib.Path(__file__).resolve().parent.parent / "notebooks" / "Lab00_UTD19_PaperFaithful_Colab.ipynb"
nb = json.load(open(NB))
cells = [c["source"] if isinstance(c["source"], str) else "".join(c["source"])
         for c in nb["cells"] if c["cell_type"] == "code"]

ns = {"__name__": "__stage1_test__"}
SKIP = ["drive.mount", "%pip"]
import pathlib as _p, datetime as _dt, duckdb as _duck, scipy as _scipy, matplotlib as _mpl
for i, src in enumerate(cells):
    if src.startswith("# ========================= STAGE 1 CONFIG"):
        exec(compile(src, f"s1cell{i}", "exec"), ns)
        ns["CONFIG"].update({
            "drive_root": str(TMP), "seed": 42, "city": "synthcity",
            "n_draws": 40,                       # smaller for test speed
            "min_detectors_per_interval": 5,
            "min_valid_intervals_per_detector": 100,
            "k_bin_width_candidates": [2.0, 4.0],
            "duckdb_temp_dir": str(TMP / "ddb_tmp"),
        })
        continue
    if any(m in src for m in SKIP):
        # provide what the skipped cells define
        if "drive.mount" in src:
            ns.update({"os": os, "pathlib": _p, "ROOT": TMP, "RAW": TMP / "raw", "S1": TMP / "stage1"})
        if "%pip" in src:
            ns.update({"sys": __import__("sys"), "platform": __import__("platform"),
                       "datetime": _dt, "np": np, "pd": pd, "duckdb": _duck,
                       "scipy": _scipy, "matplotlib": _mpl,
                       "ENV": {"synthetic": True}, "rng": np.random.default_rng(42)})
        continue
    if "urllib.request" in src:   # comparison cell fetches supplementary; run offline-safe
        src = src.replace('urllib.request.urlretrieve(url, supp)', 'pass')
    exec(compile(src, f"s1cell{i}", "exec"), ns)

# ---- assertions against planted truth ----
r = ns["results"][(2.0, 0.95)]
k_star, q_star, v_star = r["k_crit"], r["q_crit"], r["v_crit"]
print(f"\nplanted:   k*={KC}, q*={QC}, v*={QC/KC:.1f}")
print(f"recovered: k*={k_star:.1f}, q*={q_star:.0f}, v*={v_star:.1f}")
assert ns["OCC_PERCENT"] is True or ns["OCC_PERCENT"] == True, "percent scale not detected"
assert abs(k_star - KC) / KC < 0.30, f"k* off by >30%: {k_star} vs {KC}"
assert abs(q_star - QC) / QC < 0.15, f"q* off by >15%: {q_star} vs {QC}"
assert abs(v_star - QC / KC) / (QC / KC) < 0.35, f"v* off by >35%"
rem = pd.read_csv(TMP / "stage1/tables/stage1_filter_counts.csv").set_index("rule")
assert int(rem.loc["V10_error_flag", "flagged"]) == 1
assert int(rem.loc["V4_negative_flow", "flagged"]) == 1
assert (TMP / "stage1/figures/PAPER_FAITHFUL_MFD.png").exists()
assert (TMP / "stage1/figures/critical_point_visualization.png").exists()
assert (TMP / "stage1/stage1_run_record.json").exists()
print("\nALL STAGE-1 SYNTHETIC TESTS PASSED — planted critical point recovered within tolerance")
