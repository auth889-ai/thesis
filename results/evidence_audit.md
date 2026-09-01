# Evidence Audit

Generated UTC: `2026-09-01T16:42:42.301399+00:00`.
Overall status: **PASS_WITH_PENDING_ITEMS**.

| area | status | artifact | check | details |
|---|---|---|---|---|
| Dhaka twin prediction data | PASS | `predict/data/dhaka_twin/MANIFEST.json` | PASS manifest, labelled simulated, >=3 seeds | label=DHAKA_SIMULATED_SENSOR_GRAPH; acceptance=PASS; seeds=3; shape=[288, 250, 5] |
| Prediction floors | PASS | `predict/results/twin_floors.json` | persistence and historical-average at 4 horizons | models=['historical_average', 'persistence']; horizons_min=[5, 15, 30, 60] |
| Colab BasicTS benchmark | PENDING | `predict/results/benchmark.csv` | real benchmark table copied from Drive | run the Colab notebook, then pull results |
| Routing decision guard | PASS | `route/results/decision_guard.json` | appendix simulation either selects a safe arm or honestly blocks unsafe action | decision=NO_SAFE_ROUTING_ACTION; selected=None; benefit_total_vehicle_hours=None |
| Live Google reference | PASS | `artifacts/p_live/live_reference_summary.json` | live/reference only, no Google route content persisted | corridors=6; states={'CONGESTED': 2, 'FREE_FLOW': 1, 'SLOW': 3}; route_content_persisted=False |
| Real route advisor | PASS | `live/results/route_advice.jsonl` | real live advisory exists and stores no Google route content | rows=1; real_rows=1; route_content_persisted=False |
| Real user pilot | PENDING | `live/results/pilot_metrics.json` | completed trip metrics exist | run live/user_trip_logger.py start/complete for the 3 users |
| Asset bootstrap manifest | PASS | `docs/ASSET_MANIFEST.json` | manifest has assets and no missing entries | assets=50; missing_when_built=0 |
| V2X networking sweep | PASS | `network/results/penetration.csv` | non-empty penetration table | rows=15 |
| NLP incident classifier | PASS | `nlp/results/classifier.json` | classifier metrics JSON exists | metric_keys=['distilbert', 'tfidf_lr', 'tfidf_lr_dhaka_aug'] |

Reality rule: live Google data is used only as runtime/reference evidence, not as cached training data. Dhaka twin sensor data is simulated on the real frozen R1 topology and must not be described as real sensor measurements.
The `live/` route-advisor and user-pilot path is the no-fixed-seed real-world evidence path.
