# V2X closed loop — V2X_CLOSED_LOOP_v1 · la_c4_central_wide · profile `ideal` · penetration 0.3 · seeds [101]

Model Graph WaveNet (207-node METR-LA, verified) (ckpt `548e399bd53c`), 83 of 207 detectors mapped, routing config `ea08dddedc14`. SYNTHETIC_WHAT_IF randomTrips on the real OSM network, one draw per seed, departures 0-1800 s. REAL METR-LA detector speeds (mph), replayed as lane speed caps on mapped edges in every arm. SIMULATED V2X (pipeline/v2x/channel.py) — not radio hardware: latency 0.0 ms ± 0.0, loss 0.0, TTL 60.0 s.

Identical-state fork at 480 s: state hashes {101: 'bd20b216eaeb'} — identical across arms: **True**. Reroutes applied by arm: {'baseline': 0, 'oracle_net_v2x': 33}.

| pair | metric | n | mean % | median % | 95 % CI | W/L/T | label |
|---|---|---|---|---|---|---|---|
| oracle_net_v2x vs baseline | total_vehicle_hours_incl_never_inserted | 1 | -0.61 | -0.61 | [None, None] | 1/0/0 | **INCONCLUSIVE** |
| oracle_net_v2x vs baseline | mean_travel_time_all | 1 | -0.61 | -0.61 | [None, None] | 1/0/0 | **INCONCLUSIVE** |
| oracle_net_v2x vs baseline | p95_travel_time_s | 1 | -1.78 | -1.78 | [None, None] | 1/0/0 | **INCONCLUSIVE** |
| oracle_net_v2x vs baseline | total_waiting_s | 1 | -2.21 | -2.21 | [None, None] | 1/0/0 | **INCONCLUSIVE** |
| oracle_net_v2x vs baseline | mean_queue_veh | 1 | -2.81 | -2.81 | [None, None] | 1/0/0 | **INCONCLUSIVE** |
| oracle_net_v2x vs baseline | arrived | 1 | 0.0 | 0.0 | [None, None] | 0/0/1 | **INCONCLUSIVE** |
- s101 baseline: veh-h 187.7333, mean tt 769 s, p95 1406 s, arrived 832, teleports 0, reroutes applied 0, sim `sim_v2x_s101_baseline_ideal_p30`
- s101 oracle_net_v2x: veh-h 186.5864, mean tt 764 s, p95 1381 s, arrived 832, teleports 0, reroutes applied 33, sim `sim_v2x_s101_oracle_net_v2x_ideal_p30`
