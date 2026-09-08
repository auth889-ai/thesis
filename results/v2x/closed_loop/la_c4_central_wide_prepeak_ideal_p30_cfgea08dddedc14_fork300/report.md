# V2X closed loop — V2X_CLOSED_LOOP_v1 · la_c4_central_wide · profile `ideal` · penetration 0.3 · seeds [101, 102, 103]

Model Graph WaveNet (207-node METR-LA, verified) (ckpt `548e399bd53c`), 83 of 207 detectors mapped, routing config `ea08dddedc14`. SYNTHETIC_WHAT_IF randomTrips on the real OSM network, one draw per seed, departures 0-1800 s. REAL METR-LA detector speeds (mph), replayed as lane speed caps on mapped edges in every arm. SIMULATED V2X (pipeline/v2x/channel.py) — not radio hardware: latency 0.0 ms ± 0.0, loss 0.0, TTL 60.0 s.

Identical-state fork at 300 s: state hashes {101: '824cc121047c', 102: '63bad18676ab', 103: 'cf6dfe59c8ac'} — identical across arms: **True**. Reroutes applied by arm: {'baseline': 0, 'reactive': 0, 'persistence_v2x': 36, 'predictive_v2x': 36, 'oracle_v2x': 102}.

| pair | metric | n | mean % | median % | 95 % CI | W/L/T | label |
|---|---|---|---|---|---|---|---|
| reactive vs baseline | total_vehicle_hours_incl_never_inserted | 3 | -0.34 | -0.12 | [-1.57, 0.89] | 2/1/0 | **INCONCLUSIVE** |
| reactive vs baseline | mean_travel_time_all | 3 | -0.34 | -0.12 | [-1.57, 0.89] | 2/1/0 | **INCONCLUSIVE** |
| reactive vs baseline | p95_travel_time_s | 3 | -0.12 | -0.38 | [-2.43, 2.19] | 2/1/0 | **INCONCLUSIVE** |
| reactive vs baseline | total_waiting_s | 3 | 0.13 | 0.5 | [-2.35, 2.62] | 1/2/0 | **INCONCLUSIVE** |
| reactive vs baseline | mean_queue_veh | 3 | -0.14 | -0.28 | [-3.93, 3.65] | 2/1/0 | **INCONCLUSIVE** |
| reactive vs baseline | arrived | 3 | 0.08 | 0.12 | [-0.37, 0.52] | 2/1/0 | **INCONCLUSIVE** |
| persistence_v2x vs baseline | total_vehicle_hours_incl_never_inserted | 3 | 0.12 | 0.19 | [-0.81, 1.05] | 1/2/0 | **INCONCLUSIVE** |
| persistence_v2x vs baseline | mean_travel_time_all | 3 | 0.12 | 0.19 | [-0.81, 1.05] | 1/2/0 | **INCONCLUSIVE** |
| persistence_v2x vs baseline | p95_travel_time_s | 3 | -0.2 | -0.07 | [-1.44, 1.04] | 2/1/0 | **INCONCLUSIVE** |
| persistence_v2x vs baseline | total_waiting_s | 3 | 1.52 | 1.83 | [-0.22, 3.25] | 0/3/0 | **INCONCLUSIVE** |
| persistence_v2x vs baseline | mean_queue_veh | 3 | 1.1 | 0.91 | [-1.6, 3.79] | 0/3/0 | **INCONCLUSIVE** |
| persistence_v2x vs baseline | arrived | 3 | 0.08 | -0.23 | [-1.27, 1.42] | 1/2/0 | **INCONCLUSIVE** |
| persistence_v2x vs reactive | total_vehicle_hours_incl_never_inserted | 3 | 0.46 | 0.44 | [0.07, 0.85] | 0/3/0 | **HURT** |
| persistence_v2x vs reactive | mean_travel_time_all | 3 | 0.46 | 0.44 | [0.07, 0.85] | 0/3/0 | **HURT** |
| persistence_v2x vs reactive | p95_travel_time_s | 3 | -0.07 | 0.15 | [-2.09, 1.94] | 1/2/0 | **INCONCLUSIVE** |
| persistence_v2x vs reactive | total_waiting_s | 3 | 1.39 | 1.09 | [-1.96, 4.73] | 0/3/0 | **INCONCLUSIVE** |
| persistence_v2x vs reactive | mean_queue_veh | 3 | 1.24 | 1.19 | [0.08, 2.4] | 0/3/0 | **HURT** |
| persistence_v2x vs reactive | arrived | 3 | -0.0 | -0.12 | [-1.05, 1.04] | 1/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | total_vehicle_hours_incl_never_inserted | 3 | 0.06 | 0.2 | [-0.7, 0.82] | 1/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | mean_travel_time_all | 3 | 0.06 | 0.2 | [-0.7, 0.82] | 1/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | p95_travel_time_s | 3 | -0.35 | -1.27 | [-5.18, 4.48] | 2/1/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | total_waiting_s | 3 | 1.08 | 0.96 | [-0.6, 2.76] | 0/3/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | mean_queue_veh | 3 | 1.1 | 0.97 | [-1.38, 3.57] | 0/3/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | arrived | 3 | -0.12 | -0.12 | [-1.87, 1.63] | 1/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | total_vehicle_hours_incl_never_inserted | 3 | 0.4 | 0.32 | [-0.08, 0.87] | 0/3/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | mean_travel_time_all | 3 | 0.4 | 0.32 | [-0.08, 0.87] | 0/3/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | p95_travel_time_s | 3 | -0.23 | -0.76 | [-2.82, 2.36] | 2/1/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | total_waiting_s | 3 | 0.96 | 0.46 | [-3.23, 5.14] | 1/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | mean_queue_veh | 3 | 1.24 | 1.25 | [-0.13, 2.61] | 0/3/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | arrived | 3 | -0.2 | -0.23 | [-1.51, 1.12] | 1/2/0 | **INCONCLUSIVE** |
| oracle_v2x vs baseline | total_vehicle_hours_incl_never_inserted | 3 | -0.08 | 0.1 | [-1.24, 1.08] | 1/2/0 | **INCONCLUSIVE** |
| oracle_v2x vs baseline | mean_travel_time_all | 3 | -0.08 | 0.1 | [-1.24, 1.08] | 1/2/0 | **INCONCLUSIVE** |
| oracle_v2x vs baseline | p95_travel_time_s | 3 | 0.73 | 0.23 | [-1.43, 2.88] | 0/3/0 | **INCONCLUSIVE** |
| oracle_v2x vs baseline | total_waiting_s | 3 | -0.45 | 0.2 | [-3.85, 2.96] | 1/2/0 | **INCONCLUSIVE** |
| oracle_v2x vs baseline | mean_queue_veh | 3 | -1.11 | -0.87 | [-4.71, 2.48] | 2/1/0 | **INCONCLUSIVE** |
| oracle_v2x vs baseline | arrived | 3 | 0.12 | 0.0 | [-0.39, 0.62] | 1/0/2 | **INCONCLUSIVE** |
| oracle_v2x vs reactive | total_vehicle_hours_incl_never_inserted | 3 | 0.26 | 0.29 | [-0.11, 0.63] | 0/3/0 | **INCONCLUSIVE** |
| oracle_v2x vs reactive | mean_travel_time_all | 3 | 0.26 | 0.29 | [-0.11, 0.63] | 0/3/0 | **INCONCLUSIVE** |
| oracle_v2x vs reactive | p95_travel_time_s | 3 | 0.86 | 0.6 | [-3.31, 5.03] | 1/2/0 | **INCONCLUSIVE** |
| oracle_v2x vs reactive | total_waiting_s | 3 | -0.58 | -0.42 | [-1.56, 0.4] | 3/0/0 | **INCONCLUSIVE** |
| oracle_v2x vs reactive | mean_queue_veh | 3 | -0.98 | -1.1 | [-1.82, -0.14] | 3/0/0 | **HELPED** |
| oracle_v2x vs reactive | arrived | 3 | 0.04 | 0.12 | [-0.3, 0.38] | 2/1/0 | **INCONCLUSIVE** |
| predictive_v2x vs oracle_v2x | total_vehicle_hours_incl_never_inserted | 3 | 0.14 | 0.17 | [-0.35, 0.63] | 1/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs oracle_v2x | mean_travel_time_all | 3 | 0.14 | 0.17 | [-0.35, 0.63] | 1/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs oracle_v2x | p95_travel_time_s | 3 | -1.05 | -1.5 | [-7.32, 5.21] | 2/1/0 | **INCONCLUSIVE** |
| predictive_v2x vs oracle_v2x | total_waiting_s | 3 | 1.55 | 0.76 | [-3.6, 6.7] | 1/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs oracle_v2x | mean_queue_veh | 3 | 2.24 | 1.95 | [0.78, 3.7] | 0/3/0 | **HURT** |
| predictive_v2x vs oracle_v2x | arrived | 3 | -0.24 | -0.12 | [-1.57, 1.1] | 1/2/0 | **INCONCLUSIVE** |

Network (means over seeds): connected 258 vehicles · uplink TX 15331 RX 15331 PDR 1.0 lat med 0.0 p95 0.0 ms · downlink TX 12 RX 12 dropped 0 expired 0 PDR 1.0 lat med 0.0 p95 0.0 ms · reroutes applied 36 · inapplicable 0

- s101 baseline: veh-h 182.1714, mean tt 730 s, p95 1335 s, arrived 856, teleports 0, reroutes applied 0, sim `sim_v2x_s101_baseline_ideal_p30`
- s101 reactive: veh-h 180.5242, mean tt 724 s, p95 1330 s, arrived 858, teleports 0, reroutes applied 0, sim `sim_v2x_s101_reactive_ideal_p30`
- s101 persistence_v2x: veh-h 181.6447, mean tt 728 s, p95 1338 s, arrived 862, teleports 0, reroutes applied 12, sim `sim_v2x_s101_persistence_v2x_ideal_p30`
- s101 predictive_v2x: veh-h 181.6372, mean tt 728 s, p95 1318 s, arrived 861, teleports 0, reroutes applied 11, sim `sim_v2x_s101_predictive_v2x_ideal_p30`
- s101 oracle_v2x: veh-h 181.0528, mean tt 726 s, p95 1338 s, arrived 859, teleports 0, reroutes applied 28, sim `sim_v2x_s101_oracle_v2x_ideal_p30`
- s102 baseline: veh-h 180.0556, mean tt 723 s, p95 1325 s, arrived 849, teleports 0, reroutes applied 0, sim `sim_v2x_s102_baseline_ideal_p30`
- s102 reactive: veh-h 180.07, mean tt 723 s, p95 1337 s, arrived 848, teleports 0, reroutes applied 0, sim `sim_v2x_s102_reactive_ideal_p30`
- s102 persistence_v2x: veh-h 180.8667, mean tt 727 s, p95 1324 s, arrived 847, teleports 0, reroutes applied 13, sim `sim_v2x_s102_persistence_v2x_ideal_p30`
- s102 predictive_v2x: veh-h 180.5425, mean tt 725 s, p95 1350 s, arrived 842, teleports 0, reroutes applied 14, sim `sim_v2x_s102_predictive_v2x_ideal_p30`
- s102 oracle_v2x: veh-h 180.2361, mean tt 724 s, p95 1328 s, arrived 849, teleports 0, reroutes applied 37, sim `sim_v2x_s102_oracle_v2x_ideal_p30`
- s103 baseline: veh-h 175.0956, mean tt 705 s, p95 1330 s, arrived 855, teleports 0, reroutes applied 0, sim `sim_v2x_s103_baseline_ideal_p30`
- s103 reactive: veh-h 174.8869, mean tt 704 s, p95 1318 s, arrived 856, teleports 0, reroutes applied 0, sim `sim_v2x_s103_reactive_ideal_p30`
- s103 persistence_v2x: veh-h 175.4258, mean tt 706 s, p95 1320 s, arrived 853, teleports 0, reroutes applied 11, sim `sim_v2x_s103_persistence_v2x_ideal_p30`
- s103 predictive_v2x: veh-h 175.4392, mean tt 706 s, p95 1308 s, arrived 854, teleports 0, reroutes applied 11, sim `sim_v2x_s103_predictive_v2x_ideal_p30`
- s103 oracle_v2x: veh-h 175.5583, mean tt 707 s, p95 1353 s, arrived 855, teleports 0, reroutes applied 37, sim `sim_v2x_s103_oracle_v2x_ideal_p30`
