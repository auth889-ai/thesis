# V2X closed loop — V2X_CLOSED_LOOP_v1 · la_c4_central_wide · profile `its-g5` · penetration 0.3 · seeds [202]

Model Graph WaveNet (207-node METR-LA, verified) (ckpt `548e399bd53c`), 83 of 207 detectors mapped, routing config `ea08dddedc14`. SYNTHETIC_WHAT_IF randomTrips on the real OSM network, one draw per seed, scale 8.0x, profile peak [(0, 600, 0.5), (600, 1500, 0.8), (1500, 2400, 1.0), (2400, 3600, 1.0)]. REAL METR-LA detector speeds (mph), replayed as lane speed caps on mapped edges in every arm. SIMULATED V2X (src/pipeline/v2x/channel.py) — not radio hardware: latency 16.2 ms ± 0.0, loss 0.1, TTL 600.0 s.

Identical-state fork at 1200 s: state hashes {202: '4513309cd8e2'} — identical across arms: **True**. Reroutes applied by arm: {'baseline': 0, 'predictive_corrected_v2x': 373}.

| pair | metric | n | mean % | median % | 95 % CI | W/L/T | label |
|---|---|---|---|---|---|---|---|
| predictive_corrected_v2x vs baseline | total_vehicle_hours_incl_never_inserted | 1 | 1.15 | 1.15 | [None, None] | 0/1/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs baseline | mean_travel_time_all | 1 | 1.15 | 1.15 | [None, None] | 0/1/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs baseline | p95_travel_time_s | 1 | 0.87 | 0.87 | [None, None] | 0/1/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs baseline | total_waiting_s | 1 | 0.52 | 0.52 | [None, None] | 0/1/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs baseline | mean_queue_veh | 1 | 2.15 | 2.15 | [None, None] | 0/1/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs baseline | arrived | 1 | -0.91 | -0.91 | [None, None] | 0/1/0 | **INCONCLUSIVE** |
| predictive_corrected_v2x vs baseline | teleports | 1 | -13.22 | -13.22 | [None, None] | 1/0/0 | **INCONCLUSIVE** |
- s202 baseline: veh-h 3715.0886, mean tt 1156 s, p95 2186 s, arrived 9281, teleports 121, reroutes applied 0, sim `sim_v2x_s202_baseline_its-g5_p30`
- s202 predictive_corrected_v2x: veh-h 3757.6306, mean tt 1169 s, p95 2205 s, arrived 9197, teleports 105, reroutes applied 373, sim `sim_v2x_s202_predictive_corrected_v2x_its-g5_p30`
