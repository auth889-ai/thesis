# benchmarks/

Cross-lab fair comparisons built on `dhakaflow.evaluation.BenchmarkSpec`.
Each benchmark declares scenarios, seeds, warmup, duration, metrics and safety
constraints once; every arm runs under exactly those conditions
(`assert_fair` enforces it). Planned: forecasting leaderboard (Labs 07-12),
signal-control benchmark (Labs 14-20), routing benchmark (Lab 22).
Empty until Lab 07.
