# V2X penetration sweep - Eclipse MOSAIC 25.2, Dhaka R1 (registered scenario)

Knob: `mapping_config.json` -> `typeDistributions.DEFAULT_VEHTYPE` = [{AdHoc: WeatherWarningApp+SlowDownApp, weight p}, {Unequipped: SlowDownApp, weight 1-p}], `config.fixedOrder=false` (stochastic, seed-driven). Hazard: TRACTION_HAZARD/ICE rectangle at Karwan Bazar (environment_config.json); equipped vehicles that sense it broadcast DENMs over SNS ad-hoc (ITS-G5, multi-hop TTL 20); receivers with the hazard on their route reroute through the official NavigationModule.

Definitions: equipped = registered with WeatherWarningApp; delivery_ratio_veh = distinct receivers / equipped; latency = t_rx - t_tx per MessageId; route switches = CentralNavigationComponent 'Change to route' lines; travel time = SUMO tripinfo of finished trips (equipped vs unequipped split).

## Per point

| p | seed | wall s | registered | equipped | DENM sent | senders | receptions | receivers | deliv. ratio | lat mean ms | lat p95 ms | route switches | veh switched | trips fin. | TT mean s | TT p95 s | timeLoss mean s | TT eq. s | TT uneq. s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.0 | 11 | 16 | 2147 | 0 | 0 | 0 | 0 | 0 |  |  |  | 0 | 0 | 543 | 332.0 | 484.9 | 119.6 |  | 332.0 |
| 0.0 | 22 | 38 | 2161 | 0 | 0 | 0 | 0 | 0 |  |  |  | 0 | 0 | 549 | 337.9 | 490.0 | 120.7 |  | 337.9 |
| 0.0 | 33 | 12 | 2121 | 0 | 0 | 0 | 0 | 0 |  |  |  | 0 | 0 | 560 | 335.4 | 496.1 | 121.3 |  | 335.4 |
| 0.1 | 11 | 17 | 2157 | 218 | 3702 | 31 | 428339 | 211 | 0.968 | 30.0 | 57.44 | 68 | 68 | 569 | 335.3 | 481.2 | 119.2 | 341.1 | 334.7 |
| 0.1 | 22 | 44 | 2157 | 208 | 4650 | 36 | 518792 | 202 | 0.971 | 30.0 | 57.45 | 59 | 59 | 557 | 338.6 | 483.4 | 124.2 | 334.6 | 339.1 |
| 0.1 | 33 | 14 | 2193 | 207 | 3716 | 36 | 414112 | 198 | 0.957 | 29.98 | 57.38 | 69 | 69 | 534 | 333.5 | 474.3 | 119.8 | 332.6 | 333.6 |
| 0.25 | 11 | 35 | 2127 | 520 | 11165 | 89 | 3033412 | 499 | 0.96 | 30.01 | 57.44 | 171 | 171 | 552 | 332.3 | 478.0 | 120.8 | 326.1 | 334.2 |
| 0.25 | 22 | 50 | 2164 | 540 | 10294 | 93 | 2970222 | 529 | 0.98 | 30.0 | 57.48 | 170 | 170 | 570 | 336.3 | 481.0 | 121.3 | 329.6 | 338.6 |
| 0.25 | 33 | 22 | 2156 | 527 | 7986 | 79 | 2217156 | 511 | 0.97 | 29.99 | 57.4 | 156 | 156 | 563 | 337.4 | 495.0 | 124.6 | 326.2 | 341.3 |
| 0.5 | 11 | 103 | 2153 | 1083 | 22563 | 184 | 12880209 | 1057 | 0.976 | 30.0 | 57.45 | 375 | 375 | 578 | 341.6 | 492.9 | 124.3 | 342.0 | 341.3 |
| 0.5 | 22 | 103 | 2177 | 1093 | 21676 | 187 | 13082548 | 1058 | 0.968 | 30.0 | 57.42 | 357 | 357 | 559 | 335.8 | 511.0 | 123.6 | 334.5 | 336.9 |
| 0.5 | 33 | 59 | 2153 | 1075 | 19050 | 185 | 11088610 | 1042 | 0.969 | 30.0 | 57.42 | 354 | 354 | 547 | 334.6 | 469.1 | 123.0 | 333.6 | 335.6 |
| 1.0 | 11 | 751 | 2175 | 2175 | 47845 | 411 | 58037523 | 2124 | 0.977 | 30.0 | 57.45 | 724 | 724 | 567 | 334.6 | 486.7 | 124.0 | 334.6 |  |
| 1.0 | 22 | 356 | 2185 | 2185 | 45732 | 387 | 54688803 | 2130 | 0.975 | 30.0 | 57.45 | 706 | 706 | 542 | 329.1 | 471.9 | 117.5 | 329.1 |  |
| 1.0 | 33 | 312 | 2168 | 2168 | 44928 | 388 | 54208312 | 2107 | 0.972 | 30.0 | 57.44 | 708 | 708 | 533 | 327.3 | 492.4 | 118.5 | 327.3 |  |

## Mean over seeds

| p | n seeds | equipped frac | receivers | deliv. ratio | lat mean ms | lat p95 ms | route switches | TT mean s | TT p95 s | timeLoss mean s |
|---|---|---|---|---|---|---|---|---|---|---|
| 0.0 | 3 | 0.0 | 0.0 | - | - | - | 0.0 | 335.1 | 490.3 | 120.5 |
| 0.1 | 3 | 0.097 | 204.0 | 0.965 | 29.99 | 57.42 | 65.0 | 335.8 | 479.6 | 121.1 |
| 0.25 | 3 | 0.246 | 513.0 | 0.97 | 30.0 | 57.44 | 166.0 | 335.3 | 484.7 | 122.2 |
| 0.5 | 3 | 0.501 | 1052.0 | 0.971 | 30.0 | 57.43 | 362.0 | 337.3 | 491.0 | 123.6 |
| 1.0 | 3 | 1.0 | 2120.0 | 0.975 | 30.0 | 57.45 | 713.0 | 330.3 | 483.7 | 120.0 |

Source JSONs: `results/networking/penetration_p{P}_s{SEED}.json`; regenerate with `python pipeline/networking/penetration_sweep.py --aggregate`.
