# Oracle outcome gate — FINAL_PROTOCOL_v1 (dev seeds [101, 102, 103])

**Verdict on the primary metric (total vehicle-hours of every vehicle loaded before the horizon: inserted vehicles to arrival or the horizon, never-inserted vehicles from their departure to the horizon; ORACLE vs BASELINE): INCONCLUSIVE** — mean -5.16 %, median -5.19 %, 95 % CI [-12.3, 1.98], wins/losses/ties 3/0/0.

## Frozen protocol

- network: `paper_labs/02_dhaka_osm/outputs/lab02_v2/network/dhaka_r1.net.xml`
- network_hash: `06194df03974`
- demand_source: `artifacts/gates/routes_repeat_1h.rou.xml.gz`
- demand_source_hash: `e42e8450863c`
- demand_sample_fraction: `0.25`
- simulation_duration_s: `3600`
- routing_round_s: `900`
- compliance: `0.3`
- coverage_mode: `oracle: MEASURED per-edge travel time (sampledSeconds-weighted over the round), unmeasured edges free flow; no DERIVED propagation`
- routing_config_hash: `ea08dddedc14`
- min_saving_s: `60.0`
- min_saving_pct: `5.0`
- sumo_version: `Eclipse SUMO sumo 1.27.1`
- dev_seeds: `[101, 102, 103]`
- final_seeds: `[201, 202, 203, 204, 205, 206, 207, 208, 209, 210]`
- admission: `{"_rule": "thin TrafficTwin layer above SUMO routing: a vehicle is admitted to an alternative only if no edge of it would exceed max_edge_load_ratio after admission, and no more than max_share_per_alternative of the vehicles in the round are sent to the same alternative; a vehicle rerouted within reroute_cooldown_s is not advised again", "max_edge_load_ratio": 1.0, "max_share_per_alternative": 0.4, "reroute_cooldown_s": 300, "share_gate_min_vehicles": 5, "_share_gate_min": "the share gate only applies to rounds of at least share_gate_min_vehicles vehicles: a single analysed trip is not a herd"}`
- identical inserted population in all arms, every seed: **True**

## Per seed

| seed | arm | veh-h (all loaded) | veh-h (inserted) | never inserted | mean TT (all) | p95 TT | waiting s | mean/max queue | arrived | reroutes | teleports | top-route share | top-edge conc. | probe TT |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 101 | baseline | 503.0 | 498.4 | 67 | 403 | 850 | 266558 | 108.5/255 | 3849 | 0 | 12 | 0.0351 | 0.2211 | 285.0 |
| 101 | reactive | 487.1 | 487.1 | 4 | 388 | 831 | 255847 | 109.7/280 | 3851 | 8399 | 44 | 0.0377 | 0.2197 | 299.0 |
| 101 | oracle | 462.7 | 462.7 | 0 | 369 | 726 | 230213 | 76.2/204 | 3972 | 448 | 15 | 0.0342 | 0.2223 | 311.0 |
| 102 | baseline | 500.3 | 500.3 | 0 | 405 | 908 | 268741 | 103.2/253 | 3783 | 0 | 11 | 0.033 | 0.2183 | 362.0 |
| 102 | reactive | 511.9 | 502.9 | 68 | 413 | 893 | 290560 | 132.3/307 | 3690 | 9115 | 41 | 0.0382 | 0.2222 | 302.0 |
| 102 | oracle | 474.3 | 474.3 | 0 | 384 | 781 | 249886 | 92.2/204 | 3856 | 481 | 16 | 0.0324 | 0.2308 | 342.0 |
| 103 | baseline | 509.9 | 509.9 | 0 | 404 | 862 | 263973 | 102.3/284 | 3844 | 0 | 5 | 0.0341 | 0.225 | 307.0 |
| 103 | reactive | 505.8 | 505.4 | 13 | 401 | 861 | 286985 | 118.8/328 | 3806 | 8588 | 43 | 0.0413 | 0.2254 | 323.0 |
| 103 | oracle | 498.4 | 498.4 | 0 | 395 | 804 | 266726 | 107.1/264 | 3868 | 488 | 18 | 0.0346 | 0.2203 | 308.0 |

## Paired statistics (percentage change per seed, first arm relative to second)

| pair | metric | n | mean % | median % | 95 % CI | wins/losses/ties | label |
|---|---|---|---|---|---|---|---|
| oracle vs baseline | total_vehicle_hours_incl_never_inserted | 3 | -5.16 | -5.19 | [-12.3, 1.98] | 3/0/0 | **INCONCLUSIVE** |
| oracle vs baseline | total_vehicle_hours | 3 | -4.88 | -5.19 | [-11.0, 1.25] | 3/0/0 | **INCONCLUSIVE** |
| oracle vs baseline | mean_travel_time_all | 3 | -5.33 | -5.19 | [-13.14, 2.47] | 3/0/0 | **INCONCLUSIVE** |
| oracle vs baseline | mean_travel_time_s | 3 | -4.47 | -4.8 | [-7.31, -1.63] | 3/0/0 | **HELPED** |
| oracle vs baseline | p95_travel_time_s | 3 | -11.77 | -13.99 | [-22.64, -0.9] | 3/0/0 | **HELPED** |
| oracle vs baseline | total_waiting_s | 3 | -6.54 | -7.02 | [-24.8, 11.73] | 2/1/0 | **INCONCLUSIVE** |
| oracle vs baseline | mean_queue_veh | 3 | -11.91 | -10.71 | [-54.77, 30.96] | 2/1/0 | **INCONCLUSIVE** |
| oracle vs baseline | max_queue_veh | 3 | -15.47 | -19.37 | [-33.62, 2.68] | 3/0/0 | **INCONCLUSIVE** |
| oracle vs baseline | arrived | 3 | 1.92 | 1.93 | [-1.28, 5.11] | 3/0/0 | **INCONCLUSIVE** |
| oracle vs baseline | teleports | 3 | 110.15 | 45.45 | [-213.25, 433.55] | 0/3/0 | **INCONCLUSIVE** |
| oracle vs reactive | total_vehicle_hours_incl_never_inserted | 3 | -4.62 | -5.02 | [-11.96, 2.73] | 3/0/0 | **INCONCLUSIVE** |
| oracle vs reactive | total_vehicle_hours | 3 | -4.04 | -5.01 | [-9.78, 1.71] | 3/0/0 | **INCONCLUSIVE** |
| oracle vs reactive | mean_travel_time_all | 3 | -4.64 | -5.1 | [-11.49, 2.22] | 3/0/0 | **INCONCLUSIVE** |
| oracle vs reactive | mean_travel_time_s | 3 | -2.58 | -2.41 | [-4.95, -0.2] | 3/0/0 | **HELPED** |
| oracle vs reactive | p95_travel_time_s | 3 | -10.6 | -12.54 | [-19.16, -2.04] | 3/0/0 | **HELPED** |
| oracle vs reactive | total_waiting_s | 3 | -10.36 | -10.02 | [-19.01, -1.71] | 3/0/0 | **HELPED** |
| oracle vs reactive | mean_queue_veh | 3 | -23.58 | -30.35 | [-53.1, 5.94] | 3/0/0 | **INCONCLUSIVE** |
| oracle vs reactive | max_queue_veh | 3 | -26.73 | -27.14 | [-44.19, -9.28] | 3/0/0 | **HELPED** |
| oracle vs reactive | arrived | 3 | 3.09 | 3.14 | [-0.48, 6.66] | 3/0/0 | **INCONCLUSIVE** |
| oracle vs reactive | teleports | 3 | -61.68 | -60.98 | [-71.44, -51.91] | 3/0/0 | **HELPED** |
| reactive vs baseline | total_vehicle_hours_incl_never_inserted | 3 | -0.54 | -0.8 | [-7.37, 6.29] | 2/1/0 | **INCONCLUSIVE** |
| reactive vs baseline | total_vehicle_hours | 3 | -0.87 | -0.88 | [-4.35, 2.61] | 2/1/0 | **INCONCLUSIVE** |
| reactive vs baseline | mean_travel_time_all | 3 | -0.71 | -0.6 | [-7.83, 6.41] | 2/1/0 | **INCONCLUSIVE** |
| reactive vs baseline | mean_travel_time_s | 3 | -1.93 | -1.23 | [-5.89, 2.03] | 3/0/0 | **INCONCLUSIVE** |
| reactive vs baseline | p95_travel_time_s | 3 | -1.33 | -1.65 | [-4.05, 1.39] | 3/0/0 | **INCONCLUSIVE** |
| reactive vs baseline | total_waiting_s | 3 | 4.27 | 8.12 | [-13.58, 22.13] | 1/2/0 | **INCONCLUSIVE** |
| reactive vs baseline | mean_queue_veh | 3 | 15.18 | 16.18 | [-18.49, 48.84] | 0/3/0 | **INCONCLUSIVE** |
| reactive vs baseline | max_queue_veh | 3 | 15.55 | 15.49 | [1.21, 29.88] | 0/3/0 | **HURT** |
| reactive vs baseline | arrived | 3 | -1.13 | -0.99 | [-4.26, 2.0] | 1/2/0 | **INCONCLUSIVE** |
| reactive vs baseline | teleports | 3 | 433.13 | 272.73 | [-270.17, 1136.43] | 0/3/0 | **INCONCLUSIVE** |

Probe trip travel time per arm (seconds, per seed; one user trip, not the system conclusion): {"baseline": [285.0, 362.0, 307.0], "reactive": [299.0, 302.0, 323.0], "oracle": [311.0, 342.0, 308.0]}

