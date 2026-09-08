# Incident scenario — INCIDENT — lane speed cut to 2 m/s on motorway edge 864049094 (METR-LA detector 761599) from 600 s, identical in every arm; peak moment; 30 % penetration; ideal network; development seeds 101-103

| pair | metric | mean % | 95 % CI | W/L/T | label |
|---|---|---|---|---|---|
| reactive vs baseline | total_vehicle_hours_incl_never_inserted | -0.67 | [-1.29, -0.05] | 3/0/0 | **HELPED** |
| reactive vs baseline | p95_travel_time_s | -1.93 | [-7.99, 4.12] | 2/1/0 | **INCONCLUSIVE** |
| reactive vs baseline | total_waiting_s | 0.75 | [-1.62, 3.11] | 0/3/0 | **INCONCLUSIVE** |
| reactive vs baseline | mean_queue_veh | 1.03 | [-0.74, 2.8] | 0/3/0 | **INCONCLUSIVE** |
| reactive vs baseline | arrived | -0.04 | [-1.54, 1.46] | 2/1/0 | **INCONCLUSIVE** |
| predictive_forecast_only vs baseline | total_vehicle_hours_incl_never_inserted | 0.07 | [-1.61, 1.75] | 1/2/0 | **INCONCLUSIVE** |
| predictive_forecast_only vs baseline | p95_travel_time_s | -0.69 | [-9.64, 8.26] | 1/2/0 | **INCONCLUSIVE** |
| predictive_forecast_only vs baseline | total_waiting_s | 0.99 | [-5.47, 7.45] | 1/2/0 | **INCONCLUSIVE** |
| predictive_forecast_only vs baseline | mean_queue_veh | 1.22 | [-4.88, 7.31] | 1/2/0 | **INCONCLUSIVE** |
| predictive_forecast_only vs baseline | arrived | -0.12 | [-1.74, 1.5] | 1/2/0 | **INCONCLUSIVE** |
| predictive_fused vs baseline | total_vehicle_hours_incl_never_inserted | 0.1 | [-1.27, 1.46] | 1/2/0 | **INCONCLUSIVE** |
| predictive_fused vs baseline | p95_travel_time_s | -0.21 | [-6.24, 5.83] | 1/2/0 | **INCONCLUSIVE** |
| predictive_fused vs baseline | total_waiting_s | -0.19 | [-4.47, 4.08] | 1/2/0 | **INCONCLUSIVE** |
| predictive_fused vs baseline | mean_queue_veh | 1.05 | [-3.15, 5.25] | 1/2/0 | **INCONCLUSIVE** |
| predictive_fused vs baseline | arrived | -0.62 | [-1.24, -0.01] | 0/3/0 | **HURT** |
| predictive_forecast_only vs reactive | total_vehicle_hours_incl_never_inserted | 0.74 | [-0.62, 2.1] | 0/3/0 | **INCONCLUSIVE** |
| predictive_forecast_only vs reactive | p95_travel_time_s | 1.26 | [-3.82, 6.34] | 1/2/0 | **INCONCLUSIVE** |
| predictive_forecast_only vs reactive | total_waiting_s | 0.27 | [-8.42, 8.95] | 1/2/0 | **INCONCLUSIVE** |
| predictive_forecast_only vs reactive | mean_queue_veh | 0.19 | [-5.87, 6.24] | 1/2/0 | **INCONCLUSIVE** |
| predictive_forecast_only vs reactive | arrived | -0.08 | [-1.53, 1.38] | 1/1/1 | **INCONCLUSIVE** |
| predictive_fused vs reactive | total_vehicle_hours_incl_never_inserted | 0.77 | [-0.15, 1.69] | 0/3/0 | **INCONCLUSIVE** |
| predictive_fused vs reactive | p95_travel_time_s | 1.77 | [-1.93, 5.47] | 0/3/0 | **INCONCLUSIVE** |
| predictive_fused vs reactive | total_waiting_s | -0.92 | [-7.43, 5.6] | 1/2/0 | **INCONCLUSIVE** |
| predictive_fused vs reactive | mean_queue_veh | 0.03 | [-4.58, 4.63] | 1/2/0 | **INCONCLUSIVE** |
| predictive_fused vs reactive | arrived | -0.58 | [-1.9, 0.74] | 0/3/0 | **INCONCLUSIVE** |

Reroutes applied over three seeds: forecast-only 51, fused 358, reactive uses SUMO's own rerouteTraveltime.

Per-seed vehicle-hours: {"101": {"baseline": 188.86, "reactive": 187.33, "predictive_fused": 187.97, "predictive_forecast_only": 187.55}, "102": {"baseline": 185.72, "reactive": 185.01, "predictive_fused": 186.87, "predictive_forecast_only": 186.81}, "103": {"baseline": 182.43, "reactive": 180.94, "predictive_fused": 182.68, "predictive_forecast_only": 183.0}}
