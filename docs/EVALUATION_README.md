# TrafficTwin — evaluation bundle (2026-09-07, branch rebuild-120h)

Source-only snapshot for code review. Binary data, SUMO XML outputs, checkpoints, media and
git history are omitted; every file here is the real production file from the repository.

## What the system claims
1. Forecast: a Graph WaveNet checkpoint trained on AWS (g5.xlarge) on the user-uploaded METR-LA
   subset, validated on the chronological held-out 20 % (skill +26 % vs persistence). STID,
   STAEformer, DCRNN likewise; Chronos and OpenCity pretrained only; persistence/HA baselines.
   Chronos does NOT beat persistence on METR-LA (negative result kept).
2. Forecast → routing: continuous future edge travel times (length / bounded predicted speed),
   0/1/2-hop DERIVED propagation, K=5 duarouter candidates, generalized cost (forecast tt + BPR
   load + overlap + switch cost), minimum-saving threshold, capacity/share/cooldown admission.
3. Outcome gates in SUMO 1.27.1, paired seeds, 95 % CI:
   - Oracle gate (FINAL_PROTOCOL_v1, Dhaka R1): oracle −4.02 % vehicle-hours vs baseline
     [−5.95, −2.09], 9/10 seeds. Perfect information; not a learned model.
   - Learned-model gate (FINAL_LEARNED_PROTOCOL_v1, Los Angeles, 20 held-out seeds, Graph WaveNet
     checkpoint 566b97d97943 pinned by training job): INCONCLUSIVE — GWNet vs baseline −0.05 %
     [−0.24, +0.14], 10/10; vs persistence −0.08 % [−0.19, +0.02]; oracle on the same seeds −1.22 %
     HELPED (research-only). Forecast skill +11 % on the mapped detectors, but only 8 DIRECT edges of
     8,952, so 0–11 reroutes per seed. Thesis conclusion: the trained model improved forecast accuracy,
     but that improvement was not sufficient to establish a system-level routing benefit under the
     frozen scenario. Report: results/routing/learned_gate/FINAL_LEARNED_PROTOCOL_v1_final_*/report.md
   - Coverage rescue (feasibility, 2026-09-06): a VERIFIED 207-node METR-LA Graph WaveNet checkpoint
     (SHA 548e399bd53c, held-out MAE 2.71/3.10/3.56 mph vs published 2.69/3.07/3.53) exists; all 207
     genuine detectors mapped with strict gates onto four candidate OSM corridors; recommended corridor
     la_c4_central_wide (83 detectors, 74 DIRECT / 134 DERIVED edges, 58 % of vehicles and 8.4 % of
     vehicle-time exposed vs 31 % / 2.7 % before). No final v2 experiment run yet; at the development
     moment no reroute cleared the frozen 60 s / 5 % threshold. Report: results/routing/coverage_rescue/REPORT.md
4. Digital twin: the exact user trip driven by a probe vehicle in real sumo-gui via TraCI, with
   provenance ids (analysis → routing → simulation), teleports never hidden.

## Where to look
- dashboard/backend/main.py            FastAPI API (analysis, routing, twin, training, experiments)
- dashboard/backend/analyze.py, dataset_ops.py, route_opt.py, twin_test.py, live_sim.py,
  train_jobs.py, model_registry.py, provenance.py
- dashboard/frontend/                  ES-module app (Home, Prediction, Route Optimization, Digital Twin, Results)
- pipeline/routing/edge_costs.py, route_optimizer.py, oracle_gate.py, learned_gate.py, routing_config.json
- pipeline/city/sensor_map.py           genuine METR-LA detector metadata → SUMO edges (no synthesis)
- pipeline/forecasting/                 BasicTS-legacy adapters (official algorithms, pinned SHA)
- backend/tests/rebuild/, dashboard/backend/tests/   pytest suite (402 passed, 5 skipped on 2026-09-06)
- results/routing/oracle_gate/*/report.md    the frozen oracle result
- results/routing/learned_gate/*/report.md   the learned-model result (final, 20 seeds, INCONCLUSIVE)
- results/routing/coverage_rescue/REPORT.md  the 207-sensor coverage feasibility study and corridor choice
- results/forecasting/verify_GWNet_METR-LA_207.json   verification of the full 207-node checkpoint
- pipeline/city/coverage_rescue.py           the coverage / traffic-exposure measurement
- dashboard/backend/forecast_map.py + dashboard/frontend/components/prediction-page.js   TRAFFIC FORECAST page (network map, DIRECT/DERIVED provenance, validation replay)
- docs/REBUILD_120H_PLAN.md, docs/audit/     plan and audit trail

## Things a reviewer should check hard
- No preset supplies output values; forecasts are computed per request (provenance hashes).
- Official upstream algorithms are never replaced by simplified re-implementations.
- Google Routes data is never used for model training/validation.
- Failures are surfaced (404 ANALYSIS_RUN_NOT_FOUND, SUMO_OD_MAPPING_FAILED, NO_SENSOR_MAPPING).

## Open questions for the reviewer
- Is the negative learned-model result (v1) presented honestly, and is the coverage diagnosis convincing?
- Is FINAL_LEARNED_PROTOCOL_v2 on la_c4_central_wide with the 207-node checkpoint the right next experiment,
  given that the frozen reroute threshold (60 s / 5 %) may still suppress reroutes?
- Any place where the code could be mistaken for a preset or a hard-coded output?
