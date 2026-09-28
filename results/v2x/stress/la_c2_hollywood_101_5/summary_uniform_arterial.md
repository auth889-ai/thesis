# Stress-scenario calibration — la_c2_hollywood_101_5 · profile uniform · OD rule arterial · development seeds [101, 102, 103]

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
