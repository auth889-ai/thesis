# RESULTS — DhakaFlow rebuild

Generated 2026-09-01T15:26 @ `a503947` by `python results/build_results.py`.

Every table below is read from a file written by the pipeline named next to it. Nothing here is typed by hand.


## Evidence audit — reality labels and missing work

`python results/evidence_audit.py` → `results/evidence_audit.md`

# Evidence Audit

Generated UTC: `2026-09-01T09:26:01.311552+00:00`.
Overall status: **PASS_WITH_PENDING_ITEMS**.

| area | status | artifact | check | details |
|---|---|---|---|---|
| Dhaka twin prediction data | PASS | `predict/data/dhaka_twin/MANIFEST.json` | PASS manifest, labelled simulated, >=3 seeds | label=DHAKA_SIMULATED_SENSOR_GRAPH; acceptance=PASS; seeds=3; shape=[288, 250, 5] |
| Prediction floors | PASS | `predict/results/twin_floors.json` | persistence and historical-average at 4 horizons | models=['historical_average', 'persistence']; horizons_min=[5, 15, 30, 60] |
| Colab BasicTS benchmark | PENDING | `predict/results/benchmark.csv` | real benchmark table copied from Drive | run the Colab notebook, then pull results |
| Routing decision guard | PASS | `route/results/decision_guard.json` | deployable arm improves required metrics on paired seeds | decision=ACT; selected=predictive_persistence; benefit_total_vehicle_hours=32.42411218615388 |
| Live Google reference | PASS | `artifacts/p_live/live_reference_summary.json` | live/reference only, no Google route content persisted | corridors=6; states={'CONGESTED': 2, 'FREE_FLOW': 1, 'SLOW': 3}; route_content_persisted=False |
| Asset bootstrap manifest | PASS | `docs/ASSET_MANIFEST.json` | manifest has assets and no missing entries | assets=50; missing_when_built=0 |
| V2X networking sweep | PASS | `network/results/penetration.csv` | non-empty penetration table | rows=15 |
| NLP incident classifier | PASS | `nlp/results/classifier.json` | classifier metrics JSON exists | metric_keys=['distilbert', 'tfidf_lr', 'tfidf_lr_dhaka_aug'] |

Reality rule: live Google data is used only as runtime/reference evidence, not as cached training data. Dhaka twin sensor data is simulated on the real frozen R1 topology and must not be described as real sensor measurements.


## Prediction — twin floors (persistence / historical average)

`make data && python predict/baselines_twin.py` → `predict/results/twin_floors.md`

# Dhaka twin floors (DHAKA_SIMULATED_SENSOR_GRAPH)

dataset `predict/data/dhaka_twin` shape [288, 250, 5], split sha256 `86b7b5e336f307d2`, mask coverage 84.3%

| model | MAE@5 | RMSE@5 | MAE@15 | RMSE@15 | MAE@30 | RMSE@30 | MAE@60 | RMSE@60 |
|---|---|---|---|---|---|---|---|---|
| persistence | 0.719 | 1.160 | 0.724 | 1.241 | 0.653 | 1.201 | 0.647 | 1.248 |
| historical_average | 0.570 | 1.143 | 0.570 | 1.143 | 0.570 | 1.143 | 0.570 | 1.143 |

target = speed_ms (m/s), test region only, masked


## Prediction — BasicTS benchmark (METR-LA / PEMS-BAY / PEMS08)

`notebooks/Predict_BasicTS_Colab.ipynb (Colab Pro) -> predict/results/benchmark.csv` → `predict/results/benchmark.md`

_NOT YET PRODUCED_


## Routing — arms × paired seeds on Dhaka R1

`make route` → `route/results/stats.md`

# Routing arms, horizon 7200 s, paired seeds

Source: `route/results/arms_h7200.json` (run_arms.py). Values are mean +/- sd over seeds.

| arm | n | total_vehicle_hours | mean_travel_time_all | mean_travel_time_s | p95_travel_time_s | total_waiting_s | mean_time_loss_s | arrived | unfinished | teleports | wall s/run |
|---|---|---|---|---|---|---|---|---|---|---|---|
| static | 3 | 995.6 +/- 140.9 | 597.3 +/- 84.5 | 526.0 +/- 29.2 | 1620.7 +/- 221.2 | 996317.3 +/- 191920.2 | 267.0 +/- 28.4 | 5843.3 +/- 167.4 | 156.7 +/- 167.4 | 151.0 +/- 120.9 | 32.4 |
| reactive | 3 | 1185.7 +/- 35.8 | 726.5 +/- 21.3 | 591.2 +/- 43.2 | 1960.7 +/- 307.1 | 1350573.0 +/- 243850.6 | 340.6 +/- 42.9 | 5530.0 +/- 16.8 | 345.3 +/- 6.8 | 374.3 +/- 35.3 | 100.8 |
| predictive_oracle | 3 | 882.1 +/- 128.4 | 531.2 +/- 80.2 | 513.5 +/- 65.6 | 1549.7 +/- 348.0 | 1018490.0 +/- 352866.8 | 259.8 +/- 66.9 | 5926.7 +/- 84.0 | 55.0 +/- 55.0 | 122.3 +/- 83.1 | 93.6 |
| predictive_persistence | 3 | 799.1 +/- 91.3 | 479.4 +/- 54.8 | 479.4 +/- 54.8 | 1342.7 +/- 303.7 | 821828.7 +/- 305020.7 | 226.3 +/- 56.6 | 6000.0 +/- 0.0 | 0.0 +/- 0.0 | 59.3 +/- 45.6 | 75.6 |
| due | 3 | 631.7 +/- 60.2 | 379.0 +/- 36.1 | 379.0 +/- 36.1 | 668.7 +/- 132.1 | 405794.7 +/- 170198.6 | 142.6 +/- 34.3 | 6000.0 +/- 0.0 | 0.0 +/- 0.0 | 31.7 +/- 29.1 | 550.9 |

DUE status per seed: {"due": {"11": "ok", "12": "ok", "13": "ok"}}

## Paired change vs `static` (mean % change over seeds [bootstrap 95 % CI], paired Wilcoxon p)

| arm | total_vehicle_hours | mean_travel_time_all | mean_travel_time_s | p95_travel_time_s | total_waiting_s | mean_time_loss_s | arrived | unfinished | teleports |
|---|---|---|---|---|---|---|---|---|---|
| reactive | 20.6 % [5.0, 37.8], p=0.25 | 23.2 % [7.4, 40.6], p=0.25 | 12.3 % [10.2, 14.3], p=0.25 | 20.9 % [15.0, 24.6], p=0.25 | 35.8 % [34.3, 38.0], p=0.25 | 27.4 % [24.3, 29.8], p=0.25 | -5.3 % [-7.7, -2.8], p=0.25 | 77.1 % [6.0, 148.2], p=0.25 | 918.5 % [50.0, 2600.0], p=0.25 |
| predictive_oracle | -9.0 % [-24.7, 21.8], p=0.50 | -8.6 % [-24.7, 22.9], p=0.50 | -1.8 % [-16.9, 16.6], p=0.75 | -1.3 % [-33.8, 35.4], p=0.75 | 8.8 % [-39.0, 70.2], p=1.00 | -0.6 % [-29.8, 36.7], p=1.00 | 1.5 % [-2.8, 4.9], p=0.75 | -91.7 % [-100.0, -83.5], p=0.50 | 434.6 % [-83.2, 1430.8], p=1.00 |
| predictive_persistence | -17.9 % [-30.7, 6.4], p=0.50 | -17.9 % [-30.7, 6.4], p=0.50 | -8.3 % [-23.5, 6.4], p=0.50 | -14.5 % [-46.1, 11.6], p=0.75 | -11.8 % [-56.1, 37.0], p=0.75 | -13.3 % [-42.0, 16.4], p=0.75 | 2.7 % [0.0, 5.9], p=0.50 | -100.0 % [-100.0, -100.0], p=0.50 | 167.6 % [-95.0, 669.2], p=0.50 |
| due | -35.0 % [-48.3, -17.1], p=0.25 | -35.0 % [-48.3, -17.1], p=0.25 | -27.7 % [-33.4, -17.1], p=0.25 | -57.9 % [-66.0, -43.3], p=0.25 | -57.2 % [-73.7, -29.3], p=0.25 | -45.9 % [-56.6, -27.1], p=0.25 | 2.7 % [0.0, 5.9], p=0.50 | -100.0 % [-100.0, -100.0], p=0.50 | 71.3 % [-95.4, 400.0], p=0.50 |

## Paired change vs `reactive` (mean % change over seeds [bootstrap 95 % CI], paired Wilcoxon p)

| arm | total_vehicle_hours | mean_travel_time_all | mean_travel_time_s | p95_travel_time_s | total_waiting_s | mean_time_loss_s | arrived | unfinished | teleports |
|---|---|---|---|---|---|---|---|---|---|
| static | -16.1 % [-27.4, -4.7], p=0.25 | -17.8 % [-28.9, -6.9], p=0.25 | -10.9 % [-12.5, -9.2], p=0.25 | -17.2 % [-19.7, -13.0], p=0.25 | -26.3 % [-27.5, -25.5], p=0.25 | -21.5 % [-23.0, -19.6], p=0.25 | 5.7 % [2.8, 8.4], p=0.25 | -55.1 % [-100.0, -5.7], p=0.25 | -60.3 % [-96.3, -33.3], p=0.25 |
| predictive_oracle | -25.4 % [-36.8, -11.6], p=0.25 | -26.7 % [-38.0, -12.6], p=0.25 | -12.4 % [-27.3, 5.8], p=0.50 | -18.2 % [-46.9, 10.1], p=0.50 | -20.3 % [-54.5, 23.4], p=0.50 | -21.6 % [-45.9, 10.0], p=0.50 | 7.2 % [5.4, 8.2], p=0.25 | -84.1 % [-100.0, -67.9], p=0.25 | -65.9 % [-91.8, -43.3], p=0.25 |
| predictive_persistence | -32.4 % [-41.9, -22.8], p=0.25 | -33.8 % [-43.0, -24.3], p=0.25 | -18.2 % [-33.1, -3.4], p=0.25 | -28.9 % [-56.7, -9.2], p=0.25 | -35.3 % [-67.3, -0.8], p=0.25 | -31.6 % [-55.3, -6.4], p=0.25 | 8.5 % [8.2, 8.9], p=0.25 | -100.0 % [-100.0, -100.0], p=0.25 | -83.4 % [-97.6, -71.5], p=0.25 |
| due | -46.7 % [-50.7, -39.9], p=0.25 | -47.8 % [-51.8, -41.1], p=0.25 | -35.5 % [-41.8, -24.8], p=0.25 | -65.2 % [-71.4, -53.9], p=0.25 | -68.6 % [-80.5, -48.8], p=0.25 | -57.3 % [-66.1, -41.3], p=0.25 | 8.5 % [8.2, 8.9], p=0.25 | -100.0 % [-100.0, -100.0], p=0.25 | -91.3 % [-96.9, -81.5], p=0.25 |

Footer: n = 3 paired seeds. The two-sided paired Wilcoxon signed-rank test cannot go below p = 0.25 with n = 3 (p = 0.25 at n = 3), so p-values here are coarse and can never reach 0.05; read the bootstrap CI (10k resamples of the seeds) and the sign consistency instead. Percent change on `teleports`/`unfinished` is undefined when the reference is 0 for a seed (that seed is dropped). total_vehicle_hours is the headline: it charges every inserted vehicle up to the horizon, so it is the only column that is commensurable when arms finish different numbers of trips.


## Routing — network-wide decision guard

`python route/decision_guard.py --horizon 7200 --reference reactive` → `route/results/decision_guard.md`

# Routing Decision Guard, Horizon 7200 s

Source: `/Users/jannatulferdouseva/thesis/route/results/arms_h7200.json`.
Reference arm: `reactive`.
Decision: **ACT**.
Selected deployable arm: `predictive_persistence`.

Acceptance rule: minimum 3 paired seeds; total vehicle-hours, arrivals, and teleports must all improve on every paired seed.

| arm | n | accepted | mean total-vehicle-hours benefit | mean arrivals benefit | mean teleports benefit | reason |
|---|---:|---|---:|---:|---:|---|
| predictive_persistence | 3 | True | 32.4% | 8.5% | 83.4% | improves total vehicle-hours, arrivals, and teleports on every paired seed |

Offline benchmarks, not runtime actions:

| arm | n | accepted by metrics | mean total-vehicle-hours benefit |
|---|---:|---|---:|
| due | 3 | True | 46.7% |

Upper bounds, not deployable real forecasts:

| arm | n | accepted by metrics | mean total-vehicle-hours benefit |
|---|---:|---|---:|
| predictive_oracle | 3 | True | 25.4% |

Honesty label: `DHAKA_SIMULATED_SENSOR_GRAPH`.


## Live reference — Google Routes derived congestion states

`python scripts/run_live_capture.py && python scripts/summarize_live_reference.py` → `artifacts/p_live/live_reference_summary.md`

# Live Reference Summary

Source: `/Users/jannatulferdouseva/thesis/artifacts/p_live/normalized/google_routes_runtime_reference.jsonl`.
Generated UTC: `2026-09-01T05:07:26.065250+00:00`.
Google data mode: `RUNTIME_REFERENCE`.

This summary stores only request metadata and derived congestion states.
It does not store Google route geometry, route durations, speed intervals, or training data.

Latest captured corridors: **6**.
Latest congested/severe corridors: **2**.

| corridor | captured UTC | state | latency ms | route content persisted |
|---|---|---|---:|---|
| banglamotor_to_karwanbazar | 2026-09-01T05:06:41.390288+00:00 | SLOW | 255.5 | False |
| farmgate_to_banglamotor | 2026-09-01T05:06:41.876769+00:00 | SLOW | 486.2 | False |
| farmgate_to_shahbagh | 2026-09-01T05:06:40.579774+00:00 | SLOW | 346.4 | False |
| karwanbazar_to_banglamotor | 2026-09-01T05:06:41.134441+00:00 | CONGESTED | 280.1 | False |
| karwanbazar_to_shahbagh | 2026-09-01T05:06:42.158782+00:00 | CONGESTED | 281.6 | False |
| shahbagh_to_farmgate | 2026-09-01T05:06:40.853874+00:00 | FREE_FLOW | 273.6 | False |

State counts: {"CONGESTED": 2, "FREE_FLOW": 1, "SLOW": 3}


## Networking — V2X penetration sweep (Eclipse MOSAIC)

`make network` → `network/results/penetration.md`

# V2X penetration sweep - Eclipse MOSAIC 25.2, Dhaka R1 (registered scenario)

Knob: `mapping_config.json` -> `typeDistributions.DEFAULT_VEHTYPE` = [{AdHoc: WeatherWarningApp+SlowDownApp, weight p}, {Unequipped: SlowDownApp, weight 1-p}], `config.fixedOrder=false` (stochastic, seed-driven). Hazard: TRACTION_HAZARD/ICE rectangle at Karwan Bazar (environment_config.json); equipped vehicles that sense it broadcast DENMs over SNS ad-hoc (ITS-G5, multi-hop TTL 20); receivers with the hazard on their route reroute through the official NavigationModule.

Definitions: equipped = registered with WeatherWarningApp; delivery_ratio_veh = distinct receivers / equipped; latency = t_rx - t_tx per MessageId; route switches = CentralNavigationComponent 'Change to route' lines; travel time = SUMO tripinfo of finished trips (equipped vs unequipped split).

## Per point

| p | seed | wall s | registered | equipped | DENM sent | senders | receptions | receivers | deliv. ratio | lat mean ms | lat p95 ms | route switches | veh switched | trips fin. | TT mean s | TT p95 s | timeLoss mean s | TT eq. s | TT uneq. s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.0 | 11 | 16 | 2147 | 0 | 0 | 0 | 0 | 0 |  |  |  | 0 | 0 | 543 | 332.0 | 484.9 | 119.6 |  | 332.0 |
| 0.0 | 22 | 38 | 2161 | 0 | 0 | 0 | 0 | 0 |  |  |  | 0 | 0 | 549 | 337.9 | 490.0 | 120.7 |  | 337.9 |
| 0.0 | 33 | 12 | 2121 | 0 | 0 | 0 | 0 | 0 |  |  |  | 0 | 0 | 560 | 335.4 | 496.1 | 121.3 |  | 335.4 |
| 0.1 | 11 | 17 | 2157 | 218 | 3702 | 31 | 428339 | 211 | 0.968 | 30.0 | 57.44 | 68 | 68 | 569 | 335.3 | 481.2 | 119.2 | 341.1 | 334.7 |
| 0.1 | 22 | 44 | 2157 | 208 | 4650 | 36 | 518792 | 202 | 0.971 | 30.0 | 57.45 | 59 | 59 | 557 | 338.6 | 483.4 | 124.2 | 334.6 | 339.1 |
| 0.1 | 33 | 14 | 2193 | 207 | 3716 | 36 | 414112 | 198 | 0.957 | 29.98 | 57.38 | 69 | 69 | 534 | 333.5 | 474.3 | 119.8 | 332.6 | 333.6 |
| 0.25 | 11 | 35 | 2127 | 520 | 11165 | 89 | 3033412 | 499 | 0.96 | 30.01 | 57.44 | 171 | 171 | 552 | 332.3 | 478.0 | 120.8 | 326.1 | 334.2 |
| 0.25 | 22 | 50 | 2164 | 540 | 10294 | 93 | 2970222 | 529 | 0.98 | 30.0 | 57.48 | 170 | 170 | 570 | 336.3 | 481.0 | 121.3 | 329.6 | 338.6 |
| 0.25 | 33 | 22 | 2156 | 527 | 7986 | 79 | 2217156 | 511 | 0.97 | 29.99 | 57.4 | 156 | 156 | 563 | 337.4 | 495.0 | 124.6 | 326.2 | 341.3 |
| 0.5 | 11 | 103 | 2153 | 1083 | 22563 | 184 | 12880209 | 1057 | 0.976 | 30.0 | 57.45 | 375 | 375 | 578 | 341.6 | 492.9 | 124.3 | 342.0 | 341.3 |
| 0.5 | 22 | 103 | 2177 | 1093 | 21676 | 187 | 13082548 | 1058 | 0.968 | 30.0 | 57.42 | 357 | 357 | 559 | 335.8 | 511.0 | 123.6 | 334.5 | 336.9 |
| 0.5 | 33 | 59 | 2153 | 1075 | 19050 | 185 | 11088610 | 1042 | 0.969 | 30.0 | 57.42 | 354 | 354 | 547 | 334.6 | 469.1 | 123.0 | 333.6 | 335.6 |
| 1.0 | 11 | 751 | 2175 | 2175 | 47845 | 411 | 58037523 | 2124 | 0.977 | 30.0 | 57.45 | 724 | 724 | 567 | 334.6 | 486.7 | 124.0 | 334.6 |  |
| 1.0 | 22 | 356 | 2185 | 2185 | 45732 | 387 | 54688803 | 2130 | 0.975 | 30.0 | 57.45 | 706 | 706 | 542 | 329.1 | 471.9 | 117.5 | 329.1 |  |
| 1.0 | 33 | 312 | 2168 | 2168 | 44928 | 388 | 54208312 | 2107 | 0.972 | 30.0 | 57.44 | 708 | 708 | 533 | 327.3 | 492.4 | 118.5 | 327.3 |  |

## Mean over seeds

| p | n seeds | equipped frac | receivers | deliv. ratio | lat mean ms | lat p95 ms | route switches | TT mean s | TT p95 s | timeLoss mean s |
|---|---|---|---|---|---|---|---|---|---|---|
| 0.0 | 3 | 0.0 | 0.0 | - | - | - | 0.0 | 335.1 | 490.3 | 120.5 |
| 0.1 | 3 | 0.097 | 204.0 | 0.965 | 29.99 | 57.42 | 65.0 | 335.8 | 479.6 | 121.1 |
| 0.25 | 3 | 0.246 | 513.0 | 0.97 | 30.0 | 57.44 | 166.0 | 335.3 | 484.7 | 122.2 |
| 0.5 | 3 | 0.501 | 1052.0 | 0.971 | 30.0 | 57.43 | 362.0 | 337.3 | 491.0 | 123.6 |
| 1.0 | 3 | 1.0 | 2120.0 | 0.975 | 30.0 | 57.45 | 713.0 | 330.3 | 483.7 | 120.0 |

Source JSONs: `network/results/penetration_p{P}_s{SEED}.json`; regenerate with `python network/penetration_sweep.py --aggregate`.


## Networking — latency / loss vs advisory delivery

`python network/latency_injection.py` → `network/results/latency.md`

# Latency / loss injection - fraction of route advisories delivered before the decision point

* base latency: V2XBus <- MEASURED from official Eclipse MOSAIC 25.2 Barnim example (SNS ad-hoc ITS-G5 geocast), run 2026-08-29, logs/log-20260829-163311-Barnim  (n=504, mean 2.6 ms, p95 7.0 ms)
* time budget tth: sweep JSONs (15 points, 3917 rerouting vehicles): distance from position at first DENM reception to hazard rectangle / speed
  n=3917, p10 0.0 s, p50 50.1 s, p90 249.0 s; 554 vehicles (14%) were already inside the hazard rectangle at first reception (tth = 0: no advisory can arrive in time; counted as not delivered in the all-vehicle columns, excluded in the upstream-only columns)
* Monte Carlo: 20 draws per vehicle, seed 0; delivered = not lost AND (latency + added) < tth

| added latency ms | loss % | delivered (single DENM) | delivered (1 Hz DENM repeat) | upstream-only single | upstream-only repeat | eff. latency mean ms |
|---|---|---|---|---|---|---|
| 0 | 0 | 0.859 | 0.859 | 1.000 | 1.000 | 2.6 |
| 0 | 10 | 0.773 | 0.850 | 0.900 | 0.990 | 2.6 |
| 0 | 30 | 0.600 | 0.832 | 0.701 | 0.969 | 2.6 |
| 500 | 0 | 0.775 | 0.775 | 0.902 | 0.902 | 502.6 |
| 500 | 10 | 0.697 | 0.774 | 0.810 | 0.902 | 502.6 |
| 500 | 30 | 0.542 | 0.773 | 0.627 | 0.901 | 502.6 |
| 2000 | 0 | 0.770 | 0.770 | 0.896 | 0.896 | 2002.6 |
| 2000 | 10 | 0.693 | 0.769 | 0.807 | 0.896 | 2002.6 |
| 2000 | 30 | 0.537 | 0.768 | 0.627 | 0.895 | 2002.6 |
| 5000 | 0 | 0.764 | 0.764 | 0.889 | 0.889 | 5002.6 |
| 5000 | 10 | 0.688 | 0.763 | 0.800 | 0.889 | 5002.6 |
| 5000 | 30 | 0.532 | 0.763 | 0.622 | 0.889 | 5002.6 |

single DENM: one advisory per vehicle, lost with probability `loss`. 1 Hz repeat: the official WeatherWarningApp re-sends a DENM every second while in the hazard, so a vehicle with slack tth - latency gets one extra chance per second (P = 1 - loss^n).

Regenerate: `python network/latency_injection.py [--base sweep]`.


## NLP — incident-text classifier

`make nlp` → `nlp/results/classifier.md`

# Traffic-text classifier — {incident, congestion, irrelevant}

Data: `nlp/data/MANIFEST.json` (source: REAL; test n = 10226, frozen held-out).

| model | CV acc (5-fold) | CV macro-F1 | **test acc** | **test macro-F1** | F1 incident | F1 congestion | F1 irrelevant | Dhaka-seed acc / mF1 (n=150) | train s |
|---|---|---|---|---|---|---|---|---|---|
| tfidf_lr | 0.9758 ± 0.0014 | 0.9697 ± 0.0017 | **0.9764** | **0.9705** | 0.9738 | 0.9516 | 0.9860 | 0.633 / 0.608 | 50.8 |
| tfidf_lr_dhaka_aug | 0.9747 ± 0.0010 | 0.9683 ± 0.0015 | **0.9768** | **0.9712** | 0.9744 | 0.9534 | 0.9858 | 0.873 / 0.873 | 58.1 |
| distilbert | – | – | **0.9783** | **0.9724** | 0.9769 | 0.9532 | 0.9872 | 0.647 / 0.629 | 1119.8 |

Confusion matrix (tfidf_lr, test; rows = true, cols = pred; order ['incident', 'congestion', 'irrelevant']):

```
   incident   3404     45     40
 congestion     53   1534     30
 irrelevant     45     28   5047
```

Confusion matrix (tfidf_lr_dhaka_aug, test; rows = true, cols = pred; order ['incident', 'congestion', 'irrelevant']):

```
   incident   3409     39     41
 congestion     53   1535     29
 irrelevant     46     29   5045
```

Confusion matrix (distilbert, test; rows = true, cols = pred; order ['incident', 'congestion', 'irrelevant']):

```
   incident   3424     36     29
 congestion     55   1537     25
 irrelevant     42     35   5043
```

Dhaka-seed column: `tfidf_lr`/`distilbert` = zero-shot (seed never trained on); `tfidf_lr_dhaka_aug` = 5-fold over the seed with the real corpus + 4/5 seed in training.

Regenerate: `python nlp/get_data.py && python nlp/train_classifier.py --augment-seed` (`--model distilbert` for the transformer row).
