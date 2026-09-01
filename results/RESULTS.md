# RESULTS — DhakaFlow rebuild

Generated 2026-09-01T22:23 @ `226d412` by `python results/build_results.py`.

Every table below is read from a file written by the pipeline named next to it. Nothing here is typed by hand.


## Evidence audit — reality labels and missing work

`python results/evidence_audit.py` → `results/evidence_audit.md`

# Evidence Audit

Generated UTC: `2026-09-01T10:04:02.546077+00:00`.
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


## Prediction — LIVE Dhaka congestion floors (real Google-derived stream)

`python predict/record_live.py --live --yes  (recorder) && python predict/live_state.py --report` → `predict/results/live_floors.md`

_NOT YET PRODUCED_


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
| static | 10 | 912.7 +/- 101.0 | 547.6 +/- 60.6 | 516.8 +/- 18.7 | 1587.6 +/- 156.6 | 921087.8 +/- 122172.0 | 257.9 +/- 18.5 | 5932.0 +/- 110.2 | 68.0 +/- 110.2 | 76.3 +/- 93.3 | 18.6 |
| reactive | 10 | 1172.8 +/- 118.6 | 720.5 +/- 79.0 | 582.4 +/- 78.5 | 1901.9 +/- 537.8 | 1314720.6 +/- 419545.6 | 332.0 +/- 78.0 | 5542.7 +/- 170.8 | 322.9 +/- 117.4 | 354.4 +/- 85.6 | 62.6 |
| predictive_oracle | 10 | 967.4 +/- 156.2 | 586.1 +/- 100.1 | 525.2 +/- 45.5 | 1646.3 +/- 283.1 | 1050487.3 +/- 230940.5 | 272.2 +/- 46.2 | 5803.1 +/- 197.0 | 147.2 +/- 141.0 | 194.3 +/- 125.9 | 57.1 |
| predictive_persistence | 10 | 1007.2 +/- 313.5 | 614.1 +/- 207.4 | 536.0 +/- 89.9 | 1729.2 +/- 584.8 | 1095087.1 +/- 450243.1 | 283.5 +/- 90.4 | 5773.8 +/- 391.3 | 165.3 +/- 277.5 | 195.0 +/- 196.3 | 57.2 |
| due | 10 | 725.3 +/- 230.0 | 438.5 +/- 145.0 | 399.2 +/- 64.8 | 864.8 +/- 487.3 | 503223.7 +/- 330325.0 | 162.1 +/- 64.3 | 5888.0 +/- 236.9 | 83.6 +/- 176.3 | 100.7 +/- 164.3 | 363.6 |
| predeparture_oracle_c0.05 | 3 | 903.0 +/- 51.7 | 541.8 +/- 31.0 | 517.7 +/- 10.1 | 1640.7 +/- 135.0 | 932388.3 +/- 53652.3 | 259.7 +/- 10.2 | 5943.7 +/- 51.2 | 56.3 +/- 51.2 | 108.0 +/- 61.7 | 13.1 |
| predeparture_oracle_c0.1 | 10 | 966.5 +/- 173.4 | 583.6 +/- 110.1 | 517.6 +/- 27.5 | 1628.1 +/- 207.3 | 968305.7 +/- 141684.8 | 261.7 +/- 27.4 | 5816.7 +/- 240.9 | 153.1 +/- 194.4 | 167.5 +/- 126.3 | 15.7 |
| predeparture_oracle_c0.2 | 3 | 968.6 +/- 200.1 | 588.6 +/- 131.5 | 518.1 +/- 49.0 | 1633.3 +/- 311.9 | 990767.3 +/- 281918.7 | 264.0 +/- 49.9 | 5777.7 +/- 314.4 | 160.3 +/- 208.5 | 186.0 +/- 154.4 | 13.1 |
| predeparture_oracle_c0.3 | 10 | 1176.4 +/- 280.2 | 729.5 +/- 190.0 | 617.5 +/- 130.1 | 2164.3 +/- 704.7 | 1493524.9 +/- 618646.8 | 365.4 +/- 129.8 | 5553.4 +/- 356.2 | 284.4 +/- 219.6 | 357.7 +/- 184.2 | 21.6 |
| predeparture_persistence_c0.1 | 10 | 919.1 +/- 150.1 | 554.1 +/- 98.0 | 509.3 +/- 39.1 | 1565.9 +/- 280.7 | 915180.0 +/- 193456.5 | 253.5 +/- 38.5 | 5880.0 +/- 201.9 | 100.5 +/- 142.6 | 123.9 +/- 106.1 | 27.4 |

DUE status per seed: {"due": {"11": "ok", "12": "ok", "13": "ok", "14": "ok", "15": "ok", "16": "ok", "17": "ok", "18": "ok", "19": "ok", "20": "ok"}}

## Paired change vs `static` (mean % change over seeds [bootstrap 95 % CI], paired Wilcoxon p)

| arm | total_vehicle_hours | mean_travel_time_all | mean_travel_time_s | p95_travel_time_s | total_waiting_s | mean_time_loss_s | arrived | unfinished | teleports |
|---|---|---|---|---|---|---|---|---|---|
| reactive | 29.8 % [19.0, 41.2], p=0.00 | 32.9 % [21.0, 44.8], p=0.00 | 12.8 % [5.8, 23.3], p=0.00 | 20.1 % [5.1, 42.1], p=0.01 | 44.3 % [23.5, 78.1], p=0.00 | 29.2 % [14.9, 50.6], p=0.00 | -6.5 % [-8.3, -4.7], p=0.00 | 195.4 % [35.5, 393.8], p=0.00 | 5274.4 % [1496.3, 9954.3], p=0.00 |
| predictive_oracle | 8.3 % [-7.5, 23.3], p=0.56 | 9.4 % [-7.0, 25.2], p=0.49 | 1.9 % [-5.1, 8.4], p=0.56 | 5.8 % [-10.0, 20.4], p=0.77 | 17.9 % [-3.9, 37.9], p=0.32 | 6.7 % [-7.4, 19.5], p=0.49 | -2.1 % [-4.8, 0.6], p=0.23 | -94.5 % [-100.0, -86.2], p=0.38 | 4763.8 % [1174.6, 9068.9], p=0.11 |
| predictive_persistence | 13.2 % [-9.7, 39.2], p=0.77 | 15.1 % [-9.8, 44.4], p=0.77 | 4.1 % [-6.7, 16.1], p=1.00 | 10.9 % [-11.4, 36.9], p=0.92 | 23.6 % [-9.1, 59.2], p=0.49 | 11.5 % [-9.8, 36.3], p=0.70 | -2.6 % [-7.4, 1.1], p=0.55 | -83.4 % [-100.0, -46.8], p=0.55 | 4350.3 % [491.4, 8717.1], p=0.23 |
| due | -18.7 % [-35.0, 1.0], p=0.16 | -18.0 % [-34.9, 2.9], p=0.16 | -22.5 % [-30.0, -13.4], p=0.01 | -43.9 % [-61.8, -21.6], p=0.01 | -43.2 % [-65.1, -17.0], p=0.01 | -36.3 % [-51.2, -18.9], p=0.01 | -0.7 % [-3.8, 1.9], p=1.00 | -100.0 % [-100.0, -100.0], p=1.00 | 1537.1 % [64.7, 4118.8], p=0.92 |
| predeparture_oracle_c0.05 | -8.0 % [-18.0, 9.8], p=0.50 | -8.0 % [-18.0, 9.8], p=0.50 | -1.3 % [-9.4, 4.3], p=1.00 | 3.2 % [-18.3, 25.9], p=0.75 | -3.5 % [-27.5, 18.1], p=0.75 | -1.8 % [-17.0, 9.2], p=1.00 | 1.8 % [-1.1, 4.1], p=0.50 | -85.0 % [-100.0, -70.0], p=0.50 | 254.2 % [-80.7, 876.9], p=0.75 |
| predeparture_oracle_c0.1 | 7.6 % [-6.4, 24.0], p=0.92 | 8.4 % [-6.3, 25.4], p=0.92 | 0.3 % [-3.5, 4.9], p=0.92 | 3.7 % [-6.7, 14.5], p=0.77 | 6.9 % [-5.2, 21.0], p=0.62 | 2.1 % [-5.6, 11.2], p=0.92 | -1.9 % [-5.0, 0.9], p=0.46 | -57.7 % [-98.5, -13.6], p=0.55 | 3005.3 % [782.6, 5826.5], p=0.23 |
| predeparture_oracle_c0.2 | 0.1 % [-25.3, 39.1], p=1.00 | 1.6 % [-25.3, 43.5], p=1.00 | -1.0 % [-17.5, 8.3], p=1.00 | 3.4 % [-31.0, 23.1], p=1.00 | 4.7 % [-44.4, 32.0], p=1.00 | 0.8 % [-31.0, 19.5], p=1.00 | -1.0 % [-9.7, 4.4], p=1.00 | -87.2 % [-100.0, -74.5], p=1.00 | 778.7 % [-88.6, 2438.5], p=1.00 |
| predeparture_oracle_c0.3 | 32.2 % [8.2, 55.9], p=0.05 | 36.8 % [10.4, 63.2], p=0.05 | 20.0 % [4.5, 36.7], p=0.06 | 39.0 % [10.0, 68.5], p=0.06 | 68.1 % [24.6, 117.9], p=0.03 | 43.6 % [13.2, 78.0], p=0.05 | -6.3 % [-10.5, -1.9], p=0.05 | 111.4 % [-84.6, 483.0], p=0.06 | 7513.5 % [2348.5, 13106.9], p=0.03 |
| predeparture_persistence_c0.1 | 2.0 % [-8.9, 15.9], p=0.85 | 2.5 % [-9.1, 17.9], p=0.85 | -1.2 % [-6.5, 4.6], p=0.56 | -0.1 % [-12.8, 12.8], p=0.85 | 1.6 % [-14.2, 18.5], p=0.92 | -0.9 % [-11.6, 10.9], p=0.70 | -0.8 % [-3.6, 1.2], p=0.84 | -37.3 % [-94.4, 36.1], p=0.84 | 1934.7 % [263.4, 4603.9], p=0.49 |

## Paired change vs `reactive` (mean % change over seeds [bootstrap 95 % CI], paired Wilcoxon p)

| arm | total_vehicle_hours | mean_travel_time_all | mean_travel_time_s | p95_travel_time_s | total_waiting_s | mean_time_loss_s | arrived | unfinished | teleports |
|---|---|---|---|---|---|---|---|---|---|
| static | -21.4 % [-28.0, -14.8], p=0.00 | -23.1 % [-29.9, -16.1], p=0.00 | -10.1 % [-16.7, -5.2], p=0.00 | -12.7 % [-23.5, -3.6], p=0.01 | -26.0 % [-36.2, -18.3], p=0.00 | -19.5 % [-28.6, -12.4], p=0.00 | 7.1 % [5.0, 9.2], p=0.00 | -80.9 % [-96.1, -59.8], p=0.00 | -79.5 % [-92.9, -64.5], p=0.00 |
| predictive_oracle | -16.4 % [-26.3, -4.1], p=0.02 | -17.3 % [-28.0, -3.8], p=0.02 | -8.5 % [-17.0, -0.5], p=0.13 | -8.2 % [-24.5, 7.5], p=0.49 | -13.9 % [-32.1, 3.5], p=0.32 | -14.5 % [-28.2, -1.0], p=0.13 | 4.8 % [1.7, 7.3], p=0.03 | -13.6 % [-79.3, 89.6], p=0.04 | -34.0 % [-66.1, 10.5], p=0.03 |
| predictive_persistence | -13.2 % [-28.6, 4.3], p=0.19 | -13.7 % [-30.2, 4.9], p=0.23 | -6.5 % [-17.6, 6.6], p=0.19 | -3.8 % [-25.8, 23.7], p=0.32 | -9.1 % [-35.6, 23.3], p=0.23 | -10.6 % [-29.9, 13.8], p=0.19 | 4.3 % [-1.3, 8.7], p=0.13 | -5.8 % [-88.0, 103.3], p=0.13 | -35.1 % [-73.1, 11.3], p=0.05 |
| due | -38.1 % [-47.8, -26.6], p=0.00 | -39.0 % [-48.8, -27.0], p=0.00 | -31.1 % [-36.4, -24.7], p=0.00 | -54.8 % [-65.1, -41.1], p=0.00 | -61.7 % [-73.6, -46.6], p=0.00 | -50.9 % [-59.7, -40.0], p=0.00 | 6.3 % [2.9, 9.4], p=0.02 | -64.4 % [-100.0, -16.5], p=0.02 | -72.6 % [-94.0, -44.7], p=0.01 |
| predeparture_oracle_c0.05 | -23.7 % [-31.2, -19.7], p=0.25 | -25.3 % [-32.5, -21.5], p=0.25 | -12.0 % [-20.8, -5.4], p=0.25 | -14.4 % [-34.4, 2.4], p=0.50 | -29.1 % [-46.0, -14.4], p=0.25 | -22.7 % [-36.0, -12.2], p=0.25 | 7.5 % [7.1, 8.2], p=0.25 | -83.9 % [-100.0, -71.7], p=0.25 | -70.1 % [-90.6, -55.7], p=0.25 |
| predeparture_oracle_c0.1 | -16.9 % [-25.8, -6.8], p=0.02 | -18.2 % [-27.7, -7.6], p=0.02 | -10.3 % [-14.9, -6.2], p=0.00 | -11.6 % [-19.7, -4.4], p=0.00 | -23.2 % [-31.5, -14.8], p=0.00 | -19.2 % [-25.8, -13.0], p=0.00 | 5.1 % [1.2, 8.7], p=0.03 | -14.4 % [-83.6, 67.8], p=0.06 | -45.9 % [-71.1, -16.3], p=0.02 |
| predeparture_oracle_c0.2 | -17.9 % [-37.3, 0.9], p=0.50 | -18.6 % [-38.5, 2.1], p=0.50 | -11.7 % [-27.8, -1.7], p=0.25 | -14.0 % [-44.6, 2.6], p=1.00 | -23.1 % [-58.6, -4.3], p=0.25 | -20.6 % [-46.8, -3.9], p=0.25 | 4.5 % [-2.1, 8.2], p=0.50 | -53.5 % [-100.0, 15.5], p=0.50 | -47.7 % [-94.5, -6.0], p=0.25 |
| predeparture_oracle_c0.3 | 1.5 % [-14.3, 18.5], p=1.00 | 2.7 % [-14.2, 21.3], p=1.00 | 6.8 % [-6.0, 20.2], p=0.43 | 17.8 % [-5.1, 39.8], p=0.23 | 18.9 % [-9.7, 50.7], p=0.28 | 12.5 % [-9.7, 36.2], p=0.43 | 0.3 % [-4.4, 4.8], p=0.92 | 58.7 % [-53.9, 227.2], p=0.77 | 21.7 % [-32.2, 92.9], p=1.00 |
| predeparture_persistence_c0.1 | -21.2 % [-28.2, -13.6], p=0.00 | -22.6 % [-29.9, -14.4], p=0.00 | -11.8 % [-17.0, -7.2], p=0.00 | -14.8 % [-25.1, -5.5], p=0.02 | -27.5 % [-37.0, -18.1], p=0.00 | -21.9 % [-29.4, -14.7], p=0.00 | 6.2 % [2.5, 9.2], p=0.01 | -43.3 % [-88.3, 19.8], p=0.05 | -62.0 % [-78.3, -43.9], p=0.00 |

Footer: n = 10 paired seeds. The two-sided paired Wilcoxon signed-rank test cannot go below p = 0.00195 with n = 10 (p = 0.25 at n = 3), so p-values here are coarse and can never reach 0.05; read the bootstrap CI (10k resamples of the seeds) and the sign consistency instead. Percent change on `teleports`/`unfinished` is undefined when the reference is 0 for a seed (that seed is dropped). total_vehicle_hours is the headline: it charges every inserted vehicle up to the horizon, so it is the only column that is commensurable when arms finish different numbers of trips.


## Routing — network-wide decision guard

`python route/decision_guard.py --horizon 7200 --reference reactive` → `route/results/decision_guard.md`

# Routing Decision Guard, Horizon 7200 s

Source: `/Users/jannatulferdouseva/thesis/route/results/arms_h7200.json`.
Reference arm: `reactive`.
Decision: **NO_SAFE_ROUTING_ACTION**.
Selected deployable arm: `none`.

Acceptance rule: minimum 3 paired seeds; total vehicle-hours, arrivals, and teleports must all improve on every paired seed.

| arm | n | accepted | mean total-vehicle-hours benefit | mean arrivals benefit | mean teleports benefit | reason |
|---|---:|---|---:|---:|---:|---|
| predictive_persistence | 10 | False | 13.2% | 4.3% | 35.1% | rejected: does not improve all required network-wide metrics on every paired seed |

Offline benchmarks, not runtime actions:

| arm | n | accepted by metrics | mean total-vehicle-hours benefit |
|---|---:|---|---:|
| due | 10 | False | 38.1% |

Upper bounds, not deployable real forecasts:

| arm | n | accepted by metrics | mean total-vehicle-hours benefit |
|---|---:|---|---:|
| predictive_oracle | 10 | False | 16.4% |

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


## Routing — demand-scale sensitivity / gridlock check (why scale 0.25 is primary)

`see file` → `route/results/gridlock_check.md`

# Demand-scale sensitivity check (static arm, seed 11, horizon 7200 s)

Question: is the non-monotonic behaviour between scale 0.20 and 0.25 caused by junction deadlock
(SUMO teleports) that `--ignore-junction-blocker` would remove?  Answer: no.

| scale | ignore-junction-blocker | inserted | arrived | unfinished | waiting to insert | mean TT s | mean time loss s | teleports | total veh-h |
|---|---|---|---|---|---|---|---|---|---|
| 0.20 | off | 4618 | 4368 | 250 | 182 | 831 | 490 | 88 | 1037 |
| 0.20 | 60 s | 4603 | 4364 | 239 | 197 | 824 | 482 | 76 | 1026 |
| 0.25 | off | 6000 | 6000 | 0 | 0 | 505 | 246 | 13 | 841 |
| 0.25 | 60 s | 6000 | 6000 | 0 | 0 | 497 | 238 | 2 | 828 |
| 0.30 | off | 6598 | 5861 | 737 | 602 | 1234 | 941 | 453 | 2425 |
| 0.30 | 60 s | 6399 | 5629 | 770 | 801 | 1216 | 921 | 576 | 2644 |

Reading: `--scale` < 1 makes SUMO drop a seed-dependent random subset of the 24,000 DUE trips, so
0.20 and 0.25 are *different trip mixes*, not nested ones; the 0.20 mix of seed 11 contains a
spillback that the 0.25 mix does not.  The junction-blocker option barely moves any number, so the
effect is spillback/trip-mix, not deadlock.  Consequence for the experiment design:

* the primary routing ladder is reported at **scale 0.25 with 10 paired seeds** (the scale-sweep
  choice, `SCALE_CHOICE.json`), where every arm sees exactly the same trip mix per seed;
* scale 0.20 (10 seeds, `route/results/scale0.2/`) is kept as a sensitivity appendix — the sign of
  the reactive arm flips between the two scales, which is itself a result: en-route rerouting
  effects in this twin are regime-dependent and dominated by spillback dynamics;
* every comparison is paired by seed; unpaired cross-scale comparisons are not meaningful.

Regenerate: `DHAKAFLOW_SUMO_EXTRA="--ignore-junction-blocker 60" python route/predictive_routing.py --arm static --seed 11 --horizon 7200 --scale <s> --out <dir>` (and without the env var).


## Routing — arms × 10 paired seeds at scale 0.20 (sensitivity appendix)

`python route/run_arms.py --scale 0.2 --seeds 11,…,20 --results route/results/scale0.2 && python route/stats.py --results route/results/scale0.2` → `route/results/scale0.2/stats.md`

# Routing arms, horizon 7200 s, paired seeds

Source: `route/results/arms_h7200.json` (run_arms.py). Values are mean +/- sd over seeds.

| arm | n | total_vehicle_hours | mean_travel_time_all | mean_travel_time_s | p95_travel_time_s | total_waiting_s | mean_time_loss_s | arrived | unfinished | teleports | wall s/run |
|---|---|---|---|---|---|---|---|---|---|---|---|
| static | 10 | 1042.4 +/- 24.5 | 824.9 +/- 18.4 | 847.5 +/- 17.7 | 1777.4 +/- 130.7 | 1085799.4 +/- 46178.3 | 507.4 +/- 18.0 | 4290.8 +/- 48.5 | 258.0 +/- 29.4 | 95.8 +/- 13.6 | 17.1 |
| reactive | 10 | 963.6 +/- 23.7 | 814.1 +/- 27.0 | 837.2 +/- 28.4 | 1807.8 +/- 193.7 | 1045302.3 +/- 75173.8 | 520.1 +/- 27.6 | 4084.6 +/- 127.1 | 179.4 +/- 15.0 | 21.1 +/- 8.2 | 43.8 |
| predictive_oracle | 10 | 1268.3 +/- 32.3 | 955.8 +/- 17.2 | 963.8 +/- 15.8 | 2161.4 +/- 135.7 | 1748082.8 +/- 75097.4 | 645.3 +/- 16.7 | 4682.1 +/- 113.9 | 94.7 +/- 70.6 | 109.5 +/- 28.3 | 45.3 |
| predictive_persistence | 10 | 1248.7 +/- 34.3 | 945.9 +/- 33.6 | 954.7 +/- 37.9 | 2184.7 +/- 154.1 | 1674093.3 +/- 109482.0 | 635.9 +/- 37.6 | 4656.1 +/- 155.2 | 97.9 +/- 95.1 | 88.5 +/- 19.0 | 42.6 |
| due | 10 | 859.4 +/- 99.3 | 694.5 +/- 53.5 | 709.4 +/- 54.9 | 1502.6 +/- 293.3 | 773056.3 +/- 223775.2 | 418.3 +/- 50.4 | 4211.2 +/- 308.4 | 237.8 +/- 42.3 | 52.0 +/- 38.4 | 219.1 |
| predeparture_oracle_c0.1 | 10 | 1082.1 +/- 17.5 | 824.3 +/- 16.8 | 843.5 +/- 17.4 | 1793.0 +/- 166.4 | 1150349.6 +/- 43180.8 | 511.6 +/- 16.9 | 4449.3 +/- 47.7 | 277.5 +/- 12.3 | 80.2 +/- 14.5 | 14.4 |
| predeparture_oracle_c0.3 | 10 | 1169.7 +/- 26.6 | 877.3 +/- 20.0 | 879.4 +/- 19.7 | 1795.1 +/- 126.7 | 1395984.9 +/- 88155.3 | 564.8 +/- 19.1 | 4765.8 +/- 43.6 | 34.2 +/- 43.6 | 71.6 +/- 19.6 | 15.5 |
| predeparture_persistence_c0.1 | 10 | 1077.1 +/- 15.5 | 818.3 +/- 14.1 | 837.7 +/- 15.8 | 1755.5 +/- 118.2 | 1128997.7 +/- 45885.9 | 505.8 +/- 15.6 | 4467.1 +/- 27.8 | 271.9 +/- 11.6 | 78.3 +/- 5.9 | 13.3 |

DUE status per seed: {"due": {"11": "ok", "12": "ok", "13": "ok", "14": "ok", "15": "ok", "16": "partial(-15)", "17": "partial(-15)", "18": "ok", "19": "ok", "20": "partial(-15)"}}

## Paired change vs `static` (mean % change over seeds [bootstrap 95 % CI], paired Wilcoxon p)

| arm | total_vehicle_hours | mean_travel_time_all | mean_travel_time_s | p95_travel_time_s | total_waiting_s | mean_time_loss_s | arrived | unfinished | teleports |
|---|---|---|---|---|---|---|---|---|---|
| reactive | -7.5 % [-9.3, -5.9], p=0.00 | -1.3 % [-3.6, 1.1], p=0.43 | -1.2 % [-3.6, 1.3], p=0.49 | 2.2 % [-5.2, 10.2], p=0.70 | -3.5 % [-8.5, 1.3], p=0.19 | 2.6 % [-1.3, 6.6], p=0.32 | -4.8 % [-6.5, -2.9], p=0.00 | -29.7 % [-35.2, -23.5], p=0.00 | -77.3 % [-82.9, -71.3], p=0.00 |
| predictive_oracle | 21.7 % [19.5, 23.9], p=0.00 | 15.9 % [14.5, 17.3], p=0.00 | 13.7 % [12.7, 14.7], p=0.00 | 22.1 % [15.9, 27.7], p=0.00 | 61.1 % [57.1, 65.3], p=0.00 | 27.2 % [25.4, 29.0], p=0.00 | 9.1 % [7.3, 10.8], p=0.00 | -63.7 % [-79.0, -47.9], p=0.00 | 17.9 % [-4.5, 41.2], p=0.32 |
| predictive_persistence | 19.8 % [18.0, 21.7], p=0.00 | 14.7 % [12.4, 17.2], p=0.00 | 12.7 % [10.1, 15.4], p=0.00 | 23.3 % [17.4, 29.0], p=0.00 | 54.2 % [50.2, 58.7], p=0.00 | 25.4 % [21.1, 30.2], p=0.00 | 8.5 % [6.3, 10.6], p=0.00 | -60.0 % [-82.6, -36.5], p=0.00 | -4.8 % [-21.3, 14.7], p=0.39 |
| due | -17.6 % [-23.0, -12.7], p=0.00 | -15.9 % [-19.2, -12.8], p=0.00 | -16.3 % [-19.6, -13.3], p=0.00 | -15.7 % [-23.8, -9.0], p=0.00 | -29.1 % [-40.5, -18.0], p=0.00 | -17.7 % [-22.7, -13.1], p=0.00 | -1.9 % [-6.4, 1.7], p=0.92 | -7.0 % [-17.9, 3.3], p=0.38 | -46.1 % [-67.4, -22.2], p=0.01 |
| predeparture_oracle_c0.1 | 3.9 % [2.2, 5.2], p=0.01 | -0.0 % [-1.7, 1.5], p=0.77 | -0.4 % [-2.0, 1.0], p=0.62 | 1.3 % [-5.2, 8.3], p=0.94 | 6.1 % [2.9, 9.1], p=0.01 | 0.9 % [-1.7, 3.3], p=0.70 | 3.7 % [2.7, 4.7], p=0.00 | 8.6 % [1.1, 14.5], p=0.08 | -15.8 % [-23.8, -9.5], p=0.00 |
| predeparture_oracle_c0.3 | 12.2 % [10.7, 13.8], p=0.00 | 6.4 % [4.7, 7.8], p=0.00 | 3.8 % [2.1, 5.3], p=0.01 | 1.2 % [-2.9, 5.2], p=0.56 | 28.7 % [24.0, 33.1], p=0.00 | 11.4 % [8.5, 13.9], p=0.00 | 11.1 % [10.1, 12.1], p=0.00 | -86.5 % [-95.7, -75.4], p=0.00 | -24.6 % [-36.3, -13.7], p=0.01 |
| predeparture_persistence_c0.1 | 3.4 % [1.7, 5.1], p=0.01 | -0.8 % [-2.4, 0.8], p=0.49 | -1.1 % [-2.7, 0.5], p=0.16 | -0.7 % [-6.9, 5.3], p=0.92 | 4.1 % [0.7, 7.9], p=0.08 | -0.2 % [-2.8, 2.4], p=0.85 | 4.1 % [3.5, 4.7], p=0.00 | 6.4 % [-0.2, 12.2], p=0.08 | -17.0 % [-23.1, -9.6], p=0.01 |

## Paired change vs `reactive` (mean % change over seeds [bootstrap 95 % CI], paired Wilcoxon p)

| arm | total_vehicle_hours | mean_travel_time_all | mean_travel_time_s | p95_travel_time_s | total_waiting_s | mean_time_loss_s | arrived | unfinished | teleports |
|---|---|---|---|---|---|---|---|---|---|
| static | 8.2 % [6.4, 10.4], p=0.00 | 1.4 % [-1.0, 3.9], p=0.43 | 1.3 % [-1.1, 3.8], p=0.49 | -0.7 % [-8.0, 6.6], p=0.70 | 4.4 % [-0.9, 9.6], p=0.19 | -2.2 % [-5.9, 1.5], p=0.32 | 5.1 % [3.2, 6.9], p=0.00 | 44.8 % [33.2, 56.8], p=0.00 | 430.6 % [293.7, 583.1], p=0.00 |
| predictive_oracle | 31.7 % [28.5, 34.9], p=0.00 | 17.5 % [14.9, 20.3], p=0.00 | 15.2 % [12.8, 17.8], p=0.00 | 20.7 % [12.5, 29.4], p=0.00 | 68.1 % [59.5, 77.5], p=0.00 | 24.4 % [20.1, 28.6], p=0.00 | 14.7 % [12.5, 16.7], p=0.00 | -47.4 % [-70.3, -22.4], p=0.01 | 499.1 % [340.7, 677.8], p=0.00 |
| predictive_persistence | 29.7 % [26.7, 32.6], p=0.00 | 16.3 % [12.9, 19.5], p=0.00 | 14.1 % [10.6, 17.3], p=0.00 | 22.1 % [12.7, 30.2], p=0.01 | 61.1 % [50.9, 70.7], p=0.00 | 22.5 % [16.9, 27.7], p=0.00 | 14.1 % [11.7, 16.6], p=0.00 | -47.9 % [-76.2, -18.7], p=0.02 | 387.4 % [261.2, 516.9], p=0.00 |
| due | -10.8 % [-16.8, -5.2], p=0.01 | -14.6 % [-19.0, -9.8], p=0.00 | -15.1 % [-19.6, -10.5], p=0.00 | -16.3 % [-26.1, -5.0], p=0.02 | -25.7 % [-38.5, -12.2], p=0.01 | -19.3 % [-26.0, -12.6], p=0.00 | 3.1 % [-1.5, 7.3], p=0.13 | 33.1 % [18.7, 46.8], p=0.01 | 153.8 % [67.6, 253.7], p=0.02 |
| predeparture_oracle_c0.1 | 12.3 % [10.9, 13.8], p=0.00 | 1.4 % [-1.2, 4.2], p=0.56 | 0.9 % [-1.7, 3.7], p=0.62 | 0.3 % [-8.3, 10.0], p=0.92 | 10.6 % [5.2, 16.1], p=0.01 | -1.3 % [-5.4, 3.2], p=0.32 | 9.0 % [6.7, 10.9], p=0.00 | 55.8 % [46.5, 65.2], p=0.00 | 350.9 % [226.1, 499.4], p=0.00 |
| predeparture_oracle_c0.3 | 21.4 % [19.5, 23.3], p=0.00 | 7.8 % [5.7, 9.8], p=0.00 | 5.1 % [3.3, 7.0], p=0.00 | -0.0 % [-5.5, 5.2], p=0.95 | 34.0 % [27.9, 39.5], p=0.00 | 8.8 % [5.8, 11.8], p=0.00 | 16.8 % [14.6, 18.5], p=0.00 | -81.2 % [-93.9, -66.0], p=0.00 | 297.8 % [184.9, 436.3], p=0.00 |
| predeparture_persistence_c0.1 | 11.8 % [10.0, 13.7], p=0.00 | 0.6 % [-1.6, 3.0], p=0.56 | 0.2 % [-2.3, 2.6], p=0.92 | -2.0 % [-8.6, 4.9], p=0.49 | 8.5 % [3.5, 13.6], p=0.01 | -2.5 % [-6.3, 1.3], p=0.13 | 9.5 % [7.2, 11.3], p=0.00 | 52.5 % [44.8, 60.3], p=0.00 | 328.3 % [231.0, 437.5], p=0.00 |

Footer: n = 10 paired seeds. The two-sided paired Wilcoxon signed-rank test cannot go below p = 0.00195 with n = 10 (p = 0.25 at n = 3), so p-values here are coarse and can never reach 0.05; read the bootstrap CI (10k resamples of the seeds) and the sign consistency instead. Percent change on `teleports`/`unfinished` is undefined when the reference is 0 for a seed (that seed is dropped). total_vehicle_hours is the headline: it charges every inserted vehicle up to the horizon, so it is the only column that is commensurable when arms finish different numbers of trips.


## Routing — NLP incident scenario at scale 0.20 incl. pre-departure arms

`python route/incident_scenario.py --scale 0.2 --results route/results/scale0.2` → `route/results/scale0.2/incident.md`

# NLP incident scenario — Dhaka R1, 3 paired seeds

Event: "Bus and CNG collision at Karwan Bazar signal, road blocked" → label `incident` (p=0.9975), place Karwan Bazar, 8 edges, factor ×10.0. Incident at t=900s for 1800s, speed limit 1.5 m/s; report delay 120s; compliance 0.3; demand scale 0.2; horizon 5400s.

| arm | total_vehicle_hours | mean_travel_time_all | p95_travel_time_s | affected_mean_travel_time_s | arrived | unfinished | teleports |
|---|---|---|---|---|---|---|---|
| uninformed | 893.1 ± 9.6 | 825.6 ± 14.4 | 1943.0 ± 106.0 | 1264.1 ± 34.2 | 3199.0 ± 42.6 | 695.7 ± 21.6 | 89.7 ± 12.4 |
| reactive | 897.7 ± 18.8 | 872.2 ± 12.8 | 1917.3 ± 22.5 | 1198.2 ± 38.8 | 3095.7 ± 104.1 | 611.3 ± 31.0 | 30.0 ± 13.6 |
| nlp_informed | 954.2 ± 39.6 | 939.0 ± 34.1 | 2340.7 ± 180.7 | 1415.1 ± 114.1 | 2951.3 ± 56.0 | 706.3 ± 78.8 | 81.3 ± 22.9 |
| reactive_plus_nlp | 939.2 ± 15.9 | 904.3 ± 26.1 | 2118.3 ± 119.7 | 1265.4 ± 27.7 | 3018.3 ± 79.2 | 722.0 ± 48.4 | 86.7 ± 32.8 |
| reactive_predeparture | 880.8 ± 25.7 | 849.3 ± 23.3 | 1802.3 ± 83.2 | 1203.0 ± 48.8 | 3110.7 ± 73.1 | 623.3 ± 31.5 | 15.0 ± 7.1 |
| nlp_predeparture | 903.4 ± 14.2 | 848.6 ± 15.0 | 1858.0 ± 51.2 | 1222.6 ± 26.8 | 3203.7 ± 28.4 | 629.0 ± 18.2 | 69.7 ± 7.3 |

## Paired % change vs uninformed (mean over seeds [bootstrap 95 % CI]; sign count = seeds improved)

| arm | total_vehicle_hours | mean_travel_time_all | p95_travel_time_s | affected_mean_travel_time_s | arrived | unfinished | teleports |
|---|---|---|---|---|---|---|---|
| reactive | +0.5 % [-0.9, +1.9] 1/3 | +5.7 % [+1.1, +8.8] 0/3 | -1.0 % [-9.8, +4.7] 1/3 | -5.2 % [-8.5, -2.1] 3/3 | -3.2 % [-7.5, +3.2] 1/3 | -12.1 % [-18.6, -8.1] 3/3 | -65.5 % [-83.0, -43.7] 3/3 |
| nlp_informed | +6.8 % [+2.0, +10.1] 0/3 | +13.7 % [+9.5, +16.7] 0/3 | +20.4 % [+14.7, +23.5] 0/3 | +11.8 % [+3.0, +17.4] 0/3 | -7.7 % [-8.2, -6.8] 0/3 | +1.3 % [-6.8, +13.1] 2/3 | -5.8 % [-49.1, +26.4] 1/3 |
| reactive_plus_nlp | +5.2 % [+4.2, +5.9] 0/3 | +9.5 % [+6.9, +11.1] 0/3 | +9.3 % [+0.3, +20.8] 0/3 | +0.1 % [-0.9, +1.0] 1/3 | -5.7 % [-7.4, -4.5] 0/3 | +3.8 % [-5.0, +9.6] 1/3 | -4.8 % [-44.7, +37.9] 2/3 |
| reactive_predeparture | -1.4 % [-3.6, +3.0] 2/3 | +2.9 % [+0.2, +6.0] 0/3 | -7.0 % [-13.4, +0.8] 2/3 | -4.8 % [-8.4, +0.7] 2/3 | -2.8 % [-4.2, -1.9] 0/3 | -10.4 % [-13.4, -5.8] 3/3 | -84.0 % [-88.2, -76.4] 3/3 |
| nlp_predeparture | +1.2 % [-2.0, +3.7] 1/3 | +2.8 % [-1.3, +6.6] 1/3 | -4.0 % [-14.5, +1.4] 1/3 | -3.2 % [-8.4, +0.3] 2/3 | +0.2 % [-1.7, +2.5] 1/3 | -9.5 % [-14.8, -6.6] 3/3 | -20.7 % [-39.6, -8.0] 3/3 |

`affected_*` = vehicles whose initial route ran through an incident edge. `arrived`: higher is better; all other columns: lower is better.
Regenerate: `python route/incident_scenario.py --seeds 11,12,13`.


## Prediction — Dhaka twin models (official BasicTS-legacy baselines; Colab results replace the local file)

`notebooks/Predict_Twin_Colab.ipynb (Colab GPU) -> rclone copy gdrive2tb:dhakaflow/predict/results/twin_models predict/results/twin_models` → `predict/results/twin_models.md`

# Dhaka twin forecasting — official BasicTS baselines trained locally on CPU

Dataset `predict/data/dhaka_twin` (DHAKA_SIMULATED_SENSOR_GRAPH, data.dat sha `bd02b9dba7311663`), target speed m/s, chronological 70/10/20 split, official configs (PEMS04 template → DhakaR1, CPU), harness BasicTS-legacy @4c3e2d3, NULL_VAL=0 masking.

| model | MAE@15 | RMSE@15 | MAE@30 | RMSE@30 | MAE@60 | RMSE@60 | epochs | wall s |
|---|---|---|---|---|---|---|---|---|
| STID | 0.610 | 0.998 | 0.817 | 1.250 | 0.987 | 1.476 | official | 236.0 |

Floors from `predict/results/twin_floors.md` (same split). Predictions for every test window are in `<model>_test_results.npz`.
Regenerate: `python predict/train_twin_local.py --models STID`.


## Routing — forecast model in the loop (pre-departure route choice on the twin test window)

`python route/model_in_loop.py --model STID --horizons 15,60 --compliance 0.1,0.3` → `route/results/model_in_loop_STID.md`

_NOT YET PRODUCED_


## Live chain — Dhaka live congestion to an ACT / NO_ACTION routing decision

`python route/live_chain.py --seeds 11,12,13` → `route/results/live_chain.md`

# Live chain — Dhaka live congestion to a routing decision

Generated 2026-09-01T16:21:54.268268+00:00. Source: **SYNTHETIC_WHAT_IF**. Network: real Dhaka R1. Demand: DHAKA_SIMULATED_DEMAND (live feed supplies congestion state, never demand). 53 edges congested above free flow; compliance 30%; scale 0.25; horizon 1800s.

| corridor | level | multiplier | edges |
|---|---|---|---|
| farmgate_to_shahbagh | 2.00 | x1.75 | 46 |
| karwanbazar_to_banglamotor | 3.00 | x2.50 | 21 |
| karwanbazar_to_shahbagh | 3.00 | x2.50 | 36 |

| arm | seed | total veh-h | arrived | teleports | routes changed |
|---|---|---|---|---|---|
| unaware | 11 | 213.0 | 1703 | 0 | 0 |
| advised | 11 | 217.2 | 1651 | 15 | 2152 |
| unaware | 12 | 215.0 | 1685 | 0 | 0 |
| advised | 12 | 207.9 | 1676 | 10 | 2152 |
| unaware | 13 | 213.2 | 1702 | 4 | 0 |
| advised | 13 | 221.2 | 1627 | 13 | 2152 |

Per-seed vehicle-hour change: [2.0, -3.31, 3.72] (mean 0.81 %).

## Decision: **NO_ACTION**

vehicle-hours improved on only 1/3 seeds; arrivals fall on average (-45.3); teleports rise on average (+11.3)

Rule: ACT iff total vehicle-hours improves on EVERY paired seed and mean arrivals do not fall and mean teleports do not rise

Regenerate: `python route/live_chain.py --seeds 11,12,13`.


## Live chain — advised-share sweep under a labelled congested what-if

`python route/live_chain.py --compliance 0.05 --tag _c0.05 --levels ...` → `route/results/live_chain_c0.05.md`

# Live chain — Dhaka live congestion to a routing decision

Generated 2026-09-01T16:22:38.646120+00:00. Source: **SYNTHETIC_WHAT_IF**. Network: real Dhaka R1. Demand: DHAKA_SIMULATED_DEMAND (live feed supplies congestion state, never demand). 53 edges congested above free flow; compliance 5%; scale 0.25; horizon 1800s.

| corridor | level | multiplier | edges |
|---|---|---|---|
| farmgate_to_shahbagh | 2.00 | x1.75 | 46 |
| karwanbazar_to_banglamotor | 3.00 | x2.50 | 21 |
| karwanbazar_to_shahbagh | 3.00 | x2.50 | 36 |

| arm | seed | total veh-h | arrived | teleports | routes changed |
|---|---|---|---|---|---|
| unaware | 11 | 213.0 | 1703 | 0 | 0 |
| advised | 11 | 208.5 | 1723 | 0 | 356 |
| unaware | 12 | 215.0 | 1685 | 0 | 0 |
| advised | 12 | 212.2 | 1703 | 1 | 356 |
| unaware | 13 | 213.2 | 1702 | 4 | 0 |
| advised | 13 | 209.1 | 1736 | 0 | 356 |

Per-seed vehicle-hour change: [-2.07, -1.28, -1.96] (mean -1.77 %).

## Decision: **ACT**

advised improves total vehicle-hours on every paired seed without cost to arrivals or teleports

Rule: ACT iff total vehicle-hours improves on EVERY paired seed and mean arrivals do not fall and mean teleports do not rise

Regenerate: `python route/live_chain.py --seeds 11,12,13`.


## Routing — NLP incident scenario (text → reroute → measured delay)

`python route/incident_scenario.py --seeds 11,12,13` → `route/results/incident.md`

# NLP incident scenario — Dhaka R1, 3 paired seeds

Event: "Bus and CNG collision at Karwan Bazar signal, road blocked" → label `incident` (p=0.9975), place Karwan Bazar, 8 edges, factor ×10.0. Incident at t=900s for 1800s, speed limit 1.5 m/s; report delay 120s; compliance 0.3; demand scale 0.25; horizon 5400s.

| arm | total_vehicle_hours | mean_travel_time_all | p95_travel_time_s | affected_mean_travel_time_s | arrived | unfinished | teleports |
|---|---|---|---|---|---|---|---|
| uninformed | 898.9 ± 43.9 | 539.9 ± 27.1 | 1253.7 ± 112.2 | 988.6 ± 50.5 | 5644.3 ± 107.1 | 350.0 ± 100.0 | 80.0 ± 40.2 |
| reactive | 1069.5 ± 86.9 | 670.1 ± 64.3 | 1510.3 ± 288.3 | 877.6 ± 102.1 | 5032.3 ± 268.8 | 722.7 ± 154.2 | 252.7 ± 67.1 |
| nlp_informed | 1042.3 ± 102.8 | 650.5 ± 75.1 | 1296.7 ± 212.0 | 876.1 ± 50.8 | 4995.0 ± 264.3 | 784.0 ± 171.1 | 226.3 ± 49.3 |
| reactive_plus_nlp | 996.0 ± 71.4 | 611.3 ± 52.3 | 1474.0 ± 179.7 | 922.8 ± 27.0 | 5279.3 ± 223.9 | 592.7 ± 139.2 | 199.7 ± 62.6 |

## Paired % change vs uninformed (mean over seeds [bootstrap 95 % CI]; sign count = seeds improved)

| arm | total_vehicle_hours | mean_travel_time_all | p95_travel_time_s | affected_mean_travel_time_s | arrived | unfinished | teleports |
|---|---|---|---|---|---|---|---|
| reactive | +18.9 % [+11.5, +25.6] 0/3 | +24.0 % [+13.7, +34.9] 0/3 | +20.1 % [-3.5, +35.5] 1/3 | -11.4 % [-22.6, -5.7] 3/3 | -10.9 % [-16.4, -6.8] 0/3 | +112.9 % [+68.1, +148.7] 0/3 | +264.6 % [+131.8, +364.7] 0/3 |
| nlp_informed | +15.7 % [+10.5, +24.1] 0/3 | +20.1 % [+14.2, +31.4] 0/3 | +3.2 % [-13.8, +13.1] 1/3 | -11.3 % [-16.5, -4.9] 3/3 | -11.6 % [-16.0, -9.1] 0/3 | +130.9 % [+100.9, +176.0] 0/3 | +246.9 % [+124.2, +452.9] 0/3 |
| reactive_plus_nlp | +11.4 % [-1.1, +29.1] 1/3 | +13.9 % [-1.0, +34.4] 1/3 | +19.2 % [+1.9, +51.6] 0/3 | -6.4 % [-11.9, +0.9] 2/3 | -6.4 % [-13.0, +1.1] 1/3 | +97.1 % [-13.9, +224.9] 1/3 | +289.5 % [-10.6, +694.1] 1/3 |

`affected_*` = vehicles whose initial route ran through an incident edge. `arrived`: higher is better; all other columns: lower is better.
Regenerate: `python route/incident_scenario.py --seeds 11,12,13`.


## Routing — value of early incident detection (report-delay sweep)

`python route/incident_scenario.py --seeds 11 --report-delays 60,300,900` → `route/results/incident_delay_sweep.md`

# Value of early detection — nlp_informed arm, seed 11

| report delay s | total_vehicle_hours | Δ vs uninformed | affected mean TT s | Δ affected | arrived | teleports |
|---|---|---|---|---|---|---|
| (uninformed) | 890.8 | – | 966.1 | – | 5653 | 74 |
| 60 | 1012.4 | +13.6 % | 737.1 | -23.7 % | 4983 | 232 |
| 120 | 984.2 | +10.5 % | 806.8 | -16.5 % | 5108 | 195 |
| 300 | 895.1 | +0.5 % | 735.6 | -23.9 % | 5463 | 119 |
| 900 | 970.0 | +8.9 % | 848.2 | -12.2 % | 5212 | 165 |


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


## Networking — V2X advisory from our NLP / predicted event (Eclipse MOSAIC)

`python network/event_sweep.py --source nlp_event --p 0.25` → `network/results/event_sweep.md`

# V2X advisory from OUR event (NLP report / forecast) — Eclipse MOSAIC 25.2, Dhaka R1

Hazard rectangle = bounding box of the event edges; the event is physically real in SUMO (variableSpeedSign). Same official WeatherWarningApp/NavigationModule chain as the penetration sweep; only WHERE/WHEN the hazard is comes from us.

| source | p | seed | wall_s | registered | equipped | senders | receivers | delivery_ratio_veh | route_switches | switch_fraction_of_equipped | finished.n | finished.duration_mean_s | finished.duration_p95_s | finished.timeLoss_mean_s | finished_equipped.duration_mean_s | finished_unequipped.duration_mean_s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| nlp_event | 0.25 | 11 | 60 | 2564 | 628 | 111 | 628 | 1 | 170 | 0.271 | 1045 | 391 | 664 | 161 | 391 | 390 |
| nlp_event | 0 | 11 | 25 | 2555 | 0 | 0 | 0 |  | 0 |  | 1022 | 387 | 644 | 158 |  | 387 |
| nlp_event | 1 | 11 | 953 | 2651 | 2651 | 427 | 2648 | 0.999 | 818 | 0.309 | 1027 | 384 | 621 | 156 | 384 |  |
| predicted | 0.25 | 11 | 368 | 2619 | 642 | 504 | 642 | 1 | 546 | 0.85 | 903 | 416 | 658 | 206 | 400 | 421 |

* NLP: "Bus and CNG collision at Karwan Bazar signal, road blocked" -> incident @ Karwan Bazar
* predicted: top-8 traveltime/free-flow edges of route/results/static_s11_h7200/edgedata.xml at t=200s

Regenerate: `python network/event_sweep.py --source nlp_event --p <P> --seed <S>`; `--aggregate` rebuilds this table.


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
