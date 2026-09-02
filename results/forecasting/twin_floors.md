# Dhaka twin floors (DHAKA_SIMULATED_SENSOR_GRAPH)

dataset `data/forecasting/dhaka_twin` shape [288, 250, 5], split sha256 `86b7b5e336f307d2`, mask coverage 84.3%

| model | MAE@5 | RMSE@5 | MAE@15 | RMSE@15 | MAE@30 | RMSE@30 | MAE@60 | RMSE@60 |
|---|---|---|---|---|---|---|---|---|
| persistence | 0.719 | 1.160 | 0.724 | 1.241 | 0.653 | 1.201 | 0.647 | 1.248 |
| historical_average | 0.570 | 1.143 | 0.570 | 1.143 | 0.570 | 1.143 | 0.570 | 1.143 |

target = speed_ms (m/s), test region only, masked
