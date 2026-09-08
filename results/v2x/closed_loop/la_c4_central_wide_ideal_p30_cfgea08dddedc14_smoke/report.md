# V2X closed loop — V2X_CLOSED_LOOP_v1 · la_c4_central_wide · profile `ideal` · penetration 0.3 · seeds [101]

Model Graph WaveNet (207-node METR-LA, verified) (ckpt `548e399bd53c`), 83 of 207 detectors mapped, routing config `ea08dddedc14`. SYNTHETIC_WHAT_IF randomTrips on the real OSM network, one draw per seed, departures 0-1800 s. REAL METR-LA detector speeds (mph), replayed as lane speed caps on mapped edges in every arm. SIMULATED V2X (pipeline/v2x/channel.py) — not radio hardware: latency 0.0 ms ± 0.0, loss 0.0, TTL 60.0 s.

| pair | metric | n | mean % | median % | 95 % CI | W/L/T | label |
|---|---|---|---|---|---|---|---|
| predictive_v2x vs baseline | total_vehicle_hours_incl_never_inserted | 1 | 0.0 | 0.0 | [None, None] | 0/0/1 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | mean_travel_time_all | 1 | 0.0 | 0.0 | [None, None] | 0/0/1 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | p95_travel_time_s | 1 | 0.0 | 0.0 | [None, None] | 0/0/1 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | total_waiting_s | 1 | 0.0 | 0.0 | [None, None] | 0/0/1 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | mean_queue_veh | 1 | 0.0 | 0.0 | [None, None] | 0/0/1 | **INCONCLUSIVE** |
| predictive_v2x vs baseline | arrived | 1 | 0.0 | 0.0 | [None, None] | 0/0/1 | **INCONCLUSIVE** |

Network (means over seeds): connected 253 vehicles · uplink TX 14912 RX 14912 PDR 1.0 lat med 0.0 p95 0.0 ms · downlink TX 0 RX 0 dropped 0 expired 0 PDR None lat med None p95 None ms · reroutes applied 0 · inapplicable 0

- s101 baseline: veh-h 177.3822, mean tt 710 s, p95 1347 s, arrived 867, teleports 0, reroutes applied 0, sim `sim_v2x_s101_baseline_ideal_p30`
- s101 predictive_v2x: veh-h 177.3822, mean tt 710 s, p95 1347 s, arrived 867, teleports 0, reroutes applied 0, sim `sim_v2x_s101_predictive_v2x_ideal_p30`
