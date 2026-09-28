# V2X closed loop — V2X_CLOSED_LOOP_v1 · la_c2_hollywood_101_5 · profile `ideal` · penetration 0.3 · seeds [101, 102, 103]

Model Graph WaveNet (207-node METR-LA, verified) (ckpt `548e399bd53c`), 52 of 207 detectors mapped, routing config `ea08dddedc14`. SYNTHETIC_WHAT_IF randomTrips on the real OSM network, one draw per seed, departures 0-1800 s. REAL METR-LA detector speeds (mph), replayed as lane speed caps on mapped edges in every arm. SIMULATED V2X (pipeline/v2x/channel.py) — not radio hardware: latency 0.0 ms ± 0.0, loss 0.0, TTL 60.0 s.

Identical-state fork at 480 s: state hashes {101: '41e769b4c523', 102: 'fe7916c4f390', 103: 'b378ecc6c0d5'} — identical across arms: **True**. Reroutes applied by arm: {'baseline': 0, 'reactive': 0, 'persistence_net_v2x': 81, 'predictive_v2x': 80, 'predictive_net_v2x': 77, 'oracle_v2x': 96, 'oracle_net_v2x': 87, 'random_net_v2x': 80}.

| pair | metric | n | mean % | median % | 95 % CI | W/L/T | label |
|---|---|---|---|---|---|---|---|
| reactive vs baseline | total_vehicle_hours_incl_never_inserted | 3 | -1.03 | -1.23 | [-2.62, 0.56] | 3/0/0 | **INCONCLUSIVE** |
| reactive vs baseline | mean_travel_time_all | 3 | -1.03 | -1.23 | [-2.62, 0.56] | 3/0/0 | **INCONCLUSIVE** |
| reactive vs baseline | p95_travel_time_s | 3 | -1.05 | -0.55 | [-6.74, 4.64] | 2/1/0 | **INCONCLUSIVE** |
| reactive vs baseline | total_waiting_s | 3 | 2.97 | 2.23 | [-2.38, 8.33] | 0/3/0 | **INCONCLUSIVE** |
| reactive vs baseline | mean_queue_veh | 3 | 3.24 | 2.18 | [-1.47, 7.95] | 0/3/0 | **INCONCLUSIVE** |
| reactive vs baseline | arrived | 3 | 0.35 | 0.35 | [0.06, 0.64] | 3/0/0 | **HELPED** |
| reactive vs baseline | teleports | 1 | 0.0 | 0.0 | [None, None] | 0/0/1 | **INCONCLUSIVE** |
| persistence_net_v2x vs baseline | total_vehicle_hours_incl_never_inserted | 3 | -0.02 | -0.09 | [-1.11, 1.07] | 2/1/0 | **INCONCLUSIVE** |
| persistence_net_v2x vs baseline | mean_travel_time_all | 3 | -0.02 | -0.09 | [-1.11, 1.07] | 2/1/0 | **INCONCLUSIVE** |
| persistence_net_v2x vs baseline | p95_travel_time_s | 3 | 0.06 | 0.46 | [-3.23, 3.35] | 1/2/0 | **INCONCLUSIVE** |
| persistence_net_v2x vs baseline | total_waiting_s | 3 | 1.73 | 0.77 | [-2.96, 6.42] | 0/3/0 | **INCONCLUSIVE** |
| persistence_net_v2x vs baseline | mean_queue_veh | 3 | 2.71 | 1.62 | [-2.08, 7.49] | 0/3/0 | **INCONCLUSIVE** |
| persistence_net_v2x vs baseline | arrived | 3 | 0.04 | 0.12 | [-0.57, 0.64] | 2/1/0 | **INCONCLUSIVE** |
| persistence_net_v2x vs baseline | teleports | 1 | 0.0 | 0.0 | [None, None] | 0/0/1 | **INCONCLUSIVE** |
| persistence_net_v2x vs reactive | total_vehicle_hours_incl_never_inserted | 3 | 1.02 | 1.15 | [0.48, 1.57] | 0/3/0 | **HURT** |
| persistence_net_v2x vs reactive | mean_travel_time_all | 3 | 1.02 | 1.15 | [0.48, 1.57] | 0/3/0 | **HURT** |
| persistence_net_v2x vs reactive | p95_travel_time_s | 3 | 1.13 | 1.01 | [-1.39, 3.65] | 0/3/0 | **INCONCLUSIVE** |
| persistence_net_v2x vs reactive | total_waiting_s | 3 | -1.2 | -1.42 | [-2.15, -0.26] | 3/0/0 | **HELPED** |
| persistence_net_v2x vs reactive | mean_queue_veh | 3 | -0.52 | -0.48 | [-0.69, -0.34] | 3/0/0 | **HELPED** |
| persistence_net_v2x vs reactive | arrived | 3 | -0.31 | -0.35 | [-0.75, 0.13] | 0/3/0 | **INCONCLUSIVE** |
| persistence_net_v2x vs reactive | teleports | 1 | 0.0 | 0.0 | [None, None] | 0/0/1 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | total_vehicle_hours_incl_never_inserted | 3 | -0.35 | -0.2 | [-1.06, 0.35] | 3/0/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | mean_travel_time_all | 3 | -0.35 | -0.2 | [-1.06, 0.35] | 3/0/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | p95_travel_time_s | 3 | -0.25 | 0.0 | [-3.34, 2.85] | 1/1/1 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | total_waiting_s | 3 | 1.81 | 1.92 | [0.59, 3.04] | 0/3/0 | **HURT** |
| predictive_v2x vs baseline | mean_queue_veh | 3 | 2.41 | 2.28 | [1.64, 3.18] | 0/3/0 | **HURT** |
| predictive_v2x vs baseline | arrived | 3 | 0.04 | 0.12 | [-0.57, 0.64] | 2/1/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | teleports | 1 | 0.0 | 0.0 | [None, None] | 0/0/1 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | total_vehicle_hours_incl_never_inserted | 3 | 0.69 | 0.88 | [-0.51, 1.88] | 0/3/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | mean_travel_time_all | 3 | 0.69 | 0.88 | [-0.51, 1.88] | 0/3/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | p95_travel_time_s | 3 | 0.83 | 0.55 | [-1.87, 3.52] | 1/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | total_waiting_s | 3 | -1.1 | -0.01 | [-5.85, 3.64] | 2/1/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | mean_queue_veh | 3 | -0.78 | 0.08 | [-5.56, 4.0] | 1/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | arrived | 3 | -0.31 | -0.23 | [-0.65, 0.03] | 0/3/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | teleports | 1 | 0.0 | 0.0 | [None, None] | 0/0/1 | **INCONCLUSIVE** |
| predictive_net_v2x vs baseline | total_vehicle_hours_incl_never_inserted | 3 | -0.07 | -0.01 | [-0.31, 0.18] | 3/0/0 | **INCONCLUSIVE** |
| predictive_net_v2x vs baseline | mean_travel_time_all | 3 | -0.07 | -0.01 | [-0.31, 0.18] | 3/0/0 | **INCONCLUSIVE** |
| predictive_net_v2x vs baseline | p95_travel_time_s | 3 | -0.11 | -0.27 | [-1.19, 0.97] | 2/1/0 | **INCONCLUSIVE** |
| predictive_net_v2x vs baseline | total_waiting_s | 3 | 1.84 | 1.75 | [-0.06, 3.73] | 0/3/0 | **INCONCLUSIVE** |
| predictive_net_v2x vs baseline | mean_queue_veh | 3 | 2.81 | 2.69 | [1.39, 4.23] | 0/3/0 | **HURT** |
| predictive_net_v2x vs baseline | arrived | 3 | 0.08 | 0.0 | [-0.52, 0.68] | 1/1/1 | **INCONCLUSIVE** |
| predictive_net_v2x vs baseline | teleports | 1 | 0.0 | 0.0 | [None, None] | 0/0/1 | **INCONCLUSIVE** |
| predictive_net_v2x vs reactive | total_vehicle_hours_incl_never_inserted | 3 | 0.98 | 1.24 | [-0.48, 2.43] | 0/3/0 | **INCONCLUSIVE** |
| predictive_net_v2x vs reactive | mean_travel_time_all | 3 | 0.98 | 1.24 | [-0.48, 2.43] | 0/3/0 | **INCONCLUSIVE** |
| predictive_net_v2x vs reactive | p95_travel_time_s | 3 | 0.98 | 0.27 | [-3.96, 5.91] | 1/2/0 | **INCONCLUSIVE** |
| predictive_net_v2x vs reactive | total_waiting_s | 3 | -1.08 | -0.48 | [-4.41, 2.24] | 3/0/0 | **INCONCLUSIVE** |
| predictive_net_v2x vs reactive | mean_queue_veh | 3 | -0.4 | 0.2 | [-3.63, 2.83] | 1/2/0 | **INCONCLUSIVE** |
| predictive_net_v2x vs reactive | arrived | 3 | -0.27 | -0.35 | [-0.87, 0.33] | 0/2/1 | **INCONCLUSIVE** |
| predictive_net_v2x vs reactive | teleports | 1 | 0.0 | 0.0 | [None, None] | 0/0/1 | **INCONCLUSIVE** |
| oracle_v2x vs baseline | total_vehicle_hours_incl_never_inserted | 3 | -0.46 | -0.54 | [-1.21, 0.28] | 3/0/0 | **INCONCLUSIVE** |
| oracle_v2x vs baseline | mean_travel_time_all | 3 | -0.46 | -0.54 | [-1.21, 0.28] | 3/0/0 | **INCONCLUSIVE** |
| oracle_v2x vs baseline | p95_travel_time_s | 3 | -0.76 | -0.64 | [-4.68, 3.17] | 2/1/0 | **INCONCLUSIVE** |
| oracle_v2x vs baseline | total_waiting_s | 3 | 0.04 | 0.2 | [-1.15, 1.22] | 1/2/0 | **INCONCLUSIVE** |
| oracle_v2x vs baseline | mean_queue_veh | 3 | 0.06 | -0.15 | [-1.37, 1.48] | 2/1/0 | **INCONCLUSIVE** |
| oracle_v2x vs baseline | arrived | 3 | 0.16 | 0.12 | [-0.57, 0.88] | 2/1/0 | **INCONCLUSIVE** |
| oracle_v2x vs baseline | teleports | 1 | 0.0 | 0.0 | [None, None] | 0/0/1 | **INCONCLUSIVE** |
| oracle_v2x vs reactive | total_vehicle_hours_incl_never_inserted | 3 | 0.57 | 0.7 | [-0.28, 1.43] | 0/3/0 | **INCONCLUSIVE** |
| oracle_v2x vs reactive | mean_travel_time_all | 3 | 0.57 | 0.7 | [-0.28, 1.43] | 0/3/0 | **INCONCLUSIVE** |
| oracle_v2x vs reactive | p95_travel_time_s | 3 | 0.3 | -0.09 | [-1.61, 2.22] | 2/1/0 | **INCONCLUSIVE** |
| oracle_v2x vs reactive | total_waiting_s | 3 | -2.83 | -1.98 | [-6.94, 1.29] | 3/0/0 | **INCONCLUSIVE** |
| oracle_v2x vs reactive | mean_queue_veh | 3 | -3.07 | -2.5 | [-6.12, -0.01] | 3/0/0 | **HELPED** |
| oracle_v2x vs reactive | arrived | 3 | -0.19 | -0.12 | [-0.79, 0.4] | 0/2/1 | **INCONCLUSIVE** |
| oracle_v2x vs reactive | teleports | 1 | 0.0 | 0.0 | [None, None] | 0/0/1 | **INCONCLUSIVE** |
| oracle_net_v2x vs baseline | total_vehicle_hours_incl_never_inserted | 3 | -0.54 | -0.44 | [-1.14, 0.07] | 3/0/0 | **INCONCLUSIVE** |
| oracle_net_v2x vs baseline | mean_travel_time_all | 3 | -0.54 | -0.44 | [-1.14, 0.07] | 3/0/0 | **INCONCLUSIVE** |
| oracle_net_v2x vs baseline | p95_travel_time_s | 3 | 0.29 | 0.76 | [-2.06, 2.64] | 1/2/0 | **INCONCLUSIVE** |
| oracle_net_v2x vs baseline | total_waiting_s | 3 | -0.62 | -0.88 | [-2.53, 1.3] | 2/1/0 | **INCONCLUSIVE** |
| oracle_net_v2x vs baseline | mean_queue_veh | 3 | -0.59 | -0.73 | [-1.98, 0.8] | 2/1/0 | **INCONCLUSIVE** |
| oracle_net_v2x vs baseline | arrived | 3 | 0.16 | 0.0 | [-0.51, 0.83] | 1/0/2 | **INCONCLUSIVE** |
| oracle_net_v2x vs baseline | teleports | 1 | 0.0 | 0.0 | [None, None] | 0/0/1 | **INCONCLUSIVE** |
| oracle_net_v2x vs reactive | total_vehicle_hours_incl_never_inserted | 3 | 0.5 | 0.74 | [-0.66, 1.66] | 1/2/0 | **INCONCLUSIVE** |
| oracle_net_v2x vs reactive | mean_travel_time_all | 3 | 0.5 | 0.74 | [-0.66, 1.66] | 1/2/0 | **INCONCLUSIVE** |
| oracle_net_v2x vs reactive | p95_travel_time_s | 3 | 1.37 | 1.46 | [-2.4, 5.15] | 1/2/0 | **INCONCLUSIVE** |
| oracle_net_v2x vs reactive | total_waiting_s | 3 | -3.45 | -3.38 | [-9.58, 2.68] | 3/0/0 | **INCONCLUSIVE** |
| oracle_net_v2x vs reactive | mean_queue_veh | 3 | -3.69 | -3.17 | [-8.54, 1.17] | 3/0/0 | **INCONCLUSIVE** |
| oracle_net_v2x vs reactive | arrived | 3 | -0.19 | -0.35 | [-1.12, 0.73] | 1/2/0 | **INCONCLUSIVE** |
| oracle_net_v2x vs reactive | teleports | 1 | 0.0 | 0.0 | [None, None] | 0/0/1 | **INCONCLUSIVE** |
| random_net_v2x vs baseline | total_vehicle_hours_incl_never_inserted | 3 | 0.23 | 0.04 | [-0.81, 1.26] | 1/2/0 | **INCONCLUSIVE** |
| random_net_v2x vs baseline | mean_travel_time_all | 3 | 0.23 | 0.04 | [-0.8, 1.26] | 1/2/0 | **INCONCLUSIVE** |
| random_net_v2x vs baseline | p95_travel_time_s | 3 | 0.04 | -0.09 | [-1.14, 1.23] | 2/1/0 | **INCONCLUSIVE** |
| random_net_v2x vs baseline | total_waiting_s | 3 | 2.66 | 2.98 | [-0.77, 6.08] | 0/3/0 | **INCONCLUSIVE** |
| random_net_v2x vs baseline | mean_queue_veh | 3 | 3.45 | 2.71 | [-1.15, 8.05] | 0/3/0 | **INCONCLUSIVE** |
| random_net_v2x vs baseline | arrived | 3 | 0.23 | 0.12 | [-0.53, 1.0] | 2/0/1 | **INCONCLUSIVE** |
| random_net_v2x vs baseline | teleports | 1 | 0.0 | 0.0 | [None, None] | 0/0/1 | **INCONCLUSIVE** |
| random_net_v2x vs reactive | total_vehicle_hours_incl_never_inserted | 3 | 1.27 | 1.18 | [0.52, 2.03] | 0/3/0 | **HURT** |
| random_net_v2x vs reactive | mean_travel_time_all | 3 | 1.27 | 1.18 | [0.52, 2.03] | 0/3/0 | **HURT** |
| random_net_v2x vs reactive | p95_travel_time_s | 3 | 1.13 | 0.46 | [-3.67, 5.93] | 1/2/0 | **INCONCLUSIVE** |
| random_net_v2x vs reactive | total_waiting_s | 3 | -0.29 | -0.14 | [-3.06, 2.47] | 2/1/0 | **INCONCLUSIVE** |
| random_net_v2x vs reactive | mean_queue_veh | 3 | 0.21 | 0.12 | [-0.49, 0.91] | 1/2/0 | **INCONCLUSIVE** |
| random_net_v2x vs reactive | arrived | 3 | -0.12 | -0.23 | [-0.62, 0.38] | 1/2/0 | **INCONCLUSIVE** |
| random_net_v2x vs reactive | teleports | 1 | 0.0 | 0.0 | [None, None] | 0/0/1 | **INCONCLUSIVE** |
| predictive_v2x vs oracle_v2x | total_vehicle_hours_incl_never_inserted | 3 | 0.11 | 0.04 | [-0.39, 0.61] | 1/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs oracle_v2x | mean_travel_time_all | 3 | 0.11 | 0.04 | [-0.39, 0.61] | 1/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs oracle_v2x | p95_travel_time_s | 3 | 0.52 | 0.64 | [-0.42, 1.45] | 0/3/0 | **INCONCLUSIVE** |
| predictive_v2x vs oracle_v2x | total_waiting_s | 3 | 1.77 | 1.78 | [1.11, 2.44] | 0/3/0 | **HURT** |
| predictive_v2x vs oracle_v2x | mean_queue_veh | 3 | 2.35 | 2.34 | [0.38, 4.33] | 0/3/0 | **HURT** |
| predictive_v2x vs oracle_v2x | arrived | 3 | -0.12 | -0.23 | [-0.88, 0.65] | 1/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs oracle_v2x | teleports | 1 | 0.0 | 0.0 | [None, None] | 0/0/1 | **INCONCLUSIVE** |
| predictive_net_v2x vs predictive_v2x | total_vehicle_hours_incl_never_inserted | 3 | 0.29 | 0.19 | [-0.18, 0.76] | 0/3/0 | **INCONCLUSIVE** |
| predictive_net_v2x vs predictive_v2x | mean_travel_time_all | 3 | 0.29 | 0.19 | [-0.18, 0.76] | 0/3/0 | **INCONCLUSIVE** |
| predictive_net_v2x vs predictive_v2x | p95_travel_time_s | 3 | 0.14 | -0.27 | [-2.09, 2.37] | 2/1/0 | **INCONCLUSIVE** |
| predictive_net_v2x vs predictive_v2x | total_waiting_s | 3 | 0.02 | -0.15 | [-1.51, 1.56] | 2/1/0 | **INCONCLUSIVE** |
| predictive_net_v2x vs predictive_v2x | mean_queue_veh | 3 | 0.39 | 0.13 | [-1.21, 1.99] | 1/2/0 | **INCONCLUSIVE** |
| predictive_net_v2x vs predictive_v2x | arrived | 3 | 0.04 | 0.12 | [-0.56, 0.64] | 2/1/0 | **INCONCLUSIVE** |
| predictive_net_v2x vs predictive_v2x | teleports | 1 | 0.0 | 0.0 | [None, None] | 0/0/1 | **INCONCLUSIVE** |
| oracle_net_v2x vs oracle_v2x | total_vehicle_hours_incl_never_inserted | 3 | -0.07 | -0.1 | [-0.48, 0.33] | 2/1/0 | **INCONCLUSIVE** |
| oracle_net_v2x vs oracle_v2x | mean_travel_time_all | 3 | -0.07 | -0.1 | [-0.48, 0.33] | 2/1/0 | **INCONCLUSIVE** |
| oracle_net_v2x vs oracle_v2x | p95_travel_time_s | 3 | 1.06 | 1.56 | [-1.23, 3.36] | 0/2/1 | **INCONCLUSIVE** |
| oracle_net_v2x vs oracle_v2x | total_waiting_s | 3 | -0.65 | -1.28 | [-3.67, 2.38] | 2/1/0 | **INCONCLUSIVE** |
| oracle_net_v2x vs oracle_v2x | mean_queue_veh | 3 | -0.65 | -0.69 | [-2.65, 1.36] | 2/1/0 | **INCONCLUSIVE** |
| oracle_net_v2x vs oracle_v2x | arrived | 3 | 0.0 | 0.12 | [-1.04, 1.04] | 2/1/0 | **INCONCLUSIVE** |
| oracle_net_v2x vs oracle_v2x | teleports | 1 | 0.0 | 0.0 | [None, None] | 0/0/1 | **INCONCLUSIVE** |

Network (means over seeds): connected 252 vehicles · uplink TX 11460 RX 11460 PDR 1.0 lat med 0.0 p95 0.0 ms · downlink TX 32 RX 32 dropped 0 expired 0 PDR 1.0 lat med 0.0 p95 0.0 ms · reroutes applied 80 · inapplicable 15

- s101 baseline: veh-h 148.9903, mean tt 615 s, p95 1099 s, arrived 856, teleports 1, reroutes applied 0, sim `sim_v2x_s101_baseline_ideal_p30`
- s101 reactive: veh-h 147.1586, mean tt 608 s, p95 1093 s, arrived 858, teleports 1, reroutes applied 0, sim `sim_v2x_s101_reactive_ideal_p30`
- s101 persistence_net_v2x: veh-h 148.8544, mean tt 615 s, p95 1104 s, arrived 854, teleports 1, reroutes applied 26, sim `sim_v2x_s101_persistence_net_v2x_ideal_p30`
- s101 predictive_v2x: veh-h 148.6894, mean tt 614 s, p95 1099 s, arrived 854, teleports 1, reroutes applied 26, sim `sim_v2x_s101_predictive_v2x_ideal_p30`
- s101 predictive_net_v2x: veh-h 148.9775, mean tt 615 s, p95 1096 s, arrived 855, teleports 1, reroutes applied 24, sim `sim_v2x_s101_predictive_net_v2x_ideal_p30`
- s101 oracle_v2x: veh-h 148.185, mean tt 612 s, p95 1092 s, arrived 857, teleports 1, reroutes applied 28, sim `sim_v2x_s101_oracle_v2x_ideal_p30`
- s101 oracle_net_v2x: veh-h 148.3289, mean tt 612 s, p95 1109 s, arrived 860, teleports 1, reroutes applied 25, sim `sim_v2x_s101_oracle_net_v2x_ideal_p30`
- s101 random_net_v2x: veh-h 148.8989, mean tt 615 s, p95 1098 s, arrived 856, teleports 1, reroutes applied 29, sim `sim_v2x_s101_random_net_v2x_ideal_p30`
- s102 baseline: veh-h 144.2878, mean tt 598 s, p95 1051 s, arrived 860, teleports 0, reroutes applied 0, sim `sim_v2x_s102_baseline_ideal_p30`
- s102 reactive: veh-h 143.8311, mean tt 597 s, p95 1061 s, arrived 863, teleports 0, reroutes applied 0, sim `sim_v2x_s102_reactive_ideal_p30`
- s102 persistence_net_v2x: veh-h 144.9364, mean tt 601 s, p95 1063 s, arrived 862, teleports 3, reroutes applied 25, sim `sim_v2x_s102_persistence_net_v2x_ideal_p30`
- s102 predictive_v2x: veh-h 144.0306, mean tt 597 s, p95 1060 s, arrived 861, teleports 0, reroutes applied 21, sim `sim_v2x_s102_predictive_v2x_ideal_p30`
- s102 predictive_net_v2x: veh-h 144.2703, mean tt 598 s, p95 1055 s, arrived 863, teleports 3, reroutes applied 24, sim `sim_v2x_s102_predictive_net_v2x_ideal_p30`
- s102 oracle_v2x: veh-h 144.0961, mean tt 598 s, p95 1059 s, arrived 859, teleports 0, reroutes applied 35, sim `sim_v2x_s102_oracle_v2x_ideal_p30`
- s102 oracle_net_v2x: veh-h 143.7733, mean tt 596 s, p95 1059 s, arrived 860, teleports 0, reroutes applied 34, sim `sim_v2x_s102_oracle_net_v2x_ideal_p30`
- s102 random_net_v2x: veh-h 145.3061, mean tt 603 s, p95 1057 s, arrived 861, teleports 3, reroutes applied 21, sim `sim_v2x_s102_random_net_v2x_ideal_p30`
- s103 baseline: veh-h 149.015, mean tt 614 s, p95 1128 s, arrived 859, teleports 0, reroutes applied 0, sim `sim_v2x_s103_baseline_ideal_p30`
- s103 reactive: veh-h 146.71, mean tt 605 s, p95 1088 s, arrived 863, teleports 0, reroutes applied 0, sim `sim_v2x_s103_reactive_ideal_p30`
- s103 persistence_net_v2x: veh-h 148.3903, mean tt 612 s, p95 1112 s, arrived 860, teleports 0, reroutes applied 30, sim `sim_v2x_s103_persistence_net_v2x_ideal_p30`
- s103 predictive_v2x: veh-h 147.9958, mean tt 610 s, p95 1110 s, arrived 861, teleports 0, reroutes applied 33, sim `sim_v2x_s103_predictive_v2x_ideal_p30`
- s103 predictive_net_v2x: veh-h 148.7433, mean tt 613 s, p95 1123 s, arrived 859, teleports 0, reroutes applied 29, sim `sim_v2x_s103_predictive_net_v2x_ideal_p30`
- s103 oracle_v2x: veh-h 147.9431, mean tt 610 s, p95 1101 s, arrived 863, teleports 0, reroutes applied 33, sim `sim_v2x_s103_oracle_v2x_ideal_p30`
- s103 oracle_net_v2x: veh-h 147.8008, mean tt 609 s, p95 1119 s, arrived 859, teleports 0, reroutes applied 28, sim `sim_v2x_s103_oracle_net_v2x_ideal_p30`
- s103 random_net_v2x: veh-h 149.0783, mean tt 615 s, p95 1124 s, arrived 864, teleports 0, reroutes applied 30, sim `sim_v2x_s103_random_net_v2x_ideal_p30`
