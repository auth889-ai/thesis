# V2X closed loop — V2X_CLOSED_LOOP_v1 · la_c4_central_wide · profile `ideal` · penetration 0.3 · seeds [201, 202, 203, 204, 205]

Model Graph WaveNet (207-node METR-LA, verified) (ckpt `548e399bd53c`), 83 of 207 detectors mapped, routing config `ea08dddedc14`. SYNTHETIC_WHAT_IF randomTrips on the real OSM network, one draw per seed, scale 8.0x, profile uniform [(0, 1800, 1.0)]. REAL METR-LA detector speeds (mph), replayed as lane speed caps on mapped edges in every arm. SIMULATED V2X (pipeline/v2x/channel.py) — not radio hardware: latency 0.0 ms ± 0.0, loss 0.0, TTL 60.0 s.

Identical-state fork at 1200 s: state hashes {201: '6390908e60d1', 202: '2e3428b57515', 203: '032bce52afd7', 204: '9691857c1b71', 205: '92b0f85bc7b6'} — identical across arms: **True**. Reroutes applied by arm: {'baseline': 0, 'reactive': 0, 'oracle_v2x': 871, 'persistence_v2x': 381, 'predictive_v2x': 362, 'predictive_corrected_v2x': 556, 'random_v2x': 926}.

| pair | metric | n | mean % | median % | 95 % CI | W/L/T | label |
|---|---|---|---|---|---|---|---|
| reactive vs baseline | total_vehicle_hours_incl_never_inserted | 5 | -0.56 | -1.1 | [-2.85, 1.72] | 4/1/0 | **INCONCLUSIVE** |
| reactive vs baseline | mean_travel_time_all | 5 | -0.56 | -1.07 | [-2.84, 1.72] | 4/1/0 | **INCONCLUSIVE** |
| reactive vs baseline | p95_travel_time_s | 5 | 0.14 | 0.0 | [-1.56, 1.85] | 2/2/1 | **INCONCLUSIVE** |
| reactive vs baseline | total_waiting_s | 5 | 1.0 | 0.78 | [-2.43, 4.43] | 2/3/0 | **INCONCLUSIVE** |
| reactive vs baseline | mean_queue_veh | 5 | -0.09 | -1.59 | [-6.14, 5.95] | 4/1/0 | **INCONCLUSIVE** |
| reactive vs baseline | arrived | 5 | 0.33 | 0.26 | [-0.69, 1.35] | 4/1/0 | **INCONCLUSIVE** |
| reactive vs baseline | teleports | 5 | -3.63 | -4.65 | [-27.29, 20.04] | 3/1/1 | **INCONCLUSIVE** |
| oracle_v2x vs baseline | total_vehicle_hours_incl_never_inserted | 5 | -1.64 | -1.82 | [-2.5, -0.78] | 5/0/0 | **HELPED** |
| oracle_v2x vs baseline | mean_travel_time_all | 5 | -1.64 | -1.82 | [-2.51, -0.77] | 5/0/0 | **HELPED** |
| oracle_v2x vs baseline | p95_travel_time_s | 5 | -0.2 | 0.2 | [-2.05, 1.65] | 2/3/0 | **INCONCLUSIVE** |
| oracle_v2x vs baseline | total_waiting_s | 5 | 1.9 | 1.67 | [-1.92, 5.73] | 2/3/0 | **INCONCLUSIVE** |
| oracle_v2x vs baseline | mean_queue_veh | 5 | -3.99 | -4.23 | [-6.65, -1.32] | 5/0/0 | **HELPED** |
| oracle_v2x vs baseline | arrived | 5 | 1.73 | 1.72 | [1.09, 2.37] | 5/0/0 | **HELPED** |
| oracle_v2x vs baseline | teleports | 5 | -0.5 | 4.88 | [-26.44, 25.43] | 2/3/0 | **INCONCLUSIVE** |
| oracle_v2x vs reactive | total_vehicle_hours_incl_never_inserted | 5 | -1.05 | -0.63 | [-3.77, 1.67] | 3/2/0 | **INCONCLUSIVE** |
| oracle_v2x vs reactive | mean_travel_time_all | 5 | -1.06 | -0.65 | [-3.77, 1.65] | 3/2/0 | **INCONCLUSIVE** |
| oracle_v2x vs reactive | p95_travel_time_s | 5 | -0.32 | 0.07 | [-3.34, 2.7] | 2/3/0 | **INCONCLUSIVE** |
| oracle_v2x vs reactive | total_waiting_s | 5 | 0.98 | 0.88 | [-4.91, 6.87] | 2/3/0 | **INCONCLUSIVE** |
| oracle_v2x vs reactive | mean_queue_veh | 5 | -3.68 | -2.2 | [-10.93, 3.57] | 3/2/0 | **INCONCLUSIVE** |
| oracle_v2x vs reactive | arrived | 5 | 1.39 | 1.31 | [0.26, 2.52] | 5/0/0 | **HELPED** |
| oracle_v2x vs reactive | teleports | 5 | 4.04 | 2.44 | [-19.43, 27.52] | 2/3/0 | **INCONCLUSIVE** |
| persistence_v2x vs baseline | total_vehicle_hours_incl_never_inserted | 5 | -1.01 | -1.38 | [-2.18, 0.16] | 4/1/0 | **INCONCLUSIVE** |
| persistence_v2x vs baseline | mean_travel_time_all | 5 | -1.02 | -1.4 | [-2.19, 0.16] | 4/1/0 | **INCONCLUSIVE** |
| persistence_v2x vs baseline | p95_travel_time_s | 5 | -0.29 | -0.19 | [-2.27, 1.69] | 3/2/0 | **INCONCLUSIVE** |
| persistence_v2x vs baseline | total_waiting_s | 5 | 1.15 | 0.74 | [-3.0, 5.29] | 1/4/0 | **INCONCLUSIVE** |
| persistence_v2x vs baseline | mean_queue_veh | 5 | -2.53 | -3.73 | [-5.94, 0.88] | 4/1/0 | **INCONCLUSIVE** |
| persistence_v2x vs baseline | arrived | 5 | 0.93 | 1.28 | [-0.27, 2.13] | 4/1/0 | **INCONCLUSIVE** |
| persistence_v2x vs baseline | teleports | 5 | -16.83 | -14.63 | [-28.39, -5.27] | 5/0/0 | **HELPED** |
| persistence_v2x vs reactive | total_vehicle_hours_incl_never_inserted | 5 | -0.43 | -0.57 | [-2.19, 1.33] | 4/1/0 | **INCONCLUSIVE** |
| persistence_v2x vs reactive | mean_travel_time_all | 5 | -0.44 | -0.57 | [-2.2, 1.32] | 4/1/0 | **INCONCLUSIVE** |
| persistence_v2x vs reactive | p95_travel_time_s | 5 | -0.42 | -0.78 | [-2.47, 1.62] | 3/2/0 | **INCONCLUSIVE** |
| persistence_v2x vs reactive | total_waiting_s | 5 | 0.19 | 1.02 | [-4.72, 5.11] | 2/3/0 | **INCONCLUSIVE** |
| persistence_v2x vs reactive | mean_queue_veh | 5 | -2.31 | -3.62 | [-7.36, 2.74] | 4/1/0 | **INCONCLUSIVE** |
| persistence_v2x vs reactive | arrived | 5 | 0.6 | 1.02 | [-1.04, 2.25] | 4/1/0 | **INCONCLUSIVE** |
| persistence_v2x vs reactive | teleports | 5 | -11.96 | -13.04 | [-28.1, 4.18] | 3/0/2 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | total_vehicle_hours_incl_never_inserted | 5 | -0.16 | 0.67 | [-1.91, 1.58] | 2/3/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | mean_travel_time_all | 5 | -0.17 | 0.67 | [-1.91, 1.57] | 2/3/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | p95_travel_time_s | 5 | 0.54 | 0.61 | [-1.01, 2.08] | 1/4/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | total_waiting_s | 5 | 1.59 | 2.12 | [-0.28, 3.45] | 1/4/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | mean_queue_veh | 5 | -0.41 | 1.62 | [-5.7, 4.89] | 2/3/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | arrived | 5 | 0.51 | 0.08 | [-0.66, 1.68] | 3/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | teleports | 5 | -9.28 | -8.16 | [-47.79, 29.24] | 4/1/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | total_vehicle_hours_incl_never_inserted | 5 | 0.42 | -0.1 | [-2.1, 2.95] | 3/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | mean_travel_time_all | 5 | 0.41 | -0.13 | [-2.11, 2.94] | 3/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | p95_travel_time_s | 5 | 0.4 | 0.39 | [-1.12, 1.93] | 2/3/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | total_waiting_s | 5 | 0.63 | 0.73 | [-2.98, 4.25] | 2/3/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | mean_queue_veh | 5 | -0.15 | -1.94 | [-7.65, 7.34] | 3/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | arrived | 5 | 0.18 | 0.9 | [-1.56, 1.93] | 3/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | teleports | 5 | -3.13 | 2.44 | [-48.57, 42.31] | 2/3/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs baseline | total_vehicle_hours_incl_never_inserted | 5 | -1.51 | -1.43 | [-2.71, -0.32] | 5/0/0 | **HELPED** |
| predictive_corrected_v2x vs baseline | mean_travel_time_all | 5 | -1.52 | -1.44 | [-2.71, -0.33] | 5/0/0 | **HELPED** |
| predictive_corrected_v2x vs baseline | p95_travel_time_s | 5 | -0.36 | -0.32 | [-1.14, 0.42] | 4/1/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs baseline | total_waiting_s | 5 | 0.73 | 0.73 | [-2.69, 4.14] | 2/3/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs baseline | mean_queue_veh | 5 | -3.94 | -3.25 | [-6.92, -0.97] | 5/0/0 | **HELPED** |
| predictive_corrected_v2x vs baseline | arrived | 5 | 1.16 | 1.21 | [0.21, 2.1] | 5/0/0 | **HELPED** |
| predictive_corrected_v2x vs baseline | teleports | 5 | -2.99 | 6.98 | [-48.59, 42.6] | 2/3/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs reactive | total_vehicle_hours_incl_never_inserted | 5 | -0.93 | -0.97 | [-2.88, 1.02] | 4/1/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs reactive | mean_travel_time_all | 5 | -0.95 | -0.97 | [-2.9, 1.0] | 4/1/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs reactive | p95_travel_time_s | 5 | -0.49 | -0.19 | [-1.91, 0.94] | 3/2/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs reactive | total_waiting_s | 5 | -0.21 | 0.94 | [-5.03, 4.6] | 2/3/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs reactive | mean_queue_veh | 5 | -3.73 | -5.16 | [-8.5, 1.04] | 4/1/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs reactive | arrived | 5 | 0.83 | 0.84 | [-0.05, 1.7] | 4/1/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs reactive | teleports | 5 | 3.89 | 9.8 | [-53.97, 61.76] | 2/3/0 | **INCONCLUSIVE** |
| random_v2x vs baseline | total_vehicle_hours_incl_never_inserted | 5 | -0.45 | -0.34 | [-1.27, 0.37] | 4/1/0 | **INCONCLUSIVE** |
| random_v2x vs baseline | mean_travel_time_all | 5 | -0.45 | -0.35 | [-1.27, 0.38] | 4/1/0 | **INCONCLUSIVE** |
| random_v2x vs baseline | p95_travel_time_s | 5 | -0.37 | -0.35 | [-2.44, 1.7] | 3/2/0 | **INCONCLUSIVE** |
| random_v2x vs baseline | total_waiting_s | 5 | -0.33 | -0.38 | [-8.51, 7.85] | 3/2/0 | **INCONCLUSIVE** |
| random_v2x vs baseline | mean_queue_veh | 5 | -1.05 | -1.46 | [-4.11, 2.02] | 3/2/0 | **INCONCLUSIVE** |
| random_v2x vs baseline | arrived | 5 | 0.27 | 0.86 | [-1.78, 2.33] | 3/2/0 | **INCONCLUSIVE** |
| random_v2x vs baseline | teleports | 5 | 4.24 | -4.88 | [-41.0, 49.48] | 3/2/0 | **INCONCLUSIVE** |
| random_v2x vs reactive | total_vehicle_hours_incl_never_inserted | 5 | 0.13 | 0.75 | [-1.5, 1.76] | 1/4/0 | **INCONCLUSIVE** |
| random_v2x vs reactive | mean_travel_time_all | 5 | 0.13 | 0.71 | [-1.5, 1.76] | 1/4/0 | **INCONCLUSIVE** |
| random_v2x vs reactive | p95_travel_time_s | 5 | -0.51 | -0.35 | [-1.94, 0.92] | 3/2/0 | **INCONCLUSIVE** |
| random_v2x vs reactive | total_waiting_s | 5 | -1.29 | -1.39 | [-9.55, 6.98] | 3/2/0 | **INCONCLUSIVE** |
| random_v2x vs reactive | mean_queue_veh | 5 | -0.82 | 0.13 | [-5.84, 4.19] | 2/3/0 | **INCONCLUSIVE** |
| random_v2x vs reactive | arrived | 5 | -0.06 | 0.61 | [-2.07, 1.96] | 3/2/0 | **INCONCLUSIVE** |
| random_v2x vs reactive | teleports | 5 | 15.43 | -17.39 | [-61.45, 92.31] | 3/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs oracle_v2x | total_vehicle_hours_incl_never_inserted | 5 | 1.51 | 2.61 | [-0.79, 3.81] | 2/3/0 | **INCONCLUSIVE** |
| predictive_v2x vs oracle_v2x | mean_travel_time_all | 5 | 1.51 | 2.61 | [-0.8, 3.82] | 2/3/0 | **INCONCLUSIVE** |
| predictive_v2x vs oracle_v2x | p95_travel_time_s | 5 | 0.75 | 0.06 | [-1.32, 2.83] | 2/3/0 | **INCONCLUSIVE** |
| predictive_v2x vs oracle_v2x | total_waiting_s | 5 | -0.26 | -1.51 | [-3.24, 2.71] | 3/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs oracle_v2x | mean_queue_veh | 5 | 3.81 | 7.96 | [-3.64, 11.26] | 2/3/0 | **INCONCLUSIVE** |
| predictive_v2x vs oracle_v2x | arrived | 5 | -1.19 | -1.61 | [-2.84, 0.46] | 1/4/0 | **INCONCLUSIVE** |
| predictive_v2x vs oracle_v2x | teleports | 5 | -3.65 | 0.0 | [-52.74, 45.44] | 2/2/1 | **INCONCLUSIVE** |

Network (means over seeds): connected 1659 vehicles · uplink TX 174001 RX 174001 PDR 1.0 lat med 0.0 p95 0.0 ms · downlink TX 111 RX 110 dropped 0 expired 1 PDR 0.9971399999999999 lat med 0.0 p95 0.0 ms · reroutes applied 362 · inapplicable 188

- s201 baseline: veh-h 2137.8619, mean tt 1400 s, p95 3112 s, arrived 5209, teleports 23, reroutes applied 0, sim `sim_v2x_s201_baseline_ideal_p30`
- s201 reactive: veh-h 2089.0803, mean tt 1368 s, p95 3112 s, arrived 5287, teleports 23, reroutes applied 0, sim `sim_v2x_s201_reactive_ideal_p30`
- s201 oracle_v2x: veh-h 2098.2925, mean tt 1374 s, p95 3127 s, arrived 5301, teleports 25, reroutes applied 156, sim `sim_v2x_s201_oracle_v2x_ideal_p30`
- s201 persistence_v2x: veh-h 2126.2656, mean tt 1392 s, p95 3113 s, arrived 5196, teleports 20, reroutes applied 89, sim `sim_v2x_s201_persistence_v2x_ideal_p30`
- s201 predictive_v2x: veh-h 2153.1114, mean tt 1410 s, p95 3124 s, arrived 5187, teleports 31, reroutes applied 93, sim `sim_v2x_s201_predictive_v2x_ideal_p30`
- s201 predictive_corrected_v2x: veh-h 2116.0906, mean tt 1386 s, p95 3102 s, arrived 5272, teleports 13, reroutes applied 138, sim `sim_v2x_s201_predictive_corrected_v2x_ideal_p30`
- s201 random_v2x: veh-h 2105.2786, mean tt 1379 s, p95 3101 s, arrived 5254, teleports 19, reroutes applied 218, sim `sim_v2x_s201_random_v2x_ideal_p30`
- s202 baseline: veh-h 2182.4722, mean tt 1398 s, p95 3052 s, arrived 5313, teleports 43, reroutes applied 0, sim `sim_v2x_s202_baseline_ideal_p30`
- s202 reactive: veh-h 2164.7444, mean tt 1386 s, p95 3056 s, arrived 5339, teleports 39, reroutes applied 0, sim `sim_v2x_s202_reactive_ideal_p30`
- s202 oracle_v2x: veh-h 2144.9081, mean tt 1374 s, p95 3058 s, arrived 5446, teleports 52, reroutes applied 167, sim `sim_v2x_s202_oracle_v2x_ideal_p30`
- s202 persistence_v2x: veh-h 2152.3525, mean tt 1378 s, p95 3117 s, arrived 5424, teleports 33, reroutes applied 166, sim `sim_v2x_s202_persistence_v2x_ideal_p30`
- s202 predictive_v2x: veh-h 2206.4506, mean tt 1413 s, p95 3112 s, arrived 5305, teleports 21, reroutes applied 149, sim `sim_v2x_s202_predictive_v2x_ideal_p30`
- s202 predictive_corrected_v2x: veh-h 2143.8308, mean tt 1373 s, p95 3064 s, arrived 5427, teleports 26, reroutes applied 190, sim `sim_v2x_s202_predictive_corrected_v2x_ideal_p30`
- s202 random_v2x: veh-h 2175.1658, mean tt 1393 s, p95 3084 s, arrived 5422, teleports 27, reroutes applied 254, sim `sim_v2x_s202_random_v2x_ideal_p30`
- s203 baseline: veh-h 2104.8858, mean tt 1391 s, p95 3091 s, arrived 5083, teleports 41, reroutes applied 0, sim `sim_v2x_s203_baseline_ideal_p30`
- s203 reactive: veh-h 2081.6269, mean tt 1376 s, p95 3070 s, arrived 5096, teleports 51, reroutes applied 0, sim `sim_v2x_s203_reactive_ideal_p30`
- s203 oracle_v2x: veh-h 2094.7133, mean tt 1384 s, p95 3144 s, arrived 5163, teleports 43, reroutes applied 201, sim `sim_v2x_s203_oracle_v2x_ideal_p30`
- s203 persistence_v2x: veh-h 2074.4783, mean tt 1371 s, p95 3046 s, arrived 5148, teleports 35, reroutes applied 14, sim `sim_v2x_s203_persistence_v2x_ideal_p30`
- s203 predictive_v2x: veh-h 2079.6317, mean tt 1374 s, p95 3110 s, arrived 5162, teleports 33, reroutes applied 11, sim `sim_v2x_s203_predictive_v2x_ideal_p30`
- s203 predictive_corrected_v2x: veh-h 2074.8647, mean tt 1371 s, p95 3079 s, arrived 5138, teleports 56, reroutes applied 52, sim `sim_v2x_s203_predictive_corrected_v2x_ideal_p30`
- s203 random_v2x: veh-h 2097.2161, mean tt 1386 s, p95 3076 s, arrived 5127, teleports 39, reroutes applied 59, sim `sim_v2x_s203_random_v2x_ideal_p30`
- s204 baseline: veh-h 2182.3267, mean tt 1426 s, p95 3203 s, arrived 5150, teleports 49, reroutes applied 0, sim `sim_v2x_s204_baseline_ideal_p30`
- s204 reactive: veh-h 2156.2853, mean tt 1410 s, p95 3166 s, arrived 5162, teleports 35, reroutes applied 0, sim `sim_v2x_s204_reactive_ideal_p30`
- s204 oracle_v2x: veh-h 2142.65, mean tt 1400 s, p95 3156 s, arrived 5205, teleports 32, reroutes applied 164, sim `sim_v2x_s204_oracle_v2x_ideal_p30`
- s204 persistence_v2x: veh-h 2137.625, mean tt 1397 s, p95 3140 s, arrived 5223, teleports 35, reroutes applied 24, sim `sim_v2x_s204_persistence_v2x_ideal_p30`
- s204 predictive_v2x: veh-h 2136.3064, mean tt 1396 s, p95 3158 s, arrived 5227, teleports 45, reroutes applied 24, sim `sim_v2x_s204_predictive_v2x_ideal_p30`
- s204 predictive_corrected_v2x: veh-h 2117.65, mean tt 1384 s, p95 3160 s, arrived 5219, teleports 61, reroutes applied 51, sim `sim_v2x_s204_predictive_corrected_v2x_ideal_p30`
- s204 random_v2x: veh-h 2174.8689, mean tt 1422 s, p95 3105 s, arrived 5028, teleports 76, reroutes applied 146, sim `sim_v2x_s204_random_v2x_ideal_p30`
- s205 baseline: veh-h 2153.2017, mean tt 1393 s, p95 3104 s, arrived 5296, teleports 43, reroutes applied 0, sim `sim_v2x_s205_baseline_ideal_p30`
- s205 reactive: veh-h 2208.5069, mean tt 1428 s, p95 3179 s, arrived 5253, teleports 41, reroutes applied 0, sim `sim_v2x_s205_reactive_ideal_p30`
- s205 oracle_v2x: veh-h 2102.8503, mean tt 1360 s, p95 3044 s, arrived 5387, teleports 42, reroutes applied 183, sim `sim_v2x_s205_oracle_v2x_ideal_p30`
- s205 persistence_v2x: veh-h 2161.2147, mean tt 1398 s, p95 3098 s, arrived 5303, teleports 41, reroutes applied 88, sim `sim_v2x_s205_persistence_v2x_ideal_p30`
- s205 predictive_v2x: veh-h 2167.6653, mean tt 1402 s, p95 3139 s, arrived 5300, teleports 42, reroutes applied 85, sim `sim_v2x_s205_predictive_v2x_ideal_p30`
- s205 predictive_corrected_v2x: veh-h 2144.8367, mean tt 1387 s, p95 3100 s, arrived 5297, teleports 46, reroutes applied 125, sim `sim_v2x_s205_predictive_corrected_v2x_ideal_p30`
- s205 random_v2x: veh-h 2159.7667, mean tt 1397 s, p95 3135 s, arrived 5294, teleports 54, reroutes applied 249, sim `sim_v2x_s205_random_v2x_ideal_p30`
