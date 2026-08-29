# Validation status of this delivered artifact

## Completed in the build environment

- Uploaded seven-page paper copied and rendered into seven PNG pages.
- Every Python source file compiled successfully.
- Notebook JSON validated; 54 executable/teaching cells are present.
- Synthetic UTD19/Berlin generator executed.
- Berlin flexible CSV and GeoJSON parsing functions executed on synthetic data.
- Predicted-count → SUMO edgeData XML conversion executed on synthetic data.
- Candidate-route coverage parser executed on synthetic route XML.
- GEH, actual/predicted metrics and graph generation executed on synthetic tables.
- All project paths, configuration files and expected output contracts checked.

## Not executed in the build environment

- The 6.65 GB official UTD19 download.
- Full DuckDB preprocessing, because DuckDB/pyarrow were not available in this isolated build runtime.
- Official Berlin archive download.
- Current Berlin OSM download and `netconvert`.
- `randomTrips.py`, `duarouter`, `routeSampler`, `sumo`, or `sumo-gui`, because SUMO binaries were not installed in this build runtime.
- The whole-Berlin 24-hour simulation.

The Colab install script installs those runtime dependencies. The full experiment must therefore be executed by the user in Colab/local infrastructure. No generated full-data result is bundled or claimed.

## Configuration meaning

- `demo.yaml`: synthetic smoke test through every pipeline stage.
- `subset.yaml`: all official UTD19 preprocessing, capped model rows and 30 Berlin detectors.
- `full_colab.yaml`: all official UTD19 preprocessing with transparent caps for expensive models; intended for ordinary Colab.
- `full.yaml`: literal all-row model training plus whole-Berlin 24-hour pipeline; may require a high-memory machine and long runtime.
