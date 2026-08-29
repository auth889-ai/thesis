# Execution runbook

## Lab 00

1. Upload/unzip this project in Colab or Drive.
2. Put official UTD19 files under `MyDrive/DhakaFlow-Nexus-Data/Lab00_UTD19/raw/`.
3. Open `paper_labs/00_utd19/notebooks/Lab00_UTD19_Full_Colab.ipynb`.
4. Run audit -> smoke -> selected-city full -> all-city full-release reconstruction.
5. Claude fills any real schema differences and region metadata only from verified sources.
6. Save Drive manifest and Lab 00 report.

## Lab 01

1. Open `paper_labs/01_sumo_foundation/notebooks/Lab01_SUMO_Foundation_Colab.ipynb`.
2. Install SUMO and record exact version.
3. Build unit intersection and run static tests.
4. Run same-demand Fixed-Time / Actuated / Max-Pressure benchmark.
5. Fetch official `DLR-TS/sumo-scenarios` Bologna/Acosta and record commit SHA.
6. Run official scenario unchanged first; wrapper fixes only if compatibility requires them.
7. Save metrics and report.

## Secrets

Use Colab Secrets or a private `.env`. Do not paste keys into notebooks or Git.
