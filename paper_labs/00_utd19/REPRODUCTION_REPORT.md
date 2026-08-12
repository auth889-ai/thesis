# REPRODUCTION_REPORT — Lab 00: UTD19 Traffic Science Foundation

**Paper:** Loder, Ambühl, Menendez, Axhausen (2019). *Understanding traffic
capacity of urban networks.* Scientific Reports 9:16283.
**Classification:** Independent paper-faithful reconstruction; this is **not**
the authors' official analysis code (their code is unpublished; `ambuehll/UTD19`
is a README-only dataset vignette — verified, pinned in `upstream/author_vignette/UPSTREAM.txt`).

Sections marked `[STAGE1]` are completed from `outputs/stage1/stage1_run_record.json`
after the Stage-1 Colab run; nothing here is estimated by hand.

## 1. Objective

Reproduce, as faithfully as the released material allows, the paper's estimation
chain from raw loop-detector data to a network MFD and its critical point, for
one released city — establishing the traffic-science ground truth (flow,
occupancy, density, accumulation, production, capacity, critical point) that all
later DhakaFlow Nexus labs build on.

## 2. Resources used

- Full paper text incl. Methods: Europe PMC JATS XML (PMC6841661) — `paper/`.
- UTD19 public release: ETH Research Collection, DOI 10.3929/ethz-b-000437802,
  fetched via the DSpace REST API from Colab (no API key; endpoint blocks the
  user's home network — fallback is the free utd19.ethz.ch signup).
- Compute: Google Colab (account anastasiasaat81@gmail.com); storage: Google
  Drive `DhakaFlow-Nexus-Data/Lab00_UTD19/` (~7 GB raw). Local machine holds
  only code, documents, and small artifacts.

## 3. Dataset audit (real, 2026-08-09/10 runs)

- Files: `utd19_u.csv` 6,978.6 MB; `detectors_public.csv` 2.6 MB; `links.csv`
  7.5 MB; `Manual.pdf`; checksums in `outputs/manifest/drive_manifest.csv`.
- `utd19_u.csv` contains **39 distinct city labels**; the portal lists 40 city
  names; the paper analyzed **41 cities / 107 regional networks**. Exact
  reproduction of the 107-network sample statistics is therefore impossible
  from the public release alone (Data Availability: NDA cities withheld).
- Full-file candidate-city audit (`outputs/audit/city_audit.csv`): most cities
  report **no speed**; error-flag rates reach 100% (london, bremen, zurich,
  essen, bordeaux). Modal reporting interval for the selected city: 300 s
  (matches the paper's "typical duration of 300 seconds").
- **City selection (Scientific Correction 3):** pre-registered criteria
  (DATA_SPEC §7) admitted zero cities; torino failed only the error-rate
  criterion (0.1255 vs 0.10). Documented relaxation `max_error_rate → 0.15`
  admits exactly **torino** (2,080,768 rows, 399 detectors, 21 days, 100%
  speed availability). See ASSUMPTIONS.md → MODIFIED_BY_US.

## 4. Experiments actually run

### 4.1 Smoke test (notebook `Lab00_UTD19_Colab.ipynb`, Colab)

- 7-day window 2016-09-26 → 2016-10-02; validation V1–V10 with per-rule counts
  (`outputs/audit/validation_report.csv`); occupancy scale detected as 0–100
  percent (robust 99.9th-percentile rule); figures: flow/occupancy/speed time
  series, daily profile, congestion heat map, `RAW_SANITY_MFD` (explicitly NOT
  the paper MFD); manual verification of aggregation, unit conversion, one MFD
  point, and one validation count — all assertions passed in Colab.
- Bundle: `repo_artifacts_lab00.zip` in Drive.

### 4.2 Stage 1 — PAPER_FAITHFUL_MFD (notebook `Lab00_UTD19_PaperFaithful_Colab.ipynb`, Colab)

Chain implemented exactly as METHOD_SPEC §4–5: paper-style filtering (incl.
dataset error flags), percent→fraction occupancy, step-1 occupancy rescaling to
measured free-flow speeds (ref 42; torino's own speeds — no Google), re-sampling
300×80% (ref 17), 95th/97.5th-percentile upper bound per density bin (ref 43),
functional-form fit of ref 18 by bounded NLS, critical point = fitted maximum.
Sensitivity over bin width {2,4} veh/km/lane × quantile {0.95, 0.975} — all four
estimates reported, none silently chosen.

**Completed 2026-08-10 (all numbers from `outputs/metrics/stage1_run_record.json`):**

- Filtering: 2,080,768 raw torino rows → **1,805,085** analyzed (V10 error-flag
  261,085; V5 occupancy-out-of-range 62,649; V1/V3/V4/V7 all zero — torino is a
  clean city apart from flags). 339→**335 detectors** (4 dropped as sparse).
- Occupancy scale confirmed **0–100 percent** (converted to fraction).
- Rescale scalars s_i: median 100.0, mean 101.9 ± 7.4, range 86–133 — tight
  distribution, i.e., torino detectors are mutually consistent.
- Re-sampled cloud: 300 draws × 268 detectors → **1,814,400 network-state
  points**, density range 0.4–32.0 veh/km/lane.
- Critical-point estimates (all four sensitivity variants):

| bin (veh/km) | quantile | k\* (veh/km/lane) | q\* (veh/h/lane) | v\* (km/h) |
|---|---|---|---|---|
| 2.0 | 0.950 | 31.9 | 1104 | 34.6 |
| 2.0 | 0.975 | 31.9 | 1266 | 39.7 |
| 4.0 | 0.950 | 33.0 | 1210 | 36.7 |
| 4.0 | 0.975 | 33.0 | 1228 | 37.2 |

- **Honest caveat recorded by the pipeline itself:**
  `shape_is_concave_with_interior_maximum = false` — the fitted maximum lies at
  the *edge* of the observed density range. Whole-city torino (our single
  "region", per limitation 2 below) rarely enters the congested branch, so
  (k\*, q\*) is a **lower-bound/boundary estimate** of the critical point, not an
  interior peak. This is precisely the behavior the paper's <10 km² regional
  partitioning exists to avoid.
- Figures: `outputs/figures/stage1/PAPER_FAITHFUL_MFD.png` (cloud + 95th-pct
  upper bound + ref-18 fit + critical point) and
  `critical_point_visualization.png` (v(k) with v\* marked) — both inspected.

## 5. Published vs our results

| Quantity | Published | Ours | Comparable? |
|---|---|---|---|
| MFD shape | smooth ∩-curve with interior maximum (Fig 1d) | smooth concave rise; maximum at data edge (no deep congested branch at whole-city scale) | qualitative — consistent with a free-flow-dominant aggregate |
| Critical speed | sample mean 18.8 km/h across 107 networks (Fig 2b) | v\* = 34.6–39.7 km/h (torino, uncalibrated, whole city) | within the paper's cross-network range; higher than the mean, as expected for an aggregate that dilutes congestion |
| Critical/jam ratio | critical accumulation ≤ ~1/3 jam (ref 19) | k\*/κ = 0.05 ≤ 1/3 ✓ (κ weakly identified — no congested-branch data) | consistency check passes |
| P̄\*, n̄\* (veh-km/h/km², veh/km²) | 12,236 ± 5,513; 653 ± 308 | not computed | **No** — needs OSM network length L per regional network (out of Stage-1 scope) |
| Table 1 regression | R²≈0.9, elasticities | not attempted | No — needs all 107 networks + topology variables |
| Torino-specific MFD (Supp. Figs) | image only | `[STAGE1]` | visual, if Supplementary PDF obtained |

## 6. Verification performed

- Local synthetic tests (fake data, planted defects/critical point):
  `tests/test_notebook_sql_synthetic.py` — validation-rule counts recovered
  exactly; `tests/test_stage1_synthetic.py` — planted critical point recovered
  (k\* 36.5 vs 36.0, q\* 1760 vs 1800, v\* 48.2 vs 50.0). Two real bugs caught
  before Colab (DuckDB `avg(boolean)`; fragile occupancy-scale heuristic).
- In-Colab manual checks on real data — **all passed**: smoke (4 assertions:
  mean flow/occ, unit conversion, MFD point, V4 recount) and Stage 1 (bin
  percentile recomputed by hand: 628.69 == 628.69 over 179,001 points; seeded
  draw 0 reproduced exactly, 6,048 points; fitted-maximum consistency
  q(k\*)=1104.2; v\* arithmetic).
- Config governance: `tests/test_configs_match.py` guarantees notebook CONFIGs
  mirror `configs/smoke.yaml` / `configs/full.yaml`.

## 7. Discrepancies and limitations (honest list)

1. **Google speed calibration unreproducible** — 2017-era Directions responses
   are gone. Our analysis is `UNCALIBRATED_ANALYSIS` in per-lane units; torino's
   measured speeds substitute only for the *detector-level* rescaling step.
2. **Regional networks**: paper's 107 partitions are not machine-readable; we
   treat filtered torino as one network — widens scatter, shifts the critical
   point relative to a <10 km² homogeneous zone.
3. **No L-scaling**: our (k\*, q\*) are per lane, not the paper's per-km²
   (n\*, P\*); direct numeric comparison to Table 1/Fig 2 is not possible.
4. **Released ≠ analyzed sample** (39 vs 41 cities; date ranges may differ).
5. Bin width, free-flow percentiles, sparse-detector threshold: ASSUMED
   (documented, sensitivity-checked where feasible).
6. Colab free tier disconnected repeatedly during the night runs; all steps are
   resumable and **both final runs (smoke + Stage 1) completed** on
   anastasiasaat81@gmail.com on 2026-08-10, with artifacts verified in Drive
   and copied into this repo.
7. κ (jam density) and w (wave speed) are extrapolations here: with no
   congested-branch observations the fit cannot identify them — only the
   free-flow branch and the boundary maximum are data-supported.

## 8. What was learned (teaching summary)

Flow (veh/h) is what detectors count; occupancy (fraction of time covered) is
their crowding proxy; rescaled occupancy approximates density k (veh/km); the
network's mean flow vs mean density traces the MFD; production/accumulation are
the network-scaled versions; the curve rises (free flow), peaks at the critical
point (capacity, n\*/k\*), and falls (congestion — more cars, less movement);
critical speed v\* = q\*/k\* is where congestion begins (paper: ~19 km/h on
average — city networks saturate at surprisingly low speeds). The paper notes
that maximising travel production alone would act near n ≈ n\* (Introduction
¶4); in DhakaFlow the critical point is carried forward as a **diagnostic and
optional feature** (state / reward-shaping / risk signal, to be justified by
ablation), not as a control target — later controllers optimise travel time,
waiting, queue, pressure, spillback, throughput, downstream capacity,
person/pedestrian/emergency delay, forecast risk and safety. Torino's critical
values are network-specific and are never transferred into Dhaka control or
calibration.

## 9. Relevance to DhakaFlow Nexus

Dhaka's future video-derived counts play the role of detector flows; this lab's
validated chain (audit → clean → aggregate → MFD → critical point) is exactly
what a Dhaka MFD will need, with bus production density B (Table 1) the most
Dhaka-relevant capacity factor.
