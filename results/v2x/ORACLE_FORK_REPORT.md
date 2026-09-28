# Oracle / identical-state fork phase — report

Generated 2026-09-10T01:08:01.008048+00:00 from run files (no number typed in).

## 1–2. Can genuine future information beat reactive routing? (development seeds, incident, identical fork)

### Incident response — `la_c4_central_wide_peak_ideal_p30_cfgea08dddedc14_fullbudget_inc_fork480`

Seeds [101, 102, 103] · fork 480 s · state hashes {'101': 'bd20b216eaeb', '102': '12a122bf1d08', '103': '0f9a687dc09c'} · identical across arms: **True** · reroutes by arm {'baseline': 0, 'reactive': 0, 'oracle_full_v2x': 254, 'oracle_netfull_v2x': 234}

| arm | vs baseline: mean % | 95 % CI | W/L/T | label | vs reactive: mean % | 95 % CI | W/L/T | label | p95 % | waiting % | queue % | arrived % | teleports (sum) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| no advice | — | — | — | — | — | — | — | — | — | — | — | — | 0 |
| reactive (current travel times) | -0.65 | [-1.81, 0.5] | 3/0/0 | **INCONCLUSIVE** | — | — | —/—/— | **—** | -0.05 | 0.41 | 0.88 | -0.04 | 0 |
| oracle + production optimizer, budget lifted | -0.36 | [-1.26, 0.55] | 2/1/0 | **INCONCLUSIVE** | 0.3 | [-0.33, 0.93] | 0/3/0 | **INCONCLUSIVE** | 1.03 | -2.47 | -3.01 | 0.04 | 0 |
| oracle + NETWORK optimizer, budget lifted | -0.37 | [-1.94, 1.21] | 2/1/0 | **INCONCLUSIVE** | 0.29 | [-0.9, 1.47] | 1/2/0 | **INCONCLUSIVE** | 0.26 | -3.04 | -3.04 | -0.16 | 1 |

Per-seed vehicle-hours: s101: baseline 187.7, reactive 186.3, oracle_full_v2x 186.5, oracle_netfull_v2x 185.9; s102: baseline 185.9, reactive 184.0, oracle_full_v2x 185.0, oracle_netfull_v2x 185.2; s103: baseline 180.3, reactive 180.0, oracle_full_v2x 180.4, oracle_netfull_v2x 180.8

## 16. Evaluation seeds (unseen) — the gate

### Incident response, evaluation seeds — `la_c4_central_wide_peak_ideal_p30_cfgea08dddedc14_eval_inc_fork480`

Seeds [201, 202, 203] · fork 480 s · state hashes {'201': 'ca834c1b8521', '202': 'a283e520239c', '203': '14d39c869860'} · identical across arms: **True** · reroutes by arm {'baseline': 0, 'reactive': 0, 'predictive_corrected_v2x': 78, 'oracle_v2x': 112}

| arm | vs baseline: mean % | 95 % CI | W/L/T | label | vs reactive: mean % | 95 % CI | W/L/T | label | p95 % | waiting % | queue % | arrived % | teleports (sum) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| no advice | — | — | — | — | — | — | — | — | — | — | — | — | 0 |
| reactive (current travel times) | -0.5 | [-2.42, 1.42] | 2/1/0 | **INCONCLUSIVE** | — | — | —/—/— | **—** | -0.6 | 1.4 | 2.42 | -0.48 | 0 |
| Graph WaveNet + online correction + V2X | -0.13 | [-0.89, 0.62] | 1/2/0 | **INCONCLUSIVE** | 0.38 | [-0.85, 1.6] | 1/2/0 | **INCONCLUSIVE** | -1.1 | 0.91 | 1.73 | -0.25 | 0 |
| ORACLE future state + V2X (upper bound) | -0.6 | [-1.26, 0.07] | 3/0/0 | **INCONCLUSIVE** | -0.09 | [-1.42, 1.24] | 2/1/0 | **INCONCLUSIVE** | -1.25 | -0.67 | -0.79 | -0.17 | 0 |

Per-seed vehicle-hours: s201: baseline 192.6, reactive 190.0, predictive_corrected_v2x 191.7, oracle_v2x 190.8; s202: baseline 189.2, reactive 188.7, predictive_corrected_v2x 189.3, oracle_v2x 188.4; s203: baseline 184.3, reactive 184.5, predictive_corrected_v2x 184.4, oracle_v2x 183.4

Incident detection (statistical detector, status messages, 30 % penetration): s201 predictive_corrected_v2x: detected 245.0 s after onset by 3 vehicles; first reroute applied at 600 s; s202 predictive_corrected_v2x: detected 395.0 s after onset by 3 vehicles; first reroute applied at 600 s; s203 predictive_corrected_v2x: detected 516.0 s after onset by 3 vehicles; first reroute applied at 900 s

**Controller status (computed by pipeline/v2x/controller_gate.py): `TRAFFIC_BENEFIT_NOT_ESTABLISHED`** — ESTABLISHED only if vehicle-hours vs baseline AND vs reactive are HELPED (95 % CI excludes zero) on evaluation seeds and teleports are not HURT

## 13. Forecastable congestion (pre-peak build-up, no incident)

### Pre-peak — `la_c4_central_wide_prepeak_ideal_p30_cfgea08dddedc14_fork300`

Seeds [101, 102, 103] · fork 300 s · state hashes {'101': '824cc121047c', '102': '63bad18676ab', '103': 'cf6dfe59c8ac'} · identical across arms: **True** · reroutes by arm {'baseline': 0, 'reactive': 0, 'persistence_v2x': 36, 'predictive_v2x': 36, 'oracle_v2x': 102}

| arm | vs baseline: mean % | 95 % CI | W/L/T | label | vs reactive: mean % | 95 % CI | W/L/T | label | p95 % | waiting % | queue % | arrived % | teleports (sum) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| no advice | — | — | — | — | — | — | — | — | — | — | — | — | 0 |
| reactive (current travel times) | -0.34 | [-1.57, 0.89] | 2/1/0 | **INCONCLUSIVE** | — | — | —/—/— | **—** | -0.12 | 0.13 | -0.14 | 0.08 | 0 |
| persistence + V2X | 0.12 | [-0.81, 1.05] | 1/2/0 | **INCONCLUSIVE** | 0.46 | [0.07, 0.85] | 0/3/0 | **HURT** | -0.2 | 1.52 | 1.1 | 0.08 | 0 |
| Graph WaveNet + V2X | 0.06 | [-0.7, 0.82] | 1/2/0 | **INCONCLUSIVE** | 0.4 | [-0.08, 0.87] | 0/3/0 | **INCONCLUSIVE** | -0.35 | 1.08 | 1.1 | -0.12 | 0 |
| ORACLE future state + V2X (upper bound) | -0.08 | [-1.24, 1.08] | 1/2/0 | **INCONCLUSIVE** | 0.26 | [-0.11, 0.63] | 0/3/0 | **INCONCLUSIVE** | 0.73 | -0.45 | -1.11 | 0.12 | 0 |

Optimizer contrasts: predictive_v2x_vs_oracle_v2x: 0.14 % [-0.35, 0.63] 1/2/0 INCONCLUSIVE


Per-seed vehicle-hours: s101: baseline 182.2, reactive 180.5, persistence_v2x 181.6, predictive_v2x 181.6, oracle_v2x 181.1; s102: baseline 180.1, reactive 180.1, persistence_v2x 180.9, predictive_v2x 180.5, oracle_v2x 180.2; s103: baseline 175.1, reactive 174.9, persistence_v2x 175.4, predictive_v2x 175.4, oracle_v2x 175.6

## 10. Corridor screening by route diversity (rule fixed before any outcome)

chosen = highest share_real_opportunity (≥3 distinct routes, overlap ≤ max_overlap, bottleneck-disjoint, spare capacity, detour ≤ 25 %) — computed on development demand before any outcome

| corridor | share real opportunity | ≥3 distinct | median best overlap | bottleneck disjoint | median detour % |
|---|---|---|---|---|---|
| la_c1_glendale_110_2 | **0.18** | 0.395 | 0.31 | 0.395 | 23.4 |
| la_c2_hollywood_101_5 | **0.325** | 0.532 | 0.2505 | 0.58 | 20.2 |
| la_c3_hollywood_hills | **0.077** | 0.168 | 0.4305 | 0.32 | 11.75 |
| la_c4_central_wide | **0.235** | 0.535 | 0.2395 | 0.55 | 27.6 |
| los_angeles_metr | **0.273** | 0.432 | 0.2615 | 0.608 | 16.6 |

Chosen: **la_c2_hollywood_101_5**

## 9. Oracle routing-capacity test — same oracle information, four routing layers

### `la_c4_central_wide_peak_ideal_p30_cfgea08dddedc14_captest_inc_fork480`

Seeds [101, 102, 103] · fork 480 s · state hashes {'101': 'bd20b216eaeb', '102': '12a122bf1d08', '103': '0f9a687dc09c'} · identical across arms: **True** · reroutes by arm {'baseline': 0, 'reactive': 0, 'oracle_v2x': 109, 'oracle_div_v2x': 105, 'oracle_cap_v2x': 105, 'oracle_net_v2x': 105}

| arm | vs baseline: mean % | 95 % CI | W/L/T | label | vs reactive: mean % | 95 % CI | W/L/T | label | p95 % | waiting % | queue % | arrived % | teleports (sum) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| no advice | — | — | — | — | — | — | — | — | — | — | — | — | 0 |
| reactive (current travel times) | -0.65 | [-1.81, 0.5] | 3/0/0 | **INCONCLUSIVE** | — | — | —/—/— | **—** | -0.05 | 0.41 | 0.88 | -0.04 | 0 |
| ORACLE future state + V2X (upper bound) | -0.43 | [-1.88, 1.01] | 2/1/0 | **INCONCLUSIVE** | 0.22 | [-0.39, 0.83] | 1/2/0 | **INCONCLUSIVE** | 0.12 | -1.79 | -1.37 | -0.2 | 0 |
| oracle + diverse candidates | -0.39 | [-2.47, 1.69] | 2/1/0 | **INCONCLUSIVE** | 0.26 | [-0.67, 1.19] | 1/2/0 | **INCONCLUSIVE** | 0.19 | -2.07 | -2.67 | 0.04 | 0 |
| oracle + background load & route capacity | -0.41 | [-1.96, 1.14] | 2/1/0 | **INCONCLUSIVE** | 0.24 | [-0.21, 0.7] | 0/3/0 | **INCONCLUSIVE** | 0.55 | -1.83 | -1.97 | 0.04 | 0 |
| oracle + NETWORK optimizer | -0.39 | [-2.47, 1.69] | 2/1/0 | **INCONCLUSIVE** | 0.26 | [-0.67, 1.19] | 1/2/0 | **INCONCLUSIVE** | 0.19 | -2.07 | -2.67 | 0.04 | 0 |

Optimizer contrasts: oracle_div_v2x_vs_oracle_v2x: 0.04 % [-0.86, 0.95] 1/2/0 INCONCLUSIVE; oracle_cap_v2x_vs_oracle_v2x: 0.02 % [-0.37, 0.41] 1/2/0 INCONCLUSIVE; oracle_net_v2x_vs_oracle_v2x: 0.04 % [-0.86, 0.95] 1/2/0 INCONCLUSIVE


Per-seed vehicle-hours: s101: baseline 187.7, reactive 186.3, oracle_v2x 186.2, oracle_div_v2x 186.6, oracle_cap_v2x 186.5, oracle_net_v2x 186.6; s102: baseline 185.9, reactive 184.0, oracle_v2x 184.6, oracle_div_v2x 183.9, oracle_cap_v2x 184.3, oracle_net_v2x 183.9; s103: baseline 180.3, reactive 180.0, oracle_v2x 180.7, oracle_div_v2x 181.2, oracle_cap_v2x 180.8, oracle_net_v2x 181.2

### Budget-lifted diagnostics (per-round reroute budget removed)

### `la_c4_central_wide_peak_ideal_p30_cfgea08dddedc14_fullbudget_inc_fork480`

Seeds [101, 102, 103] · fork 480 s · state hashes {'101': 'bd20b216eaeb', '102': '12a122bf1d08', '103': '0f9a687dc09c'} · identical across arms: **True** · reroutes by arm {'baseline': 0, 'reactive': 0, 'oracle_full_v2x': 254, 'oracle_netfull_v2x': 234}

| arm | vs baseline: mean % | 95 % CI | W/L/T | label | vs reactive: mean % | 95 % CI | W/L/T | label | p95 % | waiting % | queue % | arrived % | teleports (sum) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| no advice | — | — | — | — | — | — | — | — | — | — | — | — | 0 |
| reactive (current travel times) | -0.65 | [-1.81, 0.5] | 3/0/0 | **INCONCLUSIVE** | — | — | —/—/— | **—** | -0.05 | 0.41 | 0.88 | -0.04 | 0 |
| oracle + production optimizer, budget lifted | -0.36 | [-1.26, 0.55] | 2/1/0 | **INCONCLUSIVE** | 0.3 | [-0.33, 0.93] | 0/3/0 | **INCONCLUSIVE** | 1.03 | -2.47 | -3.01 | 0.04 | 0 |
| oracle + NETWORK optimizer, budget lifted | -0.37 | [-1.94, 1.21] | 2/1/0 | **INCONCLUSIVE** | 0.29 | [-0.9, 1.47] | 1/2/0 | **INCONCLUSIVE** | 0.26 | -3.04 | -3.04 | -0.16 | 1 |

Per-seed vehicle-hours: s101: baseline 187.7, reactive 186.3, oracle_full_v2x 186.5, oracle_netfull_v2x 185.9; s102: baseline 185.9, reactive 184.0, oracle_full_v2x 185.0, oracle_netfull_v2x 185.2; s103: baseline 180.3, reactive 180.0, oracle_full_v2x 180.4, oracle_netfull_v2x 180.8

## 11. CASE 2 — the high-diversity corridor chosen by the rule

### `la_c2_hollywood_101_5_peak_ideal_p30_cfgea08dddedc14_case2_inc_fork480`

Seeds [101, 102, 103] · fork 480 s · state hashes {'101': '41e769b4c523', '102': 'fe7916c4f390', '103': 'b378ecc6c0d5'} · identical across arms: **True** · reroutes by arm {'baseline': 0, 'reactive': 0, 'persistence_net_v2x': 81, 'predictive_v2x': 80, 'predictive_net_v2x': 77, 'oracle_v2x': 96, 'oracle_net_v2x': 87, 'random_net_v2x': 80}

| arm | vs baseline: mean % | 95 % CI | W/L/T | label | vs reactive: mean % | 95 % CI | W/L/T | label | p95 % | waiting % | queue % | arrived % | teleports (sum) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| no advice | — | — | — | — | — | — | — | — | — | — | — | — | 1 |
| reactive (current travel times) | -1.03 | [-2.62, 0.56] | 3/0/0 | **INCONCLUSIVE** | — | — | —/—/— | **—** | -1.05 | 2.97 | 3.24 | 0.35 | 1 |
| persistence + NETWORK optimizer | -0.02 | [-1.11, 1.07] | 2/1/0 | **INCONCLUSIVE** | 1.02 | [0.48, 1.57] | 0/3/0 | **HURT** | 0.06 | 1.73 | 2.71 | 0.04 | 4 |
| Graph WaveNet + V2X | -0.35 | [-1.06, 0.35] | 3/0/0 | **INCONCLUSIVE** | 0.69 | [-0.51, 1.88] | 0/3/0 | **INCONCLUSIVE** | -0.25 | 1.81 | 2.41 | 0.04 | 1 |
| Graph WaveNet + NETWORK optimizer | -0.07 | [-0.31, 0.18] | 3/0/0 | **INCONCLUSIVE** | 0.98 | [-0.48, 2.43] | 0/3/0 | **INCONCLUSIVE** | -0.11 | 1.84 | 2.81 | 0.08 | 4 |
| ORACLE future state + V2X (upper bound) | -0.46 | [-1.21, 0.28] | 3/0/0 | **INCONCLUSIVE** | 0.57 | [-0.28, 1.43] | 0/3/0 | **INCONCLUSIVE** | -0.76 | 0.04 | 0.06 | 0.16 | 1 |
| oracle + NETWORK optimizer | -0.54 | [-1.14, 0.07] | 3/0/0 | **INCONCLUSIVE** | 0.5 | [-0.66, 1.66] | 1/2/0 | **INCONCLUSIVE** | 0.29 | -0.62 | -0.59 | 0.16 | 1 |
| shuffled + NETWORK optimizer (control) | 0.23 | [-0.81, 1.26] | 1/2/0 | **INCONCLUSIVE** | 1.27 | [0.52, 2.03] | 0/3/0 | **HURT** | 0.04 | 2.66 | 3.45 | 0.23 | 4 |

Optimizer contrasts: predictive_v2x_vs_oracle_v2x: 0.11 % [-0.39, 0.61] 1/2/0 INCONCLUSIVE; predictive_net_v2x_vs_predictive_v2x: 0.29 % [-0.18, 0.76] 0/3/0 INCONCLUSIVE; oracle_net_v2x_vs_oracle_v2x: -0.07 % [-0.48, 0.33] 2/1/0 INCONCLUSIVE


Per-seed vehicle-hours: s101: baseline 149.0, reactive 147.2, persistence_net_v2x 148.9, predictive_v2x 148.7, predictive_net_v2x 149.0, oracle_v2x 148.2, oracle_net_v2x 148.3, random_net_v2x 148.9; s102: baseline 144.3, reactive 143.8, persistence_net_v2x 144.9, predictive_v2x 144.0, predictive_net_v2x 144.3, oracle_v2x 144.1, oracle_net_v2x 143.8, random_net_v2x 145.3; s103: baseline 149.0, reactive 146.7, persistence_net_v2x 148.4, predictive_v2x 148.0, predictive_net_v2x 148.7, oracle_v2x 147.9, oracle_net_v2x 147.8, random_net_v2x 149.1

Incident detection (statistical detector, status messages, 30 % penetration): s101 predictive_v2x: detected 524.0 s after onset by 3 vehicles; first reroute applied at 600 s; s102 predictive_v2x: detected 195.0 s after onset by 3 vehicles; first reroute applied at 600 s; s103 predictive_v2x: detected 689.0 s after onset by 3 vehicles; first reroute applied at 600 s

## Network ablation (from departure, not forked; development seeds)

**latency**: ideal p=0.3: PDR 1.0, reroutes 54, veh-h -0.24 % [-1.16, 0.69] INCONCLUSIVE; lat100 p=0.3: PDR 1.0, reroutes 52, veh-h -0.06 % [-0.32, 0.21] INCONCLUSIVE; lat500 p=0.3: PDR 1.0, reroutes 52, veh-h -0.06 % [-0.32, 0.21] INCONCLUSIVE; lat1000 p=0.3: PDR 1.0, reroutes 53, veh-h -0.08 % [-0.28, 0.12] INCONCLUSIVE; lat5000 p=0.3: PDR 1.0, reroutes 49, veh-h 0.23 % [-0.81, 1.28] INCONCLUSIVE

**loss**: ideal p=0.3: PDR 1.0, reroutes 54, veh-h -0.24 % [-1.16, 0.69] INCONCLUSIVE; loss05 p=0.3: PDR 0.9762, reroutes 50, veh-h -0.06 % [-0.32, 0.21] INCONCLUSIVE; loss10 p=0.3: PDR 0.9178666666666667, reroutes 49, veh-h -0.15 % [-0.72, 0.42] INCONCLUSIVE; loss20 p=0.3: PDR 0.8456333333333333, reroutes 49, veh-h -0.14 % [-0.72, 0.43] INCONCLUSIVE; degraded p=0.3: PDR 0.7131333333333334, reroutes 43, veh-h -0.05 % [-0.18, 0.09] INCONCLUSIVE

**penetration**: ideal p=0.0: PDR None, reroutes 0, veh-h 0.0 % [0.0, 0.0] INCONCLUSIVE; ideal p=0.1: PDR 1.0, reroutes 20, veh-h 0.05 % [-0.49, 0.59] INCONCLUSIVE; ideal p=0.3: PDR 1.0, reroutes 54, veh-h -0.24 % [-1.16, 0.69] INCONCLUSIVE; ideal p=0.5: PDR 1.0, reroutes 108, veh-h -0.58 % [-1.87, 0.71] INCONCLUSIVE; ideal p=0.7: PDR 1.0, reroutes 134, veh-h -0.34 % [-0.76, 0.08] INCONCLUSIVE; ideal p=1.0: PDR 1.0, reroutes 195, veh-h -0.5 % [-2.12, 1.12] INCONCLUSIVE

## Congested-traffic experiment

The calibrated stress scenario (demand multiplier sweep, scenario-quality gate, oracle-first protocol) is reported separately in `results/v2x/STRESS_REPORT.md`.
