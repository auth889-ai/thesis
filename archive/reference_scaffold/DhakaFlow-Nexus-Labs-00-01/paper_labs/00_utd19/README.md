# Lab 00 — UTD19 Traffic Science Foundation

**Classification:** Independent paper-faithful reconstruction; this is not the authors' official analysis code.

## Primary paper

Loder, A., Ambühl, L., Menendez, M., Axhausen, K. W. (2019), **Understanding traffic capacity of urban networks**, Scientific Reports 9, 16283.

Why this paper: it is the paper UTD19 itself asks users to cite and it establishes the network-level concepts that later forecasting/control must respect: accumulation, travel production, MFD, critical accumulation and network capacity.

## Companion method paper

Ambühl et al. (2018), **Introducing a Re-Sampling Methodology for the Estimation of Empirical Macroscopic Fundamental Diagrams**.

## What this lab does

1. Audit the **entire released UTD19 measurement file** across all cities using DuckDB (streaming/out-of-core).
2. Create deterministic city coverage/quality tables.
3. Build raw city-level sanity MFDs (explicitly **not** called paper reproduction).
4. Implement paper-required re-sampling: 300 draws at 80% detector sample size for the 2019 analysis path, with a fixed seed for reproducibility.
5. Extract 95th and 97.5th percentile upper boundaries by density/occupancy bins.
6. Fit a physically interpretable soft-min/trapezoidal MFD function as the implementation path from the cited functional-form work.
7. Estimate critical point as the maximum of the fitted curve.
8. Keep historical Google Directions calibration as an explicit unreproduced component unless the exact 2019 inputs are available.

## Important scientific limitation

The 2019 paper used **41 cities / 107 manually defined regional networks**. The current public UTD19 release advertises **40 cities**. The released data and paper analysis sample must not be silently treated as identical. Exact regional boundaries and historical Google calibration are required for exact paper replication.

Therefore this lab has two outputs:

- `FULL_RELEASE_AUDIT`: real full released UTD19 dataset.
- `PAPER_METHOD_RECONSTRUCTION`: method implementation where required region metadata is available/documented.

## Data placement

Put official UTD19 files in Google Drive:

```text
MyDrive/DhakaFlow-Nexus-Data/Lab00_UTD19/raw/
  utd19_u.csv
  detectors_public.csv   # or detectors.csv; schema resolver handles both
  links.csv
  Manual.pdf             # optional but recommended
```

The dataset is access-controlled by a free researcher signup. Do not bypass the access terms.

## Run

Open `notebooks/Lab00_UTD19_Full_Colab.ipynb` in Google Colab and run top-to-bottom.

The notebook first runs a metadata/header check, then full-dataset audit, then method reconstruction. It never copies the multi-GB measurement file to the local Git repo.

## Pass gates

- Full release loaded and audited.
- Flow / occupancy / speed fields explained with real examples.
- Raw sanity MFD generated and correctly labelled.
- Re-sampling method verified on synthetic test and real region/city subset.
- Critical point code independently checked.
- Exact deviations from 2019 paper documented.
- Full-dataset outputs and manifests saved to Drive.
