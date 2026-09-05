# TrafficTwin — evaluation bundle (2026-09-06, branch rebuild-120h)

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
   - Learned-model gate (FINAL_LEARNED_PROTOCOL_v1, Los Angeles, Graph WaveNet vs baseline /
     reactive / persistence-predictive): dev-seed smoke result included; the 20 final held-out
     seeds were running when this bundle was made (report.md is appended when finished).
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
- tests/rebuild/, dashboard/backend/tests/   pytest suite (395 passed, 5 skipped on 2026-09-06)
- results/routing/oracle_gate/*/report.md    the frozen oracle result
- results/routing/learned_gate/*/report.md   the learned-model result (dev now; final appended)
- docs/REBUILD_120H_PLAN.md, docs/audit/     plan and audit trail

## Things a reviewer should check hard
- No preset supplies output values; forecasts are computed per request (provenance hashes).
- Official upstream algorithms are never replaced by simplified re-implementations.
- Google Routes data is never used for model training/validation.
- Failures are surfaced (404 ANALYSIS_RUN_NOT_FOUND, SUMO_OD_MAPPING_FAILED, NO_SENSOR_MAPPING).
