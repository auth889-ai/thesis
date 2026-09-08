# V2X closed loop — V2X_CLOSED_LOOP_v1 · la_c4_central_wide · profile `ideal` · penetration 0.3 · seeds [101]

Model Graph WaveNet (207-node METR-LA, verified) (ckpt `548e399bd53c`), 83 of 207 detectors mapped, routing config `ea08dddedc14`. SYNTHETIC_WHAT_IF randomTrips on the real OSM network, one draw per seed, departures 0-1800 s. REAL METR-LA detector speeds (mph), replayed as lane speed caps on mapped edges in every arm. SIMULATED V2X (pipeline/v2x/channel.py) — not radio hardware: latency 0.0 ms ± 0.0, loss 0.0, TTL 60.0 s.

| pair | metric | n | mean % | median % | 95 % CI | W/L/T | label |
|---|---|---|---|---|---|---|---|
| reactive vs baseline | total_vehicle_hours_incl_never_inserted | 1 | -0.09 | -0.09 | [None, None] | 1/0/0 | **INCONCLUSIVE** |
| reactive vs baseline | mean_travel_time_all | 1 | -0.09 | -0.09 | [None, None] | 1/0/0 | **INCONCLUSIVE** |
| reactive vs baseline | p95_travel_time_s | 1 | -0.44 | -0.44 | [None, None] | 1/0/0 | **INCONCLUSIVE** |
| reactive vs baseline | total_waiting_s | 1 | 1.18 | 1.18 | [None, None] | 0/1/0 | **INCONCLUSIVE** |
| reactive vs baseline | mean_queue_veh | 1 | 0.57 | 0.57 | [None, None] | 0/1/0 | **INCONCLUSIVE** |
| reactive vs baseline | arrived | 1 | 0.23 | 0.23 | [None, None] | 1/0/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | total_vehicle_hours_incl_never_inserted | 1 | -0.63 | -0.63 | [None, None] | 1/0/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | mean_travel_time_all | 1 | -0.63 | -0.63 | [None, None] | 1/0/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | p95_travel_time_s | 1 | -1.47 | -1.47 | [None, None] | 1/0/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | total_waiting_s | 1 | -1.18 | -1.18 | [None, None] | 1/0/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | mean_queue_veh | 1 | -1.62 | -1.62 | [None, None] | 1/0/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | arrived | 1 | 0.23 | 0.23 | [None, None] | 1/0/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | total_vehicle_hours_incl_never_inserted | 1 | -0.54 | -0.54 | [None, None] | 1/0/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | mean_travel_time_all | 1 | -0.54 | -0.54 | [None, None] | 1/0/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | p95_travel_time_s | 1 | -1.03 | -1.03 | [None, None] | 1/0/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | total_waiting_s | 1 | -2.34 | -2.34 | [None, None] | 1/0/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | mean_queue_veh | 1 | -2.18 | -2.18 | [None, None] | 1/0/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | arrived | 1 | 0.0 | 0.0 | [None, None] | 0/0/1 | **INCONCLUSIVE** |

Network (means over seeds): connected 253 vehicles · uplink TX 15342 RX 15342 PDR 1.0 lat med 0.0 p95 0.0 ms · downlink TX 17 RX 17 dropped 0 expired 0 PDR 1.0 lat med 0.0 p95 0.0 ms · reroutes applied 17 · inapplicable 0

- s101 baseline: veh-h 184.5233, mean tt 738 s, p95 1359 s, arrived 858, teleports 0, reroutes applied 0, sim `sim_v2x_s101_baseline_ideal_p30`
- s101 reactive: veh-h 184.3542, mean tt 737 s, p95 1353 s, arrived 860, teleports 0, reroutes applied 0, sim `sim_v2x_s101_reactive_ideal_p30`
- s101 predictive_v2x: veh-h 183.3681, mean tt 733 s, p95 1339 s, arrived 860, teleports 0, reroutes applied 17, sim `sim_v2x_s101_predictive_v2x_ideal_p30`
