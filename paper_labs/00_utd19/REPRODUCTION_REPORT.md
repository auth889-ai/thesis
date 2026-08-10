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

`[STAGE1: filter counts, detectors used, rescale-scalar stats, critical-point
table, figures]`

## 5. Published vs our results

| Quantity | Published | Ours | Comparable? |
|---|---|---|---|
| MFD shape | smooth ∩-curve with interior maximum (Fig 1d) | `[STAGE1]` | qualitative |
| Critical speed | sample mean 18.8 km/h across 107 networks (Fig 2b) | `[STAGE1]` v\* for torino | order-of-magnitude only (one network, uncalibrated) |
| Critical/jam ratio | critical accumulation ≤ ~1/3 jam (ref 19) | `[STAGE1]` k\*/κ | consistency check |
| P̄\*, n̄\* (veh-km/h/km², veh/km²) | 12,236 ± 5,513; 653 ± 308 | not computed | **No** — needs OSM network length L per regional network (out of Stage-1 scope) |
| Table 1 regression | R²≈0.9, elasticities | not attempted | No — needs all 107 networks + topology variables |
| Torino-specific MFD (Supp. Figs) | image only | `[STAGE1]` | visual, if Supplementary PDF obtained |

## 6. Verification performed

- Local synthetic tests (fake data, planted defects/critical point):
  `tests/test_notebook_sql_synthetic.py` — validation-rule counts recovered
  exactly; `tests/test_stage1_synthetic.py` — planted critical point recovered
  (k\* 36.5 vs 36.0, q\* 1760 vs 1800, v\* 48.2 vs 50.0). Two real bugs caught
  before Colab (DuckDB `avg(boolean)`; fragile occupancy-scale heuristic).
- In-Colab manual checks on real data: smoke (4 assertions) and Stage 1
  (bin-percentile by hand, seeded draw reproduction, fitted-maximum
  consistency, v\* arithmetic) `[STAGE1: confirm]`.

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
6. Colab free tier disconnected repeatedly; all steps are resumable and the
   final runs completed `[STAGE1: confirm]`.

## 8. What was learned (teaching summary)

Flow (veh/h) is what detectors count; occupancy (fraction of time covered) is
their crowding proxy; rescaled occupancy approximates density k (veh/km); the
network's mean flow vs mean density traces the MFD; production/accumulation are
the network-scaled versions; the curve rises (free flow), peaks at the critical
point (capacity, n\*/k\*), and falls (congestion — more cars, less movement);
critical speed v\* = q\*/k\* is where congestion begins (paper: ~19 km/h on
average — city networks saturate at surprisingly low speeds). Signal control
should hold the network near n\* (Introduction ¶4) — the scientific basis for
DhakaFlow's future RL set-points.

## 9. Relevance to DhakaFlow Nexus

Dhaka's future video-derived counts play the role of detector flows; this lab's
validated chain (audit → clean → aggregate → MFD → critical point) is exactly
what a Dhaka MFD will need, with bus production density B (Table 1) the most
Dhaka-relevant capacity factor.
