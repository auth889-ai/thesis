# Claude prompt — run Lab 00 in Colab

Work on **Lab 00 only**.

1. Keep local repo as source code/docs/tests only.
2. Use Google Colab for all real/full UTD19 processing.
3. Use Google Drive for `utd19_u.csv` and large outputs.
4. Never download the multi-GB UTD19 measurement file to the Mac.
5. Read `README.md`, `METHOD_SPEC.md`, `DATA_SPEC.md`, `ASSUMPTIONS.md` and `configs/lab00.yaml` first.
6. Open/run `notebooks/Lab00_UTD19_Full_Colab.ipynb` top-to-bottom.
7. If official data files have different names/columns, adapt the schema resolver based on the **real headers**, document the change, and add a test.
8. Audit the full released dataset before selecting any city/region.
9. Do not invent the 107 regional boundaries. Extract/verify from the supplementary material when possible and populate `configs/regions.yaml`; otherwise mark region-level reproduction PARTIAL.
10. Never substitute current Google traffic data for the 2019 calibration and call it reproduced.
11. Run all tests and inspect all plots.
12. Save exact dataset checksums, environment versions and outputs manifest.

Stop with:

`LAB 00 STATUS: PASS / PARTIAL / FAIL`

and list exact Colab URL, Drive paths, commands/cells, measured results, deviations and unresolved items. Do not start Lab 01 automatically.
