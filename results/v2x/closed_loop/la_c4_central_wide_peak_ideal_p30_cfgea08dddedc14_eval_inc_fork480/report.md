# V2X closed loop — V2X_CLOSED_LOOP_v1 · la_c4_central_wide · profile `ideal` · penetration 0.3 · seeds [201, 202, 203]

Model Graph WaveNet (207-node METR-LA, verified) (ckpt `548e399bd53c`), 83 of 207 detectors mapped, routing config `ea08dddedc14`. SYNTHETIC_WHAT_IF randomTrips on the real OSM network, one draw per seed, departures 0-1800 s. REAL METR-LA detector speeds (mph), replayed as lane speed caps on mapped edges in every arm. SIMULATED V2X (pipeline/v2x/channel.py) — not radio hardware: latency 0.0 ms ± 0.0, loss 0.0, TTL 60.0 s.

Identical-state fork at 480 s: state hashes {201: 'ca834c1b8521', 202: 'a283e520239c', 203: '14d39c869860'} — identical across arms: **True**. Reroutes applied by arm: {'baseline': 0, 'reactive': 0, 'predictive_corrected_v2x': 78, 'oracle_v2x': 112}.

| pair | metric | n | mean % | median % | 95 % CI | W/L/T | label |
|---|---|---|---|---|---|---|---|
| reactive vs baseline | total_vehicle_hours_incl_never_inserted | 3 | -0.5 | -0.28 | [-2.42, 1.42] | 2/1/0 | **INCONCLUSIVE** |
| reactive vs baseline | mean_travel_time_all | 3 | -0.5 | -0.28 | [-2.42, 1.42] | 2/1/0 | **INCONCLUSIVE** |
| reactive vs baseline | p95_travel_time_s | 3 | -0.6 | -0.36 | [-2.83, 1.62] | 2/1/0 | **INCONCLUSIVE** |
| reactive vs baseline | total_waiting_s | 3 | 1.4 | 1.33 | [-2.56, 5.36] | 1/2/0 | **INCONCLUSIVE** |
| reactive vs baseline | mean_queue_veh | 3 | 2.42 | 2.7 | [-0.71, 5.56] | 0/3/0 | **INCONCLUSIVE** |
| reactive vs baseline | arrived | 3 | -0.48 | -0.49 | [-1.67, 0.71] | 0/2/1 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs baseline | total_vehicle_hours_incl_never_inserted | 3 | -0.13 | 0.04 | [-0.89, 0.62] | 1/2/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs baseline | mean_travel_time_all | 3 | -0.13 | 0.04 | [-0.89, 0.62] | 1/2/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs baseline | p95_travel_time_s | 3 | -1.1 | -1.43 | [-3.04, 0.83] | 3/0/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs baseline | total_waiting_s | 3 | 0.91 | 0.6 | [-1.49, 3.3] | 0/3/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs baseline | mean_queue_veh | 3 | 1.73 | 1.9 | [-1.51, 4.96] | 0/3/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs baseline | arrived | 3 | -0.25 | 0.0 | [-1.57, 1.08] | 1/1/1 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs reactive | total_vehicle_hours_incl_never_inserted | 3 | 0.38 | 0.32 | [-0.85, 1.6] | 1/2/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs reactive | mean_travel_time_all | 3 | 0.38 | 0.32 | [-0.85, 1.6] | 1/2/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs reactive | p95_travel_time_s | 3 | -0.5 | -0.36 | [-1.79, 0.79] | 3/0/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs reactive | total_waiting_s | 3 | -0.48 | -0.71 | [-2.17, 1.21] | 2/1/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs reactive | mean_queue_veh | 3 | -0.66 | -0.78 | [-6.81, 5.48] | 2/1/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs reactive | arrived | 3 | 0.24 | 0.0 | [-1.64, 2.12] | 1/1/1 | **INCONCLUSIVE** |
| oracle_v2x vs baseline | total_vehicle_hours_incl_never_inserted | 3 | -0.6 | -0.47 | [-1.26, 0.07] | 3/0/0 | **INCONCLUSIVE** |
| oracle_v2x vs baseline | mean_travel_time_all | 3 | -0.6 | -0.47 | [-1.26, 0.07] | 3/0/0 | **INCONCLUSIVE** |
| oracle_v2x vs baseline | p95_travel_time_s | 3 | -1.25 | -0.57 | [-5.81, 3.3] | 2/1/0 | **INCONCLUSIVE** |
| oracle_v2x vs baseline | total_waiting_s | 3 | -0.67 | -0.61 | [-3.57, 2.23] | 2/1/0 | **INCONCLUSIVE** |
| oracle_v2x vs baseline | mean_queue_veh | 3 | -0.79 | -1.11 | [-2.79, 1.21] | 2/1/0 | **INCONCLUSIVE** |
| oracle_v2x vs baseline | arrived | 3 | -0.17 | 0.12 | [-1.94, 1.61] | 2/1/0 | **INCONCLUSIVE** |
| oracle_v2x vs reactive | total_vehicle_hours_incl_never_inserted | 3 | -0.09 | -0.13 | [-1.42, 1.24] | 2/1/0 | **INCONCLUSIVE** |
| oracle_v2x vs reactive | mean_travel_time_all | 3 | -0.09 | -0.13 | [-1.42, 1.24] | 2/1/0 | **INCONCLUSIVE** |
| oracle_v2x vs reactive | p95_travel_time_s | 3 | -0.66 | -0.22 | [-3.05, 1.73] | 2/0/1 | **INCONCLUSIVE** |
| oracle_v2x vs reactive | total_waiting_s | 3 | -2.04 | -1.92 | [-3.03, -1.04] | 3/0/0 | **HELPED** |
| oracle_v2x vs reactive | mean_queue_veh | 3 | -3.12 | -3.71 | [-8.06, 1.81] | 3/0/0 | **INCONCLUSIVE** |
| oracle_v2x vs reactive | arrived | 3 | 0.32 | 0.36 | [-1.64, 2.28] | 2/1/0 | **INCONCLUSIVE** |
- s201 baseline: veh-h 192.585, mean tt 792 s, p95 1442 s, arrived 816, teleports 0, reroutes applied 0, sim `sim_v2x_s201_baseline_ideal_p30`
- s201 reactive: veh-h 189.9594, mean tt 782 s, p95 1419 s, arrived 812, teleports 0, reroutes applied 0, sim `sim_v2x_s201_reactive_ideal_p30`
- s201 predictive_corrected_v2x: veh-h 191.6561, mean tt 789 s, p95 1418 s, arrived 809, teleports 0, reroutes applied 37, sim `sim_v2x_s201_predictive_corrected_v2x_ideal_p30`
- s201 oracle_v2x: veh-h 190.8417, mean tt 785 s, p95 1394 s, arrived 808, teleports 0, reroutes applied 40, sim `sim_v2x_s201_oracle_v2x_ideal_p30`
- s202 baseline: veh-h 189.2342, mean tt 775 s, p95 1397 s, arrived 824, teleports 0, reroutes applied 0, sim `sim_v2x_s202_baseline_ideal_p30`
- s202 reactive: veh-h 188.7025, mean tt 773 s, p95 1392 s, arrived 824, teleports 0, reroutes applied 0, sim `sim_v2x_s202_reactive_ideal_p30`
- s202 predictive_corrected_v2x: veh-h 189.3044, mean tt 775 s, p95 1377 s, arrived 824, teleports 0, reroutes applied 29, sim `sim_v2x_s202_predictive_corrected_v2x_ideal_p30`
- s202 oracle_v2x: veh-h 188.4494, mean tt 772 s, p95 1389 s, arrived 827, teleports 0, reroutes applied 37, sim `sim_v2x_s202_oracle_v2x_ideal_p30`
- s203 baseline: veh-h 184.2633, mean tt 749 s, p95 1389 s, arrived 837, teleports 0, reroutes applied 0, sim `sim_v2x_s203_baseline_ideal_p30`
- s203 reactive: veh-h 184.5108, mean tt 750 s, p95 1391 s, arrived 829, teleports 0, reroutes applied 0, sim `sim_v2x_s203_reactive_ideal_p30`
- s203 predictive_corrected_v2x: veh-h 184.3528, mean tt 749 s, p95 1386 s, arrived 838, teleports 0, reroutes applied 12, sim `sim_v2x_s203_predictive_corrected_v2x_ideal_p30`
- s203 oracle_v2x: veh-h 183.3992, mean tt 745 s, p95 1391 s, arrived 838, teleports 0, reroutes applied 35, sim `sim_v2x_s203_oracle_v2x_ideal_p30`
