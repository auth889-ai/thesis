"""Build Lab00_UTD19_Colab.ipynb deterministically.

Rebuild with:  python3 src/build_notebook.py
The notebook is the version-controlled experiment definition; this builder keeps
its JSON stable and reviewable.
"""
import json
from pathlib import Path

MD = []  # (kind, source) tuples in order
CELLS = []

def md(src):
    CELLS.append({"cell_type": "markdown", "metadata": {}, "source": src})

def code(src):
    CELLS.append({"cell_type": "code", "execution_count": None, "metadata": {},
                  "outputs": [], "source": src})

md("""# Lab 00 — UTD19 Traffic Science Foundation (Colab smoke test)

**DhakaFlow Nexus** · Paper: Loder et al. 2019, *Understanding traffic capacity of urban networks* (Sci Rep 9:16283)

**Classification: Independent paper-faithful reconstruction; this is not the authors' official analysis code.**

This notebook performs the Lab 00 **smoke test** only (NOT the full paper reconstruction):
1. Mount Google Drive, create `MyDrive/DhakaFlow-Nexus-Data/Lab00_UTD19/`.
2. Download UTD19 from the ETH Research Collection **directly into Drive** (never via the local PC).
3. Candidate-city audit table → documented city selection (Scientific Correction 3).
4. Data validation V1–V10 with per-rule removal counts (nothing dropped silently).
5. Smoke analysis of the selected city: flow / occupancy / speed time series, daily profile, and a **`RAW_SANITY_MFD`** — explicitly *not* the paper's MFD (Scientific Correction 2: no re-sampling, no calibration, no L-scaling here).
6. Manual verification of aggregation arithmetic.
7. Save heavy outputs to Drive; export a small `repo_artifacts/` bundle to commit into the local git repo.

Speed values are **UNCALIBRATED** (`UNCALIBRATED_ANALYSIS`): the paper's Google-Directions calibration is `UNREPRODUCIBLE_FROM_AVAILABLE_HISTORICAL_INPUTS` (see `ASSUMPTIONS.md`).
""")

code("""# ============================== CONFIG ==============================
# All paths/parameters configurable here; no hard-coded paths below.
CONFIG = {
    # Drive layout
    "drive_root": "/content/drive/MyDrive/DhakaFlow-Nexus-Data/Lab00_UTD19",
    "subdirs": ["raw", "processed", "outputs", "outputs/audit", "outputs/figures",
                "outputs/manifest", "repo_artifacts"],

    # ETH Research Collection (UTD19) — no API key required
    "eth_api_root": "https://www.research-collection.ethz.ch/server/api",
    "eth_item_uuid": "bfb14ee7-82c8-4357-a293-3bf18d8f93f9",

    # Fallback: if the ETH endpoint is blocked, register (free) at
    # https://utd19.ethz.ch/ and paste the e-mailed direct links here:
    "manual_urls": {},   # e.g. {"utd19_u.csv": "https://...", "detectors.csv": "https://..."}

    # Paper PDF + supplementary (fetched into Drive for the record)
    "paper_pdf_url": "https://www.nature.com/articles/s41598-019-51539-5.pdf",

    # Reproducibility
    "seed": 42,
    "duckdb_memory_limit": "8GB",
    "duckdb_temp_dir": "/content/duckdb_tmp",

    # City-selection criteria (fixed BEFORE the audit; DATA_SPEC §7).
    # max_error_rate: pre-registered 0.10 admitted ZERO cities on the real
    # 2026-08-09 audit (39 cities in utd19_u.csv). torino failed ONLY this
    # criterion (error_rate 0.1255, speed_avail 1.0, 2.08M rows, 399 detectors,
    # 21 days); every other speed-reporting city failed size and/or error
    # criteria harder. Documented relaxation 0.10 -> 0.15 admits exactly one
    # city (torino). See ASSUMPTIONS.md -> MODIFIED_BY_US.
    "select": {
        "min_speed_nonnull_frac": 0.50,
        "min_rows": 1_000_000,
        "max_rows": 100_000_000,
        "min_detectors": 100,
        "min_days": 14,
        "max_error_rate": 0.15,
    },

    # Validation thresholds (ASSUMED — see ASSUMPTIONS.md)
    "max_valid_speed_kmh": 200.0,

    # Smoke-test scope
    "smoke_days": 7,          # analyze first N fully-covered days of selected city
    "example_detectors": 3,   # detectors shown in time-series plots
    "mfd_min_detectors": 10,  # min detectors reporting in an interval for a RAW_SANITY_MFD point
}
print("CONFIG ok")""")

md("## 1 · Mount Google Drive and create the data directory")

code("""import os, pathlib
from google.colab import drive
drive.mount('/content/drive')
ROOT = pathlib.Path(CONFIG["drive_root"])
for d in CONFIG["subdirs"]:
    (ROOT / d).mkdir(parents=True, exist_ok=True)
print("Drive root ready:", ROOT)""")

md("## 2 · Install exact dependencies and print environment versions")

code("""%pip -q install duckdb==1.1.3 pandas==2.2.2 pyarrow==17.0.0 matplotlib==3.8.4 requests==2.32.3
import sys, platform, sysconfig, datetime
import duckdb, pandas as pd, pyarrow, matplotlib, requests, numpy as np
ENV = {
    "run_started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "python": sys.version,
    "platform": platform.platform(),
    "duckdb": duckdb.__version__, "pandas": pd.__version__,
    "pyarrow": pyarrow.__version__, "matplotlib": matplotlib.__version__,
    "numpy": np.__version__, "requests": requests.__version__,
    "seed": CONFIG["seed"],
}
for k, v in ENV.items(): print(f"{k}: {v}")
np.random.seed(CONFIG["seed"])""")

md("""## 3 · Download UTD19 into Drive (resumable; never via the local PC)

Discovers bitstreams from the ETH DSpace REST API (download-mechanism pattern
reused — after inspection — from the earlier `utd19_berlin_sumo_e2e_v3` project;
documented in `ASSUMPTIONS.md → MODIFIED_BY_US`). Files already present in Drive
with matching size are skipped. Every file gets a sha256 recorded in the manifest.""")

code("""import hashlib, json, time, requests

def sha256_file(p, chunk=1 << 20):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        while True:
            b = f.read(chunk)
            if not b: break
            h.update(b)
    return h.hexdigest()

def eth_discover():
    s = requests.Session(); s.headers["User-Agent"] = "DhakaFlowNexus-Lab00/1.0"
    api, uuid = CONFIG["eth_api_root"], CONFIG["eth_item_uuid"]
    item = s.get(f"{api}/core/items/{uuid}", timeout=60); item.raise_for_status()
    bundles = s.get(item.json()["_links"]["bundles"]["href"], params={"size": 100}, timeout=60)
    bundles.raise_for_status()
    files = []
    def emb(payload):
        for v in payload.get("_embedded", {}).values():
            if isinstance(v, list): return v
        return []
    for b in emb(bundles.json()):
        u = b.get("_links", {}).get("bitstreams", {}).get("href")
        if not u: continue
        r = s.get(u, params={"size": 100}, timeout=60); r.raise_for_status()
        for bs in emb(r.json()):
            files.append({"name": (bs.get("name") or "").strip(),
                          "size": int(bs.get("sizeBytes") or 0),
                          "url": bs.get("_links", {}).get("content", {}).get("href")})
    return [f for f in files if f["name"] and f["url"]]

def canonical(name):
    low = name.lower()
    if "utd19" in low and low.endswith(".csv"): return "utd19_u.csv"
    if "detector" in low and low.endswith(".csv"): return "detectors.csv"
    if "link" in low and low.endswith(".csv"): return "links.csv"
    if low.endswith(".pdf"): return "manual.pdf"
    return name

def download(url, dest, expected=0):
    dest = pathlib.Path(dest)
    if dest.exists() and (expected == 0 or dest.stat().st_size == expected):
        print(f"SKIP (exists, size ok): {dest.name}"); return
    tmp = dest.with_suffix(dest.suffix + ".part")
    with requests.get(url, stream=True, timeout=120,
                      headers={"User-Agent": "DhakaFlowNexus-Lab00/1.0"}) as r:
        r.raise_for_status()
        done = 0; t0 = time.time()
        with open(tmp, 'wb') as f:
            for chunk in r.iter_content(1 << 22):
                f.write(chunk); done += len(chunk)
                if time.time() - t0 > 15:
                    print(f"  {dest.name}: {done/1e6:,.0f} MB"); t0 = time.time()
    tmp.rename(dest); print(f"DONE: {dest.name} ({dest.stat().st_size/1e6:,.1f} MB)")

RAW = ROOT / "raw"; manifest = []
try:
    listing = eth_discover()
    print("ETH Research Collection listing:")
    for f in listing: print(f"  {f['name']}  {f['size']/1e6:,.1f} MB")
    for f in listing:
        dest = RAW / canonical(f["name"])
        download(f["url"], dest, f["size"])
        manifest.append({"drive_path": str(dest.relative_to(ROOT)), "original_name": f["name"],
                         "bytes": dest.stat().st_size, "source_url": f["url"]})
except Exception as e:
    print(f"ETH endpoint failed ({type(e).__name__}: {e}).")
    if CONFIG["manual_urls"]:
        for cname, url in CONFIG["manual_urls"].items():
            dest = RAW / cname; download(url, dest)
            manifest.append({"drive_path": str(dest.relative_to(ROOT)), "original_name": cname,
                             "bytes": dest.stat().st_size, "source_url": "manual (utd19.ethz.ch registration)"})
    else:
        raise RuntimeError(
            "MANUAL STEP NEEDED: register free at https://utd19.ethz.ch/ "
            "(e.g. with studyemail953@gmail.com), receive the download link by e-mail, "
            "put the links into CONFIG['manual_urls'] and re-run this cell.")

# Paper PDF for the record (non-fatal if blocked)
try:
    download(CONFIG["paper_pdf_url"], ROOT / "raw" / "loder2019_paper.pdf")
except Exception as e:
    print("Paper PDF fetch failed (non-fatal):", e)

print("\\nHashing (first run only takes a while)...")
for m in manifest:
    m["sha256"] = sha256_file(ROOT / m["drive_path"])
mpath = ROOT / "outputs/manifest/drive_manifest.csv"
pd.DataFrame(manifest).to_csv(mpath, index=False)
print("Manifest written:", mpath)
pd.DataFrame(manifest)""")

md("## 4 · Structural peek — real headers, row counts (no invented columns)")

code("""import duckdb
RAW = ROOT / "raw"   # (re)defined here so the notebook re-runs without re-downloading
os.makedirs(CONFIG["duckdb_temp_dir"], exist_ok=True)
con = duckdb.connect()
con.execute(f\"\"\"SET memory_limit='{CONFIG["duckdb_memory_limit"]}';
                SET temp_directory='{CONFIG["duckdb_temp_dir"]}';\"\"\")
U = str(RAW / "utd19_u.csv"); D = str(RAW / "detectors.csv"); L = str(RAW / "links.csv")

for name, path in [("utd19_u.csv", U), ("detectors.csv", D), ("links.csv", L)]:
    if not pathlib.Path(path).exists():
        print(f"MISSING: {name}"); continue
    hdr = con.execute(f"SELECT * FROM read_csv('{path}', header=true, all_varchar=true, "
                      f"quote='\\"', escape='\\"') LIMIT 0").df()
    print(f"{name} columns: {list(hdr.columns)}")
rows = con.execute(f"SELECT count(*) FROM read_csv('{U}', header=true, all_varchar=true)").fetchone()[0]
print(f"utd19_u.csv rows: {rows:,}")""")

md("""## 5 · Candidate-city audit (Scientific Correction 3)

One pass over the full measurement file; the audit table decides the smoke city —
criteria were fixed in `DATA_SPEC.md §7` **before** computing this table.""")

code("""audit = con.execute(f\"\"\"
WITH raw AS (
  SELECT lower(trim(city)) AS city, trim(detid) AS detid,
         coalesce(try_strptime(day, '%Y-%m-%d')::DATE,
                  try_strptime(day, '%d.%m.%Y')::DATE) AS day_parsed,
         try_cast("interval" AS BIGINT) AS interval_s,
         try_cast(flow AS DOUBLE) AS flow, try_cast(occ AS DOUBLE) AS occ,
         try_cast(speed AS DOUBLE) AS speed,
         nullif(trim(error), '') AS error_flag
  FROM read_csv('{U}', header=true, all_varchar=true, quote='"', escape='"')
)
SELECT city,
  count(*) AS n_rows,
  count(DISTINCT detid) AS n_detectors,
  min(day_parsed) AS first_day, max(day_parsed) AS last_day,
  count(DISTINCT day_parsed) AS n_days,
  round(avg((flow  IS NOT NULL)::INT), 4) AS flow_avail,
  round(avg((occ   IS NOT NULL)::INT), 4) AS occ_avail,
  round(avg((speed IS NOT NULL)::INT), 4) AS speed_avail,
  round(avg((error_flag IS NOT NULL)::INT), 4) AS error_rate,
  round(avg((day_parsed IS NULL OR interval_s IS NULL)::INT), 6) AS bad_time_rate,
  round(1.0 - count(DISTINCT (detid, day_parsed, interval_s)) / count(*)::DOUBLE, 6) AS dup_rate
FROM raw GROUP BY city ORDER BY n_rows DESC\"\"\").df()
audit.to_csv(ROOT / "outputs/audit/city_audit.csv", index=False)
print(f"{len(audit)} cities audited (paper used 41; release lists 40 — DATA_SPEC §4)")
audit""")

code("""S = CONFIG["select"]
cand = audit[
    (audit.speed_avail >= S["min_speed_nonnull_frac"]) &
    (audit.n_rows.between(S["min_rows"], S["max_rows"])) &
    (audit.n_detectors >= S["min_detectors"]) &
    (audit.n_days >= S["min_days"]) &
    (audit.error_rate <= S["max_error_rate"])
].copy()
print("Cities passing ALL documented criteria:", list(cand.city))
if len(cand) == 0:
    raise RuntimeError("No city passes the pre-registered criteria — relax criteria "
                       "EXPLICITLY (document in ASSUMPTIONS.md) rather than silently.")
# Deterministic tie-break (documented): most days of coverage, then fewer rows (smaller smoke)
cand = cand.sort_values(["n_days", "n_rows"], ascending=[False, True])
CITY = cand.iloc[0].city
sel_reason = cand.iloc[0].to_dict()
print(f"\\nSELECTED SMOKE CITY: {CITY}")
sel_reason""")

md("""## 6 · Validation V1–V10 on the selected city (nothing dropped silently)

Each rule reports how many records it flags; the cleaned subset for analysis
excludes only V1/V2/V3(flow,occ)/V4/V5/V7 failures, and the exclusion counts are
saved to `outputs/audit/validation_report.csv`.""")

code("""con.execute(f\"\"\"
CREATE OR REPLACE TABLE city_raw AS
SELECT lower(trim(city)) AS city, trim(detid) AS detid, day AS day_str,
       coalesce(try_strptime(day, '%Y-%m-%d')::DATE,
                try_strptime(day, '%d.%m.%Y')::DATE) AS day,
       try_cast("interval" AS BIGINT) AS interval_s,
       try_cast(flow AS DOUBLE) AS flow, try_cast(occ AS DOUBLE) AS occ,
       try_cast(speed AS DOUBLE) AS speed, nullif(trim(error), '') AS error_flag
FROM read_csv('{U}', header=true, all_varchar=true, quote='"', escape='"')
WHERE lower(trim(city)) = '{CITY}'\"\"\")
n_city = con.execute("SELECT count(*) FROM city_raw").fetchone()[0]

def q1(sql): return con.execute(sql).fetchone()[0]
maxspd = CONFIG["max_valid_speed_kmh"]
# Robust scale detection: a lone corrupt row must not flip the city's occ scale,
# so use the 99.9th percentile rather than max.
occ_p999 = q1("SELECT quantile_cont(occ, 0.999) FROM city_raw WHERE occ IS NOT NULL")
occ_scale_0_100 = occ_p999 is not None and occ_p999 > 1.5   # V5 adapts; documented finding
occ_hi = 100.0 if occ_scale_0_100 else 1.0

rules = {
 "V1_bad_timestamp": "day IS NULL OR interval_s IS NULL OR interval_s < 0 OR interval_s > 86399",
 "V3_missing_flow_or_occ": "flow IS NULL OR occ IS NULL",
 "V4_negative_flow": "flow < 0",
 "V5_occ_out_of_range": f"occ < 0 OR occ > {occ_hi}",
 "V6_invalid_speed": f"speed IS NOT NULL AND (speed < 0 OR speed > {maxspd})",
 "V7_flow_without_occ": "flow > 0 AND occ = 0",
 "V10_error_flagged": "error_flag IS NOT NULL",
}
report = [{"rule": r, "flagged": q1(f"SELECT count(*) FROM city_raw WHERE {cond}"),
           "share": q1(f"SELECT round(avg(coalesce(({cond}), false)::INT),6) FROM city_raw")}
          for r, cond in rules.items()]
report.append({"rule": "V2_duplicate_key",
    "flagged": n_city - q1("SELECT count(DISTINCT (detid, day, interval_s)) FROM city_raw"),
    "share": None})
orphans = q1(f\"\"\"SELECT count(DISTINCT c.detid) FROM city_raw c LEFT JOIN
  read_csv('{D}', header=true, all_varchar=true, quote='"', escape='"') d
  ON trim(d.detid) = c.detid WHERE d.detid IS NULL\"\"\")
report.append({"rule": "V8_detid_missing_metadata", "flagged": orphans, "share": None})
gaps = con.execute(\"\"\"
  WITH s AS (SELECT detid, day, interval_s,
             interval_s - lag(interval_s) OVER (PARTITION BY detid, day ORDER BY interval_s) AS step
             FROM city_raw WHERE day IS NOT NULL AND interval_s IS NOT NULL)
  SELECT count(*) FILTER (WHERE step IS NOT NULL AND step <= 0) AS nonmonotonic,
         mode(step) FILTER (WHERE step IS NOT NULL) AS modal_step_s FROM s\"\"\").fetchone()
report.append({"rule": "V9_nonmonotonic_time", "flagged": gaps[0], "share": None})
MODAL_STEP = int(gaps[1]); print(f"Modal interval step: {MODAL_STEP} s (paper: ~300 s typical)")
rep = pd.DataFrame(report); rep.insert(0, "city", CITY); rep.insert(1, "total_rows", n_city)
rep.to_csv(ROOT / "outputs/audit/validation_report.csv", index=False)
if occ_scale_0_100: print("FINDING: occ scale is 0-100 for this city (V5 adapted; document in DATA_SPEC).")
rep""")

code("""# Cleaned analysis subset (exclusions per report above) + first N fully-covered days
con.execute(f\"\"\"
CREATE OR REPLACE TABLE city_clean AS
SELECT * FROM city_raw
WHERE NOT ({rules['V1_bad_timestamp']}) AND NOT ({rules['V3_missing_flow_or_occ']})
  AND NOT ({rules['V4_negative_flow']}) AND NOT ({rules['V5_occ_out_of_range']})
  AND NOT ({rules['V7_flow_without_occ']})
QUALIFY row_number() OVER (PARTITION BY detid, day, interval_s ORDER BY flow DESC) = 1\"\"\")
days = con.execute(f\"\"\"SELECT day FROM (SELECT day, count(*) c FROM city_clean GROUP BY day
    ORDER BY day) WHERE c > 0.5*(SELECT max(c) FROM (SELECT count(*) c FROM city_clean GROUP BY day))
    LIMIT {CONFIG['smoke_days']}\"\"\").df().day.tolist()
con.execute(f"CREATE OR REPLACE TABLE smoke AS SELECT * FROM city_clean WHERE day IN ({','.join(repr(str(d)) for d in days)})")
n_clean = con.execute("SELECT count(*) FROM city_clean").fetchone()[0]
n_smoke = con.execute("SELECT count(*) FROM smoke").fetchone()[0]
print(f"city rows {n_city:,} → clean {n_clean:,} (excluded {n_city-n_clean:,}) → smoke window {n_smoke:,} rows over {len(days)} days: {days}")
con.execute(f"COPY smoke TO '{ROOT}/processed/{CITY}_smoke.parquet' (FORMAT PARQUET)")""")

md("""## 7 · Smoke plots

All figures carry the city, date range, and `UNCALIBRATED_ANALYSIS` provenance.
The MFD-like scatter is titled **RAW_SANITY_MFD** — it is *not* the paper's MFD
(no re-sampling, no occupancy rescaling, no calibration, no network-length scaling).""")

code("""import matplotlib.pyplot as plt
import matplotlib.dates as mdates
FIG = ROOT / "outputs/figures"
meta = f"UTD19 · {CITY} · {days[0]}–{days[-1]} · UNCALIBRATED_ANALYSIS · Lab00 smoke"

top = con.execute(f"SELECT detid, count(*) c FROM smoke GROUP BY detid ORDER BY c DESC LIMIT {CONFIG['example_detectors']}").df()
DETS = top.detid.tolist(); print("Example detectors:", DETS)

def ts(df):  # datetime axis from day+interval
    return pd.to_datetime(df.day) + pd.to_timedelta(df.interval_s, unit='s')

# --- 7a. flow time series (example detectors) ---
fig, ax = plt.subplots(figsize=(12, 4))
for det in DETS:
    d = con.execute(f"SELECT day, interval_s, flow FROM smoke WHERE detid='{det}' ORDER BY day, interval_s").df()
    ax.plot(ts(d), d.flow, lw=0.6, label=f"detector {det}")
ax.set(title=f"Traffic flow time series — {meta}", xlabel="time", ylabel="flow (veh/h per lane)")
ax.legend(); fig.autofmt_xdate(); fig.tight_layout()
fig.savefig(FIG / "traffic_time_series.png", dpi=150); plt.show()

# --- 7b. occupancy + speed time series ---
fig, axes = plt.subplots(2, 1, figsize=(12, 6), sharex=True)
for det in DETS:
    d = con.execute(f"SELECT day, interval_s, occ, speed FROM smoke WHERE detid='{det}' ORDER BY day, interval_s").df()
    axes[0].plot(ts(d), d.occ, lw=0.6, label=f"det {det}")
    if d.speed.notna().any(): axes[1].plot(ts(d), d.speed, lw=0.6, label=f"det {det}")
axes[0].set(title=f"Occupancy — {meta}", ylabel="occupancy (fraction)")
axes[1].set(title="Speed (as reported by detector, UNCALIBRATED)", ylabel="speed (km/h)", xlabel="time")
for a in axes: a.legend()
fig.autofmt_xdate(); fig.tight_layout(); fig.savefig(FIG / "occ_speed_time_series.png", dpi=150); plt.show()

# --- 7c. detector-level daily profile ---
prof = con.execute(\"\"\"SELECT detid, interval_s, avg(flow) mean_flow FROM smoke
                      WHERE detid IN (SELECT unnest(?)) GROUP BY detid, interval_s
                      ORDER BY detid, interval_s\"\"\", [DETS]).df()
fig, ax = plt.subplots(figsize=(10, 4))
for det, g in prof.groupby("detid"):
    ax.plot(g.interval_s / 3600, g.mean_flow, label=f"det {det}")
ax.set(title=f"Mean daily flow profile — {meta}", xlabel="hour of day", ylabel="mean flow (veh/h per lane)")
ax.legend(); fig.tight_layout(); fig.savefig(FIG / "daily_profile.png", dpi=150); plt.show()

# --- 7d. congestion visualization: network mean occupancy heat by hour × day ---
heat = con.execute("SELECT day, floor(interval_s/3600)::INT AS hr, avg(occ) mo FROM smoke GROUP BY day, hr").df()
piv = heat.pivot(index="day", columns="hr", values="mo")
fig, ax = plt.subplots(figsize=(10, 3.5))
im = ax.imshow(piv.values, aspect="auto", cmap="magma")
ax.set(title=f"Network mean occupancy by hour × day (congestion picture) — {meta}",
       xlabel="hour of day", ylabel="day")
ax.set_yticks(range(len(piv.index)), [str(d) for d in piv.index])
fig.colorbar(im, label="mean occupancy (fraction)"); fig.tight_layout()
fig.savefig(FIG / "congestion_plot.png", dpi=150); plt.show()""")

code("""# --- 7e. RAW_SANITY_MFD — explicitly NOT the paper's MFD ---
mfd = con.execute(f\"\"\"SELECT day, interval_s, avg(flow) qbar, avg(occ) obar, count(*) ndet
                     FROM smoke GROUP BY day, interval_s
                     HAVING count(*) >= {CONFIG['mfd_min_detectors']}
                     ORDER BY day, interval_s\"\"\").df()
fig, ax = plt.subplots(figsize=(7.5, 6))
sc = ax.scatter(mfd.obar, mfd.qbar, s=6, c=mfd.interval_s / 3600, cmap="viridis", alpha=0.6)
fig.colorbar(sc, label="hour of day")
ax.set(title=f"RAW_SANITY_MFD (loops-method raw aggregate) — {meta}\\n"
             "NOT the paper MFD: no re-sampling, no rescaling, no calibration, no L-scaling",
       xlabel="mean occupancy over detectors (fraction)",
       ylabel="mean flow over detectors (veh/h per lane)")
fig.tight_layout(); fig.savefig(FIG / "RAW_SANITY_MFD.png", dpi=150); plt.show()
mfd.to_csv(ROOT / "outputs/audit/raw_sanity_mfd_points.csv", index=False)
print(f"{len(mfd):,} network-interval points")""")

md("""## 8 · Manual verification (aggregation arithmetic checked by hand)

Recompute, in plain Python on raw fetched rows, quantities the SQL pipeline
produced; assert exact agreement. Verifies: mean-flow aggregation, mean-occupancy
aggregation, veh/h→veh-per-interval conversion, and one validation count.""")

code("""det0, day0 = DETS[0], str(days[0])
rows = con.execute(f"SELECT interval_s, flow, occ FROM smoke WHERE detid='{det0}' AND day='{day0}' AND interval_s < 3600 ORDER BY interval_s").df()
print(f"Manual sample: detector {det0}, {day0}, first hour → {len(rows)} rows"); print(rows)

manual_mean_flow = sum(rows.flow) / len(rows)
manual_mean_occ  = sum(rows.occ)  / len(rows)
sql_mean_flow, sql_mean_occ = con.execute(
    f"SELECT avg(flow), avg(occ) FROM smoke WHERE detid='{det0}' AND day='{day0}' AND interval_s < 3600").fetchone()
assert abs(manual_mean_flow - sql_mean_flow) < 1e-9, (manual_mean_flow, sql_mean_flow)
assert abs(manual_mean_occ  - sql_mean_occ)  < 1e-9, (manual_mean_occ,  sql_mean_occ)
print(f"OK mean flow: manual {manual_mean_flow:.4f} == sql {sql_mean_flow:.4f}")
print(f"OK mean occ : manual {manual_mean_occ:.6f} == sql {sql_mean_occ:.6f}")

veh_per_interval = [f * MODAL_STEP / 3600 for f in rows.flow]   # veh/h × (s/3600)
print(f"OK unit conversion: first interval {rows.flow.iloc[0]:.1f} veh/h × {MODAL_STEP}s/3600 = {veh_per_interval[0]:.2f} vehicles")

# One network-interval point of the RAW_SANITY_MFD recomputed by hand
t0 = int(mfd.iloc[0].interval_s); d0 = str(mfd.iloc[0].day)
pts = con.execute(f"SELECT flow, occ FROM smoke WHERE day='{d0}' AND interval_s={t0}").df()
assert abs(sum(pts.flow)/len(pts) - mfd.iloc[0].qbar) < 1e-9
assert abs(sum(pts.occ)/len(pts)  - mfd.iloc[0].obar) < 1e-9
print(f"OK RAW_SANITY_MFD point ({d0} t={t0}s): qbar/obar reproduced from {len(pts)} detector rows")

# Independent recount of one validation rule
neg = con.execute("SELECT count(*) FROM city_raw WHERE flow < 0").fetchone()[0]
rep_neg = int(rep.loc[rep.rule == 'V4_negative_flow', 'flagged'].iloc[0])
assert neg == rep_neg
print(f"OK V4 recount: {neg} == report {rep_neg}")
print("\\nALL MANUAL CHECKS PASSED")""")

md("""## 9 · Save results; build the small `repo_artifacts/` bundle for git

Heavy files stay in Drive. The bundle below (figures, audit CSVs, env record,
manifest) is what gets copied into the local repo at
`paper_labs/00_utd19/outputs/`.""")

code("""import shutil, json
RA = ROOT / "repo_artifacts"; shutil.rmtree(RA, ignore_errors=True); RA.mkdir()
(RA / "figures").mkdir(); (RA / "audit").mkdir(); (RA / "manifest").mkdir()
for p in FIG.glob("*.png"): shutil.copy2(p, RA / "figures" / p.name)
for p in (ROOT / "outputs/audit").glob("*.csv"): shutil.copy2(p, RA / "audit" / p.name)
shutil.copy2(ROOT / "outputs/manifest/drive_manifest.csv", RA / "manifest/drive_manifest.csv")
run_record = {"env": ENV, "config": {k: v for k, v in CONFIG.items() if k != "manual_urls"},
              "selected_city": CITY, "selection_row": {k: str(v) for k, v in sel_reason.items()},
              "smoke_days": [str(d) for d in days],
              "rows": {"city": int(n_city), "clean": int(n_clean), "smoke": int(n_smoke)},
              "modal_interval_s": MODAL_STEP}
(RA / "run_record.json").write_text(json.dumps(run_record, indent=2))
bundle = shutil.make_archive(str(ROOT / "repo_artifacts_lab00"), "zip", RA)
print("Bundle for the local repo:", bundle)
print("\\nDownload it via the Files panel, or:  from google.colab import files; files.download(bundle)")
print("Unzip into local repo at: paper_labs/00_utd19/outputs/")""")

md("""---
### Provenance
- Dataset: UTD19, ETH Research Collection DOI 10.3929/ethz-b-000437802 (checksums in `drive_manifest.csv`).
- Classification: **Independent paper-faithful reconstruction; not the authors' official analysis code.**
- This notebook = smoke test only. The `PAPER_FAITHFUL_MFD` stage (re-sampling 300×80%,
  occupancy rescaling, quantile upper bound, functional-form fit, critical point) is a
  separate follow-up after the smoke audit is approved (`METHOD_SPEC.md §9`).
""")

nb = {"nbformat": 4, "nbformat_minor": 5,
      "metadata": {"colab": {"provenance": []},
                   "kernelspec": {"name": "python3", "display_name": "Python 3"},
                   "language_info": {"name": "python"}},
      "cells": CELLS}
out = Path(__file__).resolve().parent.parent / "notebooks" / "Lab00_UTD19_Colab.ipynb"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(nb, indent=1))
print(f"wrote {out} ({len(CELLS)} cells)")
