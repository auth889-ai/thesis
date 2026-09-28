# V2X closed loop — V2X_CLOSED_LOOP_v1 · la_c4_central_wide · profile `ideal` · penetration 0.3 · seeds [101, 102, 103]

Model Graph WaveNet (207-node METR-LA, verified) (ckpt `548e399bd53c`), 83 of 207 detectors mapped, routing config `ea08dddedc14`. SYNTHETIC_WHAT_IF randomTrips on the real OSM network, one draw per seed, departures 0-1800 s. REAL METR-LA detector speeds (mph), replayed as lane speed caps on mapped edges in every arm. SIMULATED V2X (pipeline/v2x/channel.py) — not radio hardware: latency 0.0 ms ± 0.0, loss 0.0, TTL 60.0 s.

Identical-state fork at 480 s: state hashes {101: 'bd20b216eaeb', 102: '12a122bf1d08', 103: '0f9a687dc09c'} — identical across arms: **True**. Reroutes applied by arm: {'baseline': 0, 'reactive': 0, 'oracle_v2x': 109, 'oracle_div_v2x': 105, 'oracle_cap_v2x': 105, 'oracle_net_v2x': 105}.

| pair | metric | n | mean % | median % | 95 % CI | W/L/T | label |
|---|---|---|---|---|---|---|---|
| reactive vs baseline | total_vehicle_hours_incl_never_inserted | 3 | -0.65 | -0.75 | [-1.81, 0.5] | 3/0/0 | **INCONCLUSIVE** |
| reactive vs baseline | mean_travel_time_all | 3 | -0.65 | -0.75 | [-1.81, 0.5] | 3/0/0 | **INCONCLUSIVE** |
| reactive vs baseline | p95_travel_time_s | 3 | -0.05 | -1.07 | [-7.42, 7.32] | 2/1/0 | **INCONCLUSIVE** |
| reactive vs baseline | total_waiting_s | 3 | 0.41 | 0.95 | [-4.46, 5.28] | 1/2/0 | **INCONCLUSIVE** |
| reactive vs baseline | mean_queue_veh | 3 | 0.88 | 0.33 | [-3.79, 5.54] | 1/2/0 | **INCONCLUSIVE** |
| reactive vs baseline | arrived | 3 | -0.04 | -0.12 | [-1.24, 1.16] | 1/2/0 | **INCONCLUSIVE** |
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
| oracle_div_v2x vs baseline | total_vehicle_hours_incl_never_inserted | 3 | -0.39 | -0.61 | [-2.47, 1.69] | 2/1/0 | **INCONCLUSIVE** |
| oracle_div_v2x vs baseline | mean_travel_time_all | 3 | -0.39 | -0.61 | [-2.47, 1.69] | 2/1/0 | **INCONCLUSIVE** |
| oracle_div_v2x vs baseline | p95_travel_time_s | 3 | 0.19 | -1.47 | [-7.62, 7.99] | 2/1/0 | **INCONCLUSIVE** |
| oracle_div_v2x vs baseline | total_waiting_s | 3 | -2.07 | -2.21 | [-8.76, 4.62] | 2/1/0 | **INCONCLUSIVE** |
| oracle_div_v2x vs baseline | mean_queue_veh | 3 | -2.67 | -2.81 | [-8.8, 3.46] | 3/0/0 | **INCONCLUSIVE** |
| oracle_div_v2x vs baseline | arrived | 3 | 0.04 | 0.0 | [-0.13, 0.21] | 1/0/2 | **INCONCLUSIVE** |
| oracle_div_v2x vs reactive | total_vehicle_hours_incl_never_inserted | 3 | 0.26 | 0.14 | [-0.67, 1.19] | 1/2/0 | **INCONCLUSIVE** |
| oracle_div_v2x vs reactive | mean_travel_time_all | 3 | 0.26 | 0.14 | [-0.67, 1.19] | 1/2/0 | **INCONCLUSIVE** |
| oracle_div_v2x vs reactive | p95_travel_time_s | 3 | 0.24 | 0.51 | [-1.89, 2.37] | 1/2/0 | **INCONCLUSIVE** |
| oracle_div_v2x vs reactive | total_waiting_s | 3 | -2.48 | -2.98 | [-4.96, 0.0] | 3/0/0 | **INCONCLUSIVE** |
| oracle_div_v2x vs reactive | mean_queue_veh | 3 | -3.52 | -3.13 | [-5.47, -1.57] | 3/0/0 | **HELPED** |
| oracle_div_v2x vs reactive | arrived | 3 | 0.08 | 0.24 | [-1.16, 1.32] | 2/1/0 | **INCONCLUSIVE** |
| oracle_cap_v2x vs baseline | total_vehicle_hours_incl_never_inserted | 3 | -0.41 | -0.66 | [-1.96, 1.14] | 2/1/0 | **INCONCLUSIVE** |
| oracle_cap_v2x vs baseline | mean_travel_time_all | 3 | -0.41 | -0.66 | [-1.96, 1.14] | 2/1/0 | **INCONCLUSIVE** |
| oracle_cap_v2x vs baseline | p95_travel_time_s | 3 | 0.55 | -0.42 | [-4.57, 5.67] | 2/1/0 | **INCONCLUSIVE** |
| oracle_cap_v2x vs baseline | total_waiting_s | 3 | -1.83 | -1.56 | [-7.83, 4.17] | 2/1/0 | **INCONCLUSIVE** |
| oracle_cap_v2x vs baseline | mean_queue_veh | 3 | -1.97 | -2.21 | [-7.25, 3.32] | 2/1/0 | **INCONCLUSIVE** |
| oracle_cap_v2x vs baseline | arrived | 3 | 0.04 | 0.0 | [-0.42, 0.5] | 1/1/1 | **INCONCLUSIVE** |
| oracle_cap_v2x vs reactive | total_vehicle_hours_incl_never_inserted | 3 | 0.24 | 0.19 | [-0.21, 0.7] | 0/3/0 | **INCONCLUSIVE** |
| oracle_cap_v2x vs reactive | mean_travel_time_all | 3 | 0.24 | 0.19 | [-0.21, 0.7] | 0/3/0 | **INCONCLUSIVE** |
| oracle_cap_v2x vs reactive | p95_travel_time_s | 3 | 0.62 | 0.22 | [-2.45, 3.68] | 1/2/0 | **INCONCLUSIVE** |
| oracle_cap_v2x vs reactive | total_waiting_s | 3 | -2.24 | -2.49 | [-3.69, -0.79] | 3/0/0 | **HELPED** |
| oracle_cap_v2x vs reactive | mean_queue_veh | 3 | -2.82 | -2.62 | [-3.89, -1.75] | 3/0/0 | **HELPED** |
| oracle_cap_v2x vs reactive | arrived | 3 | 0.08 | 0.0 | [-0.83, 0.98] | 1/1/1 | **INCONCLUSIVE** |
| oracle_net_v2x vs baseline | total_vehicle_hours_incl_never_inserted | 3 | -0.39 | -0.61 | [-2.47, 1.69] | 2/1/0 | **INCONCLUSIVE** |
| oracle_net_v2x vs baseline | mean_travel_time_all | 3 | -0.39 | -0.61 | [-2.47, 1.69] | 2/1/0 | **INCONCLUSIVE** |
| oracle_net_v2x vs baseline | p95_travel_time_s | 3 | 0.19 | -1.47 | [-7.62, 7.99] | 2/1/0 | **INCONCLUSIVE** |
| oracle_net_v2x vs baseline | total_waiting_s | 3 | -2.07 | -2.21 | [-8.76, 4.62] | 2/1/0 | **INCONCLUSIVE** |
| oracle_net_v2x vs baseline | mean_queue_veh | 3 | -2.67 | -2.81 | [-8.8, 3.46] | 3/0/0 | **INCONCLUSIVE** |
| oracle_net_v2x vs baseline | arrived | 3 | 0.04 | 0.0 | [-0.13, 0.21] | 1/0/2 | **INCONCLUSIVE** |
| oracle_net_v2x vs reactive | total_vehicle_hours_incl_never_inserted | 3 | 0.26 | 0.14 | [-0.67, 1.19] | 1/2/0 | **INCONCLUSIVE** |
| oracle_net_v2x vs reactive | mean_travel_time_all | 3 | 0.26 | 0.14 | [-0.67, 1.19] | 1/2/0 | **INCONCLUSIVE** |
| oracle_net_v2x vs reactive | p95_travel_time_s | 3 | 0.24 | 0.51 | [-1.89, 2.37] | 1/2/0 | **INCONCLUSIVE** |
| oracle_net_v2x vs reactive | total_waiting_s | 3 | -2.48 | -2.98 | [-4.96, 0.0] | 3/0/0 | **INCONCLUSIVE** |
| oracle_net_v2x vs reactive | mean_queue_veh | 3 | -3.52 | -3.13 | [-5.47, -1.57] | 3/0/0 | **HELPED** |
| oracle_net_v2x vs reactive | arrived | 3 | 0.08 | 0.24 | [-1.16, 1.32] | 2/1/0 | **INCONCLUSIVE** |
| oracle_div_v2x vs oracle_v2x | total_vehicle_hours_incl_never_inserted | 3 | 0.04 | 0.2 | [-0.86, 0.95] | 1/2/0 | **INCONCLUSIVE** |
| oracle_div_v2x vs oracle_v2x | mean_travel_time_all | 3 | 0.04 | 0.2 | [-0.86, 0.95] | 1/2/0 | **INCONCLUSIVE** |
| oracle_div_v2x vs oracle_v2x | p95_travel_time_s | 3 | 0.06 | 0.22 | [-2.36, 2.48] | 1/2/0 | **INCONCLUSIVE** |
| oracle_div_v2x vs oracle_v2x | total_waiting_s | 3 | -0.3 | 0.1 | [-3.43, 2.83] | 1/2/0 | **INCONCLUSIVE** |
| oracle_div_v2x vs oracle_v2x | mean_queue_veh | 3 | -1.32 | -1.64 | [-4.18, 1.54] | 3/0/0 | **INCONCLUSIVE** |
| oracle_div_v2x vs oracle_v2x | arrived | 3 | 0.24 | 0.12 | [-0.83, 1.31] | 2/1/0 | **INCONCLUSIVE** |
| oracle_cap_v2x vs oracle_v2x | total_vehicle_hours_incl_never_inserted | 3 | 0.02 | 0.06 | [-0.37, 0.41] | 1/2/0 | **INCONCLUSIVE** |
| oracle_cap_v2x vs oracle_v2x | mean_travel_time_all | 3 | 0.02 | 0.06 | [-0.37, 0.41] | 1/2/0 | **INCONCLUSIVE** |
| oracle_cap_v2x vs oracle_v2x | p95_travel_time_s | 3 | 0.43 | 0.07 | [-1.13, 2.0] | 0/3/0 | **INCONCLUSIVE** |
| oracle_cap_v2x vs oracle_v2x | total_waiting_s | 3 | -0.05 | 0.46 | [-2.94, 2.83] | 1/2/0 | **INCONCLUSIVE** |
| oracle_cap_v2x vs oracle_v2x | mean_queue_veh | 3 | -0.6 | -1.14 | [-3.14, 1.94] | 2/1/0 | **INCONCLUSIVE** |
| oracle_cap_v2x vs oracle_v2x | arrived | 3 | 0.24 | 0.12 | [-0.83, 1.31] | 2/1/0 | **INCONCLUSIVE** |
| oracle_net_v2x vs oracle_v2x | total_vehicle_hours_incl_never_inserted | 3 | 0.04 | 0.2 | [-0.86, 0.95] | 1/2/0 | **INCONCLUSIVE** |
| oracle_net_v2x vs oracle_v2x | mean_travel_time_all | 3 | 0.04 | 0.2 | [-0.86, 0.95] | 1/2/0 | **INCONCLUSIVE** |
| oracle_net_v2x vs oracle_v2x | p95_travel_time_s | 3 | 0.06 | 0.22 | [-2.36, 2.48] | 1/2/0 | **INCONCLUSIVE** |
| oracle_net_v2x vs oracle_v2x | total_waiting_s | 3 | -0.3 | 0.1 | [-3.43, 2.83] | 1/2/0 | **INCONCLUSIVE** |
| oracle_net_v2x vs oracle_v2x | mean_queue_veh | 3 | -1.32 | -1.64 | [-4.18, 1.54] | 3/0/0 | **INCONCLUSIVE** |
| oracle_net_v2x vs oracle_v2x | arrived | 3 | 0.24 | 0.12 | [-0.83, 1.31] | 2/1/0 | **INCONCLUSIVE** |
- s101 baseline: veh-h 187.7333, mean tt 769 s, p95 1406 s, arrived 832, teleports 0, reroutes applied 0, sim `sim_v2x_s101_baseline_ideal_p30`
- s101 reactive: veh-h 186.3278, mean tt 763 s, p95 1391 s, arrived 836, teleports 0, reroutes applied 0, sim `sim_v2x_s101_reactive_ideal_p30`
- s101 oracle_v2x: veh-h 186.2097, mean tt 763 s, p95 1378 s, arrived 833, teleports 0, reroutes applied 32, sim `sim_v2x_s101_oracle_v2x_ideal_p30`
- s101 oracle_div_v2x: veh-h 186.5864, mean tt 764 s, p95 1381 s, arrived 832, teleports 0, reroutes applied 33, sim `sim_v2x_s101_oracle_div_v2x_ideal_p30`
- s101 oracle_cap_v2x: veh-h 186.4981, mean tt 764 s, p95 1394 s, arrived 834, teleports 0, reroutes applied 31, sim `sim_v2x_s101_oracle_cap_v2x_ideal_p30`
- s101 oracle_net_v2x: veh-h 186.5864, mean tt 764 s, p95 1381 s, arrived 832, teleports 0, reroutes applied 33, sim `sim_v2x_s101_oracle_net_v2x_ideal_p30`
- s102 baseline: veh-h 185.9344, mean tt 761 s, p95 1431 s, arrived 824, teleports 0, reroutes applied 0, sim `sim_v2x_s102_baseline_ideal_p30`
- s102 reactive: veh-h 183.9594, mean tt 753 s, p95 1397 s, arrived 823, teleports 0, reroutes applied 0, sim `sim_v2x_s102_reactive_ideal_p30`
- s102 oracle_v2x: veh-h 184.5828, mean tt 755 s, p95 1424 s, arrived 824, teleports 0, reroutes applied 38, sim `sim_v2x_s102_oracle_v2x_ideal_p30`
- s102 oracle_div_v2x: veh-h 183.8947, mean tt 752 s, p95 1410 s, arrived 825, teleports 0, reroutes applied 39, sim `sim_v2x_s102_oracle_div_v2x_ideal_p30`
- s102 oracle_cap_v2x: veh-h 184.3011, mean tt 754 s, p95 1425 s, arrived 823, teleports 0, reroutes applied 38, sim `sim_v2x_s102_oracle_cap_v2x_ideal_p30`
- s102 oracle_net_v2x: veh-h 183.8947, mean tt 752 s, p95 1410 s, arrived 825, teleports 0, reroutes applied 39, sim `sim_v2x_s102_oracle_net_v2x_ideal_p30`
- s103 baseline: veh-h 180.2839, mean tt 736 s, p95 1338 s, arrived 843, teleports 0, reroutes applied 0, sim `sim_v2x_s103_baseline_ideal_p30`
- s103 reactive: veh-h 180.0164, mean tt 735 s, p95 1382 s, arrived 839, teleports 0, reroutes applied 0, sim `sim_v2x_s103_reactive_ideal_p30`
- s103 oracle_v2x: veh-h 180.7053, mean tt 738 s, p95 1376 s, arrived 837, teleports 0, reroutes applied 39, sim `sim_v2x_s103_oracle_v2x_ideal_p30`
- s103 oracle_div_v2x: veh-h 181.2461, mean tt 740 s, p95 1389 s, arrived 843, teleports 0, reroutes applied 33, sim `sim_v2x_s103_oracle_div_v2x_ideal_p30`
- s103 oracle_cap_v2x: veh-h 180.8167, mean tt 738 s, p95 1377 s, arrived 843, teleports 0, reroutes applied 36, sim `sim_v2x_s103_oracle_cap_v2x_ideal_p30`
- s103 oracle_net_v2x: veh-h 181.2461, mean tt 740 s, p95 1389 s, arrived 843, teleports 0, reroutes applied 33, sim `sim_v2x_s103_oracle_net_v2x_ideal_p30`
