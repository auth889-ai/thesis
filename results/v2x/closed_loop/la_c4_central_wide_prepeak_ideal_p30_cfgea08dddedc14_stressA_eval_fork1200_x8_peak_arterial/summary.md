# V2X closed loop — V2X_CLOSED_LOOP_v1 · la_c4_central_wide · profile `ideal` · penetration 0.3 · seeds [201, 202, 203, 204, 205]

Model Graph WaveNet (207-node METR-LA, verified) (ckpt `548e399bd53c`), 83 of 207 detectors mapped, routing config `ea08dddedc14`. SYNTHETIC_WHAT_IF randomTrips on the real OSM network, one draw per seed, scale 8.0x, profile peak [(0, 600, 0.5), (600, 1500, 0.8), (1500, 2400, 1.0), (2400, 3600, 1.0)]. REAL METR-LA detector speeds (mph), replayed as lane speed caps on mapped edges in every arm. SIMULATED V2X (pipeline/v2x/channel.py) — not radio hardware: latency 0.0 ms ± 0.0, loss 0.0, TTL 60.0 s.

Identical-state fork at 1200 s: state hashes {201: 'ac117185cee8', 202: '4513309cd8e2', 203: '445f0528fbea', 204: '275065f17e02', 205: '4590acadfe33'} — identical across arms: **True**. Reroutes applied by arm: {'baseline': 0, 'reactive': 0, 'persistence_v2x': 1088, 'predictive_v2x': 1031, 'predictive_corrected_v2x': 1236, 'random_v2x': 2215, 'oracle_v2x': 1422}.

| pair | metric | n | mean % | median % | 95 % CI | W/L/T | label |
|---|---|---|---|---|---|---|---|
| reactive vs baseline | total_vehicle_hours_incl_never_inserted | 5 | 0.81 | 0.59 | [-0.55, 2.17] | 1/4/0 | **INCONCLUSIVE** |
| reactive vs baseline | mean_travel_time_all | 5 | 0.82 | 0.59 | [-0.58, 2.21] | 1/4/0 | **INCONCLUSIVE** |
| reactive vs baseline | p95_travel_time_s | 5 | 0.16 | 0.66 | [-4.99, 5.3] | 2/3/0 | **INCONCLUSIVE** |
| reactive vs baseline | total_waiting_s | 5 | 0.54 | 1.06 | [-4.38, 5.47] | 1/4/0 | **INCONCLUSIVE** |
| reactive vs baseline | mean_queue_veh | 5 | 1.33 | 0.89 | [-1.23, 3.88] | 1/4/0 | **INCONCLUSIVE** |
| reactive vs baseline | arrived | 5 | -0.44 | -0.23 | [-1.46, 0.58] | 2/3/0 | **INCONCLUSIVE** |
| reactive vs baseline | teleports | 5 | 12.19 | 5.98 | [-50.42, 74.8] | 2/3/0 | **INCONCLUSIVE** |
| persistence_v2x vs baseline | total_vehicle_hours_incl_never_inserted | 5 | 0.1 | 0.12 | [-0.98, 1.17] | 2/3/0 | **INCONCLUSIVE** |
| persistence_v2x vs baseline | mean_travel_time_all | 5 | 0.11 | 0.15 | [-0.98, 1.19] | 2/3/0 | **INCONCLUSIVE** |
| persistence_v2x vs baseline | p95_travel_time_s | 5 | 0.16 | 0.42 | [-4.59, 4.91] | 2/3/0 | **INCONCLUSIVE** |
| persistence_v2x vs baseline | total_waiting_s | 5 | 0.41 | -1.19 | [-6.89, 7.71] | 3/2/0 | **INCONCLUSIVE** |
| persistence_v2x vs baseline | mean_queue_veh | 5 | 0.27 | 0.03 | [-1.11, 1.65] | 2/3/0 | **INCONCLUSIVE** |
| persistence_v2x vs baseline | arrived | 5 | -0.04 | -0.03 | [-0.4, 0.31] | 2/3/0 | **INCONCLUSIVE** |
| persistence_v2x vs baseline | teleports | 5 | 17.34 | 5.83 | [-36.8, 71.48] | 2/3/0 | **INCONCLUSIVE** |
| persistence_v2x vs reactive | total_vehicle_hours_incl_never_inserted | 5 | -0.69 | -0.53 | [-1.98, 0.59] | 4/1/0 | **INCONCLUSIVE** |
| persistence_v2x vs reactive | mean_travel_time_all | 5 | -0.7 | -0.51 | [-1.98, 0.59] | 4/1/0 | **INCONCLUSIVE** |
| persistence_v2x vs reactive | p95_travel_time_s | 5 | 0.03 | -0.05 | [-2.4, 2.46] | 3/2/0 | **INCONCLUSIVE** |
| persistence_v2x vs reactive | total_waiting_s | 5 | -0.18 | -1.47 | [-3.54, 3.19] | 3/2/0 | **INCONCLUSIVE** |
| persistence_v2x vs reactive | mean_queue_veh | 5 | -1.02 | -0.44 | [-3.6, 1.56] | 4/1/0 | **INCONCLUSIVE** |
| persistence_v2x vs reactive | arrived | 5 | 0.4 | 0.12 | [-0.59, 1.4] | 3/2/0 | **INCONCLUSIVE** |
| persistence_v2x vs reactive | teleports | 5 | 6.96 | 7.21 | [-5.1, 19.03] | 2/3/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | total_vehicle_hours_incl_never_inserted | 5 | 0.12 | 0.27 | [-0.92, 1.16] | 2/3/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | mean_travel_time_all | 5 | 0.13 | 0.28 | [-0.94, 1.21] | 2/3/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | p95_travel_time_s | 5 | -0.35 | -0.33 | [-3.69, 2.99] | 3/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | total_waiting_s | 5 | -1.04 | -1.04 | [-3.48, 1.4] | 3/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | mean_queue_veh | 5 | 0.48 | 0.7 | [-1.22, 2.19] | 2/3/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | arrived | 5 | -0.29 | -0.31 | [-0.93, 0.34] | 2/3/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | teleports | 5 | -5.51 | 2.44 | [-34.64, 23.62] | 2/3/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | total_vehicle_hours_incl_never_inserted | 5 | -0.68 | -0.77 | [-1.21, -0.15] | 5/0/0 | **HELPED** |
| predictive_v2x vs reactive | mean_travel_time_all | 5 | -0.68 | -0.75 | [-1.21, -0.14] | 5/0/0 | **HELPED** |
| predictive_v2x vs reactive | p95_travel_time_s | 5 | -0.41 | 0.89 | [-4.92, 4.1] | 2/3/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | total_waiting_s | 5 | -1.5 | -2.67 | [-4.53, 1.52] | 4/1/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | mean_queue_veh | 5 | -0.82 | -0.32 | [-2.05, 0.41] | 5/0/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | arrived | 5 | 0.15 | 0.28 | [-0.57, 0.86] | 3/1/1 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | teleports | 5 | -9.01 | -4.5 | [-38.61, 20.59] | 4/1/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs baseline | total_vehicle_hours_incl_never_inserted | 5 | -0.12 | 0.01 | [-1.07, 0.83] | 2/3/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs baseline | mean_travel_time_all | 5 | -0.12 | 0.0 | [-1.09, 0.85] | 2/3/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs baseline | p95_travel_time_s | 5 | -0.31 | -0.73 | [-3.74, 3.11] | 3/2/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs baseline | total_waiting_s | 5 | 0.47 | 1.18 | [-3.2, 4.14] | 2/3/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs baseline | mean_queue_veh | 5 | -0.54 | -0.58 | [-2.56, 1.47] | 4/1/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs baseline | arrived | 5 | 0.22 | 0.1 | [-0.28, 0.72] | 4/1/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs baseline | teleports | 5 | 9.43 | -1.71 | [-30.49, 49.36] | 3/2/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs reactive | total_vehicle_hours_incl_never_inserted | 5 | -0.91 | -0.72 | [-2.15, 0.33] | 4/1/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs reactive | mean_travel_time_all | 5 | -0.92 | -0.78 | [-2.18, 0.33] | 4/1/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs reactive | p95_travel_time_s | 5 | -0.36 | -2.3 | [-5.54, 4.81] | 3/2/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs reactive | total_waiting_s | 5 | 0.01 | 0.12 | [-4.64, 4.66] | 2/3/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs reactive | mean_queue_veh | 5 | -1.82 | -1.28 | [-4.84, 1.2] | 4/1/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs reactive | arrived | 5 | 0.67 | 0.69 | [-0.6, 1.93] | 3/2/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs reactive | teleports | 5 | 2.71 | -5.47 | [-18.96, 24.38] | 3/2/0 | **INCONCLUSIVE** |
| random_v2x vs baseline | total_vehicle_hours_incl_never_inserted | 5 | 0.42 | 0.48 | [-0.44, 1.28] | 1/4/0 | **INCONCLUSIVE** |
| random_v2x vs baseline | mean_travel_time_all | 5 | 0.43 | 0.49 | [-0.43, 1.28] | 1/4/0 | **INCONCLUSIVE** |
| random_v2x vs baseline | p95_travel_time_s | 5 | 1.02 | -0.14 | [-2.32, 4.37] | 3/2/0 | **INCONCLUSIVE** |
| random_v2x vs baseline | total_waiting_s | 5 | 0.89 | 1.85 | [-2.13, 3.91] | 2/3/0 | **INCONCLUSIVE** |
| random_v2x vs baseline | mean_queue_veh | 5 | 0.53 | 0.48 | [-1.05, 2.11] | 2/3/0 | **INCONCLUSIVE** |
| random_v2x vs baseline | arrived | 5 | -0.1 | -0.01 | [-0.43, 0.23] | 2/3/0 | **INCONCLUSIVE** |
| random_v2x vs baseline | teleports | 5 | 24.25 | 30.83 | [-20.66, 69.16] | 1/4/0 | **INCONCLUSIVE** |
| random_v2x vs reactive | total_vehicle_hours_incl_never_inserted | 5 | -0.38 | -0.44 | [-1.75, 1.0] | 3/2/0 | **INCONCLUSIVE** |
| random_v2x vs reactive | mean_travel_time_all | 5 | -0.38 | -0.44 | [-1.76, 1.01] | 3/2/0 | **INCONCLUSIVE** |
| random_v2x vs reactive | p95_travel_time_s | 5 | 0.94 | -0.27 | [-2.6, 4.47] | 3/2/0 | **INCONCLUSIVE** |
| random_v2x vs reactive | total_waiting_s | 5 | 0.41 | 0.79 | [-2.45, 3.26] | 2/3/0 | **INCONCLUSIVE** |
| random_v2x vs reactive | mean_queue_veh | 5 | -0.75 | -0.12 | [-3.97, 2.47] | 3/2/0 | **INCONCLUSIVE** |
| random_v2x vs reactive | arrived | 5 | 0.34 | 0.31 | [-0.87, 1.56] | 3/2/0 | **INCONCLUSIVE** |
| random_v2x vs reactive | teleports | 5 | 16.45 | 22.66 | [-15.85, 48.75] | 1/4/0 | **INCONCLUSIVE** |
| oracle_v2x vs baseline | total_vehicle_hours_incl_never_inserted | 5 | -1.05 | -1.51 | [-2.14, 0.04] | 4/1/0 | **INCONCLUSIVE** |
| oracle_v2x vs baseline | mean_travel_time_all | 5 | -1.05 | -1.51 | [-2.13, 0.02] | 4/1/0 | **INCONCLUSIVE** |
| oracle_v2x vs baseline | p95_travel_time_s | 5 | -0.71 | -0.71 | [-4.88, 3.46] | 3/2/0 | **INCONCLUSIVE** |
| oracle_v2x vs baseline | total_waiting_s | 5 | 1.35 | 1.89 | [-2.37, 5.07] | 2/3/0 | **INCONCLUSIVE** |
| oracle_v2x vs baseline | mean_queue_veh | 5 | -4.78 | -4.9 | [-7.17, -2.39] | 5/0/0 | **HELPED** |
| oracle_v2x vs baseline | arrived | 5 | 1.39 | 1.5 | [0.56, 2.23] | 5/0/0 | **HELPED** |
| oracle_v2x vs baseline | teleports | 5 | -14.98 | -13.68 | [-41.09, 11.12] | 4/1/0 | **INCONCLUSIVE** |
| oracle_v2x vs reactive | total_vehicle_hours_incl_never_inserted | 5 | -1.83 | -1.07 | [-3.52, -0.14] | 5/0/0 | **HELPED** |
| oracle_v2x vs reactive | mean_travel_time_all | 5 | -1.85 | -1.16 | [-3.54, -0.16] | 5/0/0 | **HELPED** |
| oracle_v2x vs reactive | p95_travel_time_s | 5 | -0.77 | -1.42 | [-6.0, 4.46] | 3/2/0 | **INCONCLUSIVE** |
| oracle_v2x vs reactive | total_waiting_s | 5 | 0.92 | -0.55 | [-4.99, 6.82] | 3/2/0 | **INCONCLUSIVE** |
| oracle_v2x vs reactive | mean_queue_veh | 5 | -5.98 | -4.52 | [-9.76, -2.21] | 5/0/0 | **HELPED** |
| oracle_v2x vs reactive | arrived | 5 | 1.84 | 1.36 | [0.48, 3.2] | 5/0/0 | **HELPED** |
| oracle_v2x vs reactive | teleports | 5 | -19.86 | -13.51 | [-35.52, -4.21] | 5/0/0 | **HELPED** |
| predictive_v2x vs oracle_v2x | total_vehicle_hours_incl_never_inserted | 5 | 1.19 | 0.7 | [-0.26, 2.64] | 0/5/0 | **INCONCLUSIVE** |
| predictive_v2x vs oracle_v2x | mean_travel_time_all | 5 | 1.21 | 0.72 | [-0.25, 2.66] | 0/5/0 | **INCONCLUSIVE** |
| predictive_v2x vs oracle_v2x | p95_travel_time_s | 5 | 0.46 | 0.78 | [-5.21, 6.13] | 2/3/0 | **INCONCLUSIVE** |
| predictive_v2x vs oracle_v2x | total_waiting_s | 5 | -2.29 | -3.1 | [-6.55, 1.97] | 3/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs oracle_v2x | mean_queue_veh | 5 | 5.56 | 4.17 | [2.33, 8.79] | 0/5/0 | **HURT** |
| predictive_v2x vs oracle_v2x | arrived | 5 | -1.66 | -1.73 | [-2.66, -0.67] | 0/5/0 | **HURT** |
| predictive_v2x vs oracle_v2x | teleports | 5 | 12.33 | 10.42 | [-12.12, 36.77] | 1/4/0 | **INCONCLUSIVE** |

Network (means over seeds): connected 3485 vehicles · uplink TX 339480 RX 339480 PDR 1.0 lat med 0.0 p95 0.0 ms · downlink TX 336 RX 335 dropped 0 expired 1 PDR 0.9975400000000001 lat med 0.0 p95 0.0 ms · reroutes applied 1031 · inapplicable 642

- s201 baseline: veh-h 3750.8756, mean tt 1173 s, p95 2123 s, arrived 9037, teleports 163, reroutes applied 0, sim `sim_v2x_s201_baseline_ideal_p30`
- s201 oracle_v2x: veh-h 3757.4858, mean tt 1175 s, p95 2217 s, arrived 9059, teleports 96, reroutes applied 267, sim `sim_v2x_s201_oracle_v2x_ideal_p30`
- s201 persistence_v2x: veh-h 3788.6058, mean tt 1185 s, p95 2243 s, arrived 9056, teleports 119, reroutes applied 300, sim `sim_v2x_s201_persistence_v2x_ideal_p30`
- s201 predictive_corrected_v2x: veh-h 3770.6531, mean tt 1179 s, p95 2177 s, arrived 9046, teleports 138, reroutes applied 367, sim `sim_v2x_s201_predictive_corrected_v2x_ideal_p30`
- s201 predictive_v2x: veh-h 3760.9631, mean tt 1176 s, p95 2116 s, arrived 9009, teleports 106, reroutes applied 272, sim `sim_v2x_s201_predictive_v2x_ideal_p30`
- s201 random_v2x: veh-h 3769.9358, mean tt 1179 s, p95 2243 s, arrived 9038, teleports 113, reroutes applied 510, sim `sim_v2x_s201_random_v2x_ideal_p30`
- s201 reactive: veh-h 3798.1661, mean tt 1188 s, p95 2249 s, arrived 8984, teleports 111, reroutes applied 0, sim `sim_v2x_s201_reactive_ideal_p30`
- s202 baseline: veh-h 3715.0886, mean tt 1156 s, p95 2186 s, arrived 9281, teleports 121, reroutes applied 0, sim `sim_v2x_s202_baseline_ideal_p30`
- s202 oracle_v2x: veh-h 3653.1319, mean tt 1137 s, p95 2117 s, arrived 9442, teleports 88, reroutes applied 305, sim `sim_v2x_s202_oracle_v2x_ideal_p30`
- s202 persistence_v2x: veh-h 3719.66, mean tt 1158 s, p95 2164 s, arrived 9263, teleports 119, reroutes applied 377, sim `sim_v2x_s202_persistence_v2x_ideal_p30`
- s202 predictive_corrected_v2x: veh-h 3715.5333, mean tt 1156 s, p95 2170 s, arrived 9308, teleports 118, reroutes applied 410, sim `sim_v2x_s202_predictive_corrected_v2x_ideal_p30`
- s202 predictive_v2x: veh-h 3762.6347, mean tt 1171 s, p95 2255 s, arrived 9184, teleports 93, reroutes applied 375, sim `sim_v2x_s202_predictive_v2x_ideal_p30`
- s202 random_v2x: veh-h 3732.7653, mean tt 1162 s, p95 2183 s, arrived 9280, teleports 133, reroutes applied 462, sim `sim_v2x_s202_random_v2x_ideal_p30`
- s202 reactive: veh-h 3804.2936, mean tt 1184 s, p95 2221 s, arrived 9116, teleports 100, reroutes applied 0, sim `sim_v2x_s202_reactive_ideal_p30`
- s203 baseline: veh-h 3533.5294, mean tt 1112 s, p95 2165 s, arrived 9132, teleports 82, reroutes applied 0, sim `sim_v2x_s203_baseline_ideal_p30`
- s203 oracle_v2x: veh-h 3518.2636, mean tt 1107 s, p95 2167 s, arrived 9269, teleports 94, reroutes applied 286, sim `sim_v2x_s203_oracle_v2x_ideal_p30`
- s203 persistence_v2x: veh-h 3563.9867, mean tt 1122 s, p95 2174 s, arrived 9129, teleports 155, reroutes applied 43, sim `sim_v2x_s203_persistence_v2x_ideal_p30`
- s203 predictive_corrected_v2x: veh-h 3557.27, mean tt 1120 s, p95 2216 s, arrived 9110, teleports 136, reroutes applied 52, sim `sim_v2x_s203_predictive_corrected_v2x_ideal_p30`
- s203 predictive_v2x: veh-h 3542.9369, mean tt 1115 s, p95 2184 s, arrived 9088, teleports 84, reroutes applied 43, sim `sim_v2x_s203_predictive_v2x_ideal_p30`
- s203 random_v2x: veh-h 3584.3653, mean tt 1128 s, p95 2189 s, arrived 9080, teleports 129, reroutes applied 244, sim `sim_v2x_s203_random_v2x_ideal_p30`
- s203 reactive: veh-h 3543.6594, mean tt 1115 s, p95 2112 s, arrived 9158, teleports 162, reroutes applied 0, sim `sim_v2x_s203_reactive_ideal_p30`
- s204 baseline: veh-h 3639.1961, mean tt 1145 s, p95 2256 s, arrived 8967, teleports 117, reroutes applied 0, sim `sim_v2x_s204_baseline_ideal_p30`
- s204 oracle_v2x: veh-h 3584.3625, mean tt 1127 s, p95 2240 s, arrived 9146, teleports 101, reroutes applied 246, sim `sim_v2x_s204_oracle_v2x_ideal_p30`
- s204 persistence_v2x: veh-h 3601.6131, mean tt 1132 s, p95 2143 s, arrived 8928, teleports 141, reroutes applied 74, sim `sim_v2x_s204_persistence_v2x_ideal_p30`
- s204 predictive_corrected_v2x: veh-h 3599.9308, mean tt 1132 s, p95 2213 s, arrived 9044, teleports 115, reroutes applied 86, sim `sim_v2x_s204_predictive_corrected_v2x_ideal_p30`
- s204 predictive_v2x: veh-h 3601.7978, mean tt 1132 s, p95 2163 s, arrived 8988, teleports 145, reroutes applied 72, sim `sim_v2x_s204_predictive_v2x_ideal_p30`
- s204 random_v2x: veh-h 3621.7814, mean tt 1139 s, p95 2237 s, arrived 8974, teleports 180, reroutes applied 364, sim `sim_v2x_s204_random_v2x_ideal_p30`
- s204 reactive: veh-h 3620.6894, mean tt 1138 s, p95 2144 s, arrived 8946, teleports 124, reroutes applied 0, sim `sim_v2x_s204_reactive_ideal_p30`
- s205 baseline: veh-h 3715.2556, mean tt 1158 s, p95 2268 s, arrived 9164, teleports 120, reroutes applied 0, sim `sim_v2x_s205_baseline_ideal_p30`
- s205 oracle_v2x: veh-h 3647.2019, mean tt 1137 s, p95 2173 s, arrived 9301, teleports 111, reroutes applied 318, sim `sim_v2x_s205_oracle_v2x_ideal_p30`
- s205 persistence_v2x: veh-h 3698.1842, mean tt 1153 s, p95 2285 s, arrived 9187, teleports 127, reroutes applied 294, sim `sim_v2x_s205_persistence_v2x_ideal_p30`
- s205 predictive_corrected_v2x: veh-h 3688.6814, mean tt 1150 s, p95 2181 s, arrived 9173, teleports 121, reroutes applied 321, sim `sim_v2x_s205_predictive_corrected_v2x_ideal_p30`
- s205 predictive_v2x: veh-h 3708.4008, mean tt 1156 s, p95 2238 s, arrived 9176, teleports 125, reroutes applied 269, sim `sim_v2x_s205_predictive_v2x_ideal_p30`
- s205 random_v2x: veh-h 3720.7617, mean tt 1160 s, p95 2253 s, arrived 9163, teleports 157, reroutes applied 635, sim `sim_v2x_s205_random_v2x_ideal_p30`
- s205 reactive: veh-h 3737.0611, mean tt 1165 s, p95 2283 s, arrived 9176, teleports 128, reroutes applied 0, sim `sim_v2x_s205_reactive_ideal_p30`
