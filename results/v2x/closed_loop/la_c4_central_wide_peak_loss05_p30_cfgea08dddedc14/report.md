# V2X closed loop — V2X_CLOSED_LOOP_v1 · la_c4_central_wide · profile `loss05` · penetration 0.3 · seeds [101, 102, 103]

Model Graph WaveNet (207-node METR-LA, verified) (ckpt `548e399bd53c`), 83 of 207 detectors mapped, routing config `ea08dddedc14`. SYNTHETIC_WHAT_IF randomTrips on the real OSM network, one draw per seed, departures 0-1800 s. REAL METR-LA detector speeds (mph), replayed as lane speed caps on mapped edges in every arm. SIMULATED V2X (pipeline/v2x/channel.py) — not radio hardware: latency 50.0 ms ± 20.0, loss 0.05, TTL 60.0 s.

| pair | metric | n | mean % | median % | 95 % CI | W/L/T | label |
|---|---|---|---|---|---|---|---|
| reactive vs baseline | total_vehicle_hours_incl_never_inserted | 3 | -0.35 | -0.34 | [-1.0, 0.3] | 3/0/0 | **INCONCLUSIVE** |
| reactive vs baseline | mean_travel_time_all | 3 | -0.35 | -0.34 | [-1.0, 0.3] | 3/0/0 | **INCONCLUSIVE** |
| reactive vs baseline | p95_travel_time_s | 3 | -0.15 | -0.07 | [-0.81, 0.51] | 2/1/0 | **INCONCLUSIVE** |
| reactive vs baseline | total_waiting_s | 3 | -0.08 | -0.65 | [-2.8, 2.64] | 2/1/0 | **INCONCLUSIVE** |
| reactive vs baseline | mean_queue_veh | 3 | -0.58 | -0.66 | [-3.37, 2.2] | 2/1/0 | **INCONCLUSIVE** |
| reactive vs baseline | arrived | 3 | 0.2 | 0.23 | [-0.25, 0.64] | 2/0/1 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | total_vehicle_hours_incl_never_inserted | 3 | -0.06 | -0.03 | [-0.32, 0.21] | 2/1/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | mean_travel_time_all | 3 | -0.06 | -0.03 | [-0.32, 0.21] | 2/1/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | p95_travel_time_s | 3 | -0.02 | 0.0 | [-0.3, 0.26] | 1/1/1 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | total_waiting_s | 3 | 0.42 | 0.21 | [-0.74, 1.57] | 0/3/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | mean_queue_veh | 3 | 0.2 | 0.26 | [-0.58, 0.97] | 1/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | arrived | 3 | 0.0 | 0.0 | [-0.29, 0.29] | 1/1/1 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | total_vehicle_hours_incl_never_inserted | 3 | 0.29 | 0.38 | [-0.56, 1.14] | 1/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | mean_travel_time_all | 3 | 0.29 | 0.38 | [-0.56, 1.15] | 1/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | p95_travel_time_s | 3 | 0.12 | -0.07 | [-0.73, 0.97] | 2/1/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | total_waiting_s | 3 | 0.51 | 0.87 | [-3.07, 4.09] | 1/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | mean_queue_veh | 3 | 0.79 | 0.92 | [-2.8, 4.39] | 1/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | arrived | 3 | -0.19 | -0.23 | [-0.36, -0.03] | 0/3/0 | **HURT** |

Network (means over seeds): connected 259 vehicles · uplink TX 15982 RX 15188 PDR 0.9503 lat med 49.836666666666666 p95 67.96666666666667 ms · downlink TX 17 RX 17 dropped 0 expired 0 PDR 0.9762 lat med 52.5 p95 67.47666666666667 ms · reroutes applied 50 · inapplicable 0

- s101 baseline: veh-h 184.5233, mean tt 738 s, p95 1359 s, arrived 858, teleports 0, reroutes applied 0, sim `sim_v2x_s101_baseline_ideal_p30`
- s101 reactive: veh-h 184.3542, mean tt 737 s, p95 1353 s, arrived 860, teleports 0, reroutes applied 0, sim `sim_v2x_s101_reactive_ideal_p30`
- s101 predictive_v2x: veh-h 184.2031, mean tt 737 s, p95 1360 s, arrived 858, teleports 0, reroutes applied 13, sim `sim_v2x_s101_predictive_v2x_loss05_p30`
- s102 baseline: veh-h 182.6078, mean tt 730 s, p95 1359 s, arrived 847, teleports 0, reroutes applied 0, sim `sim_v2x_s102_baseline_ideal_p30`
- s102 reactive: veh-h 181.4856, mean tt 726 s, p95 1358 s, arrived 850, teleports 0, reroutes applied 0, sim `sim_v2x_s102_reactive_ideal_p30`
- s102 predictive_v2x: veh-h 182.5536, mean tt 730 s, p95 1357 s, arrived 848, teleports 0, reroutes applied 24, sim `sim_v2x_s102_predictive_v2x_loss05_p30`
- s103 baseline: veh-h 178.7522, mean tt 715 s, p95 1331 s, arrived 863, teleports 0, reroutes applied 0, sim `sim_v2x_s103_baseline_ideal_p30`
- s103 reactive: veh-h 178.1469, mean tt 713 s, p95 1332 s, arrived 863, teleports 0, reroutes applied 0, sim `sim_v2x_s103_reactive_ideal_p30`
- s103 predictive_v2x: veh-h 178.8161, mean tt 715 s, p95 1331 s, arrived 862, teleports 0, reroutes applied 13, sim `sim_v2x_s103_predictive_v2x_loss05_p30`
