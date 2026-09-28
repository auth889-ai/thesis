# Oracle outcome gate — FINAL_PROTOCOL_v1 (final seeds [201, 202, 203, 204, 205, 206, 207, 208, 209, 210])

**Verdict on the primary metric (total vehicle-hours of every vehicle loaded before the horizon: inserted vehicles to arrival or the horizon, never-inserted vehicles from their departure to the horizon; ORACLE vs BASELINE): HELPED** — mean -4.02 %, median -4.4 %, 95 % CI [-5.95, -2.09], wins/losses/ties 9/1/0.

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
| 201 | baseline | 577.9 | 577.9 | 0 | 441 | 957 | 318172 | 154.0/411 | 3893 | 0 | 7 | 0.036 | 0.2212 | 342.0 |
| 201 | reactive | 594.1 | 592.4 | 35 | 456 | 977 | 335095 | 188.2/509 | 3754 | 10614 | 85 | 0.0405 | 0.2246 | 331.0 |
| 201 | oracle | 562.4 | 562.4 | 4 | 430 | 852 | 321815 | 153.7/392 | 3919 | 509 | 32 | 0.0357 | 0.2156 | 356.0 |
| 202 | baseline | 511.6 | 511.6 | 0 | 415 | 900 | 273496 | 117.7/288 | 3745 | 0 | 10 | 0.0368 | 0.2272 | 303.0 |
| 202 | reactive | 472.1 | 472.1 | 0 | 383 | 800 | 249643 | 93.7/252 | 3823 | 8029 | 10 | 0.0371 | 0.2294 | 309.0 |
| 202 | oracle | 478.9 | 478.8 | 9 | 390 | 777 | 263351 | 101.1/251 | 3823 | 454 | 28 | 0.0356 | 0.2242 | 324.0 |
| 203 | baseline | 487.0 | 487.0 | 0 | 392 | 775 | 237555 | 89.3/225 | 3869 | 0 | 13 | 0.0326 | 0.2189 | 269.0 |
| 203 | reactive | 507.4 | 507.4 | 0 | 408 | 924 | 319766 | 123.5/281 | 3835 | 9232 | 34 | 0.0399 | 0.2243 | 304.0 |
| 203 | oracle | 453.6 | 453.6 | 0 | 365 | 687 | 182528 | 73.2/206 | 3901 | 456 | 13 | 0.0328 | 0.2189 | 335.0 |
| 204 | baseline | 520.5 | 520.5 | 0 | 413 | 961 | 303035 | 111.8/241 | 3890 | 0 | 9 | 0.0378 | 0.2208 | 292.0 |
| 204 | reactive | 498.8 | 497.1 | 31 | 397 | 796 | 270984 | 115.6/286 | 3879 | 8585 | 38 | 0.0418 | 0.2333 | 331.0 |
| 204 | oracle | 492.7 | 492.7 | 0 | 391 | 759 | 268832 | 99.8/267 | 3942 | 499 | 17 | 0.0368 | 0.2255 | 338.0 |
| 205 | baseline | 501.0 | 501.0 | 0 | 406 | 800 | 258735 | 110.0/247 | 3813 | 0 | 38 | 0.0349 | 0.2192 | 308.0 |
| 205 | reactive | 537.3 | 531.3 | 78 | 438 | 880 | 293532 | 168.8/433 | 3613 | 9774 | 80 | 0.0404 | 0.2156 | 300.0 |
| 205 | oracle | 463.1 | 463.1 | 1 | 375 | 732 | 235672 | 78.3/173 | 3910 | 464 | 6 | 0.0325 | 0.2156 | 351.0 |
| 206 | baseline | 530.6 | 530.6 | 0 | 424 | 938 | 313549 | 123.1/257 | 3869 | 0 | 12 | 0.0339 | 0.2212 | 313.0 |
| 206 | reactive | 525.2 | 525.1 | 4 | 420 | 923 | 308504 | 136.2/401 | 3797 | 9056 | 31 | 0.0398 | 0.217 | 342.0 |
| 206 | oracle | 507.7 | 507.7 | 0 | 406 | 715 | 243101 | 115.7/257 | 3871 | 483 | 6 | 0.0331 | 0.2178 | 331.0 |
| 207 | baseline | 512.3 | 512.3 | 0 | 404 | 850 | 282462 | 101.3/251 | 3911 | 0 | 4 | 0.034 | 0.2219 | 289.0 |
| 207 | reactive | 529.2 | 529.2 | 0 | 417 | 970 | 338149 | 138.2/358 | 3830 | 9483 | 37 | 0.035 | 0.2225 | 327.0 |
| 207 | oracle | 499.7 | 499.7 | 0 | 394 | 717 | 247948 | 109.1/291 | 3863 | 490 | 21 | 0.0316 | 0.2252 | 294.0 |
| 208 | baseline | 498.8 | 498.8 | 0 | 402 | 793 | 249277 | 94.9/250 | 3851 | 0 | 4 | 0.033 | 0.2207 | 335.0 |
| 208 | reactive | 567.2 | 558.3 | 75 | 457 | 1085 | 387636 | 187.0/502 | 3566 | 10889 | 77 | 0.0407 | 0.2151 | 371.0 |
| 208 | oracle | 502.7 | 501.5 | 25 | 406 | 923 | 324963 | 118.5/235 | 3787 | 501 | 28 | 0.0314 | 0.2189 | 368.0 |
| 209 | baseline | 481.6 | 481.6 | 1 | 384 | 863 | 239585 | 83.5/200 | 3967 | 0 | 19 | 0.033 | 0.2198 | 326.0 |
| 209 | reactive | 486.8 | 482.8 | 49 | 389 | 870 | 255948 | 105.0/250 | 3871 | 8262 | 32 | 0.0385 | 0.2193 | 383.0 |
| 209 | oracle | 460.0 | 460.0 | 1 | 366 | 682 | 196637 | 69.7/146 | 3998 | 455 | 4 | 0.0333 | 0.2169 | 378.0 |
| 210 | baseline | 473.2 | 473.2 | 0 | 382 | 753 | 234815 | 78.4/196 | 3908 | 0 | 6 | 0.0312 | 0.2203 | 346.0 |
| 210 | reactive | 513.3 | 512.3 | 23 | 416 | 997 | 363228 | 131.7/286 | 3812 | 8988 | 33 | 0.0386 | 0.2151 | 354.0 |
| 210 | oracle | 469.0 | 468.9 | 7 | 380 | 769 | 237438 | 90.0/208 | 3874 | 454 | 26 | 0.0312 | 0.2184 | 359.0 |

## Paired statistics (percentage change per seed, first arm relative to second)

| pair | metric | n | mean % | median % | 95 % CI | wins/losses/ties | label |
|---|---|---|---|---|---|---|---|
| oracle vs baseline | total_vehicle_hours_incl_never_inserted | 10 | -4.02 | -4.4 | [-5.95, -2.09] | 9/1/0 | **HELPED** |
| oracle vs baseline | total_vehicle_hours | 10 | -4.05 | -4.4 | [-5.94, -2.16] | 9/1/0 | **HELPED** |
| oracle vs baseline | mean_travel_time_all | 10 | -3.95 | -4.4 | [-5.93, -1.97] | 9/1/0 | **HELPED** |
| oracle vs baseline | mean_travel_time_s | 10 | -3.97 | -4.63 | [-6.22, -1.72] | 9/1/0 | **HELPED** |
| oracle vs baseline | p95_travel_time_s | 10 | -10.74 | -12.51 | [-19.4, -2.08] | 8/2/0 | **HELPED** |
| oracle vs baseline | total_waiting_s | 10 | -6.71 | -10.1 | [-17.91, 4.5] | 7/3/0 | **INCONCLUSIVE** |
| oracle vs baseline | mean_queue_veh | 10 | -4.73 | -8.43 | [-16.54, 7.09] | 7/3/0 | **INCONCLUSIVE** |
| oracle vs baseline | max_queue_veh | 10 | -5.6 | -5.31 | [-16.3, 5.1] | 6/3/1 | **INCONCLUSIVE** |
| oracle vs baseline | arrived | 10 | 0.45 | 0.72 | [-0.54, 1.45] | 7/3/0 | **INCONCLUSIVE** |
| oracle vs baseline | teleports | 10 | 177.12 | 134.44 | [4.9, 349.34] | 3/6/1 | **HURT** |
| oracle vs reactive | total_vehicle_hours_incl_never_inserted | 10 | -6.39 | -5.53 | [-9.79, -3.0] | 9/1/0 | **HELPED** |
| oracle vs reactive | total_vehicle_hours | 10 | -6.02 | -5.32 | [-9.25, -2.8] | 9/1/0 | **HELPED** |
| oracle vs reactive | mean_travel_time_all | 10 | -6.53 | -5.71 | [-9.97, -3.09] | 9/1/0 | **HELPED** |
| oracle vs reactive | mean_travel_time_s | 10 | -4.84 | -4.93 | [-7.45, -2.23] | 9/1/0 | **HELPED** |
| oracle vs reactive | p95_travel_time_s | 10 | -17.08 | -19.21 | [-23.01, -11.16] | 10/0/0 | **HELPED** |
| oracle vs reactive | total_waiting_s | 10 | -18.37 | -20.46 | [-29.2, -7.55] | 9/1/0 | **HELPED** |
| oracle vs reactive | mean_queue_veh | 10 | -25.66 | -26.34 | [-38.02, -13.31] | 9/1/0 | **HELPED** |
| oracle vs reactive | max_queue_veh | 10 | -29.34 | -26.98 | [-42.88, -15.81] | 10/0/0 | **HELPED** |
| oracle vs reactive | arrived | 10 | 2.99 | 1.83 | [1.15, 4.83] | 9/0/1 | **HELPED** |
| oracle vs reactive | teleports | 10 | -38.81 | -62.06 | [-95.83, 18.2] | 9/1/0 | **INCONCLUSIVE** |
| reactive vs baseline | total_vehicle_hours_incl_never_inserted | 10 | 2.79 | 3.04 | [-1.68, 7.25] | 3/7/0 | **INCONCLUSIVE** |
| reactive vs baseline | total_vehicle_hours | 10 | 2.32 | 2.9 | [-1.87, 6.52] | 3/7/0 | **INCONCLUSIVE** |
| reactive vs baseline | mean_travel_time_all | 10 | 3.02 | 3.28 | [-1.49, 7.53] | 3/7/0 | **INCONCLUSIVE** |
| reactive vs baseline | mean_travel_time_s | 10 | 1.04 | 0.34 | [-2.4, 4.48] | 4/6/0 | **INCONCLUSIVE** |
| reactive vs baseline | p95_travel_time_s | 10 | 8.56 | 6.04 | [-3.99, 21.1] | 3/7/0 | **INCONCLUSIVE** |
| reactive vs baseline | total_waiting_s | 10 | 16.92 | 10.14 | [-0.34, 34.18] | 3/7/0 | **INCONCLUSIVE** |
| reactive vs baseline | mean_queue_veh | 10 | 33.48 | 31.08 | [9.43, 57.54] | 1/9/0 | **HURT** |
| reactive vs baseline | max_queue_veh | 10 | 40.06 | 33.81 | [17.23, 62.89] | 1/9/0 | **HURT** |
| reactive vs baseline | arrived | 10 | -2.41 | -2.25 | [-4.28, -0.54] | 1/9/0 | **HURT** |
| reactive vs baseline | teleports | 10 | 503.53 | 241.88 | [84.28, 922.79] | 0/9/1 | **HURT** |

Probe trip travel time per arm (seconds, per seed; one user trip, not the system conclusion): {"baseline": [342.0, 303.0, 269.0, 292.0, 308.0, 313.0, 289.0, 335.0, 326.0, 346.0], "reactive": [331.0, 309.0, 304.0, 331.0, 300.0, 342.0, 327.0, 371.0, 383.0, 354.0], "oracle": [356.0, 324.0, 335.0, 338.0, 351.0, 331.0, 294.0, 368.0, 378.0, 359.0]}

