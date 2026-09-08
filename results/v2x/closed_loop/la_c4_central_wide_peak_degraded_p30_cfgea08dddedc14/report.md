# V2X closed loop — V2X_CLOSED_LOOP_v1 · la_c4_central_wide · profile `degraded` · penetration 0.3 · seeds [101, 102, 103]

Model Graph WaveNet (207-node METR-LA, verified) (ckpt `548e399bd53c`), 83 of 207 detectors mapped, routing config `ea08dddedc14`. SYNTHETIC_WHAT_IF randomTrips on the real OSM network, one draw per seed, departures 0-1800 s. REAL METR-LA detector speeds (mph), replayed as lane speed caps on mapped edges in every arm. SIMULATED V2X (pipeline/v2x/channel.py) — not radio hardware: latency 500.0 ms ± 100.0, loss 0.3, TTL 60.0 s.

| pair | metric | n | mean % | median % | 95 % CI | W/L/T | label |
|---|---|---|---|---|---|---|---|
| reactive vs baseline | total_vehicle_hours_incl_never_inserted | 3 | -0.35 | -0.34 | [-1.0, 0.3] | 3/0/0 | **INCONCLUSIVE** |
| reactive vs baseline | mean_travel_time_all | 3 | -0.35 | -0.34 | [-1.0, 0.3] | 3/0/0 | **INCONCLUSIVE** |
| reactive vs baseline | p95_travel_time_s | 3 | -0.15 | -0.07 | [-0.81, 0.51] | 2/1/0 | **INCONCLUSIVE** |
| reactive vs baseline | total_waiting_s | 3 | -0.08 | -0.65 | [-2.8, 2.64] | 2/1/0 | **INCONCLUSIVE** |
| reactive vs baseline | mean_queue_veh | 3 | -0.58 | -0.66 | [-3.37, 2.2] | 2/1/0 | **INCONCLUSIVE** |
| reactive vs baseline | arrived | 3 | 0.2 | 0.23 | [-0.25, 0.64] | 2/0/1 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | total_vehicle_hours_incl_never_inserted | 3 | -0.05 | -0.03 | [-0.18, 0.09] | 2/0/1 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | mean_travel_time_all | 3 | -0.05 | -0.03 | [-0.18, 0.09] | 2/0/1 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | p95_travel_time_s | 3 | -0.56 | -0.96 | [-3.1, 1.98] | 2/1/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | total_waiting_s | 3 | 0.0 | 0.6 | [-2.91, 2.91] | 1/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | mean_queue_veh | 3 | -0.17 | -0.32 | [-1.48, 1.14] | 2/1/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | arrived | 3 | 0.08 | 0.12 | [-0.94, 1.09] | 2/1/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | total_vehicle_hours_incl_never_inserted | 3 | 0.31 | 0.34 | [-0.45, 1.06] | 1/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | mean_travel_time_all | 3 | 0.31 | 0.34 | [-0.45, 1.06] | 1/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | p95_travel_time_s | 3 | -0.41 | -0.52 | [-2.63, 1.81] | 2/1/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | total_waiting_s | 3 | 0.09 | -0.42 | [-2.72, 2.9] | 2/1/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | mean_queue_veh | 3 | 0.43 | 0.34 | [-3.67, 4.52] | 1/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | arrived | 3 | -0.12 | -0.23 | [-0.88, 0.65] | 1/2/0 | **INCONCLUSIVE** |

Network (means over seeds): connected 259 vehicles · uplink TX 16028 RX 11203 PDR 0.6991333333333333 lat med 498.80999999999995 p95 589.6766666666666 ms · downlink TX 20 RX 14 dropped 6 expired 0 PDR 0.7131333333333334 lat med 498.3533333333333 p95 584.6533333333333 ms · reroutes applied 43 · inapplicable 0

- s101 baseline: veh-h 184.5233, mean tt 738 s, p95 1359 s, arrived 858, teleports 0, reroutes applied 0, sim `sim_v2x_s101_baseline_ideal_p30`
- s101 reactive: veh-h 184.3542, mean tt 737 s, p95 1353 s, arrived 860, teleports 0, reroutes applied 0, sim `sim_v2x_s101_reactive_ideal_p30`
- s101 predictive_v2x: veh-h 184.3244, mean tt 737 s, p95 1346 s, arrived 862, teleports 0, reroutes applied 13, sim `sim_v2x_s101_predictive_v2x_degraded_p30`
- s102 baseline: veh-h 182.6078, mean tt 730 s, p95 1359 s, arrived 847, teleports 0, reroutes applied 0, sim `sim_v2x_s102_baseline_ideal_p30`
- s102 reactive: veh-h 181.4856, mean tt 726 s, p95 1358 s, arrived 850, teleports 0, reroutes applied 0, sim `sim_v2x_s102_reactive_ideal_p30`
- s102 predictive_v2x: veh-h 182.5592, mean tt 730 s, p95 1341 s, arrived 848, teleports 0, reroutes applied 19, sim `sim_v2x_s102_predictive_v2x_degraded_p30`
- s103 baseline: veh-h 178.7522, mean tt 715 s, p95 1331 s, arrived 863, teleports 0, reroutes applied 0, sim `sim_v2x_s103_baseline_ideal_p30`
- s103 reactive: veh-h 178.1469, mean tt 713 s, p95 1332 s, arrived 863, teleports 0, reroutes applied 0, sim `sim_v2x_s103_reactive_ideal_p30`
- s103 predictive_v2x: veh-h 178.7519, mean tt 715 s, p95 1339 s, arrived 860, teleports 0, reroutes applied 11, sim `sim_v2x_s103_predictive_v2x_degraded_p30`
