# Stress-scenario calibration — la_c2_hollywood_101_5 · profile uniform · OD rule any · development seeds [101, 102, 103]

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
