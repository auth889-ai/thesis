# V2X closed loop — V2X_CLOSED_LOOP_v1 · la_c4_central_wide · profile `its-g5` · penetration 0.3 · seeds [201]

Model Graph WaveNet (207-node METR-LA, verified) (ckpt `548e399bd53c`), 83 of 207 detectors mapped, routing config `ea08dddedc14`. SYNTHETIC_WHAT_IF randomTrips on the real OSM network, one draw per seed, scale 8.0x, profile peak [(0, 600, 0.5), (600, 1500, 0.8), (1500, 2400, 1.0), (2400, 3600, 1.0)]. REAL METR-LA detector speeds (mph), replayed as lane speed caps on mapped edges in every arm. SIMULATED V2X (src/pipeline/v2x/channel.py) — not radio hardware: latency 16.2 ms ± 0.0, loss 0.1, TTL 600.0 s.

Identical-state fork at 1200 s: state hashes {201: 'ac117185cee8'} — identical across arms: **True**. Reroutes applied by arm: {'baseline': 0, 'predictive_corrected_v2x': 283}.

| pair | metric | n | mean % | median % | 95 % CI | W/L/T | label |
|---|---|---|---|---|---|---|---|
| predictive_corrected_v2x vs baseline | total_vehicle_hours_incl_never_inserted | 1 | -0.39 | -0.39 | [None, None] | 1/0/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs baseline | mean_travel_time_all | 1 | -0.38 | -0.38 | [None, None] | 1/0/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs baseline | p95_travel_time_s | 1 | 4.05 | 4.05 | [None, None] | 0/1/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs baseline | total_waiting_s | 1 | 2.55 | 2.55 | [None, None] | 0/1/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs baseline | mean_queue_veh | 1 | -1.08 | -1.08 | [None, None] | 1/0/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs baseline | arrived | 1 | 0.43 | 0.43 | [None, None] | 1/0/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs baseline | teleports | 1 | -44.17 | -44.17 | [None, None] | 1/0/0 | **INCONCLUSIVE** |
- s201 baseline: veh-h 3750.8756, mean tt 1173 s, p95 2123 s, arrived 9037, teleports 163, reroutes applied 0, sim `sim_v2x_s201_baseline_its-g5_p30`
- s201 predictive_corrected_v2x: veh-h 3736.2419, mean tt 1168 s, p95 2209 s, arrived 9076, teleports 91, reroutes applied 283, sim `sim_v2x_s201_predictive_corrected_v2x_its-g5_p30`
