# Latency / loss injection - fraction of route advisories delivered before the decision point

* base latency: V2XBus <- MEASURED from official Eclipse MOSAIC 25.2 Barnim example (SNS ad-hoc ITS-G5 geocast), run 2026-08-29, logs/log-20260829-163311-Barnim  (n=504, mean 2.6 ms, p95 7.0 ms)
* time budget tth: sweep JSONs (15 points, 3917 rerouting vehicles): distance from position at first DENM reception to hazard rectangle / speed
  n=3917, p10 0.0 s, p50 50.1 s, p90 249.0 s; 554 vehicles (14%) were already inside the hazard rectangle at first reception (tth = 0: no advisory can arrive in time; counted as not delivered in the all-vehicle columns, excluded in the upstream-only columns)
* Monte Carlo: 20 draws per vehicle, seed 0; delivered = not lost AND (latency + added) < tth

| added latency ms | loss % | delivered (single DENM) | delivered (1 Hz DENM repeat) | upstream-only single | upstream-only repeat | eff. latency mean ms |
|---|---|---|---|---|---|---|
| 0 | 0 | 0.859 | 0.859 | 1.000 | 1.000 | 2.6 |
| 0 | 10 | 0.773 | 0.850 | 0.900 | 0.990 | 2.6 |
| 0 | 30 | 0.600 | 0.832 | 0.701 | 0.969 | 2.6 |
| 500 | 0 | 0.775 | 0.775 | 0.902 | 0.902 | 502.6 |
| 500 | 10 | 0.697 | 0.774 | 0.810 | 0.902 | 502.6 |
| 500 | 30 | 0.542 | 0.773 | 0.627 | 0.901 | 502.6 |
| 2000 | 0 | 0.770 | 0.770 | 0.896 | 0.896 | 2002.6 |
| 2000 | 10 | 0.693 | 0.769 | 0.807 | 0.896 | 2002.6 |
| 2000 | 30 | 0.537 | 0.768 | 0.627 | 0.895 | 2002.6 |
| 5000 | 0 | 0.764 | 0.764 | 0.889 | 0.889 | 5002.6 |
| 5000 | 10 | 0.688 | 0.763 | 0.800 | 0.889 | 5002.6 |
| 5000 | 30 | 0.532 | 0.763 | 0.622 | 0.889 | 5002.6 |

single DENM: one advisory per vehicle, lost with probability `loss`. 1 Hz repeat: the official WeatherWarningApp re-sends a DENM every second while in the hazard, so a vehicle with slack tth - latency gets one extra chance per second (P = 1 - loss^n).

Regenerate: `python network/latency_injection.py [--base sweep]`.
