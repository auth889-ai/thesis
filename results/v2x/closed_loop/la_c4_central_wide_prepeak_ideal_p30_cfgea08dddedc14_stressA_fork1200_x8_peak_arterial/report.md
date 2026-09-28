# V2X closed loop — V2X_CLOSED_LOOP_v1 · la_c4_central_wide · profile `ideal` · penetration 0.3 · seeds [101, 102, 103]

Model Graph WaveNet (207-node METR-LA, verified) (ckpt `548e399bd53c`), 83 of 207 detectors mapped, routing config `ea08dddedc14`. SYNTHETIC_WHAT_IF randomTrips on the real OSM network, one draw per seed, scale 8.0x, profile peak [(0, 600, 0.5), (600, 1500, 0.8), (1500, 2400, 1.0), (2400, 3600, 1.0)]. REAL METR-LA detector speeds (mph), replayed as lane speed caps on mapped edges in every arm. SIMULATED V2X (pipeline/v2x/channel.py) — not radio hardware: latency 0.0 ms ± 0.0, loss 0.0, TTL 60.0 s.

Identical-state fork at 1200 s: state hashes {101: '5009e45519e6', 102: '18849e64fd9f', 103: 'cd5a3e42ac57'} — identical across arms: **True**. Reroutes applied by arm: {'baseline': 0, 'reactive': 0, 'oracle_v2x': 854, 'persistence_v2x': 615, 'predictive_v2x': 600, 'predictive_corrected_v2x': 650, 'random_v2x': 1548}.

| pair | metric | n | mean % | median % | 95 % CI | W/L/T | label |
|---|---|---|---|---|---|---|---|
| reactive vs baseline | total_vehicle_hours_incl_never_inserted | 3 | 1.57 | 1.53 | [0.41, 2.72] | 0/3/0 | **HURT** |
| reactive vs baseline | mean_travel_time_all | 3 | 1.57 | 1.53 | [0.39, 2.75] | 0/3/0 | **HURT** |
| reactive vs baseline | p95_travel_time_s | 3 | -1.78 | -2.12 | [-3.43, -0.13] | 3/0/0 | **HELPED** |
| reactive vs baseline | total_waiting_s | 3 | 2.01 | 0.07 | [-6.64, 10.65] | 1/2/0 | **INCONCLUSIVE** |
| reactive vs baseline | mean_queue_veh | 3 | 3.29 | 3.38 | [-0.86, 7.45] | 0/3/0 | **INCONCLUSIVE** |
| reactive vs baseline | arrived | 3 | -0.85 | -0.7 | [-1.55, -0.15] | 0/3/0 | **HURT** |
| reactive vs baseline | teleports | 3 | 15.24 | 39.13 | [-128.36, 158.84] | 1/2/0 | **INCONCLUSIVE** |
| oracle_v2x vs baseline | total_vehicle_hours_incl_never_inserted | 3 | -0.92 | -0.88 | [-1.37, -0.47] | 3/0/0 | **HELPED** |
| oracle_v2x vs baseline | mean_travel_time_all | 3 | -0.92 | -0.87 | [-1.37, -0.47] | 3/0/0 | **HELPED** |
| oracle_v2x vs baseline | p95_travel_time_s | 3 | -0.68 | -0.95 | [-5.72, 4.35] | 2/1/0 | **INCONCLUSIVE** |
| oracle_v2x vs baseline | total_waiting_s | 3 | 0.64 | 0.77 | [-2.6, 3.87] | 1/2/0 | **INCONCLUSIVE** |
| oracle_v2x vs baseline | mean_queue_veh | 3 | -4.49 | -4.51 | [-4.61, -4.38] | 3/0/0 | **HELPED** |
| oracle_v2x vs baseline | arrived | 3 | 1.39 | 1.31 | [0.86, 1.92] | 3/0/0 | **HELPED** |
| oracle_v2x vs baseline | teleports | 3 | -22.09 | -22.22 | [-51.63, 7.45] | 3/0/0 | **INCONCLUSIVE** |
| oracle_v2x vs reactive | total_vehicle_hours_incl_never_inserted | 3 | -2.45 | -2.26 | [-3.91, -0.99] | 3/0/0 | **HELPED** |
| oracle_v2x vs reactive | mean_travel_time_all | 3 | -2.45 | -2.26 | [-3.94, -0.96] | 3/0/0 | **HELPED** |
| oracle_v2x vs reactive | p95_travel_time_s | 3 | 1.11 | 1.29 | [-2.59, 4.82] | 1/2/0 | **INCONCLUSIVE** |
| oracle_v2x vs reactive | total_waiting_s | 3 | -1.24 | 0.71 | [-12.38, 9.89] | 1/2/0 | **INCONCLUSIVE** |
| oracle_v2x vs reactive | mean_queue_veh | 3 | -7.52 | -7.63 | [-11.35, -3.68] | 3/0/0 | **HELPED** |
| oracle_v2x vs reactive | arrived | 3 | 2.26 | 2.35 | [1.5, 3.03] | 3/0/0 | **HELPED** |
| oracle_v2x vs reactive | teleports | 3 | -6.95 | -50.54 | [-198.76, 184.85] | 2/1/0 | **INCONCLUSIVE** |
| persistence_v2x vs baseline | total_vehicle_hours_incl_never_inserted | 3 | -0.15 | -0.29 | [-1.05, 0.75] | 2/1/0 | **INCONCLUSIVE** |
| persistence_v2x vs baseline | mean_travel_time_all | 3 | -0.16 | -0.28 | [-1.05, 0.74] | 2/1/0 | **INCONCLUSIVE** |
| persistence_v2x vs baseline | p95_travel_time_s | 3 | -1.3 | -1.4 | [-2.79, 0.18] | 3/0/0 | **INCONCLUSIVE** |
| persistence_v2x vs baseline | total_waiting_s | 3 | -0.41 | -0.5 | [-2.18, 1.36] | 2/1/0 | **INCONCLUSIVE** |
| persistence_v2x vs baseline | mean_queue_veh | 3 | -0.12 | -0.4 | [-2.48, 2.25] | 2/1/0 | **INCONCLUSIVE** |
| persistence_v2x vs baseline | arrived | 3 | 0.11 | 0.16 | [-0.86, 1.08] | 2/1/0 | **INCONCLUSIVE** |
| persistence_v2x vs baseline | teleports | 3 | 9.81 | 17.39 | [-25.88, 45.5] | 1/2/0 | **INCONCLUSIVE** |
| persistence_v2x vs reactive | total_vehicle_hours_incl_never_inserted | 3 | -1.69 | -1.53 | [-3.03, -0.35] | 3/0/0 | **HELPED** |
| persistence_v2x vs reactive | mean_travel_time_all | 3 | -1.7 | -1.54 | [-3.04, -0.35] | 3/0/0 | **HELPED** |
| persistence_v2x vs reactive | p95_travel_time_s | 3 | 0.49 | 0.36 | [-0.26, 1.23] | 0/3/0 | **INCONCLUSIVE** |
| persistence_v2x vs reactive | total_waiting_s | 3 | -2.29 | -1.0 | [-10.75, 6.17] | 2/1/0 | **INCONCLUSIVE** |
| persistence_v2x vs reactive | mean_queue_veh | 3 | -3.28 | -2.44 | [-7.11, 0.54] | 3/0/0 | **INCONCLUSIVE** |
| persistence_v2x vs reactive | arrived | 3 | 0.97 | 0.88 | [0.53, 1.41] | 3/0/0 | **HELPED** |
| persistence_v2x vs reactive | teleports | 3 | 16.32 | -15.62 | [-140.52, 173.16] | 2/1/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | total_vehicle_hours_incl_never_inserted | 3 | 0.21 | -0.03 | [-1.21, 1.63] | 2/1/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | mean_travel_time_all | 3 | 0.19 | -0.06 | [-1.25, 1.64] | 2/1/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | p95_travel_time_s | 3 | 0.05 | 0.32 | [-3.87, 3.98] | 1/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | total_waiting_s | 3 | 0.01 | -0.18 | [-1.98, 2.0] | 2/1/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | mean_queue_veh | 3 | 0.59 | -0.28 | [-5.03, 6.21] | 2/1/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | arrived | 3 | -0.17 | 0.11 | [-1.64, 1.31] | 2/1/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | teleports | 3 | 2.18 | 22.61 | [-94.22, 98.57] | 1/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | total_vehicle_hours_incl_never_inserted | 3 | -1.34 | -1.71 | [-3.69, 1.02] | 3/0/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | mean_travel_time_all | 3 | -1.35 | -1.72 | [-3.75, 1.04] | 3/0/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | p95_travel_time_s | 3 | 1.88 | 2.59 | [-3.68, 7.44] | 1/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | total_waiting_s | 3 | -1.9 | -0.73 | [-8.27, 4.48] | 3/0/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | mean_queue_veh | 3 | -2.58 | -4.34 | [-11.52, 6.36] | 2/1/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | arrived | 3 | 0.69 | 0.93 | [-1.19, 2.57] | 2/1/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | teleports | 3 | -5.0 | -11.88 | [-52.1, 42.1] | 2/1/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs baseline | total_vehicle_hours_incl_never_inserted | 3 | 0.0 | -0.38 | [-1.72, 1.72] | 2/1/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs baseline | mean_travel_time_all | 3 | -0.01 | -0.4 | [-1.73, 1.71] | 2/1/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs baseline | p95_travel_time_s | 3 | -1.16 | -0.9 | [-2.58, 0.26] | 3/0/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs baseline | total_waiting_s | 3 | -0.27 | -0.28 | [-1.41, 0.86] | 2/1/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs baseline | mean_queue_veh | 3 | 0.16 | -0.33 | [-2.68, 3.01] | 2/1/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs baseline | arrived | 3 | 0.04 | 0.36 | [-1.69, 1.77] | 2/1/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs baseline | teleports | 3 | 1.0 | 12.82 | [-58.02, 60.02] | 1/2/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs reactive | total_vehicle_hours_incl_never_inserted | 3 | -1.54 | -1.89 | [-4.25, 1.17] | 3/0/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs reactive | mean_travel_time_all | 3 | -1.55 | -1.9 | [-4.27, 1.16] | 3/0/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs reactive | p95_travel_time_s | 3 | 0.64 | 1.24 | [-2.48, 3.76] | 1/2/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs reactive | total_waiting_s | 3 | -2.17 | -0.79 | [-9.39, 5.05] | 3/0/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs reactive | mean_queue_veh | 3 | -3.0 | -3.59 | [-9.59, 3.59] | 3/0/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs reactive | arrived | 3 | 0.9 | 1.2 | [-1.22, 3.02] | 2/1/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs reactive | teleports | 3 | 1.6 | -16.25 | [-102.13, 105.34] | 2/1/0 | **INCONCLUSIVE** |
| random_v2x vs baseline | total_vehicle_hours_incl_never_inserted | 3 | 0.02 | 0.06 | [-0.75, 0.79] | 1/2/0 | **INCONCLUSIVE** |
| random_v2x vs baseline | mean_travel_time_all | 3 | 0.0 | 0.05 | [-0.8, 0.8] | 1/2/0 | **INCONCLUSIVE** |
| random_v2x vs baseline | p95_travel_time_s | 3 | -0.25 | -0.36 | [-1.01, 0.5] | 2/1/0 | **INCONCLUSIVE** |
| random_v2x vs baseline | total_waiting_s | 3 | -0.54 | -0.84 | [-2.84, 1.75] | 2/1/0 | **INCONCLUSIVE** |
| random_v2x vs baseline | mean_queue_veh | 3 | -0.84 | -1.13 | [-4.78, 3.1] | 2/1/0 | **INCONCLUSIVE** |
| random_v2x vs baseline | arrived | 3 | 0.01 | 0.01 | [-1.05, 1.08] | 2/1/0 | **INCONCLUSIVE** |
| random_v2x vs baseline | teleports | 3 | -30.59 | -41.74 | [-89.37, 28.19] | 3/0/0 | **INCONCLUSIVE** |
| random_v2x vs reactive | total_vehicle_hours_incl_never_inserted | 3 | -1.52 | -1.81 | [-3.08, 0.03] | 3/0/0 | **INCONCLUSIVE** |
| random_v2x vs reactive | mean_travel_time_all | 3 | -1.54 | -1.84 | [-3.12, 0.04] | 3/0/0 | **INCONCLUSIVE** |
| random_v2x vs reactive | p95_travel_time_s | 3 | 1.56 | 1.79 | [-0.75, 3.88] | 0/3/0 | **INCONCLUSIVE** |
| random_v2x vs reactive | total_waiting_s | 3 | -2.42 | -1.35 | [-11.45, 6.61] | 2/1/0 | **INCONCLUSIVE** |
| random_v2x vs reactive | mean_queue_veh | 3 | -3.97 | -5.45 | [-11.03, 3.1] | 3/0/0 | **INCONCLUSIVE** |
| random_v2x vs reactive | arrived | 3 | 0.88 | 0.69 | [-0.86, 2.61] | 3/0/0 | **INCONCLUSIVE** |
| random_v2x vs reactive | teleports | 3 | -29.5 | -38.59 | [-114.2, 55.2] | 2/1/0 | **INCONCLUSIVE** |
| predictive_v2x vs oracle_v2x | total_vehicle_hours_incl_never_inserted | 3 | 1.14 | 1.1 | [-0.34, 2.61] | 0/3/0 | **INCONCLUSIVE** |
| predictive_v2x vs oracle_v2x | mean_travel_time_all | 3 | 1.12 | 1.07 | [-0.36, 2.6] | 0/3/0 | **INCONCLUSIVE** |
| predictive_v2x vs oracle_v2x | p95_travel_time_s | 3 | 0.79 | 1.28 | [-8.23, 9.81] | 1/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs oracle_v2x | total_waiting_s | 3 | -0.6 | -1.43 | [-5.47, 4.27] | 2/1/0 | **INCONCLUSIVE** |
| predictive_v2x vs oracle_v2x | mean_queue_veh | 3 | 5.32 | 4.44 | [-0.45, 11.09] | 0/3/0 | **INCONCLUSIVE** |
| predictive_v2x vs oracle_v2x | arrived | 3 | -1.53 | -1.18 | [-3.51, 0.44] | 0/3/0 | **INCONCLUSIVE** |
| predictive_v2x vs oracle_v2x | teleports | 3 | 37.36 | 62.64 | [-123.2, 197.92] | 1/2/0 | **INCONCLUSIVE** |

Network (means over seeds): connected 3443 vehicles · uplink TX 339613 RX 339613 PDR 1.0 lat med 0.0 p95 0.0 ms · downlink TX 274 RX 274 dropped 0 expired 0 PDR 0.9983333333333334 lat med 0.0 p95 0.0 ms · reroutes applied 600 · inapplicable 222

- s101 baseline: veh-h 3656.9922, mean tt 1145 s, p95 2221 s, arrived 9123, teleports 115, reroutes applied 0, sim `sim_v2x_s101_baseline_ideal_p30`
- s101 reactive: veh-h 3731.9119, mean tt 1169 s, p95 2174 s, arrived 9061, teleports 160, reroutes applied 0, sim `sim_v2x_s101_reactive_ideal_p30`
- s101 oracle_v2x: veh-h 3616.0522, mean tt 1132 s, p95 2164 s, arrived 9235, teleports 76, reroutes applied 263, sim `sim_v2x_s101_oracle_v2x_ideal_p30`
- s101 persistence_v2x: veh-h 3646.2658, mean tt 1142 s, p95 2180 s, arrived 9138, teleports 135, reroutes applied 171, sim `sim_v2x_s101_persistence_v2x_ideal_p30`
- s101 predictive_v2x: veh-h 3655.8308, mean tt 1145 s, p95 2254 s, arrived 9145, teleports 141, reroutes applied 166, sim `sim_v2x_s101_predictive_v2x_ideal_p30`
- s101 predictive_corrected_v2x: veh-h 3641.9336, mean tt 1141 s, p95 2201 s, arrived 9170, teleports 134, reroutes applied 169, sim `sim_v2x_s101_predictive_corrected_v2x_ideal_p30`
- s101 random_v2x: veh-h 3659.1392, mean tt 1146 s, p95 2213 s, arrived 9124, teleports 67, reroutes applied 504, sim `sim_v2x_s101_random_v2x_ideal_p30`
- s102 baseline: veh-h 3633.2381, mean tt 1139 s, p95 2259 s, arrived 9167, teleports 148, reroutes applied 0, sim `sim_v2x_s102_baseline_ideal_p30`
- s102 reactive: veh-h 3688.9858, mean tt 1157 s, p95 2236 s, arrived 9059, teleports 73, reroutes applied 0, sim `sim_v2x_s102_reactive_ideal_p30`
- s102 oracle_v2x: veh-h 3605.5356, mean tt 1130 s, p95 2292 s, arrived 9287, teleports 133, reroutes applied 255, sim `sim_v2x_s102_oracle_v2x_ideal_p30`
- s102 persistence_v2x: veh-h 3642.6653, mean tt 1142 s, p95 2244 s, arrived 9139, teleports 138, reroutes applied 154, sim `sim_v2x_s102_persistence_v2x_ideal_p30`
- s102 predictive_v2x: veh-h 3625.7878, mean tt 1137 s, p95 2222 s, arrived 9177, teleports 85, reroutes applied 150, sim `sim_v2x_s102_predictive_v2x_ideal_p30`
- s102 predictive_corrected_v2x: veh-h 3619.2992, mean tt 1135 s, p95 2218 s, arrived 9200, teleports 109, reroutes applied 166, sim `sim_v2x_s102_predictive_corrected_v2x_ideal_p30`
- s102 random_v2x: veh-h 3622.1219, mean tt 1135 s, p95 2248 s, arrived 9208, teleports 79, reroutes applied 516, sim `sim_v2x_s102_random_v2x_ideal_p30`
- s103 baseline: veh-h 3609.6275, mean tt 1136 s, p95 2213 s, arrived 9183, teleports 117, reroutes applied 0, sim `sim_v2x_s103_baseline_ideal_p30`
- s103 reactive: veh-h 3650.0975, mean tt 1148 s, p95 2164 s, arrived 9119, teleports 184, reroutes applied 0, sim `sim_v2x_s103_reactive_ideal_p30`
- s103 oracle_v2x: veh-h 3578.0342, mean tt 1126 s, p95 2192 s, arrived 9333, teleports 91, reroutes applied 336, sim `sim_v2x_s103_oracle_v2x_ideal_p30`
- s103 persistence_v2x: veh-h 3594.3475, mean tt 1131 s, p95 2182 s, arrived 9226, teleports 139, reroutes applied 290, sim `sim_v2x_s103_persistence_v2x_ideal_p30`
- s103 predictive_v2x: veh-h 3640.6297, mean tt 1145 s, p95 2220 s, arrived 9105, teleports 148, reroutes applied 284, sim `sim_v2x_s103_predictive_v2x_ideal_p30`
- s103 predictive_corrected_v2x: veh-h 3638.4908, mean tt 1145 s, p95 2196 s, arrived 9113, teleports 132, reroutes applied 315, sim `sim_v2x_s103_predictive_corrected_v2x_ideal_p30`
- s103 random_v2x: veh-h 3620.7442, mean tt 1139 s, p95 2215 s, arrived 9145, teleports 113, reroutes applied 528, sim `sim_v2x_s103_random_v2x_ideal_p30`
