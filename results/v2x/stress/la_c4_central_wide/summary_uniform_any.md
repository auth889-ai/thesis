# Stress-scenario calibration — la_c4_central_wide · profile uniform · OD rule any · development seeds [101, 102, 103]

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
