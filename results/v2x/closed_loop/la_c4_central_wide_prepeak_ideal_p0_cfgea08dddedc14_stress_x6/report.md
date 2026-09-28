# V2X closed loop — V2X_CLOSED_LOOP_v1 · la_c4_central_wide · profile `ideal` · penetration 0.0 · seeds [101, 102, 103]

Model Graph WaveNet (207-node METR-LA, verified) (ckpt `548e399bd53c`), 83 of 207 detectors mapped, routing config `ea08dddedc14`. SYNTHETIC_WHAT_IF randomTrips on the real OSM network, one draw per seed, scale 6.0x, profile uniform [(0, 1800, 1.0)]. REAL METR-LA detector speeds (mph), replayed as lane speed caps on mapped edges in every arm. SIMULATED V2X (pipeline/v2x/channel.py) — not radio hardware: latency 0.0 ms ± 0.0, loss 0.0, TTL 60.0 s.

| pair | metric | n | mean % | median % | 95 % CI | W/L/T | label |
|---|---|---|---|---|---|---|---|
- s101 baseline: veh-h 1324.8381, mean tt 883 s, p95 1917 s, arrived 5244, teleports 6, reroutes applied 0, sim `sim_v2x_s101_baseline_ideal_p0`
- s102 baseline: veh-h 1292.1497, mean tt 861 s, p95 1821 s, arrived 5304, teleports 4, reroutes applied 0, sim `sim_v2x_s102_baseline_ideal_p0`
- s103 baseline: veh-h 1332.3217, mean tt 888 s, p95 1937 s, arrived 5250, teleports 5, reroutes applied 0, sim `sim_v2x_s103_baseline_ideal_p0`
