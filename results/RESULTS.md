# RESULTS — DhakaFlow rebuild

Generated 2026-09-01T10:38 @ `38651f9` by `python results/build_results.py`.

Every table below is read from a file written by the pipeline named next to it. Nothing here is typed by hand.


## Prediction — twin floors (persistence / historical average)

`make data && python predict/baselines_twin.py` → `predict/results/twin_floors.md`

# Dhaka twin floors (DHAKA_SIMULATED_SENSOR_GRAPH)

dataset `predict/data/dhaka_twin` shape [144, 250, 5], split sha256 `e7fa8b260329f2ad`, mask coverage 29.5%

| model | MAE@5 | RMSE@5 | MAE@15 | RMSE@15 | MAE@30 | RMSE@30 | MAE@60 | RMSE@60 |
|---|---|---|---|---|---|---|---|---|
| persistence | 0.844 | 1.370 | 0.872 | 1.530 | 0.771 | 1.430 | 0.757 | 1.303 |
| historical_average | 0.665 | 1.204 | 0.665 | 1.204 | 0.665 | 1.204 | 0.665 | 1.204 |

target = speed_ms (m/s), test region only, masked


## Prediction — BasicTS benchmark (METR-LA / PEMS-BAY / PEMS08)

`notebooks/Predict_BasicTS_Colab.ipynb (Colab Pro) -> predict/results/benchmark.csv` → `predict/results/benchmark.md`

_NOT YET PRODUCED_


## Routing — arms × paired seeds on Dhaka R1

`make route` → `route/results/stats.md`

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


## Networking — V2X penetration sweep (Eclipse MOSAIC)

`make network` → `network/results/penetration.md`

# V2X penetration sweep - Eclipse MOSAIC 25.2, Dhaka R1 (registered scenario)

Knob: `mapping_config.json` -> `typeDistributions.DEFAULT_VEHTYPE` = [{AdHoc: WeatherWarningApp+SlowDownApp, weight p}, {Unequipped: SlowDownApp, weight 1-p}], `config.fixedOrder=false` (stochastic, seed-driven). Hazard: TRACTION_HAZARD/ICE rectangle at Karwan Bazar (environment_config.json); equipped vehicles that sense it broadcast DENMs over SNS ad-hoc (ITS-G5, multi-hop TTL 20); receivers with the hazard on their route reroute through the official NavigationModule.

Definitions: equipped = registered with WeatherWarningApp; delivery_ratio_veh = distinct receivers / equipped; latency = t_rx - t_tx per MessageId; route switches = CentralNavigationComponent 'Change to route' lines; travel time = SUMO tripinfo of finished trips (equipped vs unequipped split).

## Per point

| p | seed | wall s | registered | equipped | DENM sent | senders | receptions | receivers | deliv. ratio | lat mean ms | lat p95 ms | route switches | veh switched | trips fin. | TT mean s | TT p95 s | timeLoss mean s | TT eq. s | TT uneq. s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.0 | 11 | 16 | 2147 | 0 | 0 | 0 | 0 | 0 |  |  |  | 0 | 0 | 543 | 332.0 | 484.9 | 119.6 |  | 332.0 |
| 0.1 | 11 | 17 | 2157 | 218 | 3702 | 31 | 428339 | 211 | 0.968 | 30.0 | 57.44 | 68 | 68 | 569 | 335.3 | 481.2 | 119.2 | 341.1 | 334.7 |
| 0.25 | 11 | 35 | 2127 | 520 | 11165 | 89 | 3033412 | 499 | 0.96 | 30.01 | 57.44 | 171 | 171 | 552 | 332.3 | 478.0 | 120.8 | 326.1 | 334.2 |
| 0.5 | 11 | 103 | 2153 | 1083 | 22563 | 184 | 12880209 | 1057 | 0.976 | 30.0 | 57.45 | 375 | 375 | 578 | 341.6 | 492.9 | 124.3 | 342.0 | 341.3 |

## Mean over seeds

| p | n seeds | equipped frac | receivers | deliv. ratio | lat mean ms | lat p95 ms | route switches | TT mean s | TT p95 s | timeLoss mean s |
|---|---|---|---|---|---|---|---|---|---|---|
| 0.0 | 1 | 0.0 | 0.0 | - | - | - | 0.0 | 332.0 | 484.9 | 119.6 |
| 0.1 | 1 | 0.101 | 211.0 | 0.968 | 30.0 | 57.44 | 68.0 | 335.3 | 481.2 | 119.2 |
| 0.25 | 1 | 0.244 | 499.0 | 0.96 | 30.01 | 57.44 | 171.0 | 332.3 | 478.0 | 120.8 |
| 0.5 | 1 | 0.503 | 1057.0 | 0.976 | 30.0 | 57.45 | 375.0 | 341.6 | 492.9 | 124.3 |

Source JSONs: `network/results/penetration_p{P}_s{SEED}.json`; regenerate with `python network/penetration_sweep.py --aggregate`.


## Networking — latency / loss vs advisory delivery

`python network/latency_injection.py` → `network/results/latency.md`

# Latency / loss injection - fraction of route advisories delivered before the decision point

* base latency: V2XBus <- MEASURED from official Eclipse MOSAIC 25.2 Barnim example (SNS ad-hoc ITS-G5 geocast), run 2026-08-29, logs/log-20260829-163311-Barnim  (n=504, mean 2.6 ms, p95 7.0 ms)
* time budget tth: sweep JSONs (4 points, 614 rerouting vehicles): distance from position at first DENM reception to hazard rectangle / speed
  n=614, p10 0.0 s, p50 55.1 s, p90 257.3 s; 72 vehicles (12%) were already inside the hazard rectangle at first reception (tth = 0: no advisory can arrive in time; counted as not delivered in the all-vehicle columns, excluded in the upstream-only columns)
* Monte Carlo: 20 draws per vehicle, seed 0; delivered = not lost AND (latency + added) < tth

| added latency ms | loss % | delivered (single DENM) | delivered (1 Hz DENM repeat) | upstream-only single | upstream-only repeat | eff. latency mean ms |
|---|---|---|---|---|---|---|
| 0 | 0 | 0.883 | 0.883 | 1.000 | 1.000 | 2.6 |
| 0 | 10 | 0.788 | 0.875 | 0.899 | 0.991 | 2.6 |
| 0 | 30 | 0.612 | 0.859 | 0.702 | 0.973 | 2.6 |
| 500 | 0 | 0.809 | 0.809 | 0.917 | 0.917 | 502.6 |
| 500 | 10 | 0.727 | 0.809 | 0.821 | 0.916 | 502.6 |
| 500 | 30 | 0.569 | 0.807 | 0.639 | 0.915 | 502.6 |
| 2000 | 0 | 0.803 | 0.803 | 0.910 | 0.910 | 2002.6 |
| 2000 | 10 | 0.720 | 0.802 | 0.818 | 0.909 | 2002.6 |
| 2000 | 30 | 0.559 | 0.801 | 0.633 | 0.908 | 2002.6 |
| 5000 | 0 | 0.795 | 0.795 | 0.900 | 0.900 | 5002.6 |
| 5000 | 10 | 0.713 | 0.795 | 0.812 | 0.900 | 5002.6 |
| 5000 | 30 | 0.554 | 0.795 | 0.636 | 0.900 | 5002.6 |

single DENM: one advisory per vehicle, lost with probability `loss`. 1 Hz repeat: the official WeatherWarningApp re-sends a DENM every second while in the hazard, so a vehicle with slack tth - latency gets one extra chance per second (P = 1 - loss^n).

Regenerate: `python network/latency_injection.py [--base sweep]`.


## NLP — incident-text classifier

`make nlp` → `nlp/results/classifier.md`

# Traffic-text classifier — {incident, congestion, irrelevant}

Data: `nlp/data/MANIFEST.json` (source: REAL; test n = 10226, frozen held-out).

| model | CV acc (5-fold) | CV macro-F1 | **test acc** | **test macro-F1** | F1 incident | F1 congestion | F1 irrelevant | Dhaka-seed acc / mF1 (n=150) | train s |
|---|---|---|---|---|---|---|---|---|---|
| tfidf_lr | 0.9758 ± 0.0014 | 0.9697 ± 0.0017 | **0.9764** | **0.9705** | 0.9738 | 0.9516 | 0.9860 | 0.633 / 0.608 | 50.8 |
| tfidf_lr_dhaka_aug | 0.9747 ± 0.0010 | 0.9683 ± 0.0015 | **0.9768** | **0.9712** | 0.9744 | 0.9534 | 0.9858 | 0.873 / 0.873 | 58.1 |
| distilbert | – | – | **0.8224** | **0.5896** | 0.7977 | 0.0000 | 0.9711 | 0.540 / 0.434 | 17.6 |

Confusion matrix (tfidf_lr, test; rows = true, cols = pred; order ['incident', 'congestion', 'irrelevant']):

```
   incident   3404     45     40
 congestion     53   1534     30
 irrelevant     45     28   5047
```

Confusion matrix (tfidf_lr_dhaka_aug, test; rows = true, cols = pred; order ['incident', 'congestion', 'irrelevant']):

```
   incident   3409     39     41
 congestion     53   1535     29
 irrelevant     46     29   5045
```

Confusion matrix (distilbert, test; rows = true, cols = pred; order ['incident', 'congestion', 'irrelevant']):

```
   incident   3384      0    105
 congestion   1517      0    100
 irrelevant     94      0   5026
```

Dhaka-seed column: `tfidf_lr`/`distilbert` = zero-shot (seed never trained on); `tfidf_lr_dhaka_aug` = 5-fold over the seed with the real corpus + 4/5 seed in training.

Regenerate: `python nlp/get_data.py && python nlp/train_classifier.py --augment-seed` (`--model distilbert` for the transformer row).
