# V2X closed loop — V2X_CLOSED_LOOP_v1 · la_c4_central_wide · profile `ideal` · penetration 0.3 · seeds [101]

Model Graph WaveNet (207-node METR-LA, verified) (ckpt `548e399bd53c`), 83 of 207 detectors mapped, routing config `ea08dddedc14`. SYNTHETIC_WHAT_IF randomTrips on the real OSM network, one draw per seed, departures 0-1800 s. REAL METR-LA detector speeds (mph), replayed as lane speed caps on mapped edges in every arm. SIMULATED V2X (pipeline/v2x/channel.py) — not radio hardware: latency 0.0 ms ± 0.0, loss 0.0, TTL 60.0 s.

Identical-state fork at 480 s: state hashes {101: 'bd20b216eaeb'} — identical across arms: **True**. Reroutes applied by arm: {'predictive_corrected_v2x': 35}.

| pair | metric | n | mean % | median % | 95 % CI | W/L/T | label |
|---|---|---|---|---|---|---|---|
- s101 predictive_corrected_v2x: veh-h 186.7294, mean tt 765 s, p95 1422 s, arrived 832, teleports 0, reroutes applied 35, sim `sim_v2x_s101_predictive_corrected_v2x_ideal_p30`
