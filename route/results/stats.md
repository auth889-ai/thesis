# Routing arms, horizon 1800 s, paired seeds

Source: `route/results/arms_h1800.json` (run_arms.py). Values are mean +/- sd over seeds.

| arm | n | mean_travel_time_s | p95_travel_time_s | total_waiting_s | mean_time_loss_s | arrived | teleports | wall s/run |
|---|---|---|---|---|---|---|---|---|
| static | 3 | 476.8 +/- 16.2 | 1072.7 +/- 87.0 | 294957.0 +/- 32096.4 | 230.0 +/- 17.1 | 2248.0 +/- 21.4 | 47.3 +/- 5.5 | 11.3 |
| reactive | 3 | 443.9 +/- 10.3 | 963.3 +/- 43.4 | 220897.0 +/- 14892.0 | 199.7 +/- 9.6 | 2198.0 +/- 23.9 | 70.3 +/- 9.6 | 32.7 |
| predictive_oracle | 3 | 476.4 +/- 15.9 | 981.7 +/- 21.4 | 290088.7 +/- 13678.3 | 229.3 +/- 10.1 | 2381.0 +/- 29.3 | 54.3 +/- 18.0 | 29.6 |
| predictive_persistence | 3 | 480.6 +/- 15.3 | 1013.3 +/- 38.1 | 303727.7 +/- 31937.0 | 235.9 +/- 14.9 | 2281.7 +/- 23.5 | 62.0 +/- 18.1 | 30.8 |
| due | 3 | 484.6 +/- 12.3 | 992.7 +/- 68.6 | 295936.3 +/- 22639.9 | 235.7 +/- 10.9 | 2421.0 +/- 61.5 | 22.0 +/- 2.0 | 149.4 |

DUE status per seed: {"due": {"11": "ok", "12": "ok", "13": "ok"}}

## Paired change vs `static` (mean % change over seeds [bootstrap 95 % CI], paired Wilcoxon p)

| arm | mean_travel_time_s | p95_travel_time_s | total_waiting_s | mean_time_loss_s | arrived | teleports |
|---|---|---|---|---|---|---|
| reactive | -6.8 % [-11.8, -2.0], p=0.25 | -9.6 % [-20.9, 1.8], p=0.50 | -24.2 % [-37.5, -13.2], p=0.25 | -12.7 % [-22.9, -3.6], p=0.25 | -2.2 % [-4.1, -0.9], p=0.25 | 50.4 % [17.6, 75.6], p=0.25 |
| predictive_oracle | -0.1 % [-1.2, 1.2], p=0.75 | -8.2 % [-14.2, -2.8], p=0.25 | -1.2 % [-7.9, 4.1], p=1.00 | -0.2 % [-3.6, 3.2], p=0.75 | 5.9 % [5.1, 6.6], p=0.25 | 14.2 % [-9.8, 50.0], p=0.75 |
| predictive_persistence | 0.9 % [-1.5, 5.0], p=1.00 | -5.2 % [-9.1, 2.5], p=0.50 | 3.3 % [-4.4, 15.5], p=1.00 | 2.8 % [-2.3, 12.0], p=1.00 | 1.5 % [0.8, 1.9], p=0.25 | 32.8 % [-15.7, 58.0], p=0.50 |
| due | 1.8 % [-4.8, 6.6], p=0.75 | -6.7 % [-19.2, 8.5], p=0.50 | 1.5 % [-16.9, 17.3], p=1.00 | 3.1 % [-10.4, 12.2], p=0.75 | 7.7 % [5.3, 10.5], p=0.25 | -53.4 % [-56.0, -51.2], p=0.25 |

## Paired change vs `reactive` (mean % change over seeds [bootstrap 95 % CI], paired Wilcoxon p)

| arm | mean_travel_time_s | p95_travel_time_s | total_waiting_s | mean_time_loss_s | arrived | teleports |
|---|---|---|---|---|---|---|
| static | 7.5 % [2.1, 13.4], p=0.25 | 11.8 % [-1.8, 26.4], p=0.50 | 34.5 % [15.2, 59.9], p=0.25 | 15.5 % [3.8, 29.7], p=0.25 | 2.3 % [1.0, 4.3], p=0.25 | -31.6 % [-43.1, -15.0], p=0.25 |
| predictive_oracle | 7.4 % [3.3, 13.2], p=0.25 | 2.1 % [-4.6, 8.5], p=0.75 | 31.9 % [20.0, 47.3], p=0.25 | 15.1 % [7.1, 25.0], p=0.25 | 8.3 % [6.8, 11.1], p=0.25 | -23.4 % [-41.7, -5.1], p=0.25 |
| predictive_persistence | 8.3 % [5.4, 12.3], p=0.25 | 5.4 % [0.7, 14.8], p=0.25 | 38.0 % [22.6, 58.2], p=0.25 | 18.2 % [11.7, 26.7], p=0.25 | 3.8 % [2.5, 6.3], p=0.25 | -13.1 % [-28.3, 0.0], p=0.50 |
| due | 9.2 % [7.9, 10.8], p=0.25 | 3.0 % [0.3, 6.6], p=0.25 | 33.9 % [32.8, 35.2], p=0.25 | 18.0 % [16.2, 21.4], p=0.25 | 10.1 % [8.3, 12.3], p=0.25 | -68.1 % [-72.2, -60.0], p=0.25 |

Footer: n = 3 paired seeds. The two-sided paired Wilcoxon signed-rank test cannot go below p = 0.25 with n = 3 (p = 0.25 at n = 3), so p-values here are coarse and can never reach 0.05; read the bootstrap CI (10k resamples of the seeds) and the sign consistency instead. Percent change on `teleports` is undefined when the reference is 0 for a seed (that seed is dropped).
