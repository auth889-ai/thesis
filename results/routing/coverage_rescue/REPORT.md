# FULL METR-LA COVERAGE RESCUE — feasibility report (2026-09-06)

Question: **can the full 207-sensor Graph WaveNet influence a meaningful fraction of the traffic in one defensible real-LA SUMO corridor?**
Development demand and one development moment only. No final seeds were run, no threshold, objective, admission, model or UI was changed.

## 1. The full 207-node checkpoint — VERIFIED, reused (no retraining)

| item | value |
|---|---|
| checkpoint | `results/forecasting/checkpoints/GraphWaveNet/METR-LA_50_12_12/d1ffd3d52d3caacf60ebf59214673f7c/GraphWaveNet_best_val_MAE.pt` |
| checkpoint SHA-256 | `548e399bd53cc54a` |
| trained | AWS g4dn.xlarge, job `predict-metrla-ckpt` (2026-09-01), official BasicTS-legacy config `baselines/GWNet/METR-LA.py`, 50 epochs |
| upstream SHA | `4c3e2d373c647667c2123e1591f2d79c229dfcc6` (BasicTS-legacy, pinned) |
| dataset | METR-LA, 207 nodes × 34,272 steps × 3 features, speed mph, genuine (Li et al. 2018) — hash `857a98d0ec47b353` |
| graph | METR-LA `adj_mx.pkl` — hash `a35687c6` |
| split | chronological 70/10/20 = 23,990 / 3,427 / 6,855 steps; 6,832 held-out windows |
| reload | 0.54 s, state dict fits the architecture |
| held-out MAE (mph) +15 / +30 / +60 | **2.712 / 3.095 / 3.559** (recomputed on the whole test split today; the training log says 2.712 / 3.096 / 3.559) |
| published (Wu et al. 2019) | 2.69 / 3.07 / 3.53 → within 1.1–1.8 % |
| persistence floor (benchmark_floors.md, same protocol) | 3.46 / 4.15 / 5.31 → skill +22 % / +25 % / +33 % |

Full record: `results/forecasting/verify_GWNet_METR-LA_207.json`.

## 2. The 207 genuine detectors

All coordinates from the pinned DCRNN `graph_sensor_locations.csv` (207 rows). Span lat 34.043–34.222, lon −118.537 to −118.183. Densest cells lie along US-101 / SR-134 / I-5 / SR-2 / SR-110 between Hollywood, Glendale and downtown. No coordinate was invented; every detector inside a candidate bbox was snapped with the strict gate (≤ 60 m, motorway/trunk/primary/secondary only) — **every inside detector snapped GOOD, median snap ≤ 2.1 m, max ≤ 11.9 m, zero rejections inside any bbox.**

## 3–4. Candidate corridors (OSM → netconvert, randomTrips development demand seed 101, 900 vehicles, 2,700 s baseline run)

| scenario | bbox (S,W,N,E) | area km² | detectors GOOD | DIRECT / DERIVED edges | SUMO edges | drivable km | % length DIRECT / +DERIVED | % vehicles touching DIRECT / +DERIVED | % veh-km DIRECT / +DERIVED | % veh-time DIRECT / +DERIVED | % equipped decisions exposed | % candidate routes priced |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **Blocker #5 as run** (20-node dataset) | 34.045,−118.300,34.090,−118.220 | 36.8 | 8 | 8 / 15 | 8,952 | 867 | 0.42 / 0.60 | 24.1 / 30.7 | 4.2 / 6.6 | 1.7 / 2.7 | — (0–11 reroutes/seed in the final gate) | — |
| same bbox, 207-node model | 34.045,−118.300,34.090,−118.220 | 36.8 | 29 | 27 / 43 | 8,952 | 867 | 1.55 / 2.07 | 31.3 / 37.6 | 10.7 / 16.7 | 4.3 / 6.8 | 39.0 | 40.6 |
| la_c1_glendale_110_2 | 34.100,−118.318,34.160,−118.218 | 61.3 | 56 | 51 / 93 | 8,690 | 1,171 | 2.04 / 3.75 | 35.3 / 48.1 | 8.4 / 17.9 | 3.1 / 6.8 | 49.6 | 44.3 |
| la_c2_hollywood_101_5 | 34.060,−118.318,34.120,−118.218 | 61.3 | 52 | 45 / 76 | 12,828 | 1,426 | 1.67 / 2.44 | 40.3 / 52.8 | 13.3 / 19.7 | 5.3 / 7.9 | 53.3 | 58.9 |
| la_c3_hollywood_hills | 34.100,−118.378,34.160,−118.278 | 61.3 | 49 | 46 / 69 | 7,129 | 1,016 | 2.22 / 3.44 | 41.4 / 53.0 | 12.7 / 19.2 | 5.0 / 7.9 | 55.2 | 58.1 |
| **la_c4_central_wide** | 34.080,−118.342,34.160,−118.222 | 98.0 | 83 | 74 / 134 | 15,661 | 1,914 | 2.01 / 3.41 | **45.4 / 58.0** | 11.6 / **22.4** | 4.3 / **8.4** | **59.2** | 55.2 |

Notes. Vehicle-time from the baseline run's `exitTimes`; vehicle-km from edge lengths. Routing exposure = equipped vehicles (30 %) in the two 900 s development rounds whose K=5 candidate set contains at least one priced edge. Baseline SUMO wall time 5.6–8.7 s per run. Per-candidate detail: `<scenario>/coverage.json`, `<scenario>/sensor_to_edge_207.json`.

## 5. Selection rule (written before any final experiment; final seeds never inspected)

1. Mapping gate: every counted detector GOOD (≤ 60 m, major road), median snap ≤ 30 m. All candidates pass.
2. Feasibility gate: SUMO edges ≤ 20,000 and baseline run ≤ 60 s. All candidates pass.
3. Rank by **% equipped routing decisions exposed to a priced edge** (the mechanism through which a forecast can act), tie-break by **% vehicle-time on DIRECT + DERIVED edges**, then by % vehicles touching DIRECT.
4. Outcome numbers (vehicle-hours, wins) play no part.

Under this rule: **la_c4_central_wide** (59.2 % decisions exposed, 8.4 % vehicle-time, 58 % vehicles) > la_c3 (55.2 %, 7.9 %, 53 %) > la_c2 > la_c1 > old bbox. la_c3 is the compact runner-up (half the edges, 93 % of the exposure) if runtime ever matters.

## 6. Demand (to be frozen for v2, not yet frozen)

SYNTHETIC WHAT-IF: randomTrips passenger trips on the real OSM network, one draw per seed, departures 0–1,800 s, period 2.0 s (~900 vehicles), fringe factor 5 — the scenario's own wizard options. Not observed LA demand and never labelled as such. The eight-to-eighty measured detector speeds are replayed as lane speed caps as in v1.

## 7. Forecast path

207-node forward pass (0.48 s on this CPU, raw hash `c53b33310b79504f` at development index 30,395) → only the GOOD-mapped sensors of the chosen scenario (83 of 207 for c4; 124 sensors ignored because they lie outside it) → DIRECT future travel times → existing 1-hop DERIVED propagation (unchanged config `ea08dddedc14`) → UNFORECASTED elsewhere. Graph WaveNet never predicts a SUMO edge directly.

## 8. Old vs new

| | Blocker #5 scenario | la_c4_central_wide |
|---|---|---|
| model input | 20 sensors | 207 sensors |
| detectors mapped | 8 | 83 |
| DIRECT / DERIVED | 8 / 15 | 74 / 134 |
| SUMO edges | 8,952 | 15,661 |
| % vehicles touching DIRECT / +DERIVED | 24.1 / 30.7 | 45.4 / 58.0 |
| % vehicle-km covered (+DERIVED) | 6.6 | 22.4 |
| % vehicle-time covered (+DERIVED) | 2.7 | 8.4 |
| % routing decisions exposed | not measured in v1 (0–11 reroutes per seed observed) | 59.2 |

Exposure roughly doubles by vehicles, triples by distance and time. The share of vehicle-time on covered edges stays under 10 % in every candidate because randomTrips spreads trips over surface streets while the detectors sit on freeways; that is a property of the synthetic demand, reported, not hidden.

## 9. A caution the numbers force

At the development moment, with the frozen thresholds (≥ 60 s and ≥ 5 % saving), **no candidate produced a single REROUTE decision** (all KEEP_CURRENT_BELOW_THRESHOLD or NO_ALTERNATIVE), even with 74 DIRECT edges. Exposure is necessary but not sufficient: the forecast must also imply a saving above the threshold on an alternative route. Whether that happens across many held-out moments is exactly what v2 would measure. Nothing was tuned to change this.

## 10. Recommendation

**A. STRONGER SCENARIO FOUND** — freeze `la_c4_central_wide` with the verified 207-node checkpoint `548e399bd53c` for FINAL_LEARNED_PROTOCOL_v2: coverage +75 DIRECT edges, vehicles exposed 30.7 % → 58.0 %, vehicle-time covered 2.7 % → 8.4 %, 59 % of equipped decisions see a priced edge. The honest expectation: the forecast can now reach most trips, but the frozen saving threshold may still limit reroutes; v2 will report that as it is.
