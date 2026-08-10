"""Build Lab00_UTD19_PaperFaithful_Colab.ipynb (Stage 1) deterministically.

Rebuild with:  python3 src/build_stage1_notebook.py
Implements the paper-faithful estimation chain of Loder et al. 2019 (METHOD_SPEC
§4-5) for the selected city (torino), reading data ALREADY in Drive — no
re-download. Classification: independent paper-faithful reconstruction.
"""
import json
from pathlib import Path

CELLS = []

def md(src):
    CELLS.append({"cell_type": "markdown", "metadata": {}, "source": src})

def code(src):
    CELLS.append({"cell_type": "code", "execution_count": None, "metadata": {},
                  "outputs": [], "source": src})

md("""# Lab 00 · Stage 1 — PAPER_FAITHFUL_MFD (torino, UNCALIBRATED_ANALYSIS)

**Classification: Independent paper-faithful reconstruction; this is not the authors' official analysis code.**

Implements the published estimation chain (Loder et al. 2019, Methods; refs 12, 17, 18, 42, 43):
1. City extraction + validation exclusions **including dataset error-flagged rows** (paper filters "obvious errors").
2. Occupancy-scale handling (torino reports percent 0–100 → converted to fraction) and **step-1 occupancy rescaling** (ref 42): per detector, rescale occupancy so its free-flow q/o matches its measured free-flow speed. Torino reports speeds, so no Google step-2 is *needed* for a per-lane analysis — the historical Google calibration remains `UNREPRODUCIBLE_FROM_AVAILABLE_HISTORICAL_INPUTS`; therefore all outputs stay labelled **UNCALIBRATED_ANALYSIS** (per-lane units, no network-length L-scaling, no km² normalization).
3. **Re-sampling** (ref 17): 300 draws × 80% of detectors, seeded.
4. **Upper bound** (ref 43): flow's 95th and 97.5th percentiles per density bin (both kept as sensitivity, no silent choice).
5. **Functional-form fit** (ref 18): q(k) = −λ·ln(e^{−v_f k/λ} + e^{−Q/λ} + e^{−(κ−k)w/λ}) by bounded nonlinear least squares.
6. **Critical point** = maximum of the fitted curve: (k\\*, q\\*), v\\* = q\\*/k\\*.
7. Manual verification + comparison against the paper's published aggregate facts.

Units here: q (veh/h **per lane**), k (veh/km **per lane**). The paper's n\\*, P\\* are per km² of network — converting requires network lane-length L from OSM (out of Stage-1 scope, documented in ASSUMPTIONS.md).
""")

code("""# ========================= STAGE 1 CONFIG =========================
CONFIG = {
    "drive_root": "/content/drive/MyDrive/DhakaFlow-Nexus-Data/Lab00_UTD19",
    "city": "torino",
    "seed": 42,
    "n_draws": 300,          # PUBLISHED (Methods: 300 draws)
    "sample_frac": 0.80,     # PUBLISHED (80% sample size)
    "quantiles": [0.95, 0.975],   # PUBLISHED band edges; both fitted (sensitivity)
    "k_bin_width_candidates": [2.0, 4.0],  # veh/km/lane; ASSUMED (paper silent) -> sensitivity
    "min_detectors_per_interval": 10,
    "freeflow_speed_pct": 0.85,   # ASSUMED: detector free-flow speed = 85th pct of its measured speed
    "freeflow_occ_pct": 0.10,     # ASSUMED: free-flow intervals = occ below detector's 10th pct
    "min_valid_intervals_per_detector": 500,  # ASSUMED: drop sparsely-reporting detectors
    "duckdb_memory_limit": "8GB",
    "duckdb_temp_dir": "/content/duckdb_tmp",
}
print("STAGE1 CONFIG ok")""")

md("## 1 · Mount Drive (data must already exist — this stage never downloads UTD19)")

code("""import os, pathlib
from google.colab import drive
drive.mount('/content/drive')
ROOT = pathlib.Path(CONFIG["drive_root"]); RAW = ROOT / "raw"
assert (RAW / "utd19_u.csv").exists(), "utd19_u.csv missing in Drive — run the smoke notebook first"
S1 = ROOT / "stage1"; [ (S1 / d).mkdir(parents=True, exist_ok=True) for d in ["figures", "tables"] ]
print("Drive ok:", ROOT)""")

code("""%pip -q install duckdb==1.1.3 pandas==2.2.2 pyarrow==17.0.0 matplotlib==3.8.4 scipy==1.13.1
import sys, platform, datetime, numpy as np, pandas as pd, duckdb, scipy, matplotlib
ENV = {"run_started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
       "python": sys.version.split()[0], "platform": platform.platform(),
       "duckdb": duckdb.__version__, "pandas": pd.__version__, "numpy": np.__version__,
       "scipy": scipy.__version__, "matplotlib": matplotlib.__version__, "seed": CONFIG["seed"]}
print(ENV)
rng = np.random.default_rng(CONFIG["seed"])""")

md("""## 2 · Extract the full torino set (all days), paper-style filtering

Exclusions (each counted, nothing silent): V1 bad time, V2 duplicate keys, V3
missing flow/occ, V4 negative flow, V5 occ out of range, V7 flow without occ,
**V10 dataset error flag** (paper: "filter the data for obvious errors").
Occupancy is converted percent→fraction if the city's 99.9th percentile > 1.5.""")

code("""os.makedirs(CONFIG["duckdb_temp_dir"], exist_ok=True)
con = duckdb.connect()
con.execute(f\"\"\"SET memory_limit='{CONFIG["duckdb_memory_limit"]}';
                SET temp_directory='{CONFIG["duckdb_temp_dir"]}';\"\"\")
U = str(RAW / "utd19_u.csv")
con.execute(f\"\"\"
CREATE OR REPLACE TABLE t_raw AS
SELECT trim(detid) AS detid,
       coalesce(try_strptime(day, '%Y-%m-%d')::DATE, try_strptime(day, '%d.%m.%Y')::DATE) AS day,
       try_cast("interval" AS BIGINT) AS interval_s,
       try_cast(flow AS DOUBLE) AS flow, try_cast(occ AS DOUBLE) AS occ,
       try_cast(speed AS DOUBLE) AS speed, nullif(trim(error), '') AS error_flag
FROM read_csv('{U}', header=true, all_varchar=true, quote='"', escape='"')
WHERE lower(trim(city)) = '{CONFIG["city"]}'\"\"\")
n0 = con.execute("SELECT count(*) FROM t_raw").fetchone()[0]

occ_p999 = con.execute("SELECT quantile_cont(occ, 0.999) FROM t_raw WHERE occ IS NOT NULL").fetchone()[0]
OCC_PERCENT = occ_p999 is not None and occ_p999 > 1.5
occ_hi = 100.0 if OCC_PERCENT else 1.0
print(f"rows: {n0:,} | occ 99.9th pct: {occ_p999:.2f} -> scale = {'0-100 percent' if OCC_PERCENT else '0-1 fraction'}")

filters = {
 "V1_bad_timestamp": "day IS NULL OR interval_s IS NULL OR interval_s < 0 OR interval_s > 86399",
 "V3_missing": "flow IS NULL OR occ IS NULL",
 "V4_negative_flow": "flow < 0",
 "V5_occ_range": f"occ < 0 OR occ > {occ_hi}",
 "V7_flow_no_occ": "flow > 0 AND occ = 0",
 "V10_error_flag": "error_flag IS NOT NULL",
}
removal = [{"rule": r, "flagged": con.execute(f"SELECT count(*) FROM t_raw WHERE {c}").fetchone()[0]}
           for r, c in filters.items()]
cond = " OR ".join(f"({c})" for c in filters.values())
con.execute(f\"\"\"CREATE OR REPLACE TABLE t_clean AS
    SELECT detid, day, interval_s, flow, occ / {occ_hi} AS occ, speed FROM t_raw
    WHERE NOT ({cond})
    QUALIFY row_number() OVER (PARTITION BY detid, day, interval_s ORDER BY flow DESC) = 1\"\"\")
n1 = con.execute("SELECT count(*) FROM t_clean").fetchone()[0]
removal.append({"rule": "TOTAL_removed_incl_dups", "flagged": n0 - n1})
rem = pd.DataFrame(removal); rem.to_csv(S1 / "tables/stage1_filter_counts.csv", index=False)
print(rem.to_string(index=False)); print(f"clean rows: {n1:,}")

# drop sparsely-reporting detectors (ASSUMED threshold, counted)
keep = con.execute(f\"\"\"SELECT detid FROM t_clean GROUP BY detid
                       HAVING count(*) >= {CONFIG['min_valid_intervals_per_detector']}\"\"\").df()
con.register("keep_tbl", keep)
con.execute("CREATE OR REPLACE TABLE t_c2 AS SELECT c.* FROM t_clean c JOIN keep_tbl k ON k.detid = c.detid")
n_all_det = con.execute('SELECT count(DISTINCT detid) FROM t_clean').fetchone()[0]
print(f"detectors kept: {len(keep)} (dropped {n_all_det - len(keep)} sparse)")""")

md("""## 3 · Step-1 occupancy rescaling (ref 42) — measured speeds, no Google

For each detector: free-flow speed v_ff = 85th pct of its measured speed;
free-flow q/o computed on intervals with occ below the detector's 10th pct.
Scalar s_i = (free-flow q/o) / v_ff rescales occupancy into density units:
k_i = occ_i · s_i (veh/km per lane), so that q/k ≈ speed (km/h) in free flow.
The distribution of s_i is reported — it feeds the paper's uncertainty logic.""")

code("""det_stats = con.execute(f\"\"\"
WITH d AS (
  SELECT detid, quantile_cont(speed, {CONFIG['freeflow_speed_pct']}) AS v_ff,
         quantile_cont(occ, {CONFIG['freeflow_occ_pct']}) AS occ_ff_cut
  FROM t_c2 WHERE speed IS NOT NULL AND speed > 0 GROUP BY detid
)
SELECT c.detid,
       median(c.flow / nullif(c.occ, 0)) AS qo_ff,
       any_value(d.v_ff) AS v_ff
FROM t_c2 c JOIN d ON d.detid = c.detid
WHERE c.occ > 0 AND c.occ <= d.occ_ff_cut AND c.flow > 0
GROUP BY c.detid\"\"\").df()
det_stats["s_i"] = det_stats.qo_ff / det_stats.v_ff
det_stats = det_stats[np.isfinite(det_stats.s_i) & (det_stats.s_i > 0)]
det_stats.to_csv(S1 / "tables/detector_rescale_scalars.csv", index=False)
print(det_stats.s_i.describe())
con.register("scal", det_stats[["detid", "s_i"]])
con.execute(\"\"\"CREATE OR REPLACE TABLE t_k AS
  SELECT c.detid, c.day, c.interval_s, c.flow, c.occ * s.s_i AS k, c.speed
  FROM t_c2 c JOIN scal s ON s.detid = c.detid\"\"\")
print("rescaled rows:", con.execute("SELECT count(*) FROM t_k").fetchone()[0])""")

md("""## 4 · Re-sampling (ref 17): 300 draws × 80% of detectors

Each draw: sample detectors without replacement, average flow and density per
(day, interval) over the sampled detectors. The pooled cloud maps the boundary
of feasible traffic states. Seeded; draw index recorded.""")

code("""import numpy as np
dets = np.array(sorted(det_stats.detid))
m = int(round(CONFIG["sample_frac"] * len(dets)))
draws = []
for j in range(CONFIG["n_draws"]):
    sub = rng.choice(dets, size=m, replace=False)
    con.register("subd", pd.DataFrame({"detid": sub}))
    g = con.execute(f\"\"\"SELECT avg(flow) qbar, avg(k) kbar FROM t_k
                        WHERE detid IN (SELECT detid FROM subd)
                        GROUP BY day, interval_s
                        HAVING count(*) >= {CONFIG['min_detectors_per_interval']}\"\"\").df()
    g["draw"] = j
    draws.append(g)
    if (j + 1) % 50 == 0: print(f"draw {j+1}/{CONFIG['n_draws']}")
cloud = pd.concat(draws, ignore_index=True)
cloud.to_parquet(S1 / "resampled_cloud.parquet")
print(f"pooled cloud: {len(cloud):,} points | k range {cloud.kbar.min():.1f}-{cloud.kbar.max():.1f} veh/km/lane")""")

md("""## 5 · Upper bound (ref 43) + functional-form fit (ref 18) + critical point

95th and 97.5th flow percentiles per density bin; both fitted. Fit:
q(k) = −λ·ln(e^{−v_f·k/λ} + e^{−Q/λ} + e^{−(κ−k)·w/λ}), bounded least squares.
Critical point = maximum of the fitted curve on a fine grid.""")

code("""from scipy.optimize import least_squares

def mfd_func(k, vf, Q, kappa, w, lam):
    a = np.exp(-vf * k / lam) + np.exp(-Q / lam) + np.exp(-(kappa - k) * w / lam)
    return -lam * np.log(a)

def fit_upper_bound(ub):
    k, q = ub.k_mid.values, ub.q_ub.values
    low = k <= np.percentile(k, 25)
    vf0 = np.clip(np.polyfit(k[low], q[low], 1)[0], 10, 120) if low.sum() >= 2 else 40.0
    x0 = [vf0, q.max(), max(k.max() * 2.0, 60), 15.0, q.max() / 10]
    lb = [3.0, q.max() * 0.5, k.max() * 1.02, 1.0, 1.0]
    ub_b = [150.0, q.max() * 3.0, 1000.0, 80.0, 2000.0]
    x0 = np.clip(x0, lb, ub_b)
    sol = least_squares(lambda p: mfd_func(k, *p) - q, x0=x0, bounds=(lb, ub_b), method="trf")
    return sol

results = {}
for bw in CONFIG["k_bin_width_candidates"]:
    c = cloud.copy()
    c["k_bin"] = (c.kbar // bw) * bw
    for qq in CONFIG["quantiles"]:
        ub = (c.groupby("k_bin").agg(q_ub=("qbar", lambda s, qq=qq: s.quantile(qq)),
                                     n=("qbar", "size")).reset_index())
        ub = ub[ub.n >= 30]                      # ASSUMED: min points per bin
        ub["k_mid"] = ub.k_bin + bw / 2
        sol = fit_upper_bound(ub)
        vf, Q, kappa, w, lam = sol.x
        kg = np.linspace(0.1, ub.k_mid.max() * 1.1, 4000)
        qg = mfd_func(kg, *sol.x)
        i = int(np.argmax(qg))
        results[(bw, qq)] = {"ub": ub, "params": dict(vf=vf, Q=Q, kappa=kappa, w=w, lam=lam),
                             "k_crit": float(kg[i]), "q_crit": float(qg[i]),
                             "v_crit": float(qg[i] / kg[i]), "cost": float(sol.cost),
                             "n_bins": len(ub)}
        r = results[(bw, qq)]
        print(f"bin={bw:>4} q={qq:<5} -> k*={r['k_crit']:.1f} veh/km/lane, "
              f"q*={r['q_crit']:.0f} veh/h/lane, v*={r['v_crit']:.1f} km/h, "
              f"vf={vf:.1f}, kappa={kappa:.0f}, bins={len(ub)}")

rows = [{"bin_width": bw, "quantile": qq, **{k2: v2 for k2, v2 in r.items() if k2 not in ("ub", "params")},
         **r["params"]} for (bw, qq), r in results.items()]
crit = pd.DataFrame(rows); crit.to_csv(S1 / "tables/critical_point_estimates.csv", index=False)
crit""")

md("""## 6 · Figures — PAPER_FAITHFUL_MFD and critical-point visualization""")

code("""import matplotlib.pyplot as plt
BW, QQ = CONFIG["k_bin_width_candidates"][0], CONFIG["quantiles"][0]
r = results[(BW, QQ)]
meta = f"UTD19 torino, all valid days, UNCALIBRATED_ANALYSIS (per-lane units), seed {CONFIG['seed']}"

fig, ax = plt.subplots(figsize=(9, 6.5))
sub = cloud.sample(min(len(cloud), 150_000), random_state=CONFIG["seed"])
ax.scatter(sub.kbar, sub.qbar, s=2, alpha=0.08, color="#888", label="re-sampled cloud (300×80%)")
ax.scatter(r["ub"].k_mid, r["ub"].q_ub, s=22, color="#d95f02", zorder=3,
           label=f"upper bound: {int(QQ*1000)/10}th pct per {BW} veh/km bin")
kg = np.linspace(0.1, r["ub"].k_mid.max() * 1.1, 800)
ax.plot(kg, mfd_func(kg, **r["params"]), lw=2.2, color="#1b6ca8", label="fitted MFD function (ref 18)")
ax.scatter([r["k_crit"]], [r["q_crit"]], marker="*", s=340, color="#c1121f", zorder=4,
           label=f"critical point: k*={r['k_crit']:.0f}, q*={r['q_crit']:.0f}, v*={r['v_crit']:.1f} km/h")
ax.set(title=f"PAPER_FAITHFUL_MFD — {meta}", xlabel="density k (veh/km per lane, rescaled occupancy)",
       ylabel="flow q (veh/h per lane)"); ax.legend(loc="lower right", fontsize=8)
fig.tight_layout(); fig.savefig(S1 / "figures/PAPER_FAITHFUL_MFD.png", dpi=150); plt.show()

fig, ax = plt.subplots(figsize=(9, 4.5))
ax.scatter(sub.kbar, sub.qbar / sub.kbar, s=2, alpha=0.08, color="#888")
ax.plot(kg, mfd_func(kg, **r["params"]) / kg, lw=2.2, color="#1b6ca8", label="fitted v(k)")
ax.axvline(r["k_crit"], ls="--", color="#c1121f")
ax.axhline(r["v_crit"], ls=":", color="#c1121f")
ax.annotate(f"v* = {r['v_crit']:.1f} km/h (paper Fig 2b sample mean: 18.8 km/h)",
            (r["k_crit"], r["v_crit"]), textcoords="offset points", xytext=(10, 10))
ax.set(title=f"Speed–density with critical state — {meta}", xlabel="density k (veh/km per lane)",
       ylabel="mean speed v = q/k (km/h)", ylim=(0, 80)); ax.legend()
fig.tight_layout(); fig.savefig(S1 / "figures/critical_point_visualization.png", dpi=150); plt.show()""")

md("""## 7 · Manual verification (Stage 1)

Recompute by hand: one bin's 95th percentile; one re-sampling draw's first point;
the fitted function's value at the reported maximum; v* arithmetic.""")

code("""# (a) one bin's percentile by hand
ubdf = r["ub"]; c = cloud.copy(); c["k_bin"] = (c.kbar // BW) * BW
b0 = ubdf.iloc[len(ubdf) // 2]
vals = c.loc[c.k_bin == b0.k_bin, "qbar"].values
manual_q95 = float(np.quantile(vals, QQ))
assert abs(manual_q95 - b0.q_ub) < 1e-6, (manual_q95, b0.q_ub)
print(f"OK bin {b0.k_bin:.1f}: manual {QQ} pct {manual_q95:.2f} == pipeline {b0.q_ub:.2f} ({len(vals)} pts)")

# (b) reproduce draw 0 deterministically
rng2 = np.random.default_rng(CONFIG["seed"])
sub0 = rng2.choice(dets, size=m, replace=False)
con.register("subd0", pd.DataFrame({"detid": sub0}))
g0 = con.execute(f\"\"\"SELECT avg(flow) qbar, avg(k) kbar FROM t_k
                     WHERE detid IN (SELECT detid FROM subd0) GROUP BY day, interval_s
                     HAVING count(*) >= {CONFIG['min_detectors_per_interval']}\"\"\").df()
d0 = cloud[cloud.draw == 0]
assert len(g0) == len(d0)
assert abs(g0.qbar.mean() - d0.qbar.mean()) < 1e-9
print(f"OK draw 0 reproduced: {len(g0):,} points, identical means")

# (c) fitted maximum consistency + v* arithmetic
qv = mfd_func(np.array([r["k_crit"]]), **r["params"])[0]
assert abs(qv - r["q_crit"]) < 1e-6
assert abs(r["q_crit"] / r["k_crit"] - r["v_crit"]) < 1e-9
print(f"OK critical point: q(k*)={qv:.1f}, v*=q*/k*={r['v_crit']:.2f} km/h")
print("\\nALL STAGE-1 MANUAL CHECKS PASSED")""")

md("""## 8 · Comparison with the paper + record

Torino-specific published values live only in the Supplementary figures (not
machine-readable here — the notebook attempts to fetch the Supplementary PDF for
the record). Quantitative comparison is therefore limited to published aggregate
facts; everything else is shape-level. No parameter was tuned to match.""")

code("""import json, urllib.request
comp = {
  "shape_is_concave_with_interior_maximum": bool(0 < r["k_crit"] < r["ub"].k_mid.max()),
  "v_crit_kmh": r["v_crit"],
  "paper_sample_mean_v_crit_kmh": 18.8,
  "v_crit_within_paper_sample_range": bool(5 < r["v_crit"] < 40),
  "k_crit_over_kappa": r["k_crit"] / r["params"]["kappa"],
  "paper_consistency_rule": "critical accumulation should not exceed ~1/3 of jam (ref 19)",
  "k_crit_ratio_ok": bool(r["k_crit"] / r["params"]["kappa"] <= 0.40),
  "sensitivity": {f"bin{bw}_q{qq}": {"k*": results[(bw, qq)]["k_crit"],
                                     "q*": results[(bw, qq)]["q_crit"],
                                     "v*": results[(bw, qq)]["v_crit"]}
                  for (bw, qq) in results},
}
print(json.dumps(comp, indent=2))
try:
    supp = ROOT / "raw/loder2019_supplementary.pdf"
    if not supp.exists():
        url = "https://static-content.springer.com/esm/art%3A10.1038%2Fs41598-019-51539-5/MediaObjects/41598_2019_51539_MOESM1_ESM.pdf"
        urllib.request.urlretrieve(url, supp)
    print("Supplementary PDF in Drive:", supp.exists(), supp.stat().st_size if supp.exists() else 0, "bytes")
except Exception as e:
    print("Supplementary fetch failed (non-fatal):", e)

record = {"env": ENV, "config": CONFIG, "occ_scale_percent": bool(OCC_PERCENT),
          "rows_raw": int(n0), "rows_clean": int(n1), "detectors_used": int(len(dets)),
          "rescale_scalar_stats": det_stats.s_i.describe().to_dict(),
          "primary": {"bin_width": BW, "quantile": QQ, **{kk: r[kk] for kk in ("k_crit", "q_crit", "v_crit")},
                      "params": r["params"]},
          "comparison": comp}
(S1 / "stage1_run_record.json").write_text(json.dumps(record, indent=2, default=float))

import shutil
bundle = shutil.make_archive(str(ROOT / "repo_artifacts_lab00_stage1"), "zip", S1)
print("\\nStage-1 bundle:", bundle)""")

md("""---
Provenance: UTD19 (DOI 10.3929/ethz-b-000437802) · Loder et al. 2019 Methods ·
independent paper-faithful reconstruction · UNCALIBRATED_ANALYSIS · per-lane units.
""")

nb = {"nbformat": 4, "nbformat_minor": 5,
      "metadata": {"colab": {"provenance": []},
                   "kernelspec": {"name": "python3", "display_name": "Python 3"},
                   "language_info": {"name": "python"}},
      "cells": CELLS}
out = Path(__file__).resolve().parent.parent / "notebooks" / "Lab00_UTD19_PaperFaithful_Colab.ipynb"
out.write_text(json.dumps(nb, indent=1))
print(f"wrote {out} ({len(CELLS)} cells)")
