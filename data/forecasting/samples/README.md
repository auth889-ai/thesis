# Sample uploads for the Prediction page

| file | shape | what it shows |
|---|---|---|
| `los_angeles_20_sensors_14_days.csv` | wide, 20 sensors × 4,032 five-minute steps (km/h) | 14 days of METR-LA loop detectors: enough to TRAIN STID here (≈70 s on CPU, 30 epochs) and beat the "no change" floor at every horizon |
| `los_angeles_20_sensors_coords.csv` | `road, lat, lon` for the 20 sensors | upload it as the optional coordinates file: the road graph becomes the distance kernel, and Mission Control can place the sensors on the map and use the trained models along a route |
| `small_town_long_format_15min.csv` | long `time, road, speed`, 4 roads × 100 steps | the long layout and a 15-minute clock; Chronos-Bolt and persistence only (too short to train) |

Upload either on **Prediction → Your city, your data**. Values are speeds in km/h.
