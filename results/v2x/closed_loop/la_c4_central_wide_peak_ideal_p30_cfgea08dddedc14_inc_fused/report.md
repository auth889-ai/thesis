# V2X closed loop — V2X_CLOSED_LOOP_v1 · la_c4_central_wide · profile `ideal` · penetration 0.3 · seeds [101, 102, 103]

Model Graph WaveNet (207-node METR-LA, verified) (ckpt `548e399bd53c`), 83 of 207 detectors mapped, routing config `ea08dddedc14`. SYNTHETIC_WHAT_IF randomTrips on the real OSM network, one draw per seed, departures 0-1800 s. REAL METR-LA detector speeds (mph), replayed as lane speed caps on mapped edges in every arm. SIMULATED V2X (pipeline/v2x/channel.py) — not radio hardware: latency 0.0 ms ± 0.0, loss 0.0, TTL 60.0 s.

| pair | metric | n | mean % | median % | 95 % CI | W/L/T | label |
|---|---|---|---|---|---|---|---|
| reactive vs baseline | total_vehicle_hours_incl_never_inserted | 3 | -0.67 | -0.81 | [-1.29, -0.05] | 3/0/0 | **HELPED** |
| reactive vs baseline | mean_travel_time_all | 3 | -0.67 | -0.81 | [-1.29, -0.05] | 3/0/0 | **HELPED** |
| reactive vs baseline | p95_travel_time_s | 3 | -1.93 | -2.76 | [-7.99, 4.12] | 2/1/0 | **INCONCLUSIVE** |
| reactive vs baseline | total_waiting_s | 3 | 0.75 | 0.23 | [-1.62, 3.11] | 0/3/0 | **INCONCLUSIVE** |
| reactive vs baseline | mean_queue_veh | 3 | 1.03 | 1.18 | [-0.74, 2.8] | 0/3/0 | **INCONCLUSIVE** |
| reactive vs baseline | arrived | 3 | -0.04 | 0.12 | [-1.54, 1.46] | 2/1/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | total_vehicle_hours_incl_never_inserted | 3 | 0.1 | 0.13 | [-1.27, 1.46] | 1/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | mean_travel_time_all | 3 | 0.1 | 0.13 | [-1.27, 1.46] | 1/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | p95_travel_time_s | 3 | -0.21 | 0.64 | [-6.24, 5.83] | 1/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | total_waiting_s | 3 | -0.19 | 0.43 | [-4.47, 4.08] | 1/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | mean_queue_veh | 3 | 1.05 | 1.81 | [-3.15, 5.25] | 1/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | arrived | 3 | -0.62 | -0.7 | [-1.24, -0.01] | 0/3/0 | **HURT** |
| predictive_v2x vs reactive | total_vehicle_hours_incl_never_inserted | 3 | 0.77 | 0.96 | [-0.15, 1.69] | 0/3/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | mean_travel_time_all | 3 | 0.77 | 0.96 | [-0.15, 1.69] | 0/3/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | p95_travel_time_s | 3 | 1.77 | 0.95 | [-1.93, 5.47] | 0/3/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | total_waiting_s | 3 | -0.92 | 0.2 | [-7.43, 5.6] | 1/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | mean_queue_veh | 3 | 0.03 | 0.56 | [-4.58, 4.63] | 1/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | arrived | 3 | -0.58 | -0.47 | [-1.9, 0.74] | 0/3/0 | **INCONCLUSIVE** |

Network (means over seeds): connected 259 vehicles · uplink TX 16363 RX 16363 PDR 1.0 lat med 0.0 p95 0.0 ms · downlink TX 119 RX 119 dropped 0 expired 0 PDR 1.0 lat med 0.0 p95 0.0 ms · reroutes applied 358 · inapplicable 0

- s101 baseline: veh-h 188.8578, mean tt 755 s, p95 1427 s, arrived 857, teleports 0, reroutes applied 0, sim `sim_v2x_s101_baseline_ideal_p30`
- s101 reactive: veh-h 187.3306, mean tt 749 s, p95 1372 s, arrived 861, teleports 0, reroutes applied 0, sim `sim_v2x_s101_reactive_ideal_p30`
- s101 predictive_v2x: veh-h 187.9675, mean tt 752 s, p95 1385 s, arrived 851, teleports 1, reroutes applied 87, sim `sim_v2x_s101_predictive_v2x_ideal_p30`
- s102 baseline: veh-h 185.7167, mean tt 743 s, p95 1415 s, arrived 849, teleports 0, reroutes applied 0, sim `sim_v2x_s102_baseline_ideal_p30`
- s102 reactive: veh-h 185.01, mean tt 740 s, p95 1376 s, arrived 843, teleports 0, reroutes applied 0, sim `sim_v2x_s102_reactive_ideal_p30`
- s102 predictive_v2x: veh-h 186.8733, mean tt 747 s, p95 1424 s, arrived 842, teleports 0, reroutes applied 129, sim `sim_v2x_s102_predictive_v2x_ideal_p30`
- s103 baseline: veh-h 182.4311, mean tt 730 s, p95 1359 s, arrived 858, teleports 0, reroutes applied 0, sim `sim_v2x_s103_baseline_ideal_p30`
- s103 reactive: veh-h 180.9442, mean tt 724 s, p95 1370 s, arrived 859, teleports 0, reroutes applied 0, sim `sim_v2x_s103_reactive_ideal_p30`
- s103 predictive_v2x: veh-h 182.675, mean tt 731 s, p95 1382 s, arrived 855, teleports 1, reroutes applied 142, sim `sim_v2x_s103_predictive_v2x_ideal_p30`
