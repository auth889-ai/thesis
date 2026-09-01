# Routing arms on REAL MEASURED demand (Athens pNEUMA d8)

**697 vehicles, drone-measured** — origins, destinations and departure times are observed, not generated. Network: OSM extract of the same streets. Vehicle types: calibrated with the authors' published optimizer. Twin validated at speed MAE 3.0 m/s, 0 teleports (`artifacts/urban_real_site/STEP2_RECORD.json`). Horizon 900s; 3 paired seeds (seeds vary SUMO's driver noise only — the trips are fixed and measured).

| arm | total_vehicle_hours | mean_travel_time_s | p95_travel_time_s | mean_time_loss_s | arrived | teleports |
|---|---|---|---|---|---|---|
| static | 27.63 ± 9.69 | 144.23 ± 50.67 | 427.67 ± 120.65 | 129.54 ± 50.78 | 685.00 ± 8.52 | 17.67 ± 13.12 |
| static_traci | 27.63 ± 9.69 | 144.23 ± 50.67 | 427.67 ± 120.65 | 129.54 ± 50.78 | 685.00 ± 8.52 | 17.67 ± 13.12 |
| reactive_c0.05 | 21.06 ± 3.01 | 108.80 ± 15.53 | 340.33 ± 68.75 | 94.09 ± 15.52 | 697.00 ± 0.00 | 11.00 ± 3.56 |
| predeparture_oracle_c0.05 | 30.98 ± 17.91 | 124.98 ± 43.05 | 431.67 ± 189.90 | 111.04 ± 44.25 | 624.67 ± 102.29 | 23.33 ± 20.98 |
| reactive_c0.1 | 21.06 ± 3.01 | 108.80 ± 15.53 | 340.33 ± 68.75 | 94.09 ± 15.52 | 697.00 ± 0.00 | 11.00 ± 3.56 |
| predeparture_oracle_c0.1 | 30.78 ± 10.21 | 155.62 ± 49.93 | 476.67 ± 107.25 | 140.59 ± 49.94 | 691.00 ± 6.48 | 17.67 ± 6.94 |
| reactive_c0.3 | 21.24 ± 3.61 | 109.68 ± 18.66 | 357.00 ± 97.50 | 94.96 ± 18.64 | 697.00 ± 0.00 | 11.33 ± 4.50 |
| predeparture_oracle_c0.3 | 23.82 ± 12.14 | 123.02 ± 62.73 | 381.67 ± 165.01 | 107.45 ± 62.69 | 697.00 ± 0.00 | 9.33 ± 6.34 |

## Paired change vs the LIKE-FOR-LIKE baseline (per-seed, then mean)

`reactive_*` is compared against `static_traci` (same TraCI stepping, no advice); the pre-departure arms against `static` (both launched standalone). Comparing a TraCI arm to a standalone baseline would measure the harness as well as the treatment.

| arm | veh-h per seed % | mean % | arrivals Δ | teleports Δ | seeds improved |
|---|---|---|---|---|---|
| reactive_c0.05 | [-38.46, -0.7, -16.21] | -18.46 | +36 | -20 | 3/3 |
| predeparture_oracle_c0.05 | [-57.51, 204.93, -17.91] | +43.17 | -181 | +17 | 2/3 |
| reactive_c0.1 | [-38.46, -0.7, -16.21] | -18.46 | +36 | -20 | 3/3 |
| predeparture_oracle_c0.1 | [-59.49, 118.37, 51.3] | +36.73 | +18 | +0 | 1/3 |
| reactive_c0.3 | [-36.08, -3.51, -15.99] | -18.53 | +36 | -19 | 3/3 |
| predeparture_oracle_c0.3 | [-62.89, 122.07, -34.93] | +8.09 | +36 | -25 | 2/3 |

## Caveats an examiner will ask about — stated here, not buried

1. **The free-running twin gridlocks, and the headline gain is mostly deadlock relief.** In the drone data all 697 vehicles completed within the 827.8 s observation window. In the static twin arm 9 are unfinished at 900 s and 18 teleport (SUMO's deadlock escape). Diagnostic: at 10 % compliance only SIX vehicle routes actually change, yet vehicle-hours fall ~38 % and teleports drop 36 -> 13. A handful of vehicles cannot make a network 38 % more efficient; they can unlock a jammed junction. So this number measures the release of a SIMULATION deadlock, not a transport effect, and must not be quoted as a routing benefit.
1b. **The baseline is not a harness artifact** — `static_traci` (stepped by TraCI, no advice) reproduces standalone `static` exactly, so arms are compared like for like.
1c. **Compliance sets are nested by construction** (the md5 rule means the 5 % set is a subset of the 10 % set), which is why an unchanged critical vehicle can give identical results at two shares.
2. **This exceeds the twin's validated regime.** `STEP2_RECORD.json` validated it for per-cycle, short-horizon experiments with real per-cycle initialisation, and states explicitly that free-running long-horizon network behaviour is NOT validated. A 900 s free-running run is outside that envelope.
3. **The measured routes are not strawmen.** Their free-flow travel time is a median 1.00x (mean 1.09x) of the shortest path, so the improvement does not come from fixing bad map-matched routes; it comes from spreading load once the network congests.
4. **Athens is not Dhaka.** This site removes the synthetic-demand weakness, at the cost of answering the question on a different city than the one the thesis is about.

Data provenance: `route/data/athens_d8/MANIFEST.json` — REAL_MEASURED_DEMAND — vehicles and their routes come from drone-measured trajectories, map-matched to the OSM network (368/401 matched, GATE2_SAME_ROAD_TWIN PASS)

Regenerate: `python route/real_demand_arms.py --seeds 11,12,13 --compliance 0.05,0.1,0.3` (wall 29s).
