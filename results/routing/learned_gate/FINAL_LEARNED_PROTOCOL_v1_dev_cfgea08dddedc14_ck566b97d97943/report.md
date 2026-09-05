# Learned-model outcome gate — FINAL_LEARNED_PROTOCOL_v1 (dev seeds, n = 3)

**Verdict (Graph WaveNet vs baseline, total vehicle-hours): INCONCLUSIVE** — mean +0.29 %, median +0.07 %, 95 % CI [-0.75, 1.33], wins/losses/ties 0/3/0.

**Outcome class:** C: forecast/control benefit not established

Graph WaveNet vs persistence-predictive: -0.03 %, CI [-0.14, 0.09], 1/0/2, **INCONCLUSIVE**. Persistence-predictive vs baseline: +0.32 %, CI [-0.66, 1.3], **INCONCLUSIVE**.

## Frozen protocol

- city_id: `los_angeles_metr`
- network_hash: `3a55f46d9693`
- dataset: `user:los_angeles`
- dataset_hash: `0fc9c01d475c0124`
- mapping_hash: `f1c599a4366c`
- mapping_counts: `{'GOOD': 8, 'WEAK': 0, 'REJECTED': 12}`
- model: `GWNet`
- checkpoint: `GraphWaveNet_best_val_MAE.pt`
- checkpoint_sha256: `566b97d97943`
- held_out_skill: `0.2647`
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
| learned_predictive vs baseline | total_vehicle_hours_incl_never_inserted | 3 | 0.29 | 0.07 | [-0.75, 1.33] | 0/3/0 | **INCONCLUSIVE** |
| learned_predictive vs baseline | mean_travel_time_all | 3 | 0.29 | 0.07 | [-0.75, 1.33] | 0/3/0 | **INCONCLUSIVE** |
| learned_predictive vs baseline | p95_travel_time_s | 3 | 1.34 | 1.38 | [0.81, 1.88] | 0/3/0 | **HURT** |
| learned_predictive vs baseline | total_waiting_s | 3 | 1.26 | 0.51 | [-3.3, 5.83] | 1/2/0 | **INCONCLUSIVE** |
| learned_predictive vs baseline | mean_queue_veh | 3 | 0.63 | 0.46 | [-1.19, 2.46] | 0/2/1 | **INCONCLUSIVE** |
| learned_predictive vs baseline | arrived | 3 | 0.0 | 0.0 | [0.0, 0.0] | 0/0/3 | **INCONCLUSIVE** |
| learned_predictive vs baseline | teleports | 3 | 0.0 | 0.0 | [0.0, 0.0] | 0/0/3 | **INCONCLUSIVE** |
| learned_predictive vs baseline | top_edge_flow_concentration | 3 | -0.3 | 0.0 | [-1.58, 0.98] | 1/0/2 | **INCONCLUSIVE** |
| learned_predictive vs reactive | total_vehicle_hours_incl_never_inserted | 3 | 0.22 | 0.36 | [-0.64, 1.09] | 1/2/0 | **INCONCLUSIVE** |
| learned_predictive vs reactive | mean_travel_time_all | 3 | 0.22 | 0.36 | [-0.64, 1.08] | 1/2/0 | **INCONCLUSIVE** |
| learned_predictive vs reactive | p95_travel_time_s | 3 | 0.56 | 1.54 | [-7.21, 8.34] | 1/2/0 | **INCONCLUSIVE** |
| learned_predictive vs reactive | total_waiting_s | 3 | 1.05 | 1.3 | [-0.83, 2.93] | 0/3/0 | **INCONCLUSIVE** |
| learned_predictive vs reactive | mean_queue_veh | 3 | 3.02 | 2.72 | [-1.46, 7.51] | 0/3/0 | **INCONCLUSIVE** |
| learned_predictive vs reactive | arrived | 3 | 0.0 | 0.0 | [0.0, 0.0] | 0/0/3 | **INCONCLUSIVE** |
| learned_predictive vs reactive | teleports | 3 | 0.0 | 0.0 | [0.0, 0.0] | 0/0/3 | **INCONCLUSIVE** |
| learned_predictive vs reactive | top_edge_flow_concentration | 3 | 1.67 | 2.23 | [-1.99, 5.32] | 0/2/1 | **INCONCLUSIVE** |
| learned_predictive vs persistence_predictive | total_vehicle_hours_incl_never_inserted | 3 | -0.03 | 0.0 | [-0.14, 0.09] | 1/0/2 | **INCONCLUSIVE** |
| learned_predictive vs persistence_predictive | mean_travel_time_all | 3 | -0.03 | 0.0 | [-0.14, 0.09] | 1/0/2 | **INCONCLUSIVE** |
| learned_predictive vs persistence_predictive | p95_travel_time_s | 3 | -0.36 | 0.0 | [-1.91, 1.19] | 1/0/2 | **INCONCLUSIVE** |
| learned_predictive vs persistence_predictive | total_waiting_s | 3 | -0.08 | 0.0 | [-0.45, 0.28] | 1/0/2 | **INCONCLUSIVE** |
| learned_predictive vs persistence_predictive | mean_queue_veh | 3 | -0.08 | 0.0 | [-0.43, 0.27] | 1/0/2 | **INCONCLUSIVE** |
| learned_predictive vs persistence_predictive | arrived | 3 | 0.0 | 0.0 | [0.0, 0.0] | 0/0/3 | **INCONCLUSIVE** |
| learned_predictive vs persistence_predictive | teleports | 3 | 0.0 | 0.0 | [0.0, 0.0] | 0/0/3 | **INCONCLUSIVE** |
| learned_predictive vs persistence_predictive | top_edge_flow_concentration | 3 | 0.0 | 0.0 | [0.0, 0.0] | 0/0/3 | **INCONCLUSIVE** |
| persistence_predictive vs baseline | total_vehicle_hours_incl_never_inserted | 3 | 0.32 | 0.1 | [-0.66, 1.3] | 0/3/0 | **INCONCLUSIVE** |
| persistence_predictive vs baseline | mean_travel_time_all | 3 | 0.32 | 0.1 | [-0.66, 1.3] | 0/3/0 | **INCONCLUSIVE** |
| persistence_predictive vs baseline | p95_travel_time_s | 3 | 1.71 | 1.54 | [-0.04, 3.47] | 0/3/0 | **INCONCLUSIVE** |
| persistence_predictive vs baseline | total_waiting_s | 3 | 1.35 | 0.51 | [-3.0, 5.69] | 0/3/0 | **INCONCLUSIVE** |
| persistence_predictive vs baseline | mean_queue_veh | 3 | 0.72 | 0.46 | [-0.86, 2.3] | 0/3/0 | **INCONCLUSIVE** |
| persistence_predictive vs baseline | arrived | 3 | 0.0 | 0.0 | [0.0, 0.0] | 0/0/3 | **INCONCLUSIVE** |
| persistence_predictive vs baseline | teleports | 3 | 0.0 | 0.0 | [0.0, 0.0] | 0/0/3 | **INCONCLUSIVE** |
| persistence_predictive vs baseline | top_edge_flow_concentration | 3 | -0.3 | 0.0 | [-1.58, 0.98] | 1/0/2 | **INCONCLUSIVE** |
| reactive vs baseline | total_vehicle_hours_incl_never_inserted | 3 | 0.07 | -0.28 | [-1.83, 1.96] | 2/1/0 | **INCONCLUSIVE** |
| reactive vs baseline | mean_travel_time_all | 3 | 0.07 | -0.28 | [-1.83, 1.96] | 2/1/0 | **INCONCLUSIVE** |
| reactive vs baseline | p95_travel_time_s | 3 | 0.84 | -0.42 | [-7.4, 9.09] | 2/1/0 | **INCONCLUSIVE** |
| reactive vs baseline | total_waiting_s | 3 | 0.22 | -1.12 | [-6.09, 6.54] | 2/1/0 | **INCONCLUSIVE** |
| reactive vs baseline | mean_queue_veh | 3 | -2.31 | -2.2 | [-4.78, 0.17] | 3/0/0 | **INCONCLUSIVE** |
| reactive vs baseline | arrived | 3 | 0.0 | 0.0 | [0.0, 0.0] | 0/0/3 | **INCONCLUSIVE** |
| reactive vs baseline | teleports | 3 | 0.0 | 0.0 | [0.0, 0.0] | 0/0/3 | **INCONCLUSIVE** |
| reactive vs baseline | top_edge_flow_concentration | 3 | -1.92 | -2.18 | [-6.39, 2.56] | 2/0/1 | **INCONCLUSIVE** |
| oracle vs baseline | total_vehicle_hours_incl_never_inserted | 3 | -1.34 | -1.39 | [-2.49, -0.19] | 3/0/0 | **HELPED** |
| oracle vs baseline | mean_travel_time_all | 3 | -1.34 | -1.39 | [-2.49, -0.19] | 3/0/0 | **HELPED** |
| oracle vs baseline | p95_travel_time_s | 3 | -2.13 | -1.96 | [-6.3, 2.03] | 3/0/0 | **INCONCLUSIVE** |
| oracle vs baseline | total_waiting_s | 3 | -8.74 | -9.29 | [-12.81, -4.68] | 3/0/0 | **HELPED** |
| oracle vs baseline | mean_queue_veh | 3 | -11.42 | -12.11 | [-14.72, -8.12] | 3/0/0 | **HELPED** |
| oracle vs baseline | arrived | 3 | 0.0 | 0.0 | [0.0, 0.0] | 0/0/3 | **INCONCLUSIVE** |
| oracle vs baseline | teleports | 3 | 0.0 | 0.0 | [0.0, 0.0] | 0/0/3 | **INCONCLUSIVE** |
| oracle vs baseline | top_edge_flow_concentration | 3 | 1.65 | 3.27 | [-7.76, 11.06] | 1/2/0 | **INCONCLUSIVE** |

## Teleports (never hidden)

| arm | total | rate / 1000 inserted | probe affected (seeds) | share equipped | top edges |
|---|---|---|---|---|---|
| baseline | 3 | 1.11 | — | 0.333 | 398734334#0 (1), 398734325#0 (1), 384310417#0 (1) |
| reactive | 3 | 1.11 | — | 0.333 | 398734334#0 (1), 398734325#0 (1), 384310417#0 (1) |
| persistence_predictive | 3 | 1.11 | — | 0.333 | 398734334#0 (1), 398734325#0 (1), 384310417#0 (1) |
| learned_predictive | 3 | 1.11 | — | 0.333 | 398734334#0 (1), 398734325#0 (1), 384310417#0 (1) |
| oracle | 3 | 1.11 | — | 0.333 | 398734334#0 (1), 398734325#0 (1), 384310417#0 (1) |

## Forecast quality → routing outcome, per seed

| seed | moment | GWNet MAE (km/h) | persistence MAE | skill | % decisions ≠ persistence | mean predicted saving GWNet / pers (s) | reroutes GWNet / pers | realized saving vs baseline GWNet / pers (%) |
|---|---|---|---|---|---|---|---|---|
| 101 | 2012-03-13T15:10 | 8.188 | 13.611 | 0.3985 | 0.0 | 69.69 / 97.12 | 2 / 2 | -0.772 / -0.772 |
| 102 | 2012-03-13T23:15 | 2.617 | 3.597 | 0.2724 | 0.0 | 0.0 / 0.0 | 0 / 0 | -0.075 / -0.075 |
| 103 | 2012-03-14T07:20 | 7.658 | 9.117 | 0.16 | 0.37 | 77.9 / 67.05 | 3 / 2 | -0.025 / -0.104 |

Spearman(skill, realized saving vs baseline) = -1.0; Spearman(skill, learned − persistence realized saving) = -1.0 (n = 3). with n seeds this is a correlation across moments of one dataset, not a causal estimate.

Per-seed table: see report.json. Probe trip (one user trip, never the conclusion): {"baseline": [504.0, 509.0, 549.0], "reactive": [503.0, 468.0, 550.0], "persistence_predictive": [503.0, 468.0, 550.0], "learned_predictive": [503.0, 468.0, 550.0], "oracle": [463.0, 465.0, 552.0]}

