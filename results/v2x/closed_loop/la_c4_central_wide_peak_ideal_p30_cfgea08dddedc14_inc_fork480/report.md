# V2X closed loop — V2X_CLOSED_LOOP_v1 · la_c4_central_wide · profile `ideal` · penetration 0.3 · seeds [101, 102, 103]

Model Graph WaveNet (207-node METR-LA, verified) (ckpt `548e399bd53c`), 83 of 207 detectors mapped, routing config `ea08dddedc14`. SYNTHETIC_WHAT_IF randomTrips on the real OSM network, one draw per seed, departures 0-1800 s. REAL METR-LA detector speeds (mph), replayed as lane speed caps on mapped edges in every arm. SIMULATED V2X (pipeline/v2x/channel.py) — not radio hardware: latency 0.0 ms ± 0.0, loss 0.0, TTL 60.0 s.

Identical-state fork at 480 s: state hashes {101: 'bd20b216eaeb', 102: '12a122bf1d08', 103: '0f9a687dc09c'} — identical across arms: **True**. Reroutes applied by arm: {'baseline': 0, 'reactive': 0, 'persistence_v2x': 46, 'predictive_v2x': 47, 'predictive_corrected_v2x': 56, 'oracle_v2x': 109, 'random_v2x': 86}.

| pair | metric | n | mean % | median % | 95 % CI | W/L/T | label |
|---|---|---|---|---|---|---|---|
| reactive vs baseline | total_vehicle_hours_incl_never_inserted | 3 | -0.65 | -0.75 | [-1.81, 0.5] | 3/0/0 | **INCONCLUSIVE** |
| reactive vs baseline | mean_travel_time_all | 3 | -0.65 | -0.75 | [-1.81, 0.5] | 3/0/0 | **INCONCLUSIVE** |
| reactive vs baseline | p95_travel_time_s | 3 | -0.05 | -1.07 | [-7.42, 7.32] | 2/1/0 | **INCONCLUSIVE** |
| reactive vs baseline | total_waiting_s | 3 | 0.41 | 0.95 | [-4.46, 5.28] | 1/2/0 | **INCONCLUSIVE** |
| reactive vs baseline | mean_queue_veh | 3 | 0.88 | 0.33 | [-3.79, 5.54] | 1/2/0 | **INCONCLUSIVE** |
| reactive vs baseline | arrived | 3 | -0.04 | -0.12 | [-1.24, 1.16] | 1/2/0 | **INCONCLUSIVE** |
| persistence_v2x vs baseline | total_vehicle_hours_incl_never_inserted | 3 | -0.27 | -0.51 | [-1.95, 1.4] | 2/1/0 | **INCONCLUSIVE** |
| persistence_v2x vs baseline | mean_travel_time_all | 3 | -0.27 | -0.51 | [-1.95, 1.4] | 2/1/0 | **INCONCLUSIVE** |
| persistence_v2x vs baseline | p95_travel_time_s | 3 | 0.33 | -0.43 | [-4.67, 5.33] | 2/1/0 | **INCONCLUSIVE** |
| persistence_v2x vs baseline | total_waiting_s | 3 | -0.11 | -0.33 | [-6.37, 6.15] | 2/1/0 | **INCONCLUSIVE** |
| persistence_v2x vs baseline | mean_queue_veh | 3 | -0.32 | -0.97 | [-6.95, 6.32] | 2/1/0 | **INCONCLUSIVE** |
| persistence_v2x vs baseline | arrived | 3 | 0.16 | 0.12 | [-0.59, 0.91] | 2/1/0 | **INCONCLUSIVE** |
| persistence_v2x vs reactive | total_vehicle_hours_incl_never_inserted | 3 | 0.38 | 0.27 | [-0.17, 0.93] | 0/3/0 | **INCONCLUSIVE** |
| persistence_v2x vs reactive | mean_travel_time_all | 3 | 0.38 | 0.27 | [-0.17, 0.93] | 0/3/0 | **INCONCLUSIVE** |
| persistence_v2x vs reactive | p95_travel_time_s | 3 | 0.4 | 0.65 | [-1.97, 2.78] | 1/2/0 | **INCONCLUSIVE** |
| persistence_v2x vs reactive | total_waiting_s | 3 | -0.52 | -0.76 | [-2.72, 1.68] | 2/1/0 | **INCONCLUSIVE** |
| persistence_v2x vs reactive | mean_queue_veh | 3 | -1.19 | -1.29 | [-3.2, 0.82] | 3/0/0 | **INCONCLUSIVE** |
| persistence_v2x vs reactive | arrived | 3 | 0.2 | 0.24 | [-0.25, 0.65] | 2/0/1 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | total_vehicle_hours_incl_never_inserted | 3 | -0.18 | -0.25 | [-1.09, 0.73] | 2/1/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | mean_travel_time_all | 3 | -0.18 | -0.25 | [-1.09, 0.73] | 2/1/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | p95_travel_time_s | 3 | 0.1 | 0.0 | [-3.06, 3.26] | 1/1/1 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | total_waiting_s | 3 | 0.06 | 0.2 | [-2.48, 2.59] | 1/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | mean_queue_veh | 3 | -0.2 | -0.14 | [-2.82, 2.43] | 2/1/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | arrived | 3 | 0.12 | 0.0 | [-0.4, 0.64] | 1/0/2 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | total_vehicle_hours_incl_never_inserted | 3 | 0.47 | 0.36 | [-0.29, 1.24] | 0/3/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | mean_travel_time_all | 3 | 0.47 | 0.36 | [-0.29, 1.24] | 0/3/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | p95_travel_time_s | 3 | 0.19 | 1.08 | [-4.11, 4.49] | 1/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | total_waiting_s | 3 | -0.33 | -1.03 | [-5.47, 4.82] | 2/1/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | mean_queue_veh | 3 | -1.05 | -1.6 | [-4.49, 2.39] | 2/1/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | arrived | 3 | 0.16 | 0.48 | [-1.21, 1.54] | 2/1/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs baseline | total_vehicle_hours_incl_never_inserted | 3 | -0.23 | -0.34 | [-1.41, 0.96] | 2/1/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs baseline | mean_travel_time_all | 3 | -0.23 | -0.34 | [-1.41, 0.96] | 2/1/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs baseline | p95_travel_time_s | 3 | 0.32 | -1.05 | [-5.91, 6.55] | 2/1/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs baseline | total_waiting_s | 3 | 0.11 | -0.48 | [-3.68, 3.91] | 2/1/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs baseline | mean_queue_veh | 3 | 0.1 | -0.69 | [-3.41, 3.6] | 2/1/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs baseline | arrived | 3 | 0.04 | 0.0 | [-0.13, 0.21] | 1/0/2 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs reactive | total_vehicle_hours_incl_never_inserted | 3 | 0.43 | 0.45 | [-0.34, 1.2] | 0/3/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs reactive | mean_travel_time_all | 3 | 0.43 | 0.45 | [-0.34, 1.2] | 0/3/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs reactive | p95_travel_time_s | 3 | 0.38 | -0.07 | [-1.73, 2.49] | 2/1/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs reactive | total_waiting_s | 3 | -0.29 | -0.19 | [-2.98, 2.4] | 2/1/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs reactive | mean_queue_veh | 3 | -0.77 | -1.07 | [-2.38, 0.85] | 3/0/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs reactive | arrived | 3 | 0.08 | 0.12 | [-0.96, 1.12] | 2/1/0 | **INCONCLUSIVE** |
| oracle_v2x vs baseline | total_vehicle_hours_incl_never_inserted | 3 | -0.43 | -0.73 | [-1.88, 1.01] | 2/1/0 | **INCONCLUSIVE** |
| oracle_v2x vs baseline | mean_travel_time_all | 3 | -0.43 | -0.73 | [-1.88, 1.01] | 2/1/0 | **INCONCLUSIVE** |
| oracle_v2x vs baseline | p95_travel_time_s | 3 | 0.12 | -0.49 | [-6.02, 6.26] | 2/1/0 | **INCONCLUSIVE** |
| oracle_v2x vs baseline | total_waiting_s | 3 | -1.79 | -2.31 | [-5.69, 2.12] | 3/0/0 | **INCONCLUSIVE** |
| oracle_v2x vs baseline | mean_queue_veh | 3 | -1.37 | -2.77 | [-7.6, 4.87] | 2/1/0 | **INCONCLUSIVE** |
| oracle_v2x vs baseline | arrived | 3 | -0.2 | 0.0 | [-1.31, 0.92] | 1/1/1 | **INCONCLUSIVE** |
| oracle_v2x vs reactive | total_vehicle_hours_incl_never_inserted | 3 | 0.22 | 0.34 | [-0.39, 0.83] | 1/2/0 | **INCONCLUSIVE** |
| oracle_v2x vs reactive | mean_travel_time_all | 3 | 0.22 | 0.34 | [-0.39, 0.83] | 1/2/0 | **INCONCLUSIVE** |
| oracle_v2x vs reactive | p95_travel_time_s | 3 | 0.19 | -0.43 | [-3.62, 3.99] | 2/1/0 | **INCONCLUSIVE** |
| oracle_v2x vs reactive | total_waiting_s | 3 | -2.18 | -2.02 | [-4.62, 0.26] | 3/0/0 | **INCONCLUSIVE** |
| oracle_v2x vs reactive | mean_queue_veh | 3 | -2.23 | -2.2 | [-4.34, -0.12] | 3/0/0 | **HELPED** |
| oracle_v2x vs reactive | arrived | 3 | -0.16 | -0.24 | [-0.78, 0.46] | 1/2/0 | **INCONCLUSIVE** |
| random_v2x vs baseline | total_vehicle_hours_incl_never_inserted | 3 | 0.25 | -0.05 | [-1.2, 1.69] | 2/1/0 | **INCONCLUSIVE** |
| random_v2x vs baseline | mean_travel_time_all | 3 | 0.25 | -0.05 | [-1.2, 1.69] | 2/1/0 | **INCONCLUSIVE** |
| random_v2x vs baseline | p95_travel_time_s | 3 | 2.39 | 2.06 | [-2.27, 7.05] | 0/3/0 | **INCONCLUSIVE** |
| random_v2x vs baseline | total_waiting_s | 3 | 1.25 | 0.99 | [-2.2, 4.71] | 0/3/0 | **INCONCLUSIVE** |
| random_v2x vs baseline | mean_queue_veh | 3 | 0.88 | 0.36 | [-3.32, 5.08] | 1/2/0 | **INCONCLUSIVE** |
| random_v2x vs baseline | arrived | 3 | 0.2 | 0.36 | [-0.49, 0.89] | 2/1/0 | **INCONCLUSIVE** |
| random_v2x vs reactive | total_vehicle_hours_incl_never_inserted | 3 | 0.9 | 0.94 | [0.45, 1.36] | 0/3/0 | **HURT** |
| random_v2x vs reactive | mean_travel_time_all | 3 | 0.9 | 0.94 | [0.45, 1.36] | 0/3/0 | **HURT** |
| random_v2x vs reactive | p95_travel_time_s | 3 | 2.47 | 3.15 | [-0.51, 5.44] | 0/3/0 | **INCONCLUSIVE** |
| random_v2x vs reactive | total_waiting_s | 3 | 0.85 | 0.7 | [-1.36, 3.06] | 0/3/0 | **INCONCLUSIVE** |
| random_v2x vs reactive | mean_queue_veh | 3 | 0.01 | 0.04 | [-0.45, 0.47] | 1/2/0 | **INCONCLUSIVE** |
| random_v2x vs reactive | arrived | 3 | 0.24 | 0.36 | [-0.55, 1.03] | 2/1/0 | **INCONCLUSIVE** |
| predictive_v2x vs oracle_v2x | total_vehicle_hours_incl_never_inserted | 3 | 0.25 | 0.3 | [-0.38, 0.89] | 1/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs oracle_v2x | mean_travel_time_all | 3 | 0.25 | 0.3 | [-0.38, 0.89] | 1/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs oracle_v2x | p95_travel_time_s | 3 | 0.01 | -0.63 | [-4.45, 4.46] | 2/1/0 | **INCONCLUSIVE** |
| predictive_v2x vs oracle_v2x | total_waiting_s | 3 | 1.89 | 1.31 | [-1.24, 5.02] | 0/3/0 | **INCONCLUSIVE** |
| predictive_v2x vs oracle_v2x | mean_queue_veh | 3 | 1.22 | 1.54 | [-3.16, 5.59] | 1/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs oracle_v2x | arrived | 3 | 0.32 | 0.36 | [-0.72, 1.36] | 2/1/0 | **INCONCLUSIVE** |

Network (means over seeds): connected 255 vehicles · uplink TX 15187 RX 15187 PDR 1.0 lat med 0.0 p95 0.0 ms · downlink TX 17 RX 17 dropped 0 expired 0 PDR 1.0 lat med 0.0 p95 0.0 ms · reroutes applied 47 · inapplicable 3

- s101 baseline: veh-h 187.7333, mean tt 769 s, p95 1406 s, arrived 832, teleports 0, reroutes applied 0, sim `sim_v2x_s101_baseline_ideal_p30`
- s101 reactive: veh-h 186.3278, mean tt 763 s, p95 1391 s, arrived 836, teleports 0, reroutes applied 0, sim `sim_v2x_s101_reactive_ideal_p30`
- s101 persistence_v2x: veh-h 186.7806, mean tt 765 s, p95 1400 s, arrived 836, teleports 0, reroutes applied 17, sim `sim_v2x_s101_persistence_v2x_ideal_p30`
- s101 predictive_v2x: veh-h 186.7747, mean tt 765 s, p95 1406 s, arrived 832, teleports 0, reroutes applied 16, sim `sim_v2x_s101_predictive_v2x_ideal_p30`
- s101 predictive_corrected_v2x: veh-h 186.5361, mean tt 764 s, p95 1389 s, arrived 833, teleports 0, reroutes applied 19, sim `sim_v2x_s101_predictive_corrected_v2x_ideal_p30`
- s101 oracle_v2x: veh-h 186.2097, mean tt 763 s, p95 1378 s, arrived 833, teleports 0, reroutes applied 32, sim `sim_v2x_s101_oracle_v2x_ideal_p30`
- s101 random_v2x: veh-h 187.6408, mean tt 768 s, p95 1435 s, arrived 835, teleports 0, reroutes applied 27, sim `sim_v2x_s101_random_v2x_ideal_p30`
- s102 baseline: veh-h 185.9344, mean tt 761 s, p95 1431 s, arrived 824, teleports 0, reroutes applied 0, sim `sim_v2x_s102_baseline_ideal_p30`
- s102 reactive: veh-h 183.9594, mean tt 753 s, p95 1397 s, arrived 823, teleports 0, reroutes applied 0, sim `sim_v2x_s102_reactive_ideal_p30`
- s102 persistence_v2x: veh-h 184.4569, mean tt 755 s, p95 1414 s, arrived 825, teleports 0, reroutes applied 17, sim `sim_v2x_s102_persistence_v2x_ideal_p30`
- s102 predictive_v2x: veh-h 185.475, mean tt 759 s, p95 1415 s, arrived 827, teleports 0, reroutes applied 18, sim `sim_v2x_s102_predictive_v2x_ideal_p30`
- s102 predictive_corrected_v2x: veh-h 185.3017, mean tt 758 s, p95 1416 s, arrived 824, teleports 0, reroutes applied 22, sim `sim_v2x_s102_predictive_corrected_v2x_ideal_p30`
- s102 oracle_v2x: veh-h 184.5828, mean tt 755 s, p95 1424 s, arrived 824, teleports 0, reroutes applied 38, sim `sim_v2x_s102_oracle_v2x_ideal_p30`
- s102 random_v2x: veh-h 185.6917, mean tt 760 s, p95 1441 s, arrived 827, teleports 0, reroutes applied 31, sim `sim_v2x_s102_random_v2x_ideal_p30`
- s103 baseline: veh-h 180.2839, mean tt 736 s, p95 1338 s, arrived 843, teleports 0, reroutes applied 0, sim `sim_v2x_s103_baseline_ideal_p30`
- s103 reactive: veh-h 180.0164, mean tt 735 s, p95 1382 s, arrived 839, teleports 0, reroutes applied 0, sim `sim_v2x_s103_reactive_ideal_p30`
- s103 persistence_v2x: veh-h 181.1667, mean tt 739 s, p95 1373 s, arrived 842, teleports 0, reroutes applied 12, sim `sim_v2x_s103_persistence_v2x_ideal_p30`
- s103 predictive_v2x: veh-h 180.6656, mean tt 737 s, p95 1357 s, arrived 843, teleports 0, reroutes applied 13, sim `sim_v2x_s103_predictive_v2x_ideal_p30`
- s103 predictive_corrected_v2x: veh-h 180.8183, mean tt 738 s, p95 1381 s, arrived 843, teleports 0, reroutes applied 15, sim `sim_v2x_s103_predictive_corrected_v2x_ideal_p30`
- s103 oracle_v2x: veh-h 180.7053, mean tt 738 s, p95 1376 s, arrived 837, teleports 0, reroutes applied 39, sim `sim_v2x_s103_oracle_v2x_ideal_p30`
- s103 random_v2x: veh-h 181.9369, mean tt 743 s, p95 1397 s, arrived 842, teleports 0, reroutes applied 28, sim `sim_v2x_s103_random_v2x_ideal_p30`
