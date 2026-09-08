# V2X closed loop — V2X_CLOSED_LOOP_v1 · la_c4_central_wide · profile `ideal` · penetration 0.1 · seeds [101, 102, 103]

Model Graph WaveNet (207-node METR-LA, verified) (ckpt `548e399bd53c`), 83 of 207 detectors mapped, routing config `ea08dddedc14`. SYNTHETIC_WHAT_IF randomTrips on the real OSM network, one draw per seed, departures 0-1800 s. REAL METR-LA detector speeds (mph), replayed as lane speed caps on mapped edges in every arm. SIMULATED V2X (pipeline/v2x/channel.py) — not radio hardware: latency 0.0 ms ± 0.0, loss 0.0, TTL 60.0 s.

| pair | metric | n | mean % | median % | 95 % CI | W/L/T | label |
|---|---|---|---|---|---|---|---|
| reactive vs baseline | total_vehicle_hours_incl_never_inserted | 3 | -0.08 | -0.03 | [-0.68, 0.51] | 2/1/0 | **INCONCLUSIVE** |
| reactive vs baseline | mean_travel_time_all | 3 | -0.08 | -0.03 | [-0.68, 0.51] | 2/1/0 | **INCONCLUSIVE** |
| reactive vs baseline | p95_travel_time_s | 3 | -0.39 | -0.59 | [-3.0, 2.23] | 2/1/0 | **INCONCLUSIVE** |
| reactive vs baseline | total_waiting_s | 3 | -0.59 | -0.78 | [-1.88, 0.71] | 2/1/0 | **INCONCLUSIVE** |
| reactive vs baseline | mean_queue_veh | 3 | -0.66 | -0.4 | [-2.07, 0.75] | 3/0/0 | **INCONCLUSIVE** |
| reactive vs baseline | arrived | 3 | 0.04 | 0.12 | [-0.3, 0.37] | 2/1/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | total_vehicle_hours_incl_never_inserted | 3 | 0.05 | 0.13 | [-0.49, 0.59] | 1/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | mean_travel_time_all | 3 | 0.05 | 0.13 | [-0.49, 0.59] | 1/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | p95_travel_time_s | 3 | 0.08 | 0.22 | [-0.73, 0.88] | 1/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | total_waiting_s | 3 | 0.35 | 0.86 | [-2.52, 3.22] | 1/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | mean_queue_veh | 3 | 0.29 | 0.37 | [-0.4, 0.97] | 1/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | arrived | 3 | -0.04 | -0.12 | [-0.64, 0.56] | 1/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | total_vehicle_hours_incl_never_inserted | 3 | 0.14 | 0.01 | [-0.82, 1.09] | 1/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | mean_travel_time_all | 3 | 0.14 | 0.01 | [-0.82, 1.09] | 1/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | p95_travel_time_s | 3 | 0.47 | 0.81 | [-1.52, 2.46] | 1/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | total_waiting_s | 3 | 0.94 | 0.86 | [-2.01, 3.89] | 1/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | mean_queue_veh | 3 | 0.95 | 0.92 | [-0.85, 2.76] | 0/3/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | arrived | 3 | -0.08 | 0.0 | [-0.69, 0.53] | 1/1/1 | **INCONCLUSIVE** |

Network (means over seeds): connected 88 vehicles · uplink TX 5457 RX 5457 PDR 1.0 lat med 0.0 p95 0.0 ms · downlink TX 7 RX 7 dropped 0 expired 0 PDR 1.0 lat med 0.0 p95 0.0 ms · reroutes applied 20 · inapplicable 0

- s101 baseline: veh-h 184.5233, mean tt 738 s, p95 1359 s, arrived 858, teleports 0, reroutes applied 0, sim `sim_v2x_s101_baseline_ideal_p30`
- s101 reactive: veh-h 183.8825, mean tt 736 s, p95 1351 s, arrived 857, teleports 0, reroutes applied 0, sim `sim_v2x_s101_reactive_ideal_p10`
- s101 predictive_v2x: veh-h 184.9308, mean tt 740 s, p95 1362 s, arrived 857, teleports 0, reroutes applied 4, sim `sim_v2x_s101_predictive_v2x_ideal_p10`
- s102 baseline: veh-h 182.6078, mean tt 730 s, p95 1359 s, arrived 847, teleports 0, reroutes applied 0, sim `sim_v2x_s102_baseline_ideal_p30`
- s102 reactive: veh-h 182.5572, mean tt 730 s, p95 1341 s, arrived 848, teleports 0, reroutes applied 0, sim `sim_v2x_s102_reactive_ideal_p10`
- s102 predictive_v2x: veh-h 182.2547, mean tt 729 s, p95 1355 s, arrived 845, teleports 0, reroutes applied 9, sim `sim_v2x_s102_predictive_v2x_ideal_p10`
- s103 baseline: veh-h 178.7522, mean tt 715 s, p95 1331 s, arrived 863, teleports 0, reroutes applied 0, sim `sim_v2x_s103_baseline_ideal_p30`
- s103 reactive: veh-h 178.9714, mean tt 716 s, p95 1341 s, arrived 864, teleports 0, reroutes applied 0, sim `sim_v2x_s103_reactive_ideal_p10`
- s103 predictive_v2x: veh-h 178.9831, mean tt 716 s, p95 1335 s, arrived 865, teleports 0, reroutes applied 7, sim `sim_v2x_s103_predictive_v2x_ideal_p10`
