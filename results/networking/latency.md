# Latency / loss injection - fraction of route advisories delivered before the decision point

* base latency: V2XBus <- SIMULATED by official Eclipse MOSAIC 25.2 Barnim example (SNS ad-hoc ITS-G5 geocast), run 2026-08-29, logs/log-20260829-163311-Barnim  (n=504, mean 2.6 ms, p95 7.0 ms)
* time budget tth: sweep JSONs (15 points, 4386 rerouting vehicles): distance from position at first DENM reception to hazard rectangle / speed
  n=4386, p10 0.0 s, p50 50.8 s, p90 254.8 s; 628 vehicles (14%) were already inside the hazard rectangle at first reception (tth = 0: no advisory can arrive in time; counted as not delivered in the all-vehicle columns, excluded in the upstream-only columns)
* Monte Carlo: 20 draws per vehicle, seed 0; delivered = not lost AND (latency + added) < tth

| added latency ms | loss % | delivered (single DENM) | delivered (1 Hz DENM repeat) | upstream-only single | upstream-only repeat | eff. latency mean ms |
|---|---|---|---|---|---|---|
| 0 | 0 | 0.857 | 0.857 | 1.000 | 1.000 | 2.6 |
| 0 | 10 | 0.770 | 0.850 | 0.900 | 0.992 | 2.6 |
| 0 | 30 | 0.600 | 0.837 | 0.700 | 0.977 | 2.6 |
| 500 | 0 | 0.800 | 0.800 | 0.934 | 0.934 | 502.6 |
| 500 | 10 | 0.721 | 0.799 | 0.840 | 0.933 | 502.6 |
| 500 | 30 | 0.558 | 0.797 | 0.652 | 0.930 | 502.6 |
| 2000 | 0 | 0.790 | 0.790 | 0.923 | 0.923 | 2002.6 |
| 2000 | 10 | 0.713 | 0.790 | 0.829 | 0.922 | 2002.6 |
| 2000 | 30 | 0.553 | 0.788 | 0.645 | 0.920 | 2002.6 |
| 5000 | 0 | 0.778 | 0.778 | 0.908 | 0.908 | 5002.6 |
| 5000 | 10 | 0.702 | 0.778 | 0.818 | 0.908 | 5002.6 |
| 5000 | 30 | 0.544 | 0.778 | 0.635 | 0.908 | 5002.6 |

single DENM: one advisory per vehicle, lost with probability `loss`. 1 Hz repeat: the official WeatherWarningApp re-sends a DENM every second while in the hazard, so a vehicle with slack tth - latency gets one extra chance per second (P = 1 - loss^n).

Regenerate: `python pipeline/networking/latency_injection.py [--base sweep]`.
