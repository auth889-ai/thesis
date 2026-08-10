# EXPERIMENT_SPEC — Lab 00 smoke test (Colab)

Status: IN PROGRESS — fields marked `[RUN]` are filled from the completed Colab
run record (`outputs/run_record.json`); do not fill them by hand.

## Environment

- Execution: Google Colab (account `anastasiasaat81@gmail.com`, 200 GB Drive plan;
  switched from `studyemail953@gmail.com` on 2026-08-10 after its free compute
  quota was exhausted mid-run).
- Colab notebook URL: https://colab.research.google.com/drive/1k3KdxjUbdyu0abJ5_rtRyHNeXH5ZNE7R
  (earlier partial-run copy under studyemail953:
  https://colab.research.google.com/drive/10WdmUAiFSN1e25MCczjzzirY_9sIdnMT — superseded;
  its Drive holds an orphaned first copy of the 7 GB download)
- Runtime observed (first run, 2026-08-09/10): Python 3.12.13, Linux 6.6.122+ (glibc 2.35)
- Pinned deps: duckdb==1.1.3, pandas==2.2.2, pyarrow==17.0.0, requests==2.32.3,
  matplotlib==3.8.4 requested. **Observed deviation:** Colab resolved
  matplotlib 3.10.0 and numpy 2.0.2 (pre-installed wheels take precedence);
  harmless for the smoke test, recorded here rather than hidden.
- Seed: 42 (numpy; no stochastic steps in the smoke test itself).

## Dataset

- UTD19 via ETH Research Collection DOI 10.3929/ethz-b-000437802 (DSpace REST).
- Files + sizes: see DATA_SPEC §2 (utd19_u.csv 6,978.6 MB; detectors_public.csv
  2.6 MB; links.csv 7.5 MB; Manual.pdf). sha256 recorded in
  `outputs/manifest/drive_manifest.csv` `[RUN]`.
- No API key needed; endpoint verified working from Colab (blocked from the
  user's local network — documented in DATA_SPEC §1).

## Experiment definition

Exact experiment = the notebook `notebooks/Lab00_UTD19_Colab.ipynb` executed
top-to-bottom (Runtime → Run all). Command equivalent: upload notebook → Run all.
No cells may be skipped; the notebook halts by design if city selection fails.

- Selected city: **torino** (only city passing criteria incl. documented
  relaxation `max_error_rate = 0.15`; see ASSUMPTIONS.md → MODIFIED_BY_US).
  Audit facts (2026-08-09 full-file audit): 2,080,768 rows, 399 detectors,
  21 days, speed_avail 1.0, error_rate 0.1255.
- Smoke window: first 7 fully-covered days `[RUN: exact dates]`.
- Validation: rules V1–V10 (DATA_SPEC §6); per-rule counts in
  `outputs/audit/validation_report.csv` `[RUN]`.

## Inputs / outputs

- Inputs (Drive): `DhakaFlow-Nexus-Data/Lab00_UTD19/raw/{utd19_u.csv, detectors.csv, links.csv}`
- Heavy outputs (Drive): `processed/torino_smoke.parquet`, full-size figures,
  `repo_artifacts_lab00.zip`
- Repo outputs (git): `outputs/audit/*.csv`, `outputs/figures/*.png`,
  `outputs/manifest/drive_manifest.csv`, `outputs/run_record.json` `[RUN]`

## Known run-history notes (honesty log)

- 2026-08-09 (studyemail953): download + audit + city-audit completed; run
  halted by design at selection (zero cities passed pre-registered criteria);
  free-quota exhaustion then killed the runtime. Relaxation decided and
  documented; notebook rebuilt locally with the relaxation in CONFIG.
- 2026-08-10 (anastasiasaat81): corrected notebook uploaded; fresh 7 GB
  download into this account's Drive; run in progress `[RUN: final state]`.
- Colab notebook file showed "Automatic saving failed / updated remotely"
  warnings in both accounts; scientific artifacts are written to Drive by the
  code itself and are unaffected. The version-controlled notebook lives in git.
