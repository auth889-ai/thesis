# Evidence Audit

Generated UTC: `2026-10-05T00:19:52.946623+00:00`.
Overall status: **PASS_WITH_PENDING_ITEMS**.

| area | status | artifact | check | details |
|---|---|---|---|---|
| Dhaka twin prediction data | PASS | `data/forecasting/dhaka_twin/MANIFEST.json` | PASS manifest, labelled simulated, >=3 seeds | label=DHAKA_SIMULATED_SENSOR_GRAPH; acceptance=PASS; seeds=3; shape=[288, 250, 5] |
| Prediction floors | PASS | `results/forecasting/twin_floors.json` | persistence and historical-average at 4 horizons | models=['historical_average', 'persistence']; horizons_min=[5, 15, 30, 60] |
| Colab BasicTS benchmark | PASS | `results/forecasting/benchmark.md` | benchmark markdown exists | CSV not present; markdown will be shown in RESULTS |
| Routing decision guard | PASS | `results/routing/decision_guard.json` | appendix simulation either selects a safe arm or honestly blocks unsafe action | decision=NO_SAFE_ROUTING_ACTION; selected=None; benefit_total_vehicle_hours=None |
| Real user pilot | PENDING | `live/results/pilot_metrics.json` | completed trip metrics exist | run live/user_trip_logger.py start/complete for the 3 users |
| Asset bootstrap manifest | PENDING | `docs/ASSET_MANIFEST.json` | asset manifest exists | run python research/reports/build_asset_manifest.py |
| V2X networking sweep | PASS | `results/networking/penetration.csv` | non-empty penetration table | rows=15 |
| NLP incident classifier | PASS | `results/nlp/classifier.json` | classifier metrics JSON exists | metric_keys=['distilbert', 'tfidf_lr', 'tfidf_lr_dhaka_aug'] |

Reality rule: no Google data is used. Every result built on the Google Routes recording was withdrawn on 2026-10-05 (docs/proposals.md). Dhaka twin sensor data is simulated on the real frozen R1 topology and must not be described as real sensor measurements; its demand is a synthetic what-if, uncalibrated.
