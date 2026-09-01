# Dhaka twin floors (DHAKA_SIMULATED_SENSOR_GRAPH)

dataset `predict/data/dhaka_twin` shape [144, 250, 5], split sha256 `e7fa8b260329f2ad`, mask coverage 29.5%

| model | MAE@5 | RMSE@5 | MAE@15 | RMSE@15 | MAE@30 | RMSE@30 | MAE@60 | RMSE@60 |
|---|---|---|---|---|---|---|---|---|
| persistence | 0.844 | 1.370 | 0.872 | 1.530 | 0.771 | 1.430 | 0.757 | 1.303 |
| historical_average | 0.665 | 1.204 | 0.665 | 1.204 | 0.665 | 1.204 | 0.665 | 1.204 |

target = speed_ms (m/s), test region only, masked
