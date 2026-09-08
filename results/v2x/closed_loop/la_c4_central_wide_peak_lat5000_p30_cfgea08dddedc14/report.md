# V2X closed loop — V2X_CLOSED_LOOP_v1 · la_c4_central_wide · profile `lat5000` · penetration 0.3 · seeds [101, 102, 103]

Model Graph WaveNet (207-node METR-LA, verified) (ckpt `548e399bd53c`), 83 of 207 detectors mapped, routing config `ea08dddedc14`. SYNTHETIC_WHAT_IF randomTrips on the real OSM network, one draw per seed, departures 0-1800 s. REAL METR-LA detector speeds (mph), replayed as lane speed caps on mapped edges in every arm. SIMULATED V2X (pipeline/v2x/channel.py) — not radio hardware: latency 5000.0 ms ± 500.0, loss 0.0, TTL 60.0 s.

| pair | metric | n | mean % | median % | 95 % CI | W/L/T | label |
|---|---|---|---|---|---|---|---|
| reactive vs baseline | total_vehicle_hours_incl_never_inserted | 3 | -0.35 | -0.34 | [-1.0, 0.3] | 3/0/0 | **INCONCLUSIVE** |
| reactive vs baseline | mean_travel_time_all | 3 | -0.35 | -0.34 | [-1.0, 0.3] | 3/0/0 | **INCONCLUSIVE** |
| reactive vs baseline | p95_travel_time_s | 3 | -0.15 | -0.07 | [-0.81, 0.51] | 2/1/0 | **INCONCLUSIVE** |
| reactive vs baseline | total_waiting_s | 3 | -0.08 | -0.65 | [-2.8, 2.64] | 2/1/0 | **INCONCLUSIVE** |
| reactive vs baseline | mean_queue_veh | 3 | -0.58 | -0.66 | [-3.37, 2.2] | 2/1/0 | **INCONCLUSIVE** |
| reactive vs baseline | arrived | 3 | 0.2 | 0.23 | [-0.25, 0.64] | 2/0/1 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | total_vehicle_hours_incl_never_inserted | 3 | 0.23 | 0.22 | [-0.81, 1.28] | 1/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | mean_travel_time_all | 3 | 0.23 | 0.22 | [-0.81, 1.28] | 1/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | p95_travel_time_s | 3 | 0.56 | -0.37 | [-4.92, 6.04] | 2/1/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | total_waiting_s | 3 | 1.62 | 2.35 | [-1.59, 4.84] | 0/3/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | mean_queue_veh | 3 | 0.75 | 0.86 | [-2.04, 3.53] | 1/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | arrived | 3 | 0.23 | 0.12 | [-0.27, 0.74] | 3/0/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | total_vehicle_hours_incl_never_inserted | 3 | 0.59 | 0.84 | [-0.88, 2.05] | 1/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | mean_travel_time_all | 3 | 0.59 | 0.84 | [-0.88, 2.05] | 1/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | p95_travel_time_s | 3 | 0.71 | -0.29 | [-4.25, 5.66] | 2/1/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | total_waiting_s | 3 | 1.72 | 3.02 | [-4.23, 7.68] | 1/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | mean_queue_veh | 3 | 1.35 | 2.48 | [-3.7, 6.41] | 1/2/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | arrived | 3 | 0.04 | 0.12 | [-0.29, 0.37] | 2/1/0 | **INCONCLUSIVE** |

Network (means over seeds): connected 259 vehicles · uplink TX 15973 RX 15968 PDR 0.9996333333333333 lat med 4995.746666666667 p95 5447.833333333333 ms · downlink TX 17 RX 17 dropped 0 expired 0 PDR 1.0 lat med 5067.09 p95 5461.320000000001 ms · reroutes applied 49 · inapplicable 2

- s101 baseline: veh-h 184.5233, mean tt 738 s, p95 1359 s, arrived 858, teleports 0, reroutes applied 0, sim `sim_v2x_s101_baseline_ideal_p30`
- s101 reactive: veh-h 184.3542, mean tt 737 s, p95 1353 s, arrived 860, teleports 0, reroutes applied 0, sim `sim_v2x_s101_reactive_ideal_p30`
- s101 predictive_v2x: veh-h 184.1869, mean tt 737 s, p95 1345 s, arrived 859, teleports 0, reroutes applied 14, sim `sim_v2x_s101_predictive_v2x_lat5000_p30`
- s102 baseline: veh-h 182.6078, mean tt 730 s, p95 1359 s, arrived 847, teleports 0, reroutes applied 0, sim `sim_v2x_s102_baseline_ideal_p30`
- s102 reactive: veh-h 181.4856, mean tt 726 s, p95 1358 s, arrived 850, teleports 0, reroutes applied 0, sim `sim_v2x_s102_reactive_ideal_p30`
- s102 predictive_v2x: veh-h 183.0175, mean tt 732 s, p95 1354 s, arrived 851, teleports 0, reroutes applied 21, sim `sim_v2x_s102_predictive_v2x_lat5000_p30`
- s103 baseline: veh-h 178.7522, mean tt 715 s, p95 1331 s, arrived 863, teleports 0, reroutes applied 0, sim `sim_v2x_s103_baseline_ideal_p30`
- s103 reactive: veh-h 178.1469, mean tt 713 s, p95 1332 s, arrived 863, teleports 0, reroutes applied 0, sim `sim_v2x_s103_reactive_ideal_p30`
- s103 predictive_v2x: veh-h 179.9333, mean tt 720 s, p95 1372 s, arrived 864, teleports 0, reroutes applied 14, sim `sim_v2x_s103_predictive_v2x_lat5000_p30`
