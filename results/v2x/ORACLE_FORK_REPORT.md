# Oracle / identical-state fork phase — report

Generated 2026-09-08T10:45:35.823840+00:00 from run files (no number typed in).

## 1–2. Can genuine future information beat reactive routing? (development seeds, incident, identical fork)

### Incident response — `la_c4_central_wide_peak_ideal_p30_cfgea08dddedc14_eval_inc_fork480`

Seeds [201, 202, 203] · fork 480 s · state hashes {'201': 'ca834c1b8521', '202': 'a283e520239c', '203': '14d39c869860'} · identical across arms: **True** · reroutes by arm {'baseline': 0, 'reactive': 0, 'predictive_corrected_v2x': 78, 'oracle_v2x': 112}

| arm | vs baseline: mean % | 95 % CI | W/L/T | label | vs reactive: mean % | 95 % CI | W/L/T | label | p95 % | waiting % | queue % | arrived % | teleports (sum) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| no advice | — | — | — | — | — | — | — | — | — | — | — | — | 0 |
| reactive (current travel times) | -0.5 | [-2.42, 1.42] | 2/1/0 | **INCONCLUSIVE** | — | — | —/—/— | **—** | -0.6 | 1.4 | 2.42 | -0.48 | 0 |
| Graph WaveNet + online correction + V2X | -0.13 | [-0.89, 0.62] | 1/2/0 | **INCONCLUSIVE** | 0.38 | [-0.85, 1.6] | 1/2/0 | **INCONCLUSIVE** | -1.1 | 0.91 | 1.73 | -0.25 | 0 |
| ORACLE future state + V2X (upper bound) | -0.6 | [-1.26, 0.07] | 3/0/0 | **INCONCLUSIVE** | -0.09 | [-1.42, 1.24] | 2/1/0 | **INCONCLUSIVE** | -1.25 | -0.67 | -0.79 | -0.17 | 0 |

Per-seed vehicle-hours: s201: baseline 192.6, reactive 190.0, predictive_corrected_v2x 191.7, oracle_v2x 190.8; s202: baseline 189.2, reactive 188.7, predictive_corrected_v2x 189.3, oracle_v2x 188.4; s203: baseline 184.3, reactive 184.5, predictive_corrected_v2x 184.4, oracle_v2x 183.4

Incident detection (statistical detector, status messages, 30 % penetration): s201 predictive_corrected_v2x: detected 245.0 s after onset by 3 vehicles; first reroute applied at 600 s; s202 predictive_corrected_v2x: detected 395.0 s after onset by 3 vehicles; first reroute applied at 600 s; s203 predictive_corrected_v2x: detected 516.0 s after onset by 3 vehicles; first reroute applied at 900 s

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

Per-seed vehicle-hours: s101: baseline 182.2, reactive 180.5, persistence_v2x 181.6, predictive_v2x 181.6, oracle_v2x 181.1; s102: baseline 180.1, reactive 180.1, persistence_v2x 180.9, predictive_v2x 180.5, oracle_v2x 180.2; s103: baseline 175.1, reactive 174.9, persistence_v2x 175.4, predictive_v2x 175.4, oracle_v2x 175.6

## Network ablation (from departure, not forked; development seeds)

**latency**: ideal p=0.3: PDR 1.0, reroutes 54, veh-h -0.24 % [-1.16, 0.69] INCONCLUSIVE; lat100 p=0.3: PDR 1.0, reroutes 52, veh-h -0.06 % [-0.32, 0.21] INCONCLUSIVE; lat500 p=0.3: PDR 1.0, reroutes 52, veh-h -0.06 % [-0.32, 0.21] INCONCLUSIVE; lat1000 p=0.3: PDR 1.0, reroutes 53, veh-h -0.08 % [-0.28, 0.12] INCONCLUSIVE; lat5000 p=0.3: PDR 1.0, reroutes 49, veh-h 0.23 % [-0.81, 1.28] INCONCLUSIVE

**loss**: ideal p=0.3: PDR 1.0, reroutes 54, veh-h -0.24 % [-1.16, 0.69] INCONCLUSIVE; loss05 p=0.3: PDR 0.9762, reroutes 50, veh-h -0.06 % [-0.32, 0.21] INCONCLUSIVE; loss10 p=0.3: PDR 0.9178666666666667, reroutes 49, veh-h -0.15 % [-0.72, 0.42] INCONCLUSIVE; loss20 p=0.3: PDR 0.8456333333333333, reroutes 49, veh-h -0.14 % [-0.72, 0.43] INCONCLUSIVE; degraded p=0.3: PDR 0.7131333333333334, reroutes 43, veh-h -0.05 % [-0.18, 0.09] INCONCLUSIVE

**penetration**: ideal p=0.0: PDR None, reroutes 0, veh-h 0.0 % [0.0, 0.0] INCONCLUSIVE; ideal p=0.1: PDR 1.0, reroutes 20, veh-h 0.05 % [-0.49, 0.59] INCONCLUSIVE; ideal p=0.3: PDR 1.0, reroutes 54, veh-h -0.24 % [-1.16, 0.69] INCONCLUSIVE; ideal p=0.5: PDR 1.0, reroutes 108, veh-h -0.58 % [-1.87, 0.71] INCONCLUSIVE; ideal p=0.7: PDR 1.0, reroutes 134, veh-h -0.34 % [-0.76, 0.08] INCONCLUSIVE; ideal p=1.0: PDR 1.0, reroutes 195, veh-h -0.5 % [-2.12, 1.12] INCONCLUSIVE
