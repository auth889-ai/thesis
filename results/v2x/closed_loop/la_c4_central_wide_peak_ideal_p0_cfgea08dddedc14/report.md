# V2X closed loop — V2X_CLOSED_LOOP_v1 · la_c4_central_wide · profile `ideal` · penetration 0.0 · seeds [101, 102, 103]

Model Graph WaveNet (207-node METR-LA, verified) (ckpt `548e399bd53c`), 83 of 207 detectors mapped, routing config `ea08dddedc14`. SYNTHETIC_WHAT_IF randomTrips on the real OSM network, one draw per seed, departures 0-1800 s. REAL METR-LA detector speeds (mph), replayed as lane speed caps on mapped edges in every arm. SIMULATED V2X (pipeline/v2x/channel.py) — not radio hardware: latency 0.0 ms ± 0.0, loss 0.0, TTL 60.0 s.

| pair | metric | n | mean % | median % | 95 % CI | W/L/T | label |
|---|---|---|---|---|---|---|---|
| predictive_v2x vs baseline | total_vehicle_hours_incl_never_inserted | 3 | 0.0 | 0.0 | [0.0, 0.0] | 0/0/3 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | mean_travel_time_all | 3 | 0.0 | 0.0 | [0.0, 0.0] | 0/0/3 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | p95_travel_time_s | 3 | 0.0 | 0.0 | [0.0, 0.0] | 0/0/3 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | total_waiting_s | 3 | 0.0 | 0.0 | [0.0, 0.0] | 0/0/3 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | mean_queue_veh | 3 | 0.0 | 0.0 | [0.0, 0.0] | 0/0/3 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | arrived | 3 | 0.0 | 0.0 | [0.0, 0.0] | 0/0/3 | **INCONCLUSIVE** |

Network (means over seeds): connected 0 vehicles · uplink TX 0 RX 0 PDR None lat med None p95 None ms · downlink TX 0 RX 0 dropped 0 expired 0 PDR None lat med None p95 None ms · reroutes applied 0 · inapplicable 0

- s101 baseline: veh-h 184.5233, mean tt 738 s, p95 1359 s, arrived 858, teleports 0, reroutes applied 0, sim `sim_v2x_s101_baseline_ideal_p30`
- s101 predictive_v2x: veh-h 184.5233, mean tt 738 s, p95 1359 s, arrived 858, teleports 0, reroutes applied 0, sim `sim_v2x_s101_predictive_v2x_ideal_p0`
- s102 baseline: veh-h 182.6078, mean tt 730 s, p95 1359 s, arrived 847, teleports 0, reroutes applied 0, sim `sim_v2x_s102_baseline_ideal_p30`
- s102 predictive_v2x: veh-h 182.6078, mean tt 730 s, p95 1359 s, arrived 847, teleports 0, reroutes applied 0, sim `sim_v2x_s102_predictive_v2x_ideal_p0`
- s103 baseline: veh-h 178.7522, mean tt 715 s, p95 1331 s, arrived 863, teleports 0, reroutes applied 0, sim `sim_v2x_s103_baseline_ideal_p30`
- s103 predictive_v2x: veh-h 178.7522, mean tt 715 s, p95 1331 s, arrived 863, teleports 0, reroutes applied 0, sim `sim_v2x_s103_predictive_v2x_ideal_p0`
