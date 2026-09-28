# Stress-scenario calibration — la_c4_central_wide · profile uniform · OD rule arterial · development seeds [101, 102, 103]

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
