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
