# V2X closed loop — V2X_CLOSED_LOOP_v1 · la_c4_central_wide · profile `ideal` · penetration 0.3 · seeds [101, 102, 103]

Model Graph WaveNet (207-node METR-LA, verified) (ckpt `548e399bd53c`), 83 of 207 detectors mapped, routing config `ea08dddedc14`. SYNTHETIC_WHAT_IF randomTrips on the real OSM network, one draw per seed, departures 0-1800 s. REAL METR-LA detector speeds (mph), replayed as lane speed caps on mapped edges in every arm. SIMULATED V2X (pipeline/v2x/channel.py) — not radio hardware: latency 0.0 ms ± 0.0, loss 0.0, TTL 60.0 s.

Identical-state fork at 480 s: state hashes {101: 'bd20b216eaeb', 102: '12a122bf1d08', 103: '0f9a687dc09c'} — identical across arms: **True**. Reroutes applied by arm: {'baseline': 0, 'reactive': 0, 'oracle_full_v2x': 254, 'oracle_netfull_v2x': 234}.

| pair | metric | n | mean % | median % | 95 % CI | W/L/T | label |
|---|---|---|---|---|---|---|---|
| reactive vs baseline | total_vehicle_hours_incl_never_inserted | 3 | -0.65 | -0.75 | [-1.81, 0.5] | 3/0/0 | **INCONCLUSIVE** |
| reactive vs baseline | mean_travel_time_all | 3 | -0.65 | -0.75 | [-1.81, 0.5] | 3/0/0 | **INCONCLUSIVE** |
| reactive vs baseline | p95_travel_time_s | 3 | -0.05 | -1.07 | [-7.42, 7.32] | 2/1/0 | **INCONCLUSIVE** |
| reactive vs baseline | total_waiting_s | 3 | 0.41 | 0.95 | [-4.46, 5.28] | 1/2/0 | **INCONCLUSIVE** |
| reactive vs baseline | mean_queue_veh | 3 | 0.88 | 0.33 | [-3.79, 5.54] | 1/2/0 | **INCONCLUSIVE** |
| reactive vs baseline | arrived | 3 | -0.04 | -0.12 | [-1.24, 1.16] | 1/2/0 | **INCONCLUSIVE** |
| oracle_full_v2x vs baseline | total_vehicle_hours_incl_never_inserted | 3 | -0.36 | -0.48 | [-1.26, 0.55] | 2/1/0 | **INCONCLUSIVE** |
| oracle_full_v2x vs baseline | mean_travel_time_all | 3 | -0.36 | -0.48 | [-1.26, 0.55] | 2/1/0 | **INCONCLUSIVE** |
| oracle_full_v2x vs baseline | p95_travel_time_s | 3 | 1.03 | 0.28 | [-3.76, 5.81] | 1/2/0 | **INCONCLUSIVE** |
| oracle_full_v2x vs baseline | total_waiting_s | 3 | -2.47 | -2.84 | [-6.4, 1.46] | 3/0/0 | **INCONCLUSIVE** |
| oracle_full_v2x vs baseline | mean_queue_veh | 3 | -3.01 | -3.87 | [-8.0, 1.98] | 3/0/0 | **INCONCLUSIVE** |
| oracle_full_v2x vs baseline | arrived | 3 | 0.04 | 0.12 | [-0.58, 0.66] | 2/1/0 | **INCONCLUSIVE** |
| oracle_full_v2x vs reactive | total_vehicle_hours_incl_never_inserted | 3 | 0.3 | 0.2 | [-0.33, 0.93] | 0/3/0 | **INCONCLUSIVE** |
| oracle_full_v2x vs reactive | mean_travel_time_all | 3 | 0.3 | 0.2 | [-0.33, 0.93] | 0/3/0 | **INCONCLUSIVE** |
| oracle_full_v2x vs reactive | p95_travel_time_s | 3 | 1.1 | 1.37 | [-1.54, 3.74] | 1/2/0 | **INCONCLUSIVE** |
| oracle_full_v2x vs reactive | total_waiting_s | 3 | -2.86 | -2.73 | [-4.93, -0.8] | 3/0/0 | **HELPED** |
| oracle_full_v2x vs reactive | mean_queue_veh | 3 | -3.86 | -3.81 | [-4.62, -3.1] | 3/0/0 | **HELPED** |
| oracle_full_v2x vs reactive | arrived | 3 | 0.08 | 0.24 | [-0.61, 0.77] | 2/1/0 | **INCONCLUSIVE** |
| oracle_netfull_v2x vs baseline | total_vehicle_hours_incl_never_inserted | 3 | -0.37 | -0.39 | [-1.94, 1.21] | 2/1/0 | **INCONCLUSIVE** |
| oracle_netfull_v2x vs baseline | mean_travel_time_all | 3 | -0.37 | -0.39 | [-1.94, 1.21] | 2/1/0 | **INCONCLUSIVE** |
| oracle_netfull_v2x vs baseline | p95_travel_time_s | 3 | 0.26 | -0.7 | [-4.51, 5.02] | 2/1/0 | **INCONCLUSIVE** |
| oracle_netfull_v2x vs baseline | total_waiting_s | 3 | -3.04 | -3.83 | [-8.45, 2.37] | 3/0/0 | **INCONCLUSIVE** |
| oracle_netfull_v2x vs baseline | mean_queue_veh | 3 | -3.04 | -3.36 | [-8.4, 2.32] | 3/0/0 | **INCONCLUSIVE** |
| oracle_netfull_v2x vs baseline | arrived | 3 | -0.16 | -0.24 | [-1.37, 1.05] | 1/2/0 | **INCONCLUSIVE** |
| oracle_netfull_v2x vs reactive | total_vehicle_hours_incl_never_inserted | 3 | 0.29 | 0.43 | [-0.9, 1.47] | 1/2/0 | **INCONCLUSIVE** |
| oracle_netfull_v2x vs reactive | mean_travel_time_all | 3 | 0.29 | 0.43 | [-0.9, 1.47] | 1/2/0 | **INCONCLUSIVE** |
| oracle_netfull_v2x vs reactive | p95_travel_time_s | 3 | 0.33 | 0.07 | [-2.84, 3.5] | 1/2/0 | **INCONCLUSIVE** |
| oracle_netfull_v2x vs reactive | total_waiting_s | 3 | -3.43 | -3.0 | [-6.28, -0.59] | 3/0/0 | **HELPED** |
| oracle_netfull_v2x vs reactive | mean_queue_veh | 3 | -3.88 | -3.6 | [-7.19, -0.57] | 3/0/0 | **HELPED** |
| oracle_netfull_v2x vs reactive | arrived | 3 | -0.12 | -0.12 | [-1.02, 0.78] | 1/2/0 | **INCONCLUSIVE** |
- s101 baseline: veh-h 187.7333, mean tt 769 s, p95 1406 s, arrived 832, teleports 0, reroutes applied 0, sim `sim_v2x_s101_baseline_ideal_p30`
- s101 reactive: veh-h 186.3278, mean tt 763 s, p95 1391 s, arrived 836, teleports 0, reroutes applied 0, sim `sim_v2x_s101_reactive_ideal_p30`
- s101 oracle_full_v2x: veh-h 186.5308, mean tt 764 s, p95 1410 s, arrived 834, teleports 0, reroutes applied 77, sim `sim_v2x_s101_oracle_full_v2x_ideal_p30`
- s101 oracle_netfull_v2x: veh-h 185.8758, mean tt 761 s, p95 1392 s, arrived 835, teleports 1, reroutes applied 73, sim `sim_v2x_s101_oracle_netfull_v2x_ideal_p30`
- s102 baseline: veh-h 185.9344, mean tt 761 s, p95 1431 s, arrived 824, teleports 0, reroutes applied 0, sim `sim_v2x_s102_baseline_ideal_p30`
- s102 reactive: veh-h 183.9594, mean tt 753 s, p95 1397 s, arrived 823, teleports 0, reroutes applied 0, sim `sim_v2x_s102_reactive_ideal_p30`
- s102 oracle_full_v2x: veh-h 185.0383, mean tt 757 s, p95 1425 s, arrived 825, teleports 0, reroutes applied 102, sim `sim_v2x_s102_oracle_full_v2x_ideal_p30`
- s102 oracle_netfull_v2x: veh-h 185.2083, mean tt 758 s, p95 1421 s, arrived 819, teleports 0, reroutes applied 84, sim `sim_v2x_s102_oracle_netfull_v2x_ideal_p30`
- s103 baseline: veh-h 180.2839, mean tt 736 s, p95 1338 s, arrived 843, teleports 0, reroutes applied 0, sim `sim_v2x_s103_baseline_ideal_p30`
- s103 reactive: veh-h 180.0164, mean tt 735 s, p95 1382 s, arrived 839, teleports 0, reroutes applied 0, sim `sim_v2x_s103_reactive_ideal_p30`
- s103 oracle_full_v2x: veh-h 180.3856, mean tt 736 s, p95 1381 s, arrived 841, teleports 0, reroutes applied 75, sim `sim_v2x_s103_oracle_full_v2x_ideal_p30`
- s103 oracle_netfull_v2x: veh-h 180.79, mean tt 738 s, p95 1371 s, arrived 841, teleports 0, reroutes applied 77, sim `sim_v2x_s103_oracle_netfull_v2x_ideal_p30`
