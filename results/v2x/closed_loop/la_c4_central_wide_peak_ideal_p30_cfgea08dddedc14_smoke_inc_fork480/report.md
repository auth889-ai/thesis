# V2X closed loop — V2X_CLOSED_LOOP_v1 · la_c4_central_wide · profile `ideal` · penetration 0.3 · seeds [101]

Model Graph WaveNet (207-node METR-LA, verified) (ckpt `548e399bd53c`), 83 of 207 detectors mapped, routing config `ea08dddedc14`. SYNTHETIC_WHAT_IF randomTrips on the real OSM network, one draw per seed, departures 0-1800 s. REAL METR-LA detector speeds (mph), replayed as lane speed caps on mapped edges in every arm. SIMULATED V2X (pipeline/v2x/channel.py) — not radio hardware: latency 0.0 ms ± 0.0, loss 0.0, TTL 60.0 s.

Identical-state fork at 480 s: state hashes {101: '6d0cfaec52ba'} — identical across arms: **True**. Reroutes applied by arm: {'baseline': 0, 'reactive': 0, 'persistence_v2x': 18, 'predictive_v2x': 16, 'oracle_v2x': 134, 'random_v2x': 32}.

| pair | metric | n | mean % | median % | 95 % CI | W/L/T | label |
|---|---|---|---|---|---|---|---|
| reactive vs baseline | total_vehicle_hours_incl_never_inserted | 1 | -0.75 | -0.75 | [None, None] | 1/0/0 | **INCONCLUSIVE** |
| reactive vs baseline | mean_travel_time_all | 1 | -0.75 | -0.75 | [None, None] | 1/0/0 | **INCONCLUSIVE** |
| reactive vs baseline | p95_travel_time_s | 1 | -1.07 | -1.07 | [None, None] | 1/0/0 | **INCONCLUSIVE** |
| reactive vs baseline | total_waiting_s | 1 | 0.95 | 0.95 | [None, None] | 0/1/0 | **INCONCLUSIVE** |
| reactive vs baseline | mean_queue_veh | 1 | 0.33 | 0.33 | [None, None] | 0/1/0 | **INCONCLUSIVE** |
| reactive vs baseline | arrived | 1 | 0.48 | 0.48 | [None, None] | 1/0/0 | **INCONCLUSIVE** |
| persistence_v2x vs baseline | total_vehicle_hours_incl_never_inserted | 1 | -0.45 | -0.45 | [None, None] | 1/0/0 | **INCONCLUSIVE** |
| persistence_v2x vs baseline | mean_travel_time_all | 1 | -0.45 | -0.45 | [None, None] | 1/0/0 | **INCONCLUSIVE** |
| persistence_v2x vs baseline | p95_travel_time_s | 1 | 0.0 | 0.0 | [None, None] | 0/0/1 | **INCONCLUSIVE** |
| persistence_v2x vs baseline | total_waiting_s | 1 | -0.67 | -0.67 | [None, None] | 1/0/0 | **INCONCLUSIVE** |
| persistence_v2x vs baseline | mean_queue_veh | 1 | -0.38 | -0.38 | [None, None] | 1/0/0 | **INCONCLUSIVE** |
| persistence_v2x vs baseline | arrived | 1 | 0.0 | 0.0 | [None, None] | 0/0/1 | **INCONCLUSIVE** |
| persistence_v2x vs reactive | total_vehicle_hours_incl_never_inserted | 1 | 0.3 | 0.3 | [None, None] | 0/1/0 | **INCONCLUSIVE** |
| persistence_v2x vs reactive | mean_travel_time_all | 1 | 0.3 | 0.3 | [None, None] | 0/1/0 | **INCONCLUSIVE** |
| persistence_v2x vs reactive | p95_travel_time_s | 1 | 1.08 | 1.08 | [None, None] | 0/1/0 | **INCONCLUSIVE** |
| persistence_v2x vs reactive | total_waiting_s | 1 | -1.6 | -1.6 | [None, None] | 1/0/0 | **INCONCLUSIVE** |
| persistence_v2x vs reactive | mean_queue_veh | 1 | -0.71 | -0.71 | [None, None] | 1/0/0 | **INCONCLUSIVE** |
| persistence_v2x vs reactive | arrived | 1 | -0.48 | -0.48 | [None, None] | 0/1/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | total_vehicle_hours_incl_never_inserted | 1 | -0.64 | -0.64 | [None, None] | 1/0/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | mean_travel_time_all | 1 | -0.64 | -0.64 | [None, None] | 1/0/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | p95_travel_time_s | 1 | 0.28 | 0.28 | [None, None] | 0/1/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | total_waiting_s | 1 | -0.84 | -0.84 | [None, None] | 1/0/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | mean_queue_veh | 1 | -1.62 | -1.62 | [None, None] | 1/0/0 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | arrived | 1 | 0.24 | 0.24 | [None, None] | 1/0/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | total_vehicle_hours_incl_never_inserted | 1 | 0.11 | 0.11 | [None, None] | 0/1/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | mean_travel_time_all | 1 | 0.11 | 0.11 | [None, None] | 0/1/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | p95_travel_time_s | 1 | 1.37 | 1.37 | [None, None] | 0/1/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | total_waiting_s | 1 | -1.78 | -1.78 | [None, None] | 1/0/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | mean_queue_veh | 1 | -1.95 | -1.95 | [None, None] | 1/0/0 | **INCONCLUSIVE** |
| predictive_v2x vs reactive | arrived | 1 | -0.24 | -0.24 | [None, None] | 0/1/0 | **INCONCLUSIVE** |
| oracle_v2x vs baseline | total_vehicle_hours_incl_never_inserted | 1 | -0.87 | -0.87 | [None, None] | 1/0/0 | **INCONCLUSIVE** |
| oracle_v2x vs baseline | mean_travel_time_all | 1 | -0.87 | -0.87 | [None, None] | 1/0/0 | **INCONCLUSIVE** |
| oracle_v2x vs baseline | p95_travel_time_s | 1 | -2.28 | -2.28 | [None, None] | 1/0/0 | **INCONCLUSIVE** |
| oracle_v2x vs baseline | total_waiting_s | 1 | -6.06 | -6.06 | [None, None] | 1/0/0 | **INCONCLUSIVE** |
| oracle_v2x vs baseline | mean_queue_veh | 1 | -7.34 | -7.34 | [None, None] | 1/0/0 | **INCONCLUSIVE** |
| oracle_v2x vs baseline | arrived | 1 | 0.48 | 0.48 | [None, None] | 1/0/0 | **INCONCLUSIVE** |
| oracle_v2x vs reactive | total_vehicle_hours_incl_never_inserted | 1 | -0.12 | -0.12 | [None, None] | 1/0/0 | **INCONCLUSIVE** |
| oracle_v2x vs reactive | mean_travel_time_all | 1 | -0.12 | -0.12 | [None, None] | 1/0/0 | **INCONCLUSIVE** |
| oracle_v2x vs reactive | p95_travel_time_s | 1 | -1.22 | -1.22 | [None, None] | 1/0/0 | **INCONCLUSIVE** |
| oracle_v2x vs reactive | total_waiting_s | 1 | -6.95 | -6.95 | [None, None] | 1/0/0 | **INCONCLUSIVE** |
| oracle_v2x vs reactive | mean_queue_veh | 1 | -7.64 | -7.64 | [None, None] | 1/0/0 | **INCONCLUSIVE** |
| oracle_v2x vs reactive | arrived | 1 | 0.0 | 0.0 | [None, None] | 0/0/1 | **INCONCLUSIVE** |
| random_v2x vs baseline | total_vehicle_hours_incl_never_inserted | 1 | 0.78 | 0.78 | [None, None] | 0/1/0 | **INCONCLUSIVE** |
| random_v2x vs baseline | mean_travel_time_all | 1 | 0.78 | 0.78 | [None, None] | 0/1/0 | **INCONCLUSIVE** |
| random_v2x vs baseline | p95_travel_time_s | 1 | 1.49 | 1.49 | [None, None] | 0/1/0 | **INCONCLUSIVE** |
| random_v2x vs baseline | total_waiting_s | 1 | 2.46 | 2.46 | [None, None] | 0/1/0 | **INCONCLUSIVE** |
| random_v2x vs baseline | mean_queue_veh | 1 | 3.16 | 3.16 | [None, None] | 0/1/0 | **INCONCLUSIVE** |
| random_v2x vs baseline | arrived | 1 | -0.36 | -0.36 | [None, None] | 0/1/0 | **INCONCLUSIVE** |
| random_v2x vs reactive | total_vehicle_hours_incl_never_inserted | 1 | 1.54 | 1.54 | [None, None] | 0/1/0 | **INCONCLUSIVE** |
| random_v2x vs reactive | mean_travel_time_all | 1 | 1.54 | 1.54 | [None, None] | 0/1/0 | **INCONCLUSIVE** |
| random_v2x vs reactive | p95_travel_time_s | 1 | 2.59 | 2.59 | [None, None] | 0/1/0 | **INCONCLUSIVE** |
| random_v2x vs reactive | total_waiting_s | 1 | 1.49 | 1.49 | [None, None] | 0/1/0 | **INCONCLUSIVE** |
| random_v2x vs reactive | mean_queue_veh | 1 | 2.82 | 2.82 | [None, None] | 0/1/0 | **INCONCLUSIVE** |
| random_v2x vs reactive | arrived | 1 | -0.84 | -0.84 | [None, None] | 0/1/0 | **INCONCLUSIVE** |
| predictive_v2x vs oracle_v2x | total_vehicle_hours_incl_never_inserted | 1 | 0.23 | 0.23 | [None, None] | 0/1/0 | **INCONCLUSIVE** |
| predictive_v2x vs oracle_v2x | mean_travel_time_all | 1 | 0.23 | 0.23 | [None, None] | 0/1/0 | **INCONCLUSIVE** |
| predictive_v2x vs oracle_v2x | p95_travel_time_s | 1 | 2.62 | 2.62 | [None, None] | 0/1/0 | **INCONCLUSIVE** |
| predictive_v2x vs oracle_v2x | total_waiting_s | 1 | 5.56 | 5.56 | [None, None] | 0/1/0 | **INCONCLUSIVE** |
| predictive_v2x vs oracle_v2x | mean_queue_veh | 1 | 6.16 | 6.16 | [None, None] | 0/1/0 | **INCONCLUSIVE** |
| predictive_v2x vs oracle_v2x | arrived | 1 | -0.24 | -0.24 | [None, None] | 0/1/0 | **INCONCLUSIVE** |
| predictive_v2x vs oracle_v2x | teleports | 1 | -100.0 | -100.0 | [None, None] | 1/0/0 | **INCONCLUSIVE** |

Network (means over seeds): connected 247 vehicles · uplink TX 14560 RX 14560 PDR 1.0 lat med 0.0 p95 0.0 ms · downlink TX 16 RX 16 dropped 0 expired 0 PDR 1.0 lat med 0.0 p95 0.0 ms · reroutes applied 16 · inapplicable 0

- s101 baseline: veh-h 187.7333, mean tt 769 s, p95 1406 s, arrived 832, teleports 0, reroutes applied 0, sim `sim_v2x_s101_baseline_ideal_p30`
- s101 reactive: veh-h 186.3278, mean tt 763 s, p95 1391 s, arrived 836, teleports 0, reroutes applied 0, sim `sim_v2x_s101_reactive_ideal_p30`
- s101 persistence_v2x: veh-h 186.8931, mean tt 765 s, p95 1406 s, arrived 832, teleports 0, reroutes applied 18, sim `sim_v2x_s101_persistence_v2x_ideal_p30`
- s101 predictive_v2x: veh-h 186.5325, mean tt 764 s, p95 1410 s, arrived 834, teleports 0, reroutes applied 16, sim `sim_v2x_s101_predictive_v2x_ideal_p30`
- s101 oracle_v2x: veh-h 186.0978, mean tt 762 s, p95 1374 s, arrived 836, teleports 1, reroutes applied 134, sim `sim_v2x_s101_oracle_v2x_ideal_p30`
- s101 random_v2x: veh-h 189.2014, mean tt 775 s, p95 1427 s, arrived 829, teleports 0, reroutes applied 32, sim `sim_v2x_s101_random_v2x_ideal_p30`
