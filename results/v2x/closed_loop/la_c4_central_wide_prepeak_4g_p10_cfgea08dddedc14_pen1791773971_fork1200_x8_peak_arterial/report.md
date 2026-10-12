# V2X closed loop — V2X_CLOSED_LOOP_v1 · la_c4_central_wide · profile `4g` · penetration 0.1 · seeds [201]

Model Graph WaveNet (207-node METR-LA, verified) (ckpt `548e399bd53c`), 83 of 207 detectors mapped, routing config `ea08dddedc14`. SYNTHETIC_WHAT_IF randomTrips on the real OSM network, one draw per seed, scale 8.0x, profile peak [(0, 600, 0.5), (600, 1500, 0.8), (1500, 2400, 1.0), (2400, 3600, 1.0)]. REAL METR-LA detector speeds (mph), replayed as lane speed caps on mapped edges in every arm. SIMULATED V2X (src/pipeline/v2x/channel.py) — not radio hardware: latency 75.0 ms ± 0.0, loss 0.04, TTL 600.0 s.

Identical-state fork at 1200 s: state hashes {201: 'ac117185cee8'} — identical across arms: **True**. Reroutes applied by arm: {'baseline': 0}.

| pair | metric | n | mean % | median % | 95 % CI | W/L/T | label |
|---|---|---|---|---|---|---|---|
- s201 baseline: veh-h 3750.8756, mean tt 1173 s, p95 2123 s, arrived 9037, teleports 163, reroutes applied 0, sim `sim_v2x_s201_baseline_4g_p10`
