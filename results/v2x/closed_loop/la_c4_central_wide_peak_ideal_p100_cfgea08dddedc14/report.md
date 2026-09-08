# V2X closed loop — V2X_CLOSED_LOOP_v1 · la_c4_central_wide · profile `ideal` · penetration 1.0 · seeds [101, 102, 103]

Model Graph WaveNet (207-node METR-LA, verified) (ckpt `548e399bd53c`), 83 of 207 detectors mapped, routing config `ea08dddedc14`. SYNTHETIC_WHAT_IF randomTrips on the real OSM network, one draw per seed, departures 0-1800 s. REAL METR-LA detector speeds (mph), replayed as lane speed caps on mapped edges in every arm. SIMULATED V2X (pipeline/v2x/channel.py) — not radio hardware: latency 0.0 ms ± 0.0, loss 0.0, TTL 60.0 s.

| pair | metric | n | mean % | median % | 95 % CI | W/L/T | label |
|---|---|---|---|---|---|---|---|
| reactive vs baseline | total_vehicle_hours_incl_never_inserted | 3 | -0.56 | -0.53 | [-0.71, -0.41] | 3/0/0 | **HELPED** |
| reactive vs baseline | mean_travel_time_all | 3 | -0.56 | -0.53 | [-0.71, -0.41] | 3/0/0 | **HELPED** |
| reactive vs baseline | p95_travel_time_s | 3 | -0.26 | -0.66 | [-3.69, 3.17] | 2/1/0 | **INCONCLUSIVE** |
| reactive vs baseline | total_waiting_s | 3 | 2.51 | 2.93 | [0.32, 4.7] | 0/3/0 | **HURT** |
| reactive vs baseline | mean_queue_veh | 3 | 2.31 | 2.09 | [-0.24, 4.87] | 0/3/0 | **INCONCLUSIVE** |
| reactive vs baseline | arrived | 3 | 0.16 | 0.24 | [-0.45, 0.76] | 2/1/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | total_vehicle_hours_incl_never_inserted | 3 | -0.5 | -0.29 | [-2.12, 1.12] | 2/1/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | mean_travel_time_all | 3 | -0.5 | -0.29 | [-2.12, 1.12] | 2/1/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | p95_travel_time_s | 3 | 0.44 | 0.0 | [-1.62, 2.5] | 1/1/1 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | total_waiting_s | 3 | 1.28 | 2.05 | [-2.17, 4.74] | 1/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | mean_queue_veh | 3 | 0.96 | 1.82 | [-3.98, 5.89] | 1/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | arrived | 3 | 0.23 | 0.0 | [-1.02, 1.49] | 1/1/1 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | total_vehicle_hours_incl_never_inserted | 3 | 0.06 | 0.25 | [-1.42, 1.54] | 1/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | mean_travel_time_all | 3 | 0.06 | 0.24 | [-1.42, 1.54] | 1/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | p95_travel_time_s | 3 | 0.72 | 0.67 | [-4.46, 5.91] | 1/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | total_waiting_s | 3 | -1.18 | -1.01 | [-5.9, 3.53] | 2/1/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | mean_queue_veh | 3 | -1.31 | -0.26 | [-8.53, 5.92] | 2/1/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | arrived | 3 | 0.08 | -0.24 | [-1.78, 1.93] | 1/2/0 | **INCONCLUSIVE** |

Network (means over seeds): connected 900 vehicles · uplink TX 55733 RX 55733 PDR 1.0 lat med 0.0 p95 0.0 ms · downlink TX 65 RX 65 dropped 0 expired 0 PDR 1.0 lat med 0.0 p95 0.0 ms · reroutes applied 195 · inapplicable 0

- s101 baseline: veh-h 184.5233, mean tt 738 s, p95 1359 s, arrived 858, teleports 0, reroutes applied 0, sim `sim_v2x_s101_baseline_ideal_p30`
- s101 reactive: veh-h 183.5372, mean tt 734 s, p95 1340 s, arrived 861, teleports 0, reroutes applied 0, sim `sim_v2x_s101_reactive_ideal_p100`
- s101 predictive_v2x: veh-h 183.9878, mean tt 736 s, p95 1378 s, arrived 857, teleports 0, reroutes applied 61, sim `sim_v2x_s101_predictive_v2x_ideal_p100`
- s102 baseline: veh-h 182.6078, mean tt 730 s, p95 1359 s, arrived 847, teleports 0, reroutes applied 0, sim `sim_v2x_s102_baseline_ideal_p30`
- s102 reactive: veh-h 181.6597, mean tt 727 s, p95 1350 s, arrived 849, teleports 0, reroutes applied 0, sim `sim_v2x_s102_reactive_ideal_p100`
- s102 predictive_v2x: veh-h 182.6489, mean tt 731 s, p95 1359 s, arrived 847, teleports 0, reroutes applied 68, sim `sim_v2x_s102_predictive_v2x_ideal_p100`
- s103 baseline: veh-h 178.7522, mean tt 715 s, p95 1331 s, arrived 863, teleports 0, reroutes applied 0, sim `sim_v2x_s103_baseline_ideal_p30`
- s103 reactive: veh-h 177.6244, mean tt 710 s, p95 1348 s, arrived 862, teleports 0, reroutes applied 0, sim `sim_v2x_s103_reactive_ideal_p100`
- s103 predictive_v2x: veh-h 176.5556, mean tt 706 s, p95 1330 s, arrived 870, teleports 0, reroutes applied 66, sim `sim_v2x_s103_predictive_v2x_ideal_p100`
