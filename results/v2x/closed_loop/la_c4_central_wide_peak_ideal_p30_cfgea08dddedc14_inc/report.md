# V2X closed loop — V2X_CLOSED_LOOP_v1 · la_c4_central_wide · profile `ideal` · penetration 0.3 · seeds [101, 102, 103]

Model Graph WaveNet (207-node METR-LA, verified) (ckpt `548e399bd53c`), 83 of 207 detectors mapped, routing config `ea08dddedc14`. SYNTHETIC_WHAT_IF randomTrips on the real OSM network, one draw per seed, departures 0-1800 s. REAL METR-LA detector speeds (mph), replayed as lane speed caps on mapped edges in every arm. SIMULATED V2X (pipeline/v2x/channel.py) — not radio hardware: latency 0.0 ms ± 0.0, loss 0.0, TTL 60.0 s.

| pair | metric | n | mean % | median % | 95 % CI | W/L/T | label |
|---|---|---|---|---|---|---|---|

Network (means over seeds): connected 259 vehicles · uplink TX 16367 RX 16367 PDR 1.0 lat med 0.0 p95 0.0 ms · downlink TX 17 RX 17 dropped 0 expired 0 PDR 1.0 lat med 0.0 p95 0.0 ms · reroutes applied 51 · inapplicable 0

- s101 predictive_v2x: veh-h 187.5464, mean tt 750 s, p95 1360 s, arrived 855, teleports 0, reroutes applied 16, sim `sim_v2x_s101_predictive_v2x_ideal_p30`
- s102 predictive_v2x: veh-h 186.8133, mean tt 747 s, p95 1420 s, arrived 843, teleports 0, reroutes applied 21, sim `sim_v2x_s102_predictive_v2x_ideal_p30`
- s103 predictive_v2x: veh-h 182.9958, mean tt 732 s, p95 1390 s, arrived 863, teleports 0, reroutes applied 14, sim `sim_v2x_s103_predictive_v2x_ideal_p30`
