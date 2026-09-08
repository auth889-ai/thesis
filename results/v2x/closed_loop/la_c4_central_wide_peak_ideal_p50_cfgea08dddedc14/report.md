# V2X closed loop — V2X_CLOSED_LOOP_v1 · la_c4_central_wide · profile `ideal` · penetration 0.5 · seeds [101, 102, 103]

Model Graph WaveNet (207-node METR-LA, verified) (ckpt `548e399bd53c`), 83 of 207 detectors mapped, routing config `ea08dddedc14`. SYNTHETIC_WHAT_IF randomTrips on the real OSM network, one draw per seed, departures 0-1800 s. REAL METR-LA detector speeds (mph), replayed as lane speed caps on mapped edges in every arm. SIMULATED V2X (pipeline/v2x/channel.py) — not radio hardware: latency 0.0 ms ± 0.0, loss 0.0, TTL 60.0 s.

| pair | metric | n | mean % | median % | 95 % CI | W/L/T | label |
|---|---|---|---|---|---|---|---|
| reactive vs baseline | total_vehicle_hours_incl_never_inserted | 3 | -0.39 | -0.52 | [-1.26, 0.49] | 2/1/0 | **INCONCLUSIVE** |
| reactive vs baseline | mean_travel_time_all | 3 | -0.39 | -0.52 | [-1.26, 0.49] | 2/1/0 | **INCONCLUSIVE** |
| reactive vs baseline | p95_travel_time_s | 3 | 0.03 | 0.3 | [-2.51, 2.56] | 1/2/0 | **INCONCLUSIVE** |
| reactive vs baseline | total_waiting_s | 3 | 1.12 | 0.47 | [-3.49, 5.73] | 1/2/0 | **INCONCLUSIVE** |
| reactive vs baseline | mean_queue_veh | 3 | 0.74 | 0.11 | [-2.99, 4.47] | 1/2/0 | **INCONCLUSIVE** |
| reactive vs baseline | arrived | 3 | 0.24 | 0.35 | [-0.81, 1.29] | 2/1/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | total_vehicle_hours_incl_never_inserted | 3 | -0.58 | -0.61 | [-1.87, 0.71] | 3/0/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | mean_travel_time_all | 3 | -0.58 | -0.61 | [-1.87, 0.71] | 3/0/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | p95_travel_time_s | 3 | -0.93 | -1.18 | [-2.48, 0.62] | 3/0/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | total_waiting_s | 3 | -0.3 | -1.14 | [-5.36, 4.77] | 2/1/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | mean_queue_veh | 3 | -0.6 | -1.47 | [-4.76, 3.57] | 2/1/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | arrived | 3 | 0.04 | -0.12 | [-0.63, 0.72] | 1/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | total_vehicle_hours_incl_never_inserted | 3 | -0.19 | -0.09 | [-0.71, 0.32] | 3/0/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | mean_travel_time_all | 3 | -0.19 | -0.09 | [-0.71, 0.32] | 3/0/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | p95_travel_time_s | 3 | -0.95 | -0.52 | [-3.31, 1.4] | 3/0/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | total_waiting_s | 3 | -1.4 | -1.47 | [-1.98, -0.83] | 3/0/0 | **HELPED** |
| predictive_v2x vs reactive | mean_queue_veh | 3 | -1.32 | -1.13 | [-2.26, -0.39] | 3/0/0 | **HELPED** |
| predictive_v2x vs reactive | arrived | 3 | -0.19 | -0.23 | [-0.92, 0.53] | 1/2/0 | **INCONCLUSIVE** |

Network (means over seeds): connected 440 vehicles · uplink TX 27249 RX 27249 PDR 1.0 lat med 0.0 p95 0.0 ms · downlink TX 36 RX 36 dropped 0 expired 0 PDR 1.0 lat med 0.0 p95 0.0 ms · reroutes applied 108 · inapplicable 0

- s101 baseline: veh-h 184.5233, mean tt 738 s, p95 1359 s, arrived 858, teleports 0, reroutes applied 0, sim `sim_v2x_s101_baseline_ideal_p30`
- s101 reactive: veh-h 183.5572, mean tt 734 s, p95 1344 s, arrived 861, teleports 0, reroutes applied 0, sim `sim_v2x_s101_reactive_ideal_p50`
- s101 predictive_v2x: veh-h 183.3914, mean tt 734 s, p95 1340 s, arrived 857, teleports 0, reroutes applied 34, sim `sim_v2x_s101_predictive_v2x_ideal_p50`
- s102 baseline: veh-h 182.6078, mean tt 730 s, p95 1359 s, arrived 847, teleports 0, reroutes applied 0, sim `sim_v2x_s102_baseline_ideal_p30`
- s102 reactive: veh-h 182.6281, mean tt 731 s, p95 1371 s, arrived 852, teleports 0, reroutes applied 0, sim `sim_v2x_s102_reactive_ideal_p50`
- s102 predictive_v2x: veh-h 182.5283, mean tt 730 s, p95 1343 s, arrived 850, teleports 0, reroutes applied 39, sim `sim_v2x_s102_predictive_v2x_ideal_p50`
- s103 baseline: veh-h 178.7522, mean tt 715 s, p95 1331 s, arrived 863, teleports 0, reroutes applied 0, sim `sim_v2x_s103_baseline_ideal_p30`
- s103 reactive: veh-h 177.5856, mean tt 710 s, p95 1335 s, arrived 861, teleports 0, reroutes applied 0, sim `sim_v2x_s103_reactive_ideal_p50`
- s103 predictive_v2x: veh-h 176.8203, mean tt 707 s, p95 1328 s, arrived 862, teleports 0, reroutes applied 35, sim `sim_v2x_s103_predictive_v2x_ideal_p50`
