# Routing arms, horizon 7200 s, paired seeds

Source: `route/results/arms_h7200.json` (run_arms.py). Values are mean +/- sd over seeds.

| arm | n | total_vehicle_hours | mean_travel_time_all | mean_travel_time_s | p95_travel_time_s | total_waiting_s | mean_time_loss_s | arrived | unfinished | teleports | wall s/run |
|---|---|---|---|---|---|---|---|---|---|---|---|
| static | 3 | 995.6 +/- 140.9 | 597.3 +/- 84.5 | 526.0 +/- 29.2 | 1620.7 +/- 221.2 | 996317.3 +/- 191920.2 | 267.0 +/- 28.4 | 5843.3 +/- 167.4 | 156.7 +/- 167.4 | 151.0 +/- 120.9 | 32.4 |
| reactive | 3 | 1185.7 +/- 35.8 | 726.5 +/- 21.3 | 591.2 +/- 43.2 | 1960.7 +/- 307.1 | 1350573.0 +/- 243850.6 | 340.6 +/- 42.9 | 5530.0 +/- 16.8 | 345.3 +/- 6.8 | 374.3 +/- 35.3 | 100.8 |
| predictive_oracle | 3 | 882.1 +/- 128.4 | 531.2 +/- 80.2 | 513.5 +/- 65.6 | 1549.7 +/- 348.0 | 1018490.0 +/- 352866.8 | 259.8 +/- 66.9 | 5926.7 +/- 84.0 | 55.0 +/- 55.0 | 122.3 +/- 83.1 | 93.6 |
| predictive_persistence | 3 | 799.1 +/- 91.3 | 479.4 +/- 54.8 | 479.4 +/- 54.8 | 1342.7 +/- 303.7 | 821828.7 +/- 305020.7 | 226.3 +/- 56.6 | 6000.0 +/- 0.0 | 0.0 +/- 0.0 | 59.3 +/- 45.6 | 75.6 |
| due | 3 | 631.7 +/- 60.2 | 379.0 +/- 36.1 | 379.0 +/- 36.1 | 668.7 +/- 132.1 | 405794.7 +/- 170198.6 | 142.6 +/- 34.3 | 6000.0 +/- 0.0 | 0.0 +/- 0.0 | 31.7 +/- 29.1 | 550.9 |

DUE status per seed: {"due": {"11": "ok", "12": "ok", "13": "ok"}}

## Paired change vs `static` (mean % change over seeds [bootstrap 95 % CI], paired Wilcoxon p)

| arm | total_vehicle_hours | mean_travel_time_all | mean_travel_time_s | p95_travel_time_s | total_waiting_s | mean_time_loss_s | arrived | unfinished | teleports |
|---|---|---|---|---|---|---|---|---|---|
| reactive | 20.6 % [5.0, 37.8], p=0.25 | 23.2 % [7.4, 40.6], p=0.25 | 12.3 % [10.2, 14.3], p=0.25 | 20.9 % [15.0, 24.6], p=0.25 | 35.8 % [34.3, 38.0], p=0.25 | 27.4 % [24.3, 29.8], p=0.25 | -5.3 % [-7.7, -2.8], p=0.25 | 77.1 % [6.0, 148.2], p=0.25 | 918.5 % [50.0, 2600.0], p=0.25 |
| predictive_oracle | -9.0 % [-24.7, 21.8], p=0.50 | -8.6 % [-24.7, 22.9], p=0.50 | -1.8 % [-16.9, 16.6], p=0.75 | -1.3 % [-33.8, 35.4], p=0.75 | 8.8 % [-39.0, 70.2], p=1.00 | -0.6 % [-29.8, 36.7], p=1.00 | 1.5 % [-2.8, 4.9], p=0.75 | -91.7 % [-100.0, -83.5], p=0.50 | 434.6 % [-83.2, 1430.8], p=1.00 |
| predictive_persistence | -17.9 % [-30.7, 6.4], p=0.50 | -17.9 % [-30.7, 6.4], p=0.50 | -8.3 % [-23.5, 6.4], p=0.50 | -14.5 % [-46.1, 11.6], p=0.75 | -11.8 % [-56.1, 37.0], p=0.75 | -13.3 % [-42.0, 16.4], p=0.75 | 2.7 % [0.0, 5.9], p=0.50 | -100.0 % [-100.0, -100.0], p=0.50 | 167.6 % [-95.0, 669.2], p=0.50 |
| due | -35.0 % [-48.3, -17.1], p=0.25 | -35.0 % [-48.3, -17.1], p=0.25 | -27.7 % [-33.4, -17.1], p=0.25 | -57.9 % [-66.0, -43.3], p=0.25 | -57.2 % [-73.7, -29.3], p=0.25 | -45.9 % [-56.6, -27.1], p=0.25 | 2.7 % [0.0, 5.9], p=0.50 | -100.0 % [-100.0, -100.0], p=0.50 | 71.3 % [-95.4, 400.0], p=0.50 |

## Paired change vs `reactive` (mean % change over seeds [bootstrap 95 % CI], paired Wilcoxon p)

| arm | total_vehicle_hours | mean_travel_time_all | mean_travel_time_s | p95_travel_time_s | total_waiting_s | mean_time_loss_s | arrived | unfinished | teleports |
|---|---|---|---|---|---|---|---|---|---|
| static | -16.1 % [-27.4, -4.7], p=0.25 | -17.8 % [-28.9, -6.9], p=0.25 | -10.9 % [-12.5, -9.2], p=0.25 | -17.2 % [-19.7, -13.0], p=0.25 | -26.3 % [-27.5, -25.5], p=0.25 | -21.5 % [-23.0, -19.6], p=0.25 | 5.7 % [2.8, 8.4], p=0.25 | -55.1 % [-100.0, -5.7], p=0.25 | -60.3 % [-96.3, -33.3], p=0.25 |
| predictive_oracle | -25.4 % [-36.8, -11.6], p=0.25 | -26.7 % [-38.0, -12.6], p=0.25 | -12.4 % [-27.3, 5.8], p=0.50 | -18.2 % [-46.9, 10.1], p=0.50 | -20.3 % [-54.5, 23.4], p=0.50 | -21.6 % [-45.9, 10.0], p=0.50 | 7.2 % [5.4, 8.2], p=0.25 | -84.1 % [-100.0, -67.9], p=0.25 | -65.9 % [-91.8, -43.3], p=0.25 |
| predictive_persistence | -32.4 % [-41.9, -22.8], p=0.25 | -33.8 % [-43.0, -24.3], p=0.25 | -18.2 % [-33.1, -3.4], p=0.25 | -28.9 % [-56.7, -9.2], p=0.25 | -35.3 % [-67.3, -0.8], p=0.25 | -31.6 % [-55.3, -6.4], p=0.25 | 8.5 % [8.2, 8.9], p=0.25 | -100.0 % [-100.0, -100.0], p=0.25 | -83.4 % [-97.6, -71.5], p=0.25 |
| due | -46.7 % [-50.7, -39.9], p=0.25 | -47.8 % [-51.8, -41.1], p=0.25 | -35.5 % [-41.8, -24.8], p=0.25 | -65.2 % [-71.4, -53.9], p=0.25 | -68.6 % [-80.5, -48.8], p=0.25 | -57.3 % [-66.1, -41.3], p=0.25 | 8.5 % [8.2, 8.9], p=0.25 | -100.0 % [-100.0, -100.0], p=0.25 | -91.3 % [-96.9, -81.5], p=0.25 |

Footer: n = 3 paired seeds. The two-sided paired Wilcoxon signed-rank test cannot go below p = 0.25 with n = 3 (p = 0.25 at n = 3), so p-values here are coarse and can never reach 0.05; read the bootstrap CI (10k resamples of the seeds) and the sign consistency instead. Percent change on `teleports`/`unfinished` is undefined when the reference is 0 for a seed (that seed is dropped). total_vehicle_hours is the headline: it charges every inserted vehicle up to the horizon, so it is the only column that is commensurable when arms finish different numbers of trips.
