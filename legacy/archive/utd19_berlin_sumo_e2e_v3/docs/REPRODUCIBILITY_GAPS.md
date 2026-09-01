# Reproducibility gaps and how V3 handles them

The paper supplies the high-level workflow, model families, model metrics, sample tables, Berlin dates used in Figure 4, SUMO tools, GEH formula, and final reported scale. It does **not** supply enough material for bit-for-bit reproduction.

| Missing detail | V3 treatment |
|---|---|
| Exact UTD19 valid-row filter | Official manual semantics: a non-missing `error` is excluded; audit counts are saved. |
| Hourly aggregation | UTD19 `flow` is already veh/h/lane, so V3 averages interval rates within each hour and stores median as a sensitivity check. |
| Target scope | Configurable `per_lane` or `detector_total`; default uses `flow × monitored lanes` to compare with Berlin `Nveh`. |
| City population/density table | Disabled by default rather than invented. Optional user-supplied table is supported. |
| Exact split | Group holdout by complete detector, recorded in the protocol file. |
| Exact hyperparameters | All values are in YAML and exported with results. |
| Exact OSM snapshot | Current Geofabrik Berlin extract by default; checksum and timestamp are recorded. |
| Exact detector-to-lane mapping | Automated ranked mapping plus mandatory visual/manual review in subset/full mode. |
| Exact TAZ definitions | Reproducible grid TAZs plus targeted coverage routes; not claimed as authors' TAZs. |
| Exact routeSampler command | Uses paper-described route inputs, edge counts, and `--optimize full`; every remaining option is logged. |
| Exact Figure 5 quantity | V3 produces three separately labelled series: departures, running vehicles, and aggregate monitored-edge predictions. |

## Claims permitted after a run

- “Paper-faithful end-to-end reconstruction using official public data and SUMO tools.”
- “All valid UTD19 rows were scanned and aggregated.”
- “The resulting metrics/simulation are our independently generated results.”

## Claims not permitted without authors' files

- “Exact reproduction of the authors' code.”
- “Exact reproduction of Table V.”
- “Exact reproduction of the 1.2 million vehicle scenario.”
