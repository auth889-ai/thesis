# Learned-model outcome gate — FINAL_LEARNED_PROTOCOL_v1 (final seeds, n = 20)

**Verdict (Graph WaveNet vs baseline, total vehicle-hours): INCONCLUSIVE** — mean -0.05 %, median -0.02 %, 95 % CI [-0.24, 0.14], wins/losses/ties 11/9/0.

**Outcome class:** C: forecast/control benefit not established

Graph WaveNet vs persistence-predictive: -0.08 %, CI [-0.19, 0.02], 5/2/13, **INCONCLUSIVE**. Persistence-predictive vs baseline: +0.03 %, CI [-0.15, 0.21], **INCONCLUSIVE**.

## Frozen protocol

- city_id: `los_angeles_metr`
- network_hash: `3a55f46d9693`
- dataset: `user:los_angeles`
- dataset_hash: `0fc9c01d475c0124`
- mapping_hash: `f1c599a4366c`
- mapping_counts: `{'GOOD': 8, 'WEAK': 0, 'REJECTED': 12}`
- model: `GWNet`
- checkpoint: `GraphWaveNet_best_val_MAE.pt`
- checkpoint_sha256: `dd74c775ac07`
- held_out_skill: `0.2844`
- routing_config_hash: `ea08dddedc14`
- coverage_hops: `1`
- min_saving_s: `60.0`
- min_saving_pct: `5.0`
- demand_method: `SUMO randomTrips.py with the scenario's osmWebWizard passenger options, one draw per seed (--seed <seed>), departures 0-1800 s; SUMO --scale 1`
- calibration_method: `the eight mapped detectors' MEASURED speeds from the dataset moment onward are replayed every 300 s as lane speed caps (min(limit, measured)) on their mapped edges, identically in every arm`
- simulation_duration_s: `2700`
- routing_round_s: `900`
- round_horizons_min: `[10, 25, 40]`
- compliance: `0.3`
- forecast_moments: `dataset index as_of = test_start + 12 + (seed * 97) mod (test_len - 24): one held-out moment per seed; the model sees only the 12 steps before it`
- sumo_version: `Eclipse SUMO sumo 1.27.1`
- dev_seeds: `[101, 102, 103]`
- final_seeds: `[301, 302, 303, 304, 305, 306, 307, 308, 309, 310, 311, 312, 313, 314, 315, 316, 317, 318, 319, 320]`

## Paired statistics (first arm relative to second; negative = fewer vehicle-hours / less time)

| pair | metric | n | mean % | median % | 95 % CI | wins/losses/ties | label |
|---|---|---|---|---|---|---|---|
| learned_predictive vs baseline | total_vehicle_hours_incl_never_inserted | 20 | -0.05 | -0.02 | [-0.24, 0.14] | 11/9/0 | **INCONCLUSIVE** |
| learned_predictive vs baseline | mean_travel_time_all | 20 | -0.05 | -0.02 | [-0.24, 0.14] | 11/9/0 | **INCONCLUSIVE** |
| learned_predictive vs baseline | p95_travel_time_s | 20 | -0.33 | -0.28 | [-0.91, 0.25] | 12/7/1 | **INCONCLUSIVE** |
| learned_predictive vs baseline | total_waiting_s | 20 | 0.05 | 0.31 | [-0.52, 0.62] | 8/12/0 | **INCONCLUSIVE** |
| learned_predictive vs baseline | mean_queue_veh | 20 | -0.46 | 0.35 | [-1.63, 0.7] | 8/12/0 | **INCONCLUSIVE** |
| learned_predictive vs baseline | arrived | 20 | -0.02 | 0.0 | [-0.05, 0.01] | 1/3/16 | **INCONCLUSIVE** |
| learned_predictive vs baseline | teleports | 10 | -10.0 | 0.0 | [-25.08, 5.08] | 2/0/8 | **INCONCLUSIVE** |
| learned_predictive vs baseline | top_edge_flow_concentration | 20 | -0.34 | 0.0 | [-0.82, 0.14] | 3/3/14 | **INCONCLUSIVE** |
| learned_predictive vs reactive | total_vehicle_hours_incl_never_inserted | 20 | 0.11 | 0.12 | [-0.11, 0.33] | 6/14/0 | **INCONCLUSIVE** |
| learned_predictive vs reactive | mean_travel_time_all | 20 | 0.11 | 0.12 | [-0.11, 0.33] | 6/14/0 | **INCONCLUSIVE** |
| learned_predictive vs reactive | p95_travel_time_s | 20 | -0.03 | 0.14 | [-0.61, 0.55] | 9/10/1 | **INCONCLUSIVE** |
| learned_predictive vs reactive | total_waiting_s | 20 | 0.34 | 0.54 | [-0.34, 1.03] | 6/14/0 | **INCONCLUSIVE** |
| learned_predictive vs reactive | mean_queue_veh | 20 | -0.32 | -0.03 | [-1.59, 0.95] | 10/10/0 | **INCONCLUSIVE** |
| learned_predictive vs reactive | arrived | 20 | -0.02 | 0.0 | [-0.05, 0.01] | 1/3/16 | **INCONCLUSIVE** |
| learned_predictive vs reactive | teleports | 10 | -6.67 | 0.0 | [-21.75, 8.41] | 1/0/9 | **INCONCLUSIVE** |
| learned_predictive vs reactive | top_edge_flow_concentration | 20 | 0.37 | 0.0 | [-0.35, 1.09] | 4/7/9 | **INCONCLUSIVE** |
| learned_predictive vs persistence_predictive | total_vehicle_hours_incl_never_inserted | 20 | -0.08 | 0.0 | [-0.19, 0.02] | 5/2/13 | **INCONCLUSIVE** |
| learned_predictive vs persistence_predictive | mean_travel_time_all | 20 | -0.08 | 0.0 | [-0.19, 0.02] | 5/2/13 | **INCONCLUSIVE** |
| learned_predictive vs persistence_predictive | p95_travel_time_s | 20 | -0.26 | 0.0 | [-0.72, 0.19] | 5/2/13 | **INCONCLUSIVE** |
| learned_predictive vs persistence_predictive | total_waiting_s | 20 | -0.21 | 0.0 | [-0.55, 0.13] | 3/4/13 | **INCONCLUSIVE** |
| learned_predictive vs persistence_predictive | mean_queue_veh | 20 | -0.35 | 0.0 | [-0.76, 0.05] | 4/3/13 | **INCONCLUSIVE** |
| learned_predictive vs persistence_predictive | arrived | 20 | 0.01 | 0.0 | [-0.01, 0.03] | 1/0/19 | **INCONCLUSIVE** |
| learned_predictive vs persistence_predictive | teleports | 12 | 0.0 | 0.0 | [0.0, 0.0] | 0/0/12 | **INCONCLUSIVE** |
| learned_predictive vs persistence_predictive | top_edge_flow_concentration | 20 | 1.02 | 0.0 | [-0.16, 2.2] | 1/3/16 | **INCONCLUSIVE** |
| persistence_predictive vs baseline | total_vehicle_hours_incl_never_inserted | 20 | 0.03 | 0.06 | [-0.15, 0.21] | 10/10/0 | **INCONCLUSIVE** |
| persistence_predictive vs baseline | mean_travel_time_all | 20 | 0.03 | 0.06 | [-0.15, 0.21] | 10/10/0 | **INCONCLUSIVE** |
| persistence_predictive vs baseline | p95_travel_time_s | 20 | -0.06 | -0.28 | [-0.62, 0.5] | 12/7/1 | **INCONCLUSIVE** |
| persistence_predictive vs baseline | total_waiting_s | 20 | 0.27 | 0.41 | [-0.35, 0.89] | 8/12/0 | **INCONCLUSIVE** |
| persistence_predictive vs baseline | mean_queue_veh | 20 | -0.09 | 0.23 | [-1.45, 1.26] | 9/11/0 | **INCONCLUSIVE** |
| persistence_predictive vs baseline | arrived | 20 | -0.03 | 0.0 | [-0.06, 0.01] | 1/4/15 | **INCONCLUSIVE** |
| persistence_predictive vs baseline | teleports | 10 | -10.0 | 0.0 | [-25.08, 5.08] | 2/0/8 | **INCONCLUSIVE** |
| persistence_predictive vs baseline | top_edge_flow_concentration | 20 | -1.26 | 0.0 | [-2.75, 0.23] | 3/4/13 | **INCONCLUSIVE** |
| reactive vs baseline | total_vehicle_hours_incl_never_inserted | 20 | -0.16 | -0.16 | [-0.4, 0.08] | 12/8/0 | **INCONCLUSIVE** |
| reactive vs baseline | mean_travel_time_all | 20 | -0.16 | -0.16 | [-0.4, 0.08] | 12/8/0 | **INCONCLUSIVE** |
| reactive vs baseline | p95_travel_time_s | 20 | -0.3 | -0.07 | [-0.76, 0.17] | 10/7/3 | **INCONCLUSIVE** |
| reactive vs baseline | total_waiting_s | 20 | -0.28 | -0.58 | [-1.01, 0.46] | 13/7/0 | **INCONCLUSIVE** |
| reactive vs baseline | mean_queue_veh | 20 | -0.11 | -0.1 | [-1.12, 0.9] | 10/10/0 | **INCONCLUSIVE** |
| reactive vs baseline | arrived | 20 | 0.0 | 0.0 | [-0.02, 0.02] | 1/1/18 | **INCONCLUSIVE** |
| reactive vs baseline | teleports | 10 | 0.0 | 0.0 | [-16.86, 16.86] | 1/1/8 | **INCONCLUSIVE** |
| reactive vs baseline | top_edge_flow_concentration | 20 | -0.69 | 0.0 | [-1.36, -0.02] | 8/2/10 | **HELPED** |
| oracle vs baseline | total_vehicle_hours_incl_never_inserted | 20 | -1.22 | -1.2 | [-1.49, -0.95] | 20/0/0 | **HELPED** |
| oracle vs baseline | mean_travel_time_all | 20 | -1.22 | -1.2 | [-1.49, -0.95] | 20/0/0 | **HELPED** |
| oracle vs baseline | p95_travel_time_s | 20 | -1.71 | -1.92 | [-2.36, -1.06] | 17/3/0 | **HELPED** |
| oracle vs baseline | total_waiting_s | 20 | -8.92 | -8.64 | [-9.69, -8.15] | 20/0/0 | **HELPED** |
| oracle vs baseline | mean_queue_veh | 20 | -8.35 | -8.69 | [-9.72, -6.97] | 20/0/0 | **HELPED** |
| oracle vs baseline | arrived | 20 | 0.0 | 0.0 | [-0.02, 0.02] | 2/2/16 | **INCONCLUSIVE** |
| oracle vs baseline | teleports | 10 | -25.0 | 0.0 | [-50.29, 0.29] | 4/0/6 | **INCONCLUSIVE** |
| oracle vs baseline | top_edge_flow_concentration | 20 | 2.89 | 2.03 | [0.91, 4.86] | 4/13/3 | **HURT** |

## Teleports (never hidden)

| arm | total | rate / 1000 inserted | probe affected (seeds) | share equipped | top edges |
|---|---|---|---|---|---|
| baseline | 16 | 0.888 | — | 0.175 | 13462749#0 (3), 1125536674#0 (2), 47895366#0 (1), 384310417#0 (1) |
| reactive | 16 | 0.888 | — | 0.167 | 13462749#0 (3), 1125536674#0 (2), 47895366#0 (1), 384310417#0 (1) |
| persistence_predictive | 17 | 0.944 | — | 0.2 | 13462749#0 (3), 1125536674#0 (2), 47895366#0 (1), 384310417#0 (1) |
| learned_predictive | 17 | 0.944 | — | 0.2 | 13462749#0 (3), 1125536674#0 (2), 47895366#0 (1), 384310417#0 (1) |
| oracle | 12 | 0.666 | — | 0.1 | 13462749#0 (2), 1125536674#0 (2), 384310417#0 (1), -384309989#1 (1) |

## Forecast quality → routing outcome, per seed

| seed | moment | GWNet MAE (km/h) | persistence MAE | skill | % decisions ≠ persistence | mean predicted saving GWNet / pers (s) | reroutes GWNet / pers | realized saving vs baseline GWNet / pers (%) |
|---|---|---|---|---|---|---|---|---|
| 301 | 2012-03-13T00:35 | 3.281 | 3.709 | 0.1153 | 0.0 | 0.0 / 0.0 | 0 / 0 | 0.033 / 0.033 |
| 302 | 2012-03-13T08:40 | 4.621 | 5.871 | 0.2129 | 0.0 | 82.97 / 80.1 | 1 / 1 | -0.269 / -0.269 |
| 303 | 2012-03-13T16:45 | 12.656 | 14.603 | 0.1333 | 1.1 | 89.12 / 85.23 | 4 / 7 | -0.339 / -0.761 |
| 304 | 2012-03-14T00:50 | 2.512 | 3.485 | 0.2791 | 0.0 | 0.0 / 0.0 | 0 / 0 | 0.024 / 0.024 |
| 305 | 2012-03-14T08:55 | 4.122 | 5.432 | 0.2412 | 1.1 | 67.13 / 61.66 | 3 / 1 | 0.024 / -0.227 |
| 306 | 2012-03-14T17:00 | 9.7 | 11.467 | 0.1541 | 9.19 | 100.85 / 110.23 | 12 / 30 | -0.066 / -0.238 |
| 307 | 2012-03-12T07:50 | 7.401 | 10.259 | 0.2787 | 0.0 | 91.26 / 145.15 | 2 / 2 | -0.578 / -0.578 |
| 308 | 2012-03-12T15:55 | 4.984 | 5.204 | 0.0423 | 0.0 | 83.95 / 76.1 | 3 / 3 | -0.222 / -0.222 |
| 309 | 2012-03-13T00:00 | 2.697 | 2.783 | 0.0307 | 0.0 | 0.0 / 0.0 | 0 / 0 | 0.378 / 0.378 |
| 310 | 2012-03-13T08:05 | 6.893 | 14.162 | 0.5133 | 0.37 | 71.56 / 69.48 | 1 / 2 | 0.246 / 0.343 |
| 311 | 2012-03-13T16:10 | 4.548 | 7.667 | 0.4068 | 0.37 | 97.17 / 84.15 | 1 / 1 | -0.357 / -0.363 |
| 312 | 2012-03-14T00:15 | 2.08 | 2.998 | 0.3061 | 0.0 | 0.0 / 0.0 | 0 / 0 | 0.564 / 0.564 |
| 313 | 2012-03-14T08:20 | 5.663 | 5.738 | 0.0131 | 0.0 | 93.82 / 105.36 | 2 / 2 | 0.409 / 0.409 |
| 314 | 2012-03-14T16:25 | 19.511 | 14.124 | -0.3814 | 4.04 | 89.13 / 91.98 | 6 / 16 | 1.044 / 0.073 |
| 315 | 2012-03-12T07:15 | 7.357 | 8.013 | 0.0819 | 0.74 | 71.0 / 69.86 | 3 / 2 | -0.216 / -0.144 |
| 316 | 2012-03-12T15:20 | 4.681 | 4.46 | -0.0496 | 0.0 | 74.68 / 76.31 | 1 / 1 | 0.262 / 0.262 |
| 317 | 2012-03-12T23:25 | 2.284 | 2.381 | 0.0404 | 0.0 | 0.0 / 0.0 | 0 / 0 | 0.819 / 0.819 |
| 318 | 2012-03-13T07:30 | 10.88 | 6.678 | -0.6293 | 0.0 | 90.81 / 114.32 | 3 / 3 | -0.575 / -0.575 |
| 319 | 2012-03-13T15:35 | 4.959 | 4.89 | -0.014 | 0.0 | 0.0 / 0.0 | 0 / 0 | 0.018 / 0.018 |
| 320 | 2012-03-13T23:40 | 2.657 | 4.322 | 0.3853 | 0.0 | 0.0 / 0.0 | 0 / 0 | -0.175 / -0.175 |

Spearman(skill, realized saving vs baseline) = -0.241; Spearman(skill, learned − persistence realized saving) = 0.179 (n = 20). with n seeds this is a correlation across moments of one dataset, not a causal estimate.

Per-seed table: see report.json. Probe trip (one user trip, never the conclusion): {"baseline": [504.0, 509.0, 510.0, 513.0, 551.0, 550.0, 559.0, 507.0, 461.0, 508.0, 511.0, 506.0, 506.0, 470.0, 464.0, 507.0, 553.0, 510.0, 506.0, 506.0], "reactive": [504.0, 509.0, 510.0, 514.0, 550.0, 511.0, 555.0, 509.0, 462.0, 507.0, 509.0, 507.0, 506.0, 509.0, 464.0, 461.0, 552.0, 510.0, 505.0, 506.0], "persistence_predictive": [504.0, 509.0, 598.0, 514.0, 603.0, 606.0, 555.0, 465.0, 461.0, 508.0, 554.0, 507.0, 508.0, 792.0, 463.0, 506.0, 551.0, 507.0, 511.0, 506.0], "learned_predictive": [504.0, 509.0, 559.0, 514.0, 602.0, 557.0, 555.0, 465.0, 461.0, 508.0, 554.0, 507.0, 508.0, 513.0, 463.0, 506.0, 551.0, 507.0, 511.0, 506.0], "oracle": [504.0, 596.0, 600.0, 554.0, 549.0, 595.0, 600.0, 508.0, 503.0, 557.0, 601.0, 551.0, 513.0, 463.0, 507.0, 507.0, 554.0, 549.0, 513.0, 464.0]}

