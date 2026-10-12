# V2X closed loop — V2X_CLOSED_LOOP_v1 · la_c4_central_wide · profile `ideal` · penetration 0.3 · seeds [201]

Model Graph WaveNet (207-node METR-LA, verified) (ckpt `548e399bd53c`), 83 of 207 detectors mapped, routing config `ea08dddedc14`. SYNTHETIC_WHAT_IF randomTrips on the real OSM network, one draw per seed, scale 8.0x, profile peak [(0, 600, 0.5), (600, 1500, 0.8), (1500, 2400, 1.0), (2400, 3600, 1.0)]. REAL METR-LA detector speeds (mph), replayed as lane speed caps on mapped edges in every arm. SIMULATED V2X (src/pipeline/v2x/channel.py) — not radio hardware: latency 0.0 ms ± 0.0, loss 0.0, TTL 60.0 s.

Identical-state fork at 1200 s: state hashes {201: 'ac117185cee8'} — identical across arms: **True**. Reroutes applied by arm: {'baseline': 0, 'predictive_corrected_v2x': 367}.

| pair | metric | n | mean % | median % | 95 % CI | W/L/T | label |
|---|---|---|---|---|---|---|---|
| predictive_corrected_v2x vs baseline | total_vehicle_hours_incl_never_inserted | 1 | 0.53 | 0.53 | [None, None] | 0/1/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs baseline | mean_travel_time_all | 1 | 0.55 | 0.55 | [None, None] | 0/1/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs baseline | p95_travel_time_s | 1 | 2.54 | 2.54 | [None, None] | 0/1/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs baseline | total_waiting_s | 1 | 4.36 | 4.36 | [None, None] | 0/1/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs baseline | mean_queue_veh | 1 | -0.02 | -0.02 | [None, None] | 1/0/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs baseline | arrived | 1 | 0.1 | 0.1 | [None, None] | 1/0/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs baseline | teleports | 1 | -15.34 | -15.34 | [None, None] | 1/0/0 | **INCONCLUSIVE** |
- s201 baseline: veh-h 3750.8756, mean tt 1173 s, p95 2123 s, arrived 9037, teleports 163, reroutes applied 0, sim `sim_v2x_s201_baseline_ideal_p30`
- s201 predictive_corrected_v2x: veh-h 3770.6531, mean tt 1179 s, p95 2177 s, arrived 9046, teleports 138, reroutes applied 367, sim `sim_v2x_s201_predictive_corrected_v2x_ideal_p30`
