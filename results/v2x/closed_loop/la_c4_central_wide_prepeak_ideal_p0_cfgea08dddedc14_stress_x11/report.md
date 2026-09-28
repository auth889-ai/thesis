# V2X closed loop — V2X_CLOSED_LOOP_v1 · la_c4_central_wide · profile `ideal` · penetration 0.0 · seeds [101, 102, 103]

Model Graph WaveNet (207-node METR-LA, verified) (ckpt `548e399bd53c`), 83 of 207 detectors mapped, routing config `ea08dddedc14`. SYNTHETIC_WHAT_IF randomTrips on the real OSM network, one draw per seed, scale 11.0x, profile uniform [(0, 1800, 1.0)]. REAL METR-LA detector speeds (mph), replayed as lane speed caps on mapped edges in every arm. SIMULATED V2X (pipeline/v2x/channel.py) — not radio hardware: latency 0.0 ms ± 0.0, loss 0.0, TTL 60.0 s.

| pair | metric | n | mean % | median % | 95 % CI | W/L/T | label |
|---|---|---|---|---|---|---|---|
- s101 baseline: veh-h 3163.7719, mean tt 1150 s, p95 2193 s, arrived 8150, teleports 108, reroutes applied 0, sim `sim_v2x_s101_baseline_ideal_p0`
- s102 baseline: veh-h 3147.1397, mean tt 1145 s, p95 2209 s, arrived 8217, teleports 191, reroutes applied 0, sim `sim_v2x_s102_baseline_ideal_p0`
- s103 baseline: veh-h 3079.5525, mean tt 1120 s, p95 2087 s, arrived 8333, teleports 103, reroutes applied 0, sim `sim_v2x_s103_baseline_ideal_p0`
