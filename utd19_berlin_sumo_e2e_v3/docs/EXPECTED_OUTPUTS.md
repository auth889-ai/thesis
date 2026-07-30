# Stage-by-stage input and output

| Stage | Main input | Main output |
|---|---|---|
| Download UTD19 | ETH item UUID/DOI | `utd19_u.csv`, detector/link metadata, manual |
| UTD19 preprocessing | 169M-record measurement CSV + detector metadata | hourly Parquet + audit |
| Model comparison | hourly feature table | five-model metrics, fitted models, paper comparison |
| Berlin download | official Azure public blob container | selected measurement files, locations GeoJSON, archive manifest |
| Berlin preprocessing | hourly measurements + locations | clean actual detector-hour table |
| OSM network | Geofabrik Berlin PBF | SUMO `.net.xml` and import log |
| Detector mapping | locations + SUMO network | ranked mapping CSV, accepted mapping CSV, HTML review map |
| Prediction | RF model + Berlin road/time features | 24-hour flow predictions |
| Candidate generation | network + TAZs + detector edges | random, TAZ, and coverage routes |
| Coverage gate | candidate routes + monitored edges | coverage CSV; pipeline stops below 100% |
| Calibration | candidate routes + predicted edge counts | calibrated routes + mismatch XML |
| Simulation | network + calibrated demand | edge counts, summary, tripinfo, routes |
| Evaluation | actual + predicted + simulated | MAE/SMAPE, GEH, figures, report |
| GUI package | network + routes + settings | Mac-ready ZIP |
