# ASSUMPTIONS — Lab 00 (UTD19 / Loder et al. 2019)

Classification: **Independent paper-faithful reconstruction; this is not the
authors' official analysis code.** (`ambuehll/UTD19` = README-only dataset
vignette; verified 2026-08-09, clone in `upstream/author_vignette/`.)

## PUBLISHED (stated in paper or companion references)

- Detector interval ~300 s; variables q_i(t), o_i(t) (Methods "Initial dataset").
- Road classes analyzed: OSM trunk, primary, secondary, tertiary.
- Re-sampling: 300 draws at 80% sample size (Methods "MFD estimation").
- Upper bound: flow's 95th–97.5th percentile at density bins (Methods "Critical point estimation").
- Critical point = maximum of MFD function (ref 18) fitted by nonlinear least squares.
- Speed calibration: two-step; step 2 uses Google Directions API, 1000 random OD
  pairs of 1–6 km excluding freeways, matched at the fastest observed hour.
- Observation weights formula w_i (Methods "Calculation of observation weights").
- Paper sample: 41 cities, 107 regional networks; released UTD19: 40 cities
  (utd19.ethz.ch); Data Availability statement conditions release on city NDAs.
- Regional networks defined heuristically, typically <10 km².

## INFERRED (supported but not verbatim)

- The functional form of ref 18 is the smooth log-sum-exp envelope
  q(k) = −λ ln(e^{−v_f k/λ} + e^{−Q/λ} + e^{−(κ−k)w/λ}); to be re-verified
  against the ref-18 paper before the PAPER_FAITHFUL_MFD stage.
- Re-sampling draws detectors without replacement within each draw (from ref 17's
  description of sub-sampling detector sets).
- The released 40-city UTD19 is a subset of the paper's 41-city sample (missing
  city withheld under NDA); date ranges per city may also differ from those
  analyzed in the paper.
- "Average speed expected at that location" for occupancy rescaling (step 1) can
  be proxied by the detector's road speed limit (`limit` column) or fclass-mean
  free-flow speed; the authors' exact source is not stated.
- `occ` in UTD19 is a 0–1 fraction (to be confirmed by audit; rule V5 adapts if
  the data shows 0–100).

## ASSUMED (our choices where material is silent — each must be documented in outputs)

- Density-bin width for upper-bound extraction: to be chosen at
  PAPER_FAITHFUL_MFD stage with a sensitivity check (e.g., occupancy bins of
  0.01 vs 0.02); not needed for the smoke test.
- Validation thresholds V6 (speed > 200 km/h invalid) and audit criteria of
  DATA_SPEC §7 (coverage/error-rate cutoffs) are our own, stated before running.
- Smoke-test aggregation: arithmetic mean over detectors per interval (loops
  method) without detector-location bias correction — the correction of refs
  37–39 is not specified in the available text (see UNKNOWN below).
- Python stack (pandas/duckdb/matplotlib/scipy) instead of the authors' unknown
  original stack; seeds fixed (seed=42) for any random sampling.

## MODIFIED_BY_US (deliberate deviations, clearly labelled in outputs)

- **City-selection criterion relaxed after the real audit (2026-08-09 Colab run):**
  pre-registered `max_error_rate = 0.10` admitted zero cities. The audit
  (`outputs/audit/city_audit.csv`) showed torino failing ONLY that criterion
  (error rate 0.1255; speed availability 100%; 2,080,768 rows; 399 detectors;
  21 days), while all other speed-reporting cities (manchester, rotterdam,
  essen, bolton, constance, vilnius, innsbruck, birmingham, frankfurt,
  groningen) failed size and/or error criteria harder. We relaxed
  `max_error_rate` to 0.15 — admitting exactly one city — instead of dropping
  the speed criterion, because uncalibrated q/o speed checks need a
  speed-reporting city. The relaxation is in the notebook CONFIG with an
  explanatory comment; nothing was relaxed silently at run time (the notebook
  raises an error rather than auto-relaxing).
- **Observed dataset scope facts (2026-08-09 audit):** `utd19_u.csv` contains
  39 distinct city labels (website lists 40 city names; paper analyzed 41
  cities) — the audit CSV records the exact list. Error-flag rates are extreme
  for some cities (london, bremen, zurich, essen ≈ 100% flagged; bordeaux 100%).
  Most cities report no speed at all.

- `RAW_SANITY_MFD`: mean-flow vs mean-occupancy scatter WITHOUT re-sampling,
  rescaling, calibration, or L-scaling. Sanity artifact only; never presented as
  the paper's MFD.
- `UNCALIBRATED_ANALYSIS`: the Google Directions calibration (step 2) is
  **UNREPRODUCIBLE_FROM_AVAILABLE_HISTORICAL_INPUTS** (2017-era API responses
  cannot be re-queried). We do NOT substitute today's Google values. Speeds in
  our outputs are uncalibrated q/o proxies and are labelled as such. A future
  CALIBRATED_ANALYSIS with modern references would be a separate, clearly
  separated variant.
- Error filtering: paper's exact outlier/noise procedures (refs 35, 36
  TRAMO/SEATS) are cited without parameters; we implement explicit rules
  V1–V10 (DATA_SPEC §6) with per-rule removal counts instead.
- Regional networks: the paper's per-network polygons are not machine-readable
  from available material; if the released data encodes no region membership,
  our smoke test treats a single city's filtered detector set as one network —
  a deviation that widens the MFD scatter and must be stated on every figure.
- Reuse from `utd19_berlin_sumo_e2e_v3` (per Scientific Correction 5): only the
  *download mechanism pattern* (ETH DSpace REST discovery) and two verified
  data-handling facts (column names bound from real headers; Toulouse quoting
  quirk). No scientific results are reused. The Lab 00 notebook re-implements
  download + audit independently.

## UNKNOWN FROM AVAILABLE MATERIAL

- Exact parameters of outlier/noise filtering (refs 35–36 usage).
- Detector-location bias correction formula (refs 37–39 usage).
- Exact per-network partitions (Supplementary figures are images, not data).
- Density-bin width used for the quantile upper bound.
- NLS starting values/bounds for the functional-form fit.
- Which of the paper's 41 cities is absent from the 40-city release (audit will
  attempt to identify by comparing city lists).
- The authors' original analysis code (not published).
