# Congested-traffic experiment — report

Generated 2026-09-28T14:49:00.002839+00:00 from run files.

Demand is SYNTHETIC_WHAT_IF (randomTrips on the real OSM network); METR-LA carries no flow counts, so no detector-based calibration was possible (`src/pipeline/v2x/METR_LA_FLOW_NOTE.md`).

## Scenario-quality rule (frozen before any policy arm; revision log)

```
Selection rule (frozen before any policy arm is run):
    STABLE      teleports ≤ 1 % of inserted vehicles AND ≥ 85 % of loaded vehicles arrive within the horizon
                AND the loaded network's minimum mean speed stays above 2 m/s (no gridlock) — "loaded" =
                steps with at least a quarter of the peak number of running vehicles
    CONGESTED   at the busiest 300 s interval, ≥ 10 % of major-road edges run at ≥ 70 % of capacity
                (entered vehicles / lanes × 1800 veh/h/lane) AND the loaded network's mean speed is ≤ 70 % of
                the 1.0× value (queues are growing, not just signal stops)
    chosen      the HIGHEST multiplier that is both STABLE and CONGESTED; if none is CONGESTED, the highest
                STABLE one is reported with the gate FAILED (a valid negative: this corridor cannot be
                stressed by demand scaling alone)
    ladder      1, 1.5, 2, 3, 4, 6, 8, 12, 16 × — the sweep stops at the first UNSTABLE level

Revision log (every change made BEFORE any policy arm was simulated on a stress level; the v1 verdicts are
kept in the JSON next to the v2 verdicts):
  v0  "halting ≥ 5 % of running vehicles" as the queue criterion — dropped after the 1.0× baseline showed
      25 % halting from signalised stops alone.
  v1  CONGESTED = ≥ 10 % of major-road EDGES at ≥ 70 % of 1800 veh/h/lane AND loaded speed ≤ 70 % of the
      1.0× value. Outcome on la_c2 (both OD rules): never met at any stable level — the 1800 veh/h/lane
      capacity is unreachable on signalised arterials (green share), and most major-road length carries
      little traffic even at 8×, while SUMO already reports standing jams (statistic.xml: jam teleports
      99 of 149 at 8×). The criterion measured the wrong thing: network-wide lane saturation instead of
      the delay that drivers (and a router) experience.
  v2  CONGESTED = travel-time index TTI = mean travel time / 1.0× mean travel time ≥ 1.30 (the usual
      urban-peak "congested" threshold) AND SUMO reports jam-type teleports > 0 (standing queues of
      ≥ 300 s exist somewhere). STABLE unchanged. After the ladder stops, the bracket between the last
      STABLE and the first UNSTABLE level is bisected twice so the chosen level is not an artefact of the
      ladder's step size. This is the rule the gate uses.

The chosen level is written to src/pipeline/v2x/controller_config.json under "stress_scenario" and the gate
result to results/v2x/stress/<city>/summary.json. Baseline-only runs: no policy is involved in the choice.
```

## Stress calibration — la_c2_hollywood_101_5 — `summary_uniform_any.md`

scenario default: randomTrips samples origins/destinations from every passenger edge, lane-weighted, fringe factor 5

Rule: {"teleport_rate_max": 0.01, "arrival_share_min": 0.85, "loaded_min_speed_mps": 2.0, "tti_min": 1.3, "jam_teleports_min": 1, "bisection_steps": 2, "v1_share_major_ge_0.7_min": 0.1, "v1_loaded_speed_ratio_to_1x_max": 0.7}

| scale | vehicles | arrived | teleport rate (jam) | util p50 / p90 / max (major edges, busiest interval) | share ≥ 0.7 | occupancy % | spillback edges | loaded speed m/s (× of 1x) | loaded min speed | halting share | mean tt s | TTI | p95 s | STABLE | CONGESTED (v2) | v1 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1.0 | 900 | 1.00 | 0.000 (0) | 0.007 / 0.017 / 0.0847 | 0.0 | 0.2433 | 0.0 | 9.9933 (None) | 7.48 | 0.1897 | 576 | None | 1065 | True | False | False |
| 1.5 | 1351 | 1.00 | 0.000 (0) | 0.0093 / 0.018 / 0.0737 | 0.0 | 0.3033 | 0.0 | 10.0467 (1.005) | 7.8967 | 0.188 | 576 | 1.002 | 1078 | True | False | False |
| 2.0 | 1800 | 1.00 | 0.001 (0) | 0.007 / 0.027 / 0.1577 | 0.0 | 0.3667 | 0.0 | 9.9933 (1.0) | 8.11 | 0.1877 | 578 | 1.004 | 1087 | True | False | False |
| 3.0 | 2700 | 1.00 | 0.001 (1) | 0.0107 / 0.037 / 0.2157 | 0.0 | 0.4833 | 0.0 | 9.9433 (0.995) | 8.47 | 0.1897 | 584 | 1.015 | 1091 | True | False | False |
| 4.0 | 3600 | 1.00 | 0.002 (1) | 0.013 / 0.048 / 0.293 | 0.0 | 0.6033 | 0.0 | 9.6767 (0.968) | 8.2 | 0.203 | 602 | 1.046 | 1170 | True | False | False |
| 6.0 | 5401 | 1.00 | 0.001 (0) | 0.0177 / 0.0667 / 0.4043 | 0.0 | 0.84 | 0.0 | 9.2233 (0.923) | 7.1867 | 0.2257 | 638 | 1.108 | 1272 | True | False | False |
| 7.0 | 6301 | 0.99 | 0.004 (6) | 0.02 / 0.073 / 0.48 | 0.0 | 1.03 | 0.6667 | 8.6033 (0.861) | 5.56 | 0.263 | 684 | 1.188 | 1413 | True | False | False |
| 7.5 | 6750 | 0.98 | 0.008 (22) | 0.0207 / 0.0787 / 0.4577 | 0.0 | 1.1167 | 0.3333 | 8.21 (0.822) | 4.8733 | 0.2893 | 716 | 1.244 | 1489 | True | False | False |
| 8.0 | 7200 | 0.97 | 0.015 (60) | 0.0207 / 0.084 / 0.451 | 0.0 | 1.2567 | 2.0 | 7.7433 (0.775) | 3.7667 | 0.3237 | 749 | 1.302 | 1577 | False | True | False |

**Gate: STRESS_GATE_FAILED** — chosen scale 7.5 (no multiplier is both stable and congested under the rule — demand scaling alone does not stress this corridor without breaking it).

## Stress calibration — la_c2_hollywood_101_5 — `summary_uniform_arterial.md`

origins and destinations restricted to MAJOR roads (OSM motorway/trunk/primary/secondary incl. links), weight = lanes × length, minimum trip distance 2000 m — demand concentrates on the corridor's arterials instead of the 12k-edge residential grid

Rule: {"teleport_rate_max": 0.01, "arrival_share_min": 0.85, "loaded_min_speed_mps": 2.0, "tti_min": 1.3, "jam_teleports_min": 1, "bisection_steps": 2, "v1_share_major_ge_0.7_min": 0.1, "v1_loaded_speed_ratio_to_1x_max": 0.7}

| scale | vehicles | arrived | teleport rate (jam) | util p50 / p90 / max (major edges, busiest interval) | share ≥ 0.7 | occupancy % | spillback edges | loaded speed m/s (× of 1x) | loaded min speed | halting share | mean tt s | TTI | p95 s | STABLE | CONGESTED (v2) | v1 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1.0 | 900 | 1.00 | 0.001 (0) | 0.007 / 0.02 / 0.129 | 0.0 | 0.2567 | 0.0 | 10.9733 (None) | 8.39 | 0.165 | 632 | None | 1129 | True | False | False |
| 1.5 | 1351 | 1.00 | 0.001 (0) | 0.007 / 0.0257 / 0.1777 | 0.0 | 0.3133 | 0.0 | 10.9867 (1.001) | 8.9 | 0.1623 | 629 | 0.996 | 1134 | True | False | False |
| 2.0 | 1800 | 1.00 | 0.001 (0) | 0.007 / 0.0317 / 0.2287 | 0.0 | 0.38 | 0.0 | 10.93 (0.996) | 8.8433 | 0.162 | 634 | 1.003 | 1149 | True | False | False |
| 3.0 | 2700 | 1.00 | 0.001 (0) | 0.01 / 0.0447 / 0.3287 | 0.0 | 0.5033 | 0.0 | 10.73 (0.978) | 9.0033 | 0.168 | 646 | 1.023 | 1178 | True | False | False |
| 4.0 | 3600 | 1.00 | 0.002 (0) | 0.0127 / 0.057 / 0.4177 | 0.0 | 0.6267 | 0.0 | 10.5167 (0.958) | 8.71 | 0.1783 | 663 | 1.049 | 1247 | True | False | False |
| 6.0 | 5401 | 0.99 | 0.002 (0) | 0.0173 / 0.073 / 0.5357 | 0.0 | 0.8933 | 0.0 | 9.4 (0.857) | 6.5533 | 0.219 | 746 | 1.18 | 1503 | True | False | False |
| 7.0 | 6301 | 0.98 | 0.004 (10) | 0.02 / 0.084 / 0.607 | 0.0 | 1.0433 | 0.3333 | 8.7233 (0.795) | 5.1633 | 0.2587 | 793 | 1.255 | 1601 | True | False | False |
| 7.5 | 6750 | 0.97 | 0.004 (10) | 0.02 / 0.09 / 0.6467 | 0.0 | 1.1167 | 0.0 | 8.4233 (0.768) | 4.3633 | 0.2803 | 817 | 1.292 | 1674 | True | False | False |
| 8.0 | 7200 | 0.95 | 0.012 (52) | 0.0207 / 0.0933 / 0.7 | 0.0 | 1.2567 | 1.3333 | 7.8133 (0.712) | 3.3533 | 0.3243 | 860 | 1.361 | 1726 | False | True | False |

**Gate: STRESS_GATE_FAILED** — chosen scale 7.5 (no multiplier is both stable and congested under the rule — demand scaling alone does not stress this corridor without breaking it).

## Stress calibration — la_c4_central_wide — `summary_uniform_any.md`

scenario default: randomTrips samples origins/destinations from every passenger edge, lane-weighted, fringe factor 5

Rule: {"teleport_rate_max": 0.01, "arrival_share_min": 0.85, "loaded_min_speed_mps": 2.0, "tti_min": 1.3, "jam_teleports_min": 1, "bisection_steps": 2, "v1_share_major_ge_0.7_min": 0.1, "v1_loaded_speed_ratio_to_1x_max": 0.7}

| scale | vehicles | arrived | teleport rate (jam) | util p50 / p90 / max (major edges, busiest interval) | share ≥ 0.7 | occupancy % | spillback edges | loaded speed m/s (× of 1x) | loaded min speed | halting share | mean tt s | TTI | p95 s | STABLE | CONGESTED (v2) | v1 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1.0 | 900 | 1.00 | 0.000 (0) | 0.007 / 0.027 / 0.0867 | 0.0 | 0.3067 | 0.0 | 11.0233 (None) | 8.55 | 0.2017 | 724 | None | 1386 | True | False | False |
| 1.5 | 1351 | 1.00 | 0.000 (0) | 0.0113 / 0.0323 / 0.082 | 0.0 | 0.3933 | 0.0 | 10.8633 (0.985) | 8.3667 | 0.205 | 733 | 1.012 | 1412 | True | False | False |
| 2.0 | 1800 | 1.00 | 0.000 (0) | 0.0087 / 0.0433 / 0.152 | 0.0 | 0.47 | 0.0 | 10.9033 (0.989) | 8.7033 | 0.2027 | 734 | 1.013 | 1409 | True | False | False |
| 3.0 | 2700 | 1.00 | 0.001 (0) | 0.012 / 0.059 / 0.26 | 0.0 | 0.6267 | 0.0 | 10.7033 (0.971) | 8.44 | 0.2053 | 744 | 1.028 | 1442 | True | False | False |
| 4.0 | 3600 | 1.00 | 0.001 (0) | 0.013 / 0.0733 / 0.318 | 0.0 | 0.7833 | 0.0 | 10.39 (0.943) | 8.05 | 0.2177 | 766 | 1.058 | 1519 | True | False | False |
| 6.0 | 5401 | 0.97 | 0.001 (0) | 0.019 / 0.0943 / 0.3933 | 0.0 | 1.1867 | 0.0 | 8.9067 (0.808) | 5.16 | 0.296 | 877 | 1.211 | 1892 | True | False | False |
| 8.0 | 7200 | 0.91 | 0.005 (19) | 0.0213 / 0.1107 / 0.4323 | 0.0 | 1.6567 | 0.3333 | 7.3667 (0.668) | 3.5367 | 0.3833 | 1001 | 1.382 | 2117 | True | True | False |
| 10.0 | 9000 | 0.85 | 0.009 (34) | 0.026 / 0.128 / 0.6043 | 0.0 | 2.0433 | 0.3333 | 6.3133 (0.573) | 2.62 | 0.445 | 1099 | 1.517 | 2166 | True | True | False |
| 11.0 | 9901 | 0.83 | 0.013 (61) | 0.027 / 0.1357 / 0.548 | 0.0 | 2.2367 | 0.3333 | 6.01 (0.545) | 2.5133 | 0.461 | 1138 | 1.571 | 2163 | False | True | False |
| 12.0 | 10798 | 0.81 | 0.020 (95) | 0.0287 / 0.142 / 0.6313 | 0.0 | 2.4667 | 0.6667 | 5.73 (0.52) | 2.34 | 0.4777 | 1189 | 1.641 | 2221 | False | True | False |

**Gate: VALID_TRAFFIC_STRESS_CASE** — chosen scale 10.0 (highest multiplier that is STABLE and CONGESTED).

## Stress calibration — la_c4_central_wide — `summary_uniform_arterial.md`

origins and destinations restricted to MAJOR roads (OSM motorway/trunk/primary/secondary incl. links), weight = lanes × length, minimum trip distance 2000 m — demand concentrates on the corridor's arterials instead of the 12k-edge residential grid

Rule: {"teleport_rate_max": 0.01, "arrival_share_min": 0.85, "loaded_min_speed_mps": 2.0, "tti_min": 1.3, "jam_teleports_min": 1, "bisection_steps": 2, "v1_share_major_ge_0.7_min": 0.1, "v1_loaded_speed_ratio_to_1x_max": 0.7}

| scale | vehicles | arrived | teleport rate (jam) | util p50 / p90 / max (major edges, busiest interval) | share ≥ 0.7 | occupancy % | spillback edges | loaded speed m/s (× of 1x) | loaded min speed | halting share | mean tt s | TTI | p95 s | STABLE | CONGESTED (v2) | v1 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1.0 | 900 | 1.00 | 0.000 (0) | 0.0193 / 0.0347 / 0.0747 | 0.0 | 0.3133 | 0.0 | 12.8733 (None) | 9.0 | 0.1767 | 757 | None | 1428 | True | False | False |
| 1.5 | 1351 | 1.00 | 0.000 (0) | 0.007 / 0.0407 / 0.1933 | 0.0 | 0.3967 | 0.0 | 12.73 (0.989) | 9.1033 | 0.18 | 762 | 1.006 | 1433 | True | False | False |
| 2.0 | 1800 | 1.00 | 0.000 (0) | 0.0093 / 0.049 / 0.2313 | 0.0 | 0.4767 | 0.0 | 12.6633 (0.984) | 9.3567 | 0.1803 | 762 | 1.006 | 1426 | True | False | False |
| 3.0 | 2700 | 1.00 | 0.001 (1) | 0.0113 / 0.064 / 0.389 | 0.0 | 0.63 | 0.0 | 12.5167 (0.972) | 9.9233 | 0.184 | 772 | 1.019 | 1463 | True | False | False |
| 4.0 | 3600 | 1.00 | 0.000 (0) | 0.013 / 0.08 / 0.3913 | 0.0 | 0.8033 | 0.0 | 11.87 (0.922) | 8.0533 | 0.2047 | 810 | 1.07 | 1602 | True | False | False |
| 6.0 | 5401 | 0.94 | 0.002 (5) | 0.017 / 0.1037 / 0.6067 | 0.0 | 1.2233 | 0.0 | 9.6233 (0.748) | 4.2867 | 0.3113 | 948 | 1.252 | 2000 | True | False | False |
| 8.0 | 7200 | 0.87 | 0.004 (14) | 0.02 / 0.1277 / 0.6553 | 0.0 | 1.7333 | 0.0 | 7.8133 (0.607) | 2.88 | 0.4023 | 1058 | 1.398 | 2110 | True | True | False |
| 9.0 | 8101 | 0.85 | 0.005 (23) | 0.02 / 0.131 / 0.6423 | 0.0 | 1.9467 | 0.3333 | 7.4267 (0.577) | 2.7033 | 0.4187 | 1105 | 1.46 | 2171 | False | True | False |
| 10.0 | 9000 | 0.82 | 0.007 (39) | 0.023 / 0.14 / 0.7 | 0.0 | 2.15 | 0.0 | 7.06 (0.548) | 2.3467 | 0.4433 | 1153 | 1.523 | 2151 | False | True | False |
| 12.0 | 10798 | 0.78 | 0.014 (74) | 0.0233 / 0.1593 / 0.651 | 0.0 | 2.5433 | 0.0 | 6.5033 (0.505) | 2.0933 | 0.4717 | 1248 | 1.648 | 2223 | False | True | False |

**Gate: VALID_TRAFFIC_STRESS_CASE** — chosen scale 8.0 (highest multiplier that is STABLE and CONGESTED).

## Scenario-quality gate — every corridor and OD rule

| corridor | OD rule | gate | highest STABLE level | its TTI / teleport rate / jam teleports | first UNSTABLE level | its TTI / teleport rate / arrivals |
|---|---|---|---|---|---|---|
| la_c2_hollywood_101_5 | any | **STRESS_GATE_FAILED** | 7.5× | 1.244 / 0.0083 / 22.3333 | 8.0× | 1.302 / 0.0151 / 0.9675 |
| la_c2_hollywood_101_5 | arterial | **STRESS_GATE_FAILED** | 7.5× | 1.292 / 0.0039 / 9.6667 | 8.0× | 1.361 / 0.0121 / 0.9467 |
| la_c4_central_wide | any | **VALID_TRAFFIC_STRESS_CASE** | 10.0× | 1.517 / 0.0093 / 33.6667 | 11.0× | 1.571 / 0.0135 / 0.8316 |
| la_c4_central_wide | arterial | **VALID_TRAFFIC_STRESS_CASE** | 8.0× | 1.398 / 0.0042 / 14.3333 | 9.0× | 1.46 / 0.0054 / 0.8455 |

Reading: where the gate FAILED (la_c2_hollywood_101_5/any, la_c2_hollywood_101_5/arterial) the twin becomes UNSTABLE — teleport rate above 1 % of inserted vehicles, i.e. SUMO removing vehicles that waited ≥ 300 s in a jam — at, or just before, the demand level where the network-wide travel-time index reaches 1.30: local gridlock at many secondary/primary junctions precedes network-wide congestion. Where it PASSED (la_c4_central_wide/any at 10.0×, la_c4_central_wide/arterial at 8.0×) a stable regime with TTI ≥ 1.30 and standing queues exists; that level is frozen in controller_config.json and used for both scenarios. Teleporting is a property of the twin (time-to-teleport = 300 s), not of traffic; it was NOT changed to make a gate pass.

## Scenario A (forecastable congestion — demand rises to the calibrated level; no incident) — development seeds — `scenarioA_oracle_gate_dev.json`

Stress level 8.0× (VALID_TRAFFIC_STRESS_CASE), OD rule arterial. **ORACLE_HEADROOM: PASSED** — oracle_v2x must beat reactive on total vehicle-hours with a paired 95 % CI that excludes zero (paired() label HELPED).

oracle vs reactive: {'pair': 'oracle_v2x vs reactive', 'metric': 'total_vehicle_hours_incl_never_inserted', 'seeds': 3, 'per_seed_pct': [-3.105, -2.262, -1.974], 'mean_pct': -2.45, 'median_pct': -2.26, 'ci95': [-3.91, -0.99], 'wins': 3, 'losses': 0, 'ties': 0, 'label': 'HELPED', 'lower_is_better': True}

oracle vs baseline: {'pair': 'oracle_v2x vs baseline', 'metric': 'total_vehicle_hours_incl_never_inserted', 'seeds': 3, 'per_seed_pct': [-1.119, -0.762, -0.875], 'mean_pct': -0.92, 'median_pct': -0.88, 'ci95': [-1.37, -0.47], 'wins': 3, 'losses': 0, 'ties': 0, 'label': 'HELPED', 'lower_is_better': True}

reactive vs baseline: {'pair': 'reactive vs baseline', 'metric': 'total_vehicle_hours_incl_never_inserted', 'seeds': 3, 'per_seed_pct': [2.049, 1.534, 1.121], 'mean_pct': 1.57, 'median_pct': 1.53, 'ci95': [0.41, 2.72], 'wins': 0, 'losses': 3, 'ties': 0, 'label': 'HURT', 'lower_is_better': True}

### stage `learned` — `results/v2x/closed_loop/la_c4_central_wide_prepeak_ideal_p30_cfgea08dddedc14_stressA_fork1200_x8_peak_arterial`

Seeds [101, 102, 103] · fork 1200 s · state hashes {'101': '5009e45519e6', '102': '18849e64fd9f', '103': 'cd5a3e42ac57'} · identical across arms: **True** · reroutes by arm {'baseline': 0, 'reactive': 0, 'oracle_v2x': 854, 'persistence_v2x': 615, 'predictive_v2x': 600, 'predictive_corrected_v2x': 650, 'random_v2x': 1548}

| arm | vs baseline: mean % | 95 % CI | W/L/T | label | vs reactive: mean % | 95 % CI | W/L/T | label | p95 % | waiting % | queue % | arrived % | teleports (sum) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| no advice | — | — | — | — | — | — | — | — | — | — | — | — | 380 |
| reactive (current travel times) | 1.57 | [0.41, 2.72] | 0/3/0 | **HURT** | — | — | —/—/— | **—** | -1.78 | 2.01 | 3.29 | -0.85 | 417 |
| ORACLE future state + V2X (upper bound) | -0.92 | [-1.37, -0.47] | 3/0/0 | **HELPED** | -2.45 | [-3.91, -0.99] | 3/0/0 | **HELPED** | -0.68 | 0.64 | -4.49 | 1.39 | 300 |
| persistence + V2X | -0.15 | [-1.05, 0.75] | 2/1/0 | **INCONCLUSIVE** | -1.69 | [-3.03, -0.35] | 3/0/0 | **HELPED** | -1.3 | -0.41 | -0.12 | 0.11 | 412 |
| Graph WaveNet + V2X | 0.21 | [-1.21, 1.63] | 2/1/0 | **INCONCLUSIVE** | -1.34 | [-3.69, 1.02] | 3/0/0 | **INCONCLUSIVE** | 0.05 | 0.01 | 0.59 | -0.17 | 374 |
| Graph WaveNet + online correction + V2X | 0.0 | [-1.72, 1.72] | 2/1/0 | **INCONCLUSIVE** | -1.54 | [-4.25, 1.17] | 3/0/0 | **INCONCLUSIVE** | -1.16 | -0.27 | 0.16 | 0.04 | 375 |
| shuffled forecast (negative control) | 0.02 | [-0.75, 0.79] | 1/2/0 | **INCONCLUSIVE** | -1.52 | [-3.08, 0.03] | 3/0/0 | **INCONCLUSIVE** | -0.25 | -0.54 | -0.84 | 0.01 | 259 |

Optimizer contrasts: predictive_v2x_vs_oracle_v2x: 1.14 % [-0.34, 2.61] 0/3/0 INCONCLUSIVE


Per-seed vehicle-hours: s101: baseline 3657.0, reactive 3731.9, oracle_v2x 3616.1, persistence_v2x 3646.3, predictive_v2x 3655.8, predictive_corrected_v2x 3641.9, random_v2x 3659.1; s102: baseline 3633.2, reactive 3689.0, oracle_v2x 3605.5, persistence_v2x 3642.7, predictive_v2x 3625.8, predictive_corrected_v2x 3619.3, random_v2x 3622.1; s103: baseline 3609.6, reactive 3650.1, oracle_v2x 3578.0, persistence_v2x 3594.3, predictive_v2x 3640.6, predictive_corrected_v2x 3638.5, random_v2x 3620.7

First reroute applied per arm (lead time of predictive vs reactive advice): s101: oracle_v2x first reroute 1500 s, persistence_v2x first reroute 1500 s, predictive_v2x first reroute 1500 s, predictive_corrected_v2x first reroute 1500 s, random_v2x first reroute 1500 s; s102: oracle_v2x first reroute 1500 s, persistence_v2x first reroute 1500 s, predictive_v2x first reroute 1500 s, predictive_corrected_v2x first reroute 1500 s, random_v2x first reroute 1500 s; s103: oracle_v2x first reroute 1500 s, persistence_v2x first reroute 1500 s, predictive_v2x first reroute 1500 s, predictive_corrected_v2x first reroute 1500 s, random_v2x first reroute 1500 s

### stage `oracle` — `results/v2x/closed_loop/la_c4_central_wide_prepeak_ideal_p30_cfgea08dddedc14_stressA_fork1200_x8_peak_arterial`

Seeds [101, 102, 103] · fork 1200 s · state hashes {'101': '5009e45519e6', '102': '18849e64fd9f', '103': 'cd5a3e42ac57'} · identical across arms: **True** · reroutes by arm {'baseline': 0, 'reactive': 0, 'oracle_v2x': 854, 'persistence_v2x': 615, 'predictive_v2x': 600, 'predictive_corrected_v2x': 650, 'random_v2x': 1548}

| arm | vs baseline: mean % | 95 % CI | W/L/T | label | vs reactive: mean % | 95 % CI | W/L/T | label | p95 % | waiting % | queue % | arrived % | teleports (sum) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| no advice | — | — | — | — | — | — | — | — | — | — | — | — | 380 |
| reactive (current travel times) | 1.57 | [0.41, 2.72] | 0/3/0 | **HURT** | — | — | —/—/— | **—** | -1.78 | 2.01 | 3.29 | -0.85 | 417 |
| ORACLE future state + V2X (upper bound) | -0.92 | [-1.37, -0.47] | 3/0/0 | **HELPED** | -2.45 | [-3.91, -0.99] | 3/0/0 | **HELPED** | -0.68 | 0.64 | -4.49 | 1.39 | 300 |
| persistence + V2X | -0.15 | [-1.05, 0.75] | 2/1/0 | **INCONCLUSIVE** | -1.69 | [-3.03, -0.35] | 3/0/0 | **HELPED** | -1.3 | -0.41 | -0.12 | 0.11 | 412 |
| Graph WaveNet + V2X | 0.21 | [-1.21, 1.63] | 2/1/0 | **INCONCLUSIVE** | -1.34 | [-3.69, 1.02] | 3/0/0 | **INCONCLUSIVE** | 0.05 | 0.01 | 0.59 | -0.17 | 374 |
| Graph WaveNet + online correction + V2X | 0.0 | [-1.72, 1.72] | 2/1/0 | **INCONCLUSIVE** | -1.54 | [-4.25, 1.17] | 3/0/0 | **INCONCLUSIVE** | -1.16 | -0.27 | 0.16 | 0.04 | 375 |
| shuffled forecast (negative control) | 0.02 | [-0.75, 0.79] | 1/2/0 | **INCONCLUSIVE** | -1.52 | [-3.08, 0.03] | 3/0/0 | **INCONCLUSIVE** | -0.25 | -0.54 | -0.84 | 0.01 | 259 |

Optimizer contrasts: predictive_v2x_vs_oracle_v2x: 1.14 % [-0.34, 2.61] 0/3/0 INCONCLUSIVE


Per-seed vehicle-hours: s101: baseline 3657.0, reactive 3731.9, oracle_v2x 3616.1, persistence_v2x 3646.3, predictive_v2x 3655.8, predictive_corrected_v2x 3641.9, random_v2x 3659.1; s102: baseline 3633.2, reactive 3689.0, oracle_v2x 3605.5, persistence_v2x 3642.7, predictive_v2x 3625.8, predictive_corrected_v2x 3619.3, random_v2x 3622.1; s103: baseline 3609.6, reactive 3650.1, oracle_v2x 3578.0, persistence_v2x 3594.3, predictive_v2x 3640.6, predictive_corrected_v2x 3638.5, random_v2x 3620.7

First reroute applied per arm (lead time of predictive vs reactive advice): s101: oracle_v2x first reroute 1500 s, persistence_v2x first reroute 1500 s, predictive_v2x first reroute 1500 s, predictive_corrected_v2x first reroute 1500 s, random_v2x first reroute 1500 s; s102: oracle_v2x first reroute 1500 s, persistence_v2x first reroute 1500 s, predictive_v2x first reroute 1500 s, predictive_corrected_v2x first reroute 1500 s, random_v2x first reroute 1500 s; s103: oracle_v2x first reroute 1500 s, persistence_v2x first reroute 1500 s, predictive_v2x first reroute 1500 s, predictive_corrected_v2x first reroute 1500 s, random_v2x first reroute 1500 s

## Scenario A (forecastable congestion — demand rises to the calibrated level; no incident) — evaluation seeds — `scenarioA_oracle_gate_eval.json`

Stress level 8.0× (VALID_TRAFFIC_STRESS_CASE), OD rule arterial. **ORACLE_HEADROOM: PASSED** — oracle_v2x must beat reactive on total vehicle-hours with a paired 95 % CI that excludes zero (paired() label HELPED).

oracle vs reactive: {'pair': 'oracle_v2x vs reactive', 'metric': 'total_vehicle_hours_incl_never_inserted', 'seeds': 5, 'per_seed_pct': [-1.071, -3.973, -0.717, -1.003, -2.405], 'mean_pct': -1.83, 'median_pct': -1.07, 'ci95': [-3.52, -0.14], 'wins': 5, 'losses': 0, 'ties': 0, 'label': 'HELPED', 'lower_is_better': True}

oracle vs baseline: {'pair': 'oracle_v2x vs baseline', 'metric': 'total_vehicle_hours_incl_never_inserted', 'seeds': 5, 'per_seed_pct': [0.176, -1.668, -0.432, -1.507, -1.832], 'mean_pct': -1.05, 'median_pct': -1.51, 'ci95': [-2.14, 0.04], 'wins': 4, 'losses': 1, 'ties': 0, 'label': 'INCONCLUSIVE', 'lower_is_better': True}

reactive vs baseline: {'pair': 'reactive vs baseline', 'metric': 'total_vehicle_hours_incl_never_inserted', 'seeds': 5, 'per_seed_pct': [1.261, 2.401, 0.287, -0.509, 0.587], 'mean_pct': 0.81, 'median_pct': 0.59, 'ci95': [-0.55, 2.17], 'wins': 1, 'losses': 4, 'ties': 0, 'label': 'INCONCLUSIVE', 'lower_is_better': True}

### stage `learned` — `results/v2x/closed_loop/la_c4_central_wide_prepeak_ideal_p30_cfgea08dddedc14_stressA_eval_fork1200_x8_peak_arterial`

Seeds [201, 202, 203, 204, 205] · fork 1200 s · state hashes {'201': 'ac117185cee8', '202': '4513309cd8e2', '203': '445f0528fbea', '204': '275065f17e02', '205': '4590acadfe33'} · identical across arms: **True** · reroutes by arm {'baseline': 0, 'reactive': 0, 'persistence_v2x': 1088, 'predictive_v2x': 1031, 'predictive_corrected_v2x': 1236, 'random_v2x': 2215, 'oracle_v2x': 1422}

| arm | vs baseline: mean % | 95 % CI | W/L/T | label | vs reactive: mean % | 95 % CI | W/L/T | label | p95 % | waiting % | queue % | arrived % | teleports (sum) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| no advice | — | — | — | — | — | — | — | — | — | — | — | — | 603 |
| reactive (current travel times) | 0.81 | [-0.55, 2.17] | 1/4/0 | **INCONCLUSIVE** | — | — | —/—/— | **—** | 0.16 | 0.54 | 1.33 | -0.44 | 625 |
| persistence + V2X | 0.1 | [-0.98, 1.17] | 2/3/0 | **INCONCLUSIVE** | -0.69 | [-1.98, 0.59] | 4/1/0 | **INCONCLUSIVE** | 0.16 | 0.41 | 0.27 | -0.04 | 661 |
| Graph WaveNet + V2X | 0.12 | [-0.92, 1.16] | 2/3/0 | **INCONCLUSIVE** | -0.68 | [-1.21, -0.15] | 5/0/0 | **HELPED** | -0.35 | -1.04 | 0.48 | -0.29 | 553 |
| Graph WaveNet + online correction + V2X | -0.12 | [-1.07, 0.83] | 2/3/0 | **INCONCLUSIVE** | -0.91 | [-2.15, 0.33] | 4/1/0 | **INCONCLUSIVE** | -0.31 | 0.47 | -0.54 | 0.22 | 628 |
| shuffled forecast (negative control) | 0.42 | [-0.44, 1.28] | 1/4/0 | **INCONCLUSIVE** | -0.38 | [-1.75, 1.0] | 3/2/0 | **INCONCLUSIVE** | 1.02 | 0.89 | 0.53 | -0.1 | 712 |
| ORACLE future state + V2X (upper bound) | -1.05 | [-2.14, 0.04] | 4/1/0 | **INCONCLUSIVE** | -1.83 | [-3.52, -0.14] | 5/0/0 | **HELPED** | -0.71 | 1.35 | -4.78 | 1.39 | 490 |

Optimizer contrasts: predictive_v2x_vs_oracle_v2x: 1.19 % [-0.26, 2.64] 0/5/0 INCONCLUSIVE


Per-seed vehicle-hours: s201: baseline 3750.9, oracle_v2x 3757.5, persistence_v2x 3788.6, predictive_corrected_v2x 3770.7, predictive_v2x 3761.0, random_v2x 3769.9, reactive 3798.2; s202: baseline 3715.1, oracle_v2x 3653.1, persistence_v2x 3719.7, predictive_corrected_v2x 3715.5, predictive_v2x 3762.6, random_v2x 3732.8, reactive 3804.3; s203: baseline 3533.5, oracle_v2x 3518.3, persistence_v2x 3564.0, predictive_corrected_v2x 3557.3, predictive_v2x 3542.9, random_v2x 3584.4, reactive 3543.7; s204: baseline 3639.2, oracle_v2x 3584.4, persistence_v2x 3601.6, predictive_corrected_v2x 3599.9, predictive_v2x 3601.8, random_v2x 3621.8, reactive 3620.7; s205: baseline 3715.3, oracle_v2x 3647.2, persistence_v2x 3698.2, predictive_corrected_v2x 3688.7, predictive_v2x 3708.4, random_v2x 3720.8, reactive 3737.1

First reroute applied per arm (lead time of predictive vs reactive advice): s201: oracle_v2x first reroute 1500 s, persistence_v2x first reroute 1500 s, predictive_corrected_v2x first reroute 1500 s, predictive_v2x first reroute 1500 s, random_v2x first reroute 1500 s; s202: oracle_v2x first reroute 1500 s, persistence_v2x first reroute 1500 s, predictive_corrected_v2x first reroute 1500 s, predictive_v2x first reroute 1500 s, random_v2x first reroute 1500 s; s203: oracle_v2x first reroute 1500 s, persistence_v2x first reroute 1800 s, predictive_corrected_v2x first reroute 1500 s, predictive_v2x first reroute 1500 s, random_v2x first reroute 1500 s; s204: oracle_v2x first reroute 1500 s, persistence_v2x first reroute 1500 s, predictive_corrected_v2x first reroute 1500 s, predictive_v2x first reroute 1500 s, random_v2x first reroute 1500 s; s205: oracle_v2x first reroute 1500 s, persistence_v2x first reroute 1500 s, predictive_corrected_v2x first reroute 1500 s, predictive_v2x first reroute 1500 s, random_v2x first reroute 1500 s

## Scenario B (unexpected incident — lane-speed cap on the busiest DIRECT edge at 1500 s) — development seeds — `scenarioB_oracle_gate_dev.json`

Stress level 8.0× (VALID_TRAFFIC_STRESS_CASE), OD rule arterial. **ORACLE_HEADROOM: PASSED** — oracle_v2x must beat reactive on total vehicle-hours with a paired 95 % CI that excludes zero (paired() label HELPED).

oracle vs reactive: {'pair': 'oracle_v2x vs reactive', 'metric': 'total_vehicle_hours_incl_never_inserted', 'seeds': 3, 'per_seed_pct': [-2.222, -2.043, -1.651], 'mean_pct': -1.97, 'median_pct': -2.04, 'ci95': [-2.7, -1.25], 'wins': 3, 'losses': 0, 'ties': 0, 'label': 'HELPED', 'lower_is_better': True}

oracle vs baseline: {'pair': 'oracle_v2x vs baseline', 'metric': 'total_vehicle_hours_incl_never_inserted', 'seeds': 3, 'per_seed_pct': [-3.293, -2.92, -2.239], 'mean_pct': -2.82, 'median_pct': -2.92, 'ci95': [-4.15, -1.49], 'wins': 3, 'losses': 0, 'ties': 0, 'label': 'HELPED', 'lower_is_better': True}

reactive vs baseline: {'pair': 'reactive vs baseline', 'metric': 'total_vehicle_hours_incl_never_inserted', 'seeds': 3, 'per_seed_pct': [-1.095, -0.894, -0.598], 'mean_pct': -0.86, 'median_pct': -0.89, 'ci95': [-1.48, -0.24], 'wins': 3, 'losses': 0, 'ties': 0, 'label': 'HELPED', 'lower_is_better': True}

### stage `learned` — `results/v2x/closed_loop/la_c4_central_wide_prepeak_ideal_p30_cfgea08dddedc14_stressB_inc_fork1200_x8_arterial`

Seeds [101, 102, 103] · fork 1200 s · state hashes {'101': '2fd1429b853d', '102': '7bd99da19931', '103': 'aac1f872f66c'} · identical across arms: **True** · reroutes by arm {'baseline': 0, 'reactive': 0, 'oracle_v2x': 505, 'persistence_v2x': 148, 'predictive_v2x': 149, 'predictive_corrected_v2x': 198, 'random_v2x': 555}

| arm | vs baseline: mean % | 95 % CI | W/L/T | label | vs reactive: mean % | 95 % CI | W/L/T | label | p95 % | waiting % | queue % | arrived % | teleports (sum) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| no advice | — | — | — | — | — | — | — | — | — | — | — | — | 115 |
| reactive (current travel times) | -0.86 | [-1.48, -0.24] | 3/0/0 | **HELPED** | — | — | —/—/— | **—** | -0.7 | 1.67 | -1.87 | 0.77 | 103 |
| ORACLE future state + V2X (upper bound) | -2.82 | [-4.15, -1.49] | 3/0/0 | **HELPED** | -1.97 | [-2.7, -1.25] | 3/0/0 | **HELPED** | -0.13 | 3.79 | -8.61 | 3.0 | 81 |
| persistence + V2X | 0.16 | [-1.58, 1.89] | 1/2/0 | **INCONCLUSIVE** | 1.03 | [-0.41, 2.46] | 0/3/0 | **INCONCLUSIVE** | -0.11 | -2.03 | 0.85 | -0.59 | 109 |
| Graph WaveNet + V2X | -0.08 | [-2.73, 2.58] | 1/2/0 | **INCONCLUSIVE** | 0.79 | [-1.65, 3.24] | 1/2/0 | **INCONCLUSIVE** | 0.57 | -0.3 | -0.22 | -0.05 | 97 |
| Graph WaveNet + online correction + V2X | -0.93 | [-4.2, 2.33] | 2/1/0 | **INCONCLUSIVE** | -0.07 | [-2.82, 2.67] | 1/2/0 | **INCONCLUSIVE** | 0.34 | 0.91 | -2.95 | 0.77 | 77 |
| shuffled forecast (negative control) | -1.25 | [-4.79, 2.28] | 2/1/0 | **INCONCLUSIVE** | -0.39 | [-3.69, 2.9] | 1/2/0 | **INCONCLUSIVE** | 0.6 | 2.4 | -4.52 | 1.44 | 78 |

Optimizer contrasts: predictive_v2x_vs_oracle_v2x: 2.82 % [0.48, 5.16] 0/3/0 HURT


Per-seed vehicle-hours: s101: baseline 2095.0, reactive 2072.1, oracle_v2x 2026.0, persistence_v2x 2097.5, predictive_v2x 2097.1, predictive_corrected_v2x 2044.2, random_v2x 2072.5; s102: baseline 2147.2, reactive 2128.0, oracle_v2x 2084.5, persistence_v2x 2135.9, predictive_v2x 2120.9, predictive_corrected_v2x 2138.0, random_v2x 2088.0; s103: baseline 2082.1, reactive 2069.6, oracle_v2x 2035.4, persistence_v2x 2100.2, predictive_v2x 2100.6, predictive_corrected_v2x 2083.1, random_v2x 2083.6

Incident detection (statistical detector, status messages, 30 % penetration): s101 predictive_corrected_v2x: detected 44.0 s after onset by 6 vehicles; first reroute applied at 1500 s; s101 predictive_v2x: detected 44.0 s after onset by 8 vehicles; first reroute applied at 1500 s; s102 predictive_corrected_v2x: detected 47.0 s after onset by 14 vehicles; first reroute applied at 1500 s; s102 predictive_v2x: detected 47.0 s after onset by 11 vehicles; first reroute applied at 1500 s; s103 predictive_corrected_v2x: detected 46.0 s after onset by 3 vehicles; first reroute applied at 1500 s; s103 predictive_v2x: detected 46.0 s after onset by 5 vehicles; first reroute applied at 1500 s

First reroute applied per arm (lead time of predictive vs reactive advice): s101: oracle_v2x first reroute 1500 s, persistence_v2x first reroute 1500 s, predictive_v2x first reroute 1500 s, predictive_corrected_v2x first reroute 1500 s, random_v2x first reroute 1500 s; s102: oracle_v2x first reroute 1500 s, persistence_v2x first reroute 1500 s, predictive_v2x first reroute 1500 s, predictive_corrected_v2x first reroute 1500 s, random_v2x first reroute 1500 s; s103: oracle_v2x first reroute 1500 s, persistence_v2x first reroute 1500 s, predictive_v2x first reroute 1500 s, predictive_corrected_v2x first reroute 1500 s, random_v2x first reroute 1500 s

### stage `oracle` — `results/v2x/closed_loop/la_c4_central_wide_prepeak_ideal_p30_cfgea08dddedc14_stressB_inc_fork1200_x8_arterial`

Seeds [101, 102, 103] · fork 1200 s · state hashes {'101': '2fd1429b853d', '102': '7bd99da19931', '103': 'aac1f872f66c'} · identical across arms: **True** · reroutes by arm {'baseline': 0, 'reactive': 0, 'oracle_v2x': 505, 'persistence_v2x': 148, 'predictive_v2x': 149, 'predictive_corrected_v2x': 198, 'random_v2x': 555}

| arm | vs baseline: mean % | 95 % CI | W/L/T | label | vs reactive: mean % | 95 % CI | W/L/T | label | p95 % | waiting % | queue % | arrived % | teleports (sum) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| no advice | — | — | — | — | — | — | — | — | — | — | — | — | 115 |
| reactive (current travel times) | -0.86 | [-1.48, -0.24] | 3/0/0 | **HELPED** | — | — | —/—/— | **—** | -0.7 | 1.67 | -1.87 | 0.77 | 103 |
| ORACLE future state + V2X (upper bound) | -2.82 | [-4.15, -1.49] | 3/0/0 | **HELPED** | -1.97 | [-2.7, -1.25] | 3/0/0 | **HELPED** | -0.13 | 3.79 | -8.61 | 3.0 | 81 |
| persistence + V2X | 0.16 | [-1.58, 1.89] | 1/2/0 | **INCONCLUSIVE** | 1.03 | [-0.41, 2.46] | 0/3/0 | **INCONCLUSIVE** | -0.11 | -2.03 | 0.85 | -0.59 | 109 |
| Graph WaveNet + V2X | -0.08 | [-2.73, 2.58] | 1/2/0 | **INCONCLUSIVE** | 0.79 | [-1.65, 3.24] | 1/2/0 | **INCONCLUSIVE** | 0.57 | -0.3 | -0.22 | -0.05 | 97 |
| Graph WaveNet + online correction + V2X | -0.93 | [-4.2, 2.33] | 2/1/0 | **INCONCLUSIVE** | -0.07 | [-2.82, 2.67] | 1/2/0 | **INCONCLUSIVE** | 0.34 | 0.91 | -2.95 | 0.77 | 77 |
| shuffled forecast (negative control) | -1.25 | [-4.79, 2.28] | 2/1/0 | **INCONCLUSIVE** | -0.39 | [-3.69, 2.9] | 1/2/0 | **INCONCLUSIVE** | 0.6 | 2.4 | -4.52 | 1.44 | 78 |

Optimizer contrasts: predictive_v2x_vs_oracle_v2x: 2.82 % [0.48, 5.16] 0/3/0 HURT


Per-seed vehicle-hours: s101: baseline 2095.0, reactive 2072.1, oracle_v2x 2026.0, persistence_v2x 2097.5, predictive_v2x 2097.1, predictive_corrected_v2x 2044.2, random_v2x 2072.5; s102: baseline 2147.2, reactive 2128.0, oracle_v2x 2084.5, persistence_v2x 2135.9, predictive_v2x 2120.9, predictive_corrected_v2x 2138.0, random_v2x 2088.0; s103: baseline 2082.1, reactive 2069.6, oracle_v2x 2035.4, persistence_v2x 2100.2, predictive_v2x 2100.6, predictive_corrected_v2x 2083.1, random_v2x 2083.6

Incident detection (statistical detector, status messages, 30 % penetration): s101 predictive_corrected_v2x: detected 44.0 s after onset by 6 vehicles; first reroute applied at 1500 s; s101 predictive_v2x: detected 44.0 s after onset by 8 vehicles; first reroute applied at 1500 s; s102 predictive_corrected_v2x: detected 47.0 s after onset by 14 vehicles; first reroute applied at 1500 s; s102 predictive_v2x: detected 47.0 s after onset by 11 vehicles; first reroute applied at 1500 s; s103 predictive_corrected_v2x: detected 46.0 s after onset by 3 vehicles; first reroute applied at 1500 s; s103 predictive_v2x: detected 46.0 s after onset by 5 vehicles; first reroute applied at 1500 s

First reroute applied per arm (lead time of predictive vs reactive advice): s101: oracle_v2x first reroute 1500 s, persistence_v2x first reroute 1500 s, predictive_v2x first reroute 1500 s, predictive_corrected_v2x first reroute 1500 s, random_v2x first reroute 1500 s; s102: oracle_v2x first reroute 1500 s, persistence_v2x first reroute 1500 s, predictive_v2x first reroute 1500 s, predictive_corrected_v2x first reroute 1500 s, random_v2x first reroute 1500 s; s103: oracle_v2x first reroute 1500 s, persistence_v2x first reroute 1500 s, predictive_v2x first reroute 1500 s, predictive_corrected_v2x first reroute 1500 s, random_v2x first reroute 1500 s

## Scenario B (unexpected incident — lane-speed cap on the busiest DIRECT edge at 1500 s) — evaluation seeds — `scenarioB_oracle_gate_eval.json`

Stress level 8.0× (VALID_TRAFFIC_STRESS_CASE), OD rule arterial. **ORACLE_HEADROOM: FAILED** — oracle_v2x must beat reactive on total vehicle-hours with a paired 95 % CI that excludes zero (paired() label HELPED).

oracle vs reactive: {'pair': 'oracle_v2x vs reactive', 'metric': 'total_vehicle_hours_incl_never_inserted', 'seeds': 5, 'per_seed_pct': [0.441, -0.916, 0.629, -0.632, -4.784], 'mean_pct': -1.05, 'median_pct': -0.63, 'ci95': [-3.77, 1.67], 'wins': 3, 'losses': 2, 'ties': 0, 'label': 'INCONCLUSIVE', 'lower_is_better': True}

oracle vs baseline: {'pair': 'oracle_v2x vs baseline', 'metric': 'total_vehicle_hours_incl_never_inserted', 'seeds': 5, 'per_seed_pct': [-1.851, -1.721, -0.483, -1.818, -2.338], 'mean_pct': -1.64, 'median_pct': -1.82, 'ci95': [-2.5, -0.78], 'wins': 5, 'losses': 0, 'ties': 0, 'label': 'HELPED', 'lower_is_better': True}

reactive vs baseline: {'pair': 'reactive vs baseline', 'metric': 'total_vehicle_hours_incl_never_inserted', 'seeds': 5, 'per_seed_pct': [-2.282, -0.812, -1.105, -1.193, 2.569], 'mean_pct': -0.56, 'median_pct': -1.1, 'ci95': [-2.85, 1.72], 'wins': 4, 'losses': 1, 'ties': 0, 'label': 'INCONCLUSIVE', 'lower_is_better': True}

### stage `learned` — `results/v2x/closed_loop/la_c4_central_wide_prepeak_ideal_p30_cfgea08dddedc14_stressB_eval_inc_fork1200_x8_arterial`

Seeds [201, 202, 203, 204, 205] · fork 1200 s · state hashes {'201': '6390908e60d1', '202': '2e3428b57515', '203': '032bce52afd7', '204': '9691857c1b71', '205': '92b0f85bc7b6'} · identical across arms: **True** · reroutes by arm {'baseline': 0, 'reactive': 0, 'oracle_v2x': 871, 'persistence_v2x': 381, 'predictive_v2x': 362, 'predictive_corrected_v2x': 556, 'random_v2x': 926}

| arm | vs baseline: mean % | 95 % CI | W/L/T | label | vs reactive: mean % | 95 % CI | W/L/T | label | p95 % | waiting % | queue % | arrived % | teleports (sum) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| no advice | — | — | — | — | — | — | — | — | — | — | — | — | 199 |
| reactive (current travel times) | -0.56 | [-2.85, 1.72] | 4/1/0 | **INCONCLUSIVE** | — | — | —/—/— | **—** | 0.14 | 1.0 | -0.09 | 0.33 | 189 |
| ORACLE future state + V2X (upper bound) | -1.64 | [-2.5, -0.78] | 5/0/0 | **HELPED** | -1.05 | [-3.77, 1.67] | 3/2/0 | **INCONCLUSIVE** | -0.2 | 1.9 | -3.99 | 1.73 | 194 |
| persistence + V2X | -1.01 | [-2.18, 0.16] | 4/1/0 | **INCONCLUSIVE** | -0.43 | [-2.19, 1.33] | 4/1/0 | **INCONCLUSIVE** | -0.29 | 1.15 | -2.53 | 0.93 | 164 |
| Graph WaveNet + V2X | -0.16 | [-1.91, 1.58] | 2/3/0 | **INCONCLUSIVE** | 0.42 | [-2.1, 2.95] | 3/2/0 | **INCONCLUSIVE** | 0.54 | 1.59 | -0.41 | 0.51 | 172 |
| Graph WaveNet + online correction + V2X | -1.51 | [-2.71, -0.32] | 5/0/0 | **HELPED** | -0.93 | [-2.88, 1.02] | 4/1/0 | **INCONCLUSIVE** | -0.36 | 0.73 | -3.94 | 1.16 | 202 |
| shuffled forecast (negative control) | -0.45 | [-1.27, 0.37] | 4/1/0 | **INCONCLUSIVE** | 0.13 | [-1.5, 1.76] | 1/4/0 | **INCONCLUSIVE** | -0.37 | -0.33 | -1.05 | 0.27 | 215 |

Optimizer contrasts: predictive_v2x_vs_oracle_v2x: 1.51 % [-0.79, 3.81] 2/3/0 INCONCLUSIVE


Per-seed vehicle-hours: s201: baseline 2137.9, reactive 2089.1, oracle_v2x 2098.3, persistence_v2x 2126.3, predictive_v2x 2153.1, predictive_corrected_v2x 2116.1, random_v2x 2105.3; s202: baseline 2182.5, reactive 2164.7, oracle_v2x 2144.9, persistence_v2x 2152.4, predictive_v2x 2206.5, predictive_corrected_v2x 2143.8, random_v2x 2175.2; s203: baseline 2104.9, reactive 2081.6, oracle_v2x 2094.7, persistence_v2x 2074.5, predictive_v2x 2079.6, predictive_corrected_v2x 2074.9, random_v2x 2097.2; s204: baseline 2182.3, reactive 2156.3, oracle_v2x 2142.7, persistence_v2x 2137.6, predictive_v2x 2136.3, predictive_corrected_v2x 2117.7, random_v2x 2174.9; s205: baseline 2153.2, reactive 2208.5, oracle_v2x 2102.9, persistence_v2x 2161.2, predictive_v2x 2167.7, predictive_corrected_v2x 2144.8, random_v2x 2159.8

Incident detection (statistical detector, status messages, 30 % penetration): s201 predictive_corrected_v2x: detected 14.0 s after onset by 5 vehicles; first reroute applied at 1500 s; s201 predictive_v2x: detected 14.0 s after onset by 10 vehicles; first reroute applied at 1500 s; s202 predictive_corrected_v2x: detected 8.0 s after onset by 3 vehicles; first reroute applied at 1500 s; s202 predictive_v2x: detected 8.0 s after onset by 9 vehicles; first reroute applied at 1500 s; s203 predictive_corrected_v2x: detected 16.0 s after onset by 5 vehicles; first reroute applied at 1500 s; s203 predictive_v2x: detected 16.0 s after onset by 10 vehicles; first reroute applied at 1500 s; s204 predictive_corrected_v2x: detected 28.0 s after onset by 10 vehicles; first reroute applied at 1500 s; s204 predictive_v2x: detected 28.0 s after onset by 20 vehicles; first reroute applied at 1500 s; s205 predictive_corrected_v2x: detected 22.0 s after onset by 6 vehicles; first reroute applied at 1500 s; s205 predictive_v2x: detected 22.0 s after onset by 13 vehicles; first reroute applied at 1500 s

First reroute applied per arm (lead time of predictive vs reactive advice): s201: oracle_v2x first reroute 1500 s, persistence_v2x first reroute 1500 s, predictive_v2x first reroute 1500 s, predictive_corrected_v2x first reroute 1500 s, random_v2x first reroute 1500 s; s202: oracle_v2x first reroute 1500 s, persistence_v2x first reroute 1500 s, predictive_v2x first reroute 1500 s, predictive_corrected_v2x first reroute 1500 s, random_v2x first reroute 1500 s; s203: oracle_v2x first reroute 1500 s, persistence_v2x first reroute 1500 s, predictive_v2x first reroute 1500 s, predictive_corrected_v2x first reroute 1500 s, random_v2x first reroute 1500 s; s204: oracle_v2x first reroute 1500 s, persistence_v2x first reroute 1500 s, predictive_v2x first reroute 1500 s, predictive_corrected_v2x first reroute 1500 s, random_v2x first reroute 1500 s; s205: oracle_v2x first reroute 1500 s, persistence_v2x first reroute 1500 s, predictive_v2x first reroute 1500 s, predictive_corrected_v2x first reroute 1500 s, random_v2x first reroute 1500 s

## Final report (15 items)

1. **Selected stress regime**: la_c2_hollywood_101_5:uniform:arterial: 7.5× (STRESS_GATE_FAILED); la_c2_hollywood_101_5:uniform:any: 7.5× (STRESS_GATE_FAILED); la_c4_central_wide:uniform:arterial: 8.0× (VALID_TRAFFIC_STRESS_CASE); la_c4_central_wide:uniform:any: 10.0× (VALID_TRAFFIC_STRESS_CASE). Rule and per-level metrics above; demand is synthetic (scaled randomTrips), never called real.
2. **Scenario-quality gate**: la_c2_hollywood_101_5:uniform:arterial → STRESS_GATE_FAILED; la_c2_hollywood_101_5:uniform:any → STRESS_GATE_FAILED; la_c4_central_wide:uniform:arterial → VALID_TRAFFIC_STRESS_CASE; la_c4_central_wide:uniform:any → VALID_TRAFFIC_STRESS_CASE.
3. **Oracle headroom, Scenario A (forecastable peak), development seeds**: **PASSED** — oracle vs reactive -2.45 % [-3.91, -0.99] W/L/T 3/0/0 (HELPED); reactive vs baseline 1.57 % (HURT); oracle vs baseline -0.92 % (HELPED).
4. **Oracle headroom, Scenario B (unexpected incident), development seeds**: **PASSED** — oracle vs reactive -1.97 % [-2.7, -1.25] W/L/T 3/0/0 (HELPED); reactive vs baseline -0.86 % (HELPED); oracle vs baseline -2.82 % (HELPED).
5. **Learned information sources, Scenario A**: vs reactive — persistence_v2x: -1.69 % [-3.03, -0.35] HELPED; predictive_v2x: -1.34 % [-3.69, 1.02] INCONCLUSIVE; predictive_corrected_v2x: -1.54 % [-4.25, 1.17] INCONCLUSIVE; random_v2x: -1.52 % [-3.08, 0.03] INCONCLUSIVE; oracle_v2x: -2.45 % [-3.91, -0.99] HELPED Reading: reactive vs baseline is HURT; the shuffled control vs reactive is INCONCLUSIVE — a learned source only counts when it beats BOTH baseline and reactive and the shuffled control does not; no learned source beats the no-advice baseline (only the oracle does).
6. **Learned information sources, Scenario B**: vs reactive — persistence_v2x: 1.03 % [-0.41, 2.46] INCONCLUSIVE; predictive_v2x: 0.79 % [-1.65, 3.24] INCONCLUSIVE; predictive_corrected_v2x: -0.07 % [-2.82, 2.67] INCONCLUSIVE; random_v2x: -0.39 % [-3.69, 2.9] INCONCLUSIVE; oracle_v2x: -1.97 % [-2.7, -1.25] HELPED Reading: reactive vs baseline is HELPED; the shuffled control vs reactive is INCONCLUSIVE — a learned source only counts when it beats BOTH baseline and reactive and the shuffled control does not; no learned source beats the no-advice baseline (only the oracle does).
7. **Evaluation seeds (201-205)**: A **PASSED** — oracle vs reactive -1.83 % [-3.52, -0.14] W/L/T 5/0/0 (HELPED); reactive vs baseline 0.81 % (INCONCLUSIVE); oracle vs baseline -1.05 % (INCONCLUSIVE); B **FAILED** — oracle vs reactive -1.05 % [-3.77, 1.67] W/L/T 3/2/0 (INCONCLUSIVE); reactive vs baseline -0.56 % (INCONCLUSIVE); oracle vs baseline -1.64 % (HELPED). Run only after the development gate passed; never used to choose anything.
8. **Forecast lead time**: first reroute applied per arm is listed under each arm table above (predictive arms act on the forecast horizon, reactive on measured travel times).
9. **Shuffled-forecast control** (random_v2x): reported with the learned arms; it must not beat reactive, otherwise the pipeline rather than the forecast is doing the work.
10. **Low-load result kept as a negative result**: `results/v2x/ORACLE_FORK_REPORT.md` — at < 15 % edge utilisation no information source, the oracle included, beats reactive routing on either LA corridor.
11. **Controller status** is computed by `src/pipeline/v2x/controller_gate.py` from run files (`results/v2x/controller_status.json`), never set by hand.
12. **Detector-based calibration**: not possible — METR-LA is speed-only (`src/pipeline/v2x/METR_LA_FLOW_NOTE.md`).
13. **Not done, on purpose**: no new forecasting model, no retraining (OpenCity/Chronos stay pretrained), no Dhaka training, no frontend polish beyond the per-vehicle causal trace in the Control Room (`/api/experiment/v2x_closed_loop/vehicle_trace`).
14. **Three contributions, kept separate**: (A) ML/DL forecasting — Graph WaveNet 207-node METR-LA, verified against the published numbers; (B) Networking/V2X — simulated channel with latency/loss/TTL, penetration, message delivery, in-simulation closed loop; (C) Traffic control — does information change traffic outcomes? Answered by the oracle-first protocol above, with the negative results kept.
15. **Every number in this file is read from run files** by `src/pipeline/v2x/stress_report.py`; nothing was typed in, no result was edited, no parameter was tuned on a policy outcome.

## Low-load result (kept as a negative result)

The original randomTrips scenario (major-edge utilisation < 13 %) is reported in `results/v2x/ORACLE_FORK_REPORT.md`: no information source, including the oracle, beats reactive routing there; that finding stands and is not replaced by the stress scenario.
