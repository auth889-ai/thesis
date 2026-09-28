# V2X closed loop — V2X_CLOSED_LOOP_v1 · la_c4_central_wide · profile `ideal` · penetration 0.3 · seeds [101, 102, 103]

Model Graph WaveNet (207-node METR-LA, verified) (ckpt `548e399bd53c`), 83 of 207 detectors mapped, routing config `ea08dddedc14`. SYNTHETIC_WHAT_IF randomTrips on the real OSM network, one draw per seed, scale 8.0x, profile uniform [(0, 1800, 1.0)]. REAL METR-LA detector speeds (mph), replayed as lane speed caps on mapped edges in every arm. SIMULATED V2X (pipeline/v2x/channel.py) — not radio hardware: latency 0.0 ms ± 0.0, loss 0.0, TTL 60.0 s.

Identical-state fork at 1200 s: state hashes {101: '2fd1429b853d', 102: '7bd99da19931', 103: 'aac1f872f66c'} — identical across arms: **True**. Reroutes applied by arm: {'baseline': 0, 'reactive': 0, 'oracle_v2x': 505, 'persistence_v2x': 148, 'predictive_v2x': 149, 'predictive_corrected_v2x': 198, 'random_v2x': 555}.

| pair | metric | n | mean % | median % | 95 % CI | W/L/T | label |
|---|---|---|---|---|---|---|---|
| reactive vs baseline | total_vehicle_hours_incl_never_inserted | 3 | -0.86 | -0.89 | [-1.48, -0.24] | 3/0/0 | **HELPED** |
| reactive vs baseline | mean_travel_time_all | 3 | -0.87 | -0.91 | [-1.52, -0.23] | 3/0/0 | **HELPED** |
| reactive vs baseline | p95_travel_time_s | 3 | -0.7 | -0.42 | [-3.37, 1.96] | 2/1/0 | **INCONCLUSIVE** |
| reactive vs baseline | total_waiting_s | 3 | 1.67 | 0.85 | [-6.92, 10.25] | 1/2/0 | **INCONCLUSIVE** |
| reactive vs baseline | mean_queue_veh | 3 | -1.87 | -1.66 | [-3.02, -0.72] | 3/0/0 | **HELPED** |
| reactive vs baseline | arrived | 3 | 0.77 | 0.5 | [-0.97, 2.5] | 3/0/0 | **INCONCLUSIVE** |
| reactive vs baseline | teleports | 3 | -10.13 | -7.55 | [-39.07, 18.8] | 2/0/1 | **INCONCLUSIVE** |
| oracle_v2x vs baseline | total_vehicle_hours_incl_never_inserted | 3 | -2.82 | -2.92 | [-4.15, -1.49] | 3/0/0 | **HELPED** |
| oracle_v2x vs baseline | mean_travel_time_all | 3 | -2.83 | -2.94 | [-4.18, -1.48] | 3/0/0 | **HELPED** |
| oracle_v2x vs baseline | p95_travel_time_s | 3 | -0.13 | 0.1 | [-2.56, 2.29] | 1/2/0 | **INCONCLUSIVE** |
| oracle_v2x vs baseline | total_waiting_s | 3 | 3.79 | 2.67 | [-4.19, 11.77] | 0/3/0 | **INCONCLUSIVE** |
| oracle_v2x vs baseline | mean_queue_veh | 3 | -8.61 | -9.01 | [-13.04, -4.19] | 3/0/0 | **HELPED** |
| oracle_v2x vs baseline | arrived | 3 | 3.0 | 3.17 | [1.0, 5.0] | 3/0/0 | **HELPED** |
| oracle_v2x vs baseline | teleports | 3 | -26.36 | -30.19 | [-115.07, 62.36] | 2/1/0 | **INCONCLUSIVE** |
| oracle_v2x vs reactive | total_vehicle_hours_incl_never_inserted | 3 | -1.97 | -2.04 | [-2.7, -1.25] | 3/0/0 | **HELPED** |
| oracle_v2x vs reactive | mean_travel_time_all | 3 | -1.97 | -2.04 | [-2.7, -1.25] | 3/0/0 | **HELPED** |
| oracle_v2x vs reactive | p95_travel_time_s | 3 | 0.57 | 0.7 | [-0.97, 2.12] | 1/2/0 | **INCONCLUSIVE** |
| oracle_v2x vs reactive | total_waiting_s | 3 | 2.1 | 1.86 | [0.94, 3.26] | 0/3/0 | **HURT** |
| oracle_v2x vs reactive | mean_queue_veh | 3 | -6.87 | -6.78 | [-11.42, -2.32] | 3/0/0 | **HELPED** |
| oracle_v2x vs reactive | arrived | 3 | 2.21 | 2.11 | [1.21, 3.22] | 3/0/0 | **HELPED** |
| oracle_v2x vs reactive | teleports | 3 | -20.51 | -24.49 | [-94.62, 53.6] | 2/1/0 | **INCONCLUSIVE** |
| persistence_v2x vs baseline | total_vehicle_hours_incl_never_inserted | 3 | 0.16 | 0.12 | [-1.58, 1.89] | 1/2/0 | **INCONCLUSIVE** |
| persistence_v2x vs baseline | mean_travel_time_all | 3 | 0.15 | 0.1 | [-1.59, 1.88] | 1/2/0 | **INCONCLUSIVE** |
| persistence_v2x vs baseline | p95_travel_time_s | 3 | -0.11 | -0.16 | [-1.04, 0.82] | 2/1/0 | **INCONCLUSIVE** |
| persistence_v2x vs baseline | total_waiting_s | 3 | -2.03 | -2.81 | [-5.72, 1.66] | 3/0/0 | **INCONCLUSIVE** |
| persistence_v2x vs baseline | mean_queue_veh | 3 | 0.85 | 0.18 | [-4.29, 5.99] | 1/2/0 | **INCONCLUSIVE** |
| persistence_v2x vs baseline | arrived | 3 | -0.59 | -0.67 | [-2.37, 1.18] | 1/2/0 | **INCONCLUSIVE** |
| persistence_v2x vs baseline | teleports | 3 | -4.94 | -9.43 | [-27.97, 18.08] | 2/1/0 | **INCONCLUSIVE** |
| persistence_v2x vs reactive | total_vehicle_hours_incl_never_inserted | 3 | 1.03 | 1.23 | [-0.41, 2.46] | 0/3/0 | **INCONCLUSIVE** |
| persistence_v2x vs reactive | mean_travel_time_all | 3 | 1.03 | 1.23 | [-0.38, 2.44] | 0/3/0 | **INCONCLUSIVE** |
| persistence_v2x vs reactive | p95_travel_time_s | 3 | 0.6 | 0.71 | [-2.4, 3.61] | 1/2/0 | **INCONCLUSIVE** |
| persistence_v2x vs reactive | total_waiting_s | 3 | -3.59 | -3.63 | [-8.31, 1.13] | 3/0/0 | **INCONCLUSIVE** |
| persistence_v2x vs reactive | mean_queue_veh | 3 | 2.77 | 1.76 | [-1.85, 7.38] | 0/3/0 | **INCONCLUSIVE** |
| persistence_v2x vs reactive | arrived | 3 | -1.35 | -1.38 | [-1.8, -0.91] | 0/3/0 | **HURT** |
| persistence_v2x vs reactive | teleports | 3 | 7.96 | -2.04 | [-55.6, 71.52] | 2/1/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | total_vehicle_hours_incl_never_inserted | 3 | -0.08 | 0.1 | [-2.73, 2.58] | 1/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | mean_travel_time_all | 3 | -0.09 | 0.08 | [-2.76, 2.59] | 1/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | p95_travel_time_s | 3 | 0.57 | 0.54 | [0.16, 0.98] | 0/3/0 | **HURT** |
| predictive_v2x vs baseline | total_waiting_s | 3 | -0.3 | -1.2 | [-11.0, 10.4] | 2/1/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | mean_queue_veh | 3 | -0.22 | 0.05 | [-10.92, 10.48] | 1/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | arrived | 3 | -0.05 | -0.29 | [-4.35, 4.26] | 1/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | teleports | 3 | -12.45 | -14.81 | [-69.06, 44.16] | 2/1/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | total_vehicle_hours_incl_never_inserted | 3 | 0.79 | 1.21 | [-1.65, 3.24] | 1/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | mean_travel_time_all | 3 | 0.79 | 1.21 | [-1.65, 3.24] | 1/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | p95_travel_time_s | 3 | 1.29 | 0.96 | [-1.06, 3.64] | 0/3/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | total_waiting_s | 3 | -1.95 | -2.03 | [-4.2, 0.29] | 3/0/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | mean_queue_veh | 3 | 1.67 | 1.62 | [-8.29, 11.63] | 1/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | arrived | 3 | -0.81 | -0.78 | [-3.45, 1.82] | 1/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | teleports | 3 | 0.35 | -14.81 | [-96.04, 96.74] | 2/1/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs baseline | total_vehicle_hours_incl_never_inserted | 3 | -0.93 | -0.42 | [-4.2, 2.33] | 2/1/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs baseline | mean_travel_time_all | 3 | -0.95 | -0.44 | [-4.22, 2.33] | 2/1/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs baseline | p95_travel_time_s | 3 | 0.34 | 1.37 | [-4.47, 5.14] | 1/2/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs baseline | total_waiting_s | 3 | 0.91 | 1.52 | [-3.07, 4.89] | 1/2/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs baseline | mean_queue_veh | 3 | -2.95 | -1.7 | [-13.35, 7.44] | 2/1/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs baseline | arrived | 3 | 0.77 | 0.51 | [-2.18, 3.71] | 2/1/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs baseline | teleports | 3 | -35.7 | -40.0 | [-64.32, -7.07] | 3/0/0 | **HELPED** |
| predictive_corrected_v2x vs reactive | total_vehicle_hours_incl_never_inserted | 3 | -0.07 | 0.47 | [-2.82, 2.67] | 1/2/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs reactive | mean_travel_time_all | 3 | -0.07 | 0.47 | [-2.82, 2.67] | 1/2/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs reactive | p95_travel_time_s | 3 | 1.06 | 1.96 | [-5.92, 8.05] | 1/2/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs reactive | total_waiting_s | 3 | -0.7 | 0.41 | [-6.02, 4.63] | 1/2/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs reactive | mean_queue_veh | 3 | -1.1 | 0.72 | [-12.15, 9.96] | 1/2/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs reactive | arrived | 3 | 0.0 | -0.51 | [-3.4, 3.41] | 1/2/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs reactive | teleports | 3 | -27.66 | -22.22 | [-64.5, 9.17] | 3/0/0 | **INCONCLUSIVE** |
| random_v2x vs baseline | total_vehicle_hours_incl_never_inserted | 3 | -1.25 | -1.07 | [-4.79, 2.28] | 2/1/0 | **INCONCLUSIVE** |
| random_v2x vs baseline | mean_travel_time_all | 3 | -1.26 | -1.09 | [-4.82, 2.29] | 2/1/0 | **INCONCLUSIVE** |
| random_v2x vs baseline | p95_travel_time_s | 3 | 0.6 | 0.92 | [-1.11, 2.31] | 1/2/0 | **INCONCLUSIVE** |
| random_v2x vs baseline | total_waiting_s | 3 | 2.4 | 2.01 | [-7.9, 12.71] | 1/2/0 | **INCONCLUSIVE** |
| random_v2x vs baseline | mean_queue_veh | 3 | -4.52 | -4.12 | [-14.65, 5.62] | 3/0/0 | **INCONCLUSIVE** |
| random_v2x vs baseline | arrived | 3 | 1.44 | 1.32 | [-2.96, 5.85] | 2/1/0 | **INCONCLUSIVE** |
| random_v2x vs baseline | teleports | 3 | -28.16 | -25.93 | [-86.88, 30.57] | 3/0/0 | **INCONCLUSIVE** |
| random_v2x vs reactive | total_vehicle_hours_incl_never_inserted | 3 | -0.39 | 0.02 | [-3.69, 2.9] | 1/2/0 | **INCONCLUSIVE** |
| random_v2x vs reactive | mean_travel_time_all | 3 | -0.39 | 0.02 | [-3.69, 2.9] | 1/2/0 | **INCONCLUSIVE** |
| random_v2x vs reactive | p95_travel_time_s | 3 | 1.32 | 0.72 | [-2.39, 5.03] | 0/3/0 | **INCONCLUSIVE** |
| random_v2x vs reactive | total_waiting_s | 3 | 0.71 | 1.15 | [-1.32, 2.74] | 1/2/0 | **INCONCLUSIVE** |
| random_v2x vs reactive | mean_queue_veh | 3 | -2.7 | -2.61 | [-12.11, 6.7] | 2/1/0 | **INCONCLUSIVE** |
| random_v2x vs reactive | arrived | 3 | 0.67 | 0.82 | [-2.09, 3.42] | 2/1/0 | **INCONCLUSIVE** |
| random_v2x vs reactive | teleports | 3 | -17.56 | -25.93 | [-107.82, 72.7] | 2/1/0 | **INCONCLUSIVE** |
| predictive_v2x vs oracle_v2x | total_vehicle_hours_incl_never_inserted | 3 | 2.82 | 3.2 | [0.48, 5.16] | 0/3/0 | **HURT** |
| predictive_v2x vs oracle_v2x | mean_travel_time_all | 3 | 2.82 | 3.2 | [0.48, 5.16] | 0/3/0 | **HURT** |
| predictive_v2x vs oracle_v2x | p95_travel_time_s | 3 | 0.71 | 0.65 | [-1.54, 2.96] | 1/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs oracle_v2x | total_waiting_s | 3 | -3.97 | -3.76 | [-7.1, -0.84] | 3/0/0 | **HELPED** |
| predictive_v2x vs oracle_v2x | mean_queue_veh | 3 | 9.17 | 11.36 | [-0.27, 18.61] | 0/3/0 | **INCONCLUSIVE** |
| predictive_v2x vs oracle_v2x | arrived | 3 | -2.96 | -3.35 | [-5.41, -0.52] | 0/3/0 | **HURT** |
| predictive_v2x vs oracle_v2x | teleports | 3 | 49.94 | -5.41 | [-227.69, 327.58] | 2/1/0 | **INCONCLUSIVE** |

Network (means over seeds): connected 1635 vehicles · uplink TX 166921 RX 166921 PDR 1.0 lat med 0.0 p95 0.0 ms · downlink TX 67 RX 67 dropped 0 expired 0 PDR 1.0 lat med 0.0 p95 0.0 ms · reroutes applied 149 · inapplicable 53

- s101 baseline: veh-h 2095.0289, mean tt 1370 s, p95 3061 s, arrived 5238, teleports 35, reroutes applied 0, sim `sim_v2x_s101_baseline_ideal_p30`
- s101 reactive: veh-h 2072.0864, mean tt 1355 s, p95 3067 s, arrived 5264, teleports 27, reroutes applied 0, sim `sim_v2x_s101_reactive_ideal_p30`
- s101 oracle_v2x: veh-h 2026.0422, mean tt 1325 s, p95 3064 s, arrived 5404, teleports 14, reroutes applied 162, sim `sim_v2x_s101_oracle_v2x_ideal_p30`
- s101 persistence_v2x: veh-h 2097.4839, mean tt 1372 s, p95 3047 s, arrived 5203, teleports 37, reroutes applied 41, sim `sim_v2x_s101_persistence_v2x_ideal_p30`
- s101 predictive_v2x: veh-h 2097.1439, mean tt 1371 s, p95 3084 s, arrived 5223, teleports 39, reroutes applied 35, sim `sim_v2x_s101_predictive_v2x_ideal_p30`
- s101 predictive_corrected_v2x: veh-h 2044.2247, mean tt 1337 s, p95 3003 s, arrived 5346, teleports 21, reroutes applied 53, sim `sim_v2x_s101_predictive_corrected_v2x_ideal_p30`
- s101 random_v2x: veh-h 2072.5164, mean tt 1355 s, p95 3089 s, arrived 5307, teleports 33, reroutes applied 206, sim `sim_v2x_s101_random_v2x_ideal_p30`
- s102 baseline: veh-h 2147.1592, mean tt 1404 s, p95 3127 s, arrived 5128, teleports 53, reroutes applied 0, sim `sim_v2x_s102_baseline_ideal_p30`
- s102 reactive: veh-h 2127.9542, mean tt 1391 s, p95 3114 s, arrived 5208, teleports 49, reroutes applied 0, sim `sim_v2x_s102_reactive_ideal_p30`
- s102 oracle_v2x: veh-h 2084.4711, mean tt 1362 s, p95 3149 s, arrived 5318, teleports 37, reroutes applied 192, sim `sim_v2x_s102_oracle_v2x_ideal_p30`
- s102 persistence_v2x: veh-h 2135.9453, mean tt 1396 s, p95 3136 s, arrived 5136, teleports 48, reroutes applied 48, sim `sim_v2x_s102_persistence_v2x_ideal_p30`
- s102 predictive_v2x: veh-h 2120.8675, mean tt 1386 s, p95 3144 s, arrived 5220, teleports 35, reroutes applied 50, sim `sim_v2x_s102_predictive_v2x_ideal_p30`
- s102 predictive_corrected_v2x: veh-h 2138.0242, mean tt 1397 s, p95 3175 s, arrived 5154, teleports 41, reroutes applied 70, sim `sim_v2x_s102_predictive_corrected_v2x_ideal_p30`
- s102 random_v2x: veh-h 2088.0267, mean tt 1365 s, p95 3121 s, arrived 5296, teleports 25, reroutes applied 201, sim `sim_v2x_s102_random_v2x_ideal_p30`
- s103 baseline: veh-h 2082.0653, mean tt 1365 s, p95 3070 s, arrived 5276, teleports 27, reroutes applied 0, sim `sim_v2x_s103_baseline_ideal_p30`
- s103 reactive: veh-h 2069.6219, mean tt 1357 s, p95 3012 s, arrived 5289, teleports 27, reroutes applied 0, sim `sim_v2x_s103_reactive_ideal_p30`
- s103 oracle_v2x: veh-h 2035.4497, mean tt 1334 s, p95 3033 s, arrived 5388, teleports 30, reroutes applied 151, sim `sim_v2x_s103_oracle_v2x_ideal_p30`
- s103 persistence_v2x: veh-h 2100.2228, mean tt 1377 s, p95 3065 s, arrived 5209, teleports 24, reroutes applied 59, sim `sim_v2x_s103_persistence_v2x_ideal_p30`
- s103 predictive_v2x: veh-h 2100.6247, mean tt 1377 s, p95 3083 s, arrived 5189, teleports 23, reroutes applied 64, sim `sim_v2x_s103_predictive_v2x_ideal_p30`
- s103 predictive_corrected_v2x: veh-h 2083.06, mean tt 1366 s, p95 3112 s, arrived 5262, teleports 15, reroutes applied 75, sim `sim_v2x_s103_predictive_corrected_v2x_ideal_p30`
- s103 random_v2x: veh-h 2083.6025, mean tt 1366 s, p95 3103 s, arrived 5262, teleports 20, reroutes applied 148, sim `sim_v2x_s103_random_v2x_ideal_p30`
