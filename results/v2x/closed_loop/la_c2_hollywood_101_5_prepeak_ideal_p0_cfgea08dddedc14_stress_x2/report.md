# V2X closed loop — V2X_CLOSED_LOOP_v1 · la_c2_hollywood_101_5 · profile `ideal` · penetration 0.0 · seeds [101, 102, 103]

Model Graph WaveNet (207-node METR-LA, verified) (ckpt `548e399bd53c`), 52 of 207 detectors mapped, routing config `ea08dddedc14`. SYNTHETIC_WHAT_IF randomTrips on the real OSM network, one draw per seed, scale 2.0x, profile uniform [(0, 1800, 1.0)]. REAL METR-LA detector speeds (mph), replayed as lane speed caps on mapped edges in every arm. SIMULATED V2X (pipeline/v2x/channel.py) — not radio hardware: latency 0.0 ms ± 0.0, loss 0.0, TTL 60.0 s.

| pair | metric | n | mean % | median % | 95 % CI | W/L/T | label |
|---|---|---|---|---|---|---|---|
- s101 baseline: veh-h 293.5961, mean tt 587 s, p95 1116 s, arrived 1800, teleports 3, reroutes applied 0, sim `sim_v2x_s101_baseline_ideal_p0`
- s102 baseline: veh-h 288.1858, mean tt 576 s, p95 1091 s, arrived 1800, teleports 0, reroutes applied 0, sim `sim_v2x_s102_baseline_ideal_p0`
- s103 baseline: veh-h 285.1447, mean tt 570 s, p95 1053 s, arrived 1800, teleports 0, reroutes applied 0, sim `sim_v2x_s103_baseline_ideal_p0`
