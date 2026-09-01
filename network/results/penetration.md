# V2X penetration sweep - Eclipse MOSAIC 25.2, Dhaka R1 (registered scenario)

Knob: `mapping_config.json` -> `typeDistributions.DEFAULT_VEHTYPE` = [{AdHoc: WeatherWarningApp+SlowDownApp, weight p}, {Unequipped: SlowDownApp, weight 1-p}], `config.fixedOrder=false` (stochastic, seed-driven). Hazard: TRACTION_HAZARD/ICE rectangle at Karwan Bazar (environment_config.json); equipped vehicles that sense it broadcast DENMs over SNS ad-hoc (ITS-G5, multi-hop TTL 20); receivers with the hazard on their route reroute through the official NavigationModule.

Definitions: equipped = registered with WeatherWarningApp; delivery_ratio_veh = distinct receivers / equipped; latency = t_rx - t_tx per MessageId; route switches = CentralNavigationComponent 'Change to route' lines; travel time = SUMO tripinfo of finished trips (equipped vs unequipped split).

## Per point

| p | seed | wall s | registered | equipped | DENM sent | senders | receptions | receivers | deliv. ratio | lat mean ms | lat p95 ms | route switches | veh switched | trips fin. | TT mean s | TT p95 s | timeLoss mean s | TT eq. s | TT uneq. s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.0 | 11 | 16 | 2147 | 0 | 0 | 0 | 0 | 0 |  |  |  | 0 | 0 | 543 | 332.0 | 484.9 | 119.6 |  | 332.0 |
| 0.1 | 11 | 17 | 2157 | 218 | 3702 | 31 | 428339 | 211 | 0.968 | 30.0 | 57.44 | 68 | 68 | 569 | 335.3 | 481.2 | 119.2 | 341.1 | 334.7 |
| 0.25 | 11 | 35 | 2127 | 520 | 11165 | 89 | 3033412 | 499 | 0.96 | 30.01 | 57.44 | 171 | 171 | 552 | 332.3 | 478.0 | 120.8 | 326.1 | 334.2 |
| 0.5 | 11 | 103 | 2153 | 1083 | 22563 | 184 | 12880209 | 1057 | 0.976 | 30.0 | 57.45 | 375 | 375 | 578 | 341.6 | 492.9 | 124.3 | 342.0 | 341.3 |

## Mean over seeds

| p | n seeds | equipped frac | receivers | deliv. ratio | lat mean ms | lat p95 ms | route switches | TT mean s | TT p95 s | timeLoss mean s |
|---|---|---|---|---|---|---|---|---|---|---|
| 0.0 | 1 | 0.0 | 0.0 | - | - | - | 0.0 | 332.0 | 484.9 | 119.6 |
| 0.1 | 1 | 0.101 | 211.0 | 0.968 | 30.0 | 57.44 | 68.0 | 335.3 | 481.2 | 119.2 |
| 0.25 | 1 | 0.244 | 499.0 | 0.96 | 30.01 | 57.44 | 171.0 | 332.3 | 478.0 | 120.8 |
| 0.5 | 1 | 0.503 | 1057.0 | 0.976 | 30.0 | 57.45 | 375.0 | 341.6 | 492.9 | 124.3 |

Source JSONs: `network/results/penetration_p{P}_s{SEED}.json`; regenerate with `python network/penetration_sweep.py --aggregate`.
