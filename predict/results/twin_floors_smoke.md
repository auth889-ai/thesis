# Dhaka twin floors (DHAKA_SIMULATED_SENSOR_GRAPH)

dataset `predict/data/dhaka_twin_smoke` shape [24, 250, 5], split sha256 `f2320c70f8147840`, mask coverage 36.4%

| model | MAE@5 | RMSE@5 | MAE@15 | RMSE@15 | MAE@30 | RMSE@30 | MAE@60 | RMSE@60 |
|---|---|---|---|---|---|---|---|---|
| persistence | 1.289 | 2.774 | 2.179 | 4.804 | n/a | n/a | n/a | n/a |
| historical_average | 3.631 | 6.501 | 3.631 | 6.501 | n/a | n/a | n/a | n/a |

target = speed_ms (m/s), test region only, masked
