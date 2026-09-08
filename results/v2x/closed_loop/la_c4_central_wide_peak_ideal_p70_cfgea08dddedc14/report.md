# V2X closed loop — V2X_CLOSED_LOOP_v1 · la_c4_central_wide · profile `ideal` · penetration 0.7 · seeds [101, 102, 103]

Model Graph WaveNet (207-node METR-LA, verified) (ckpt `548e399bd53c`), 83 of 207 detectors mapped, routing config `ea08dddedc14`. SYNTHETIC_WHAT_IF randomTrips on the real OSM network, one draw per seed, departures 0-1800 s. REAL METR-LA detector speeds (mph), replayed as lane speed caps on mapped edges in every arm. SIMULATED V2X (pipeline/v2x/channel.py) — not radio hardware: latency 0.0 ms ± 0.0, loss 0.0, TTL 60.0 s.

| pair | metric | n | mean % | median % | 95 % CI | W/L/T | label |
|---|---|---|---|---|---|---|---|
| reactive vs baseline | total_vehicle_hours_incl_never_inserted | 3 | -0.57 | -0.48 | [-1.65, 0.51] | 3/0/0 | **INCONCLUSIVE** |
| reactive vs baseline | mean_travel_time_all | 3 | -0.57 | -0.48 | [-1.65, 0.51] | 3/0/0 | **INCONCLUSIVE** |
| reactive vs baseline | p95_travel_time_s | 3 | -1.35 | -2.13 | [-4.89, 2.2] | 2/1/0 | **INCONCLUSIVE** |
| reactive vs baseline | total_waiting_s | 3 | 1.33 | 2.14 | [-2.99, 5.65] | 1/2/0 | **INCONCLUSIVE** |
| reactive vs baseline | mean_queue_veh | 3 | 1.13 | 1.38 | [-1.07, 3.32] | 0/3/0 | **INCONCLUSIVE** |
| reactive vs baseline | arrived | 3 | 0.24 | 0.0 | [-1.31, 1.79] | 1/1/1 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | total_vehicle_hours_incl_never_inserted | 3 | -0.34 | -0.29 | [-0.76, 0.08] | 3/0/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | mean_travel_time_all | 3 | -0.34 | -0.29 | [-0.76, 0.08] | 3/0/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | p95_travel_time_s | 3 | 0.35 | 0.66 | [-1.36, 2.06] | 1/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | total_waiting_s | 3 | 0.42 | 0.45 | [-0.46, 1.3] | 0/3/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | mean_queue_veh | 3 | 0.67 | 0.45 | [-1.03, 2.38] | 0/3/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | arrived | 3 | -0.04 | -0.12 | [-0.37, 0.3] | 1/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | total_vehicle_hours_incl_never_inserted | 3 | 0.23 | -0.05 | [-1.09, 1.55] | 2/1/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | mean_travel_time_all | 3 | 0.23 | -0.05 | [-1.09, 1.55] | 2/1/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | p95_travel_time_s | 3 | 1.73 | 1.81 | [-1.17, 4.63] | 0/3/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | total_waiting_s | 3 | -0.87 | -1.65 | [-5.93, 4.19] | 2/1/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | mean_queue_veh | 3 | -0.44 | -0.91 | [-4.3, 3.42] | 2/1/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | arrived | 3 | -0.27 | -0.12 | [-1.48, 0.94] | 1/2/0 | **INCONCLUSIVE** |

Network (means over seeds): connected 612 vehicles · uplink TX 38184 RX 38184 PDR 1.0 lat med 0.0 p95 0.0 ms · downlink TX 45 RX 45 dropped 0 expired 0 PDR 1.0 lat med 0.0 p95 0.0 ms · reroutes applied 134 · inapplicable 0

- s101 baseline: veh-h 184.5233, mean tt 738 s, p95 1359 s, arrived 858, teleports 0, reroutes applied 0, sim `sim_v2x_s101_baseline_ideal_p30`
- s101 reactive: veh-h 184.1861, mean tt 737 s, p95 1330 s, arrived 858, teleports 0, reroutes applied 0, sim `sim_v2x_s101_reactive_ideal_p70`
- s101 predictive_v2x: veh-h 183.9931, mean tt 736 s, p95 1368 s, arrived 857, teleports 0, reroutes applied 44, sim `sim_v2x_s101_predictive_v2x_ideal_p70`
- s102 baseline: veh-h 182.6078, mean tt 730 s, p95 1359 s, arrived 847, teleports 0, reroutes applied 0, sim `sim_v2x_s102_baseline_ideal_p30`
- s102 reactive: veh-h 181.73, mean tt 727 s, p95 1329 s, arrived 855, teleports 0, reroutes applied 0, sim `sim_v2x_s102_reactive_ideal_p70`
- s102 predictive_v2x: veh-h 181.6403, mean tt 727 s, p95 1353 s, arrived 848, teleports 0, reroutes applied 50, sim `sim_v2x_s102_predictive_v2x_ideal_p70`
- s103 baseline: veh-h 178.7522, mean tt 715 s, p95 1331 s, arrived 863, teleports 0, reroutes applied 0, sim `sim_v2x_s103_baseline_ideal_p30`
- s103 reactive: veh-h 176.8897, mean tt 708 s, p95 1335 s, arrived 861, teleports 0, reroutes applied 0, sim `sim_v2x_s103_reactive_ideal_p70`
- s103 predictive_v2x: veh-h 178.3797, mean tt 714 s, p95 1342 s, arrived 862, teleports 0, reroutes applied 40, sim `sim_v2x_s103_predictive_v2x_ideal_p70`
