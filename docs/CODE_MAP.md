# Code map: where each feature lives (2026-10-10, code freeze)

For each feature:
- what the supervisor sees;
- the exact run command;
- the data flow, from input to `file:function (lines)` to output;
- upstream code: copied, run unchanged, or ours;
- three likely questions, each with the `file:line` to open.

Line numbers are those of the files on disk tonight. They were checked with grep and by printing the ranges. Most of this code is
uncommitted (HEAD `2fcbb862`); by the owner's rule nothing is committed until the end.

**Ports.** `make app` serves on :8000. `make present` and the browser scripts default to :8011 (`LOCAL_URL`).
**Hosted.** `https://43-205-213-250.sslip.io/` (login in `~/.dhakaflow/hosted_access.txt`).

| # | Feature | Terminal | Web |
|---|---|---|---|
| 1 | Ambulance V2X alert (RQ3) | `make run-v2x` (`ARGS="--gui-colours"`), `make gui-veins`, `make sweep-v2x` (`ARGS="--quick"`) | map `/` → Simulation → Ambulance V2X |
| 2 | Crash SOS, car to car | `make run-sos-v2v`, `make run-sos-collide` (a real SUMO collision; since R1 it also writes the crash sensor's trace from SUMO's record, replayed by the Emergency page and present step 7), `make sweep-sos` (share x crash time x seeds) | map `/` → Simulation → Crash SOS |
| 3 | Smart signals (sumo-rl) | `make run-signals` (`ARGS="--controller maxpressure|maxpressure_ev"`), `make compare-signals` | map `/` → Simulation → Smart signals (laptop only) |
| 4 | Forecasting RQ1 and Model Lab | `make run-forecast` | `/app/lab/model-lab`; map `/` → Forecast |
| 5 | Phone mesh (RQ4) | `make run-mesh`, `make gui-mesh` (The ONE's window), `make sweep-mesh` (routers x phone count) | `/app/offline`; map `/` → Simulation → Phone mesh (laptop only) |
| 6 | Live twin | `make run-twin` (opens the page; not in `make present`); `scripts/live_twin/steer_compare.py` | `/app/lab/live-twin` |
| 7 | Weak-signal prefetch (RQ5) | `make run-offline`, `make prefetch-masts` (Q3: profile from real OSM masts, app flag `TRAFFICTWIN_SIGNAL_MASTS=1`) | `/app/trip`; map `/` trip |
| 8 | Crash detection on the phone (RQ6) | step 7 of `make present` (since R1 it replays the trace step 2 built from SUMO's own collision record, `--trace=sumo_collision`); real sensor: `node frontend/tests/qa/phone_sensor.cjs` | `/app/emergency`; map `/` trip |
| 9 | Hospital reach | `python -m core.safety.reach build`; live: `node frontend/tests/qa/live_reach.cjs` | `/app/emergency`; map `/` → hospitals |
| 10 | Map app navigation | `make app` | `/` |
| 11 | AID: incident detection in SUMO (`features/aid/README.md`) | `make aid-train`, `make aid-eval`, `make aid-gui` (pairs green/yellow/red, false-alarm counter), `make aid-frontier`, `ARGS="--sensor camera"` (J2), `make aid-incidentnet` (J3-A: IncidentNet's code on our rows) | — (terminal only) |

`make present` runs features 1, 2, 3, 4, 5, 7 and 8 in that order, in about 5 minutes (`scripts/live/present.py:31-39`).

**Commands added 2026-10-11** (all in `docs/LIVE_RUNS.md`; every one a live run, nothing replayed): `make demo` (the talk's 9 live parts on Enter),
`make run-routing-quick` (RQ2 closed loop on the LA twin, checked per seed-arm; `ARGS="--quick"`), `make sweep-v2x`, `make gui-veins`, `make gui-mesh`,
`make run-sos-collide`, `make sweep-sos`, `make aid-train` / `aid-eval` / `aid-gui` / `aid-frontier` / `aid-incidentnet`, `make prefetch-masts`, `make run-twin`; on the map app: live hospital reach (Hospitals → "Live reach: tap the map")
and the phone's own crash sensor (trip → "Use this phone's crash sensor"). Each feature's own page: `features/<name>/README.md`. Where every shown number comes from: `docs/HARDCODE_AUDIT.md` (2026-10-11).

---

## 1. Ambulance V2X alert (RQ3)

**What Sir sees**
- **sumo-gui:** it follows the ambulance (white, green cross).
  - Blue radio ring: 425 m for ITS-G5, 625 m for C-V2X, none for 4G.
  - Cars making way turn orange.
  - A label shows sent / delivered / lost / out of range, cars alerted and junctions green.
- **Terminal:** travel time without and with the alert, message counts, and `THESIS CHECK … REPRODUCED exactly`. Seed 11, Dhaka level: 292 s → 284 s.

**Run**
- `make run-v2x ARGS="--tech c_v2x --share 0.5 --seed 12 --level x2"` (Makefile:25-26). Other options: `--arm alert|alert_preemption`, `--no-gui`.
- Veins second view: `ARGS="--veins"`. Web: `POST /api/live/v2x`.

**Data flow**
1. Inputs:
   - `core/simulation/ambulance/configs/ambulance.yaml` (make-way v2, 100 m; bluelight on);
   - `core/networking/v2x/configs/network_model.yaml` (range and delivery per technology);
   - `service.scenario` (`core/simulation/ambulance/service.py:57-103`).
2. `scripts/live/run_v2x.py:main` (124-206) runs the no-alert run, then the alert run with `sumo_binary="sumo-gui"` and `hook=gui_hook` (164, 177-179).
3. `service.py:run_one` (297-350) runs the TraCI loop (324-331), calling `AmbulanceRun.step` (133-152) each step.
4. `service.py:AmbulanceRun._alert` (169-207):
   - cars ahead within 100 m that carry a radio make way (180-183);
   - junctions on the route are handled at 197-207;
   - every message goes through `_send` (209-213).
5. `core/networking/v2x/model.py:deliver` (75-86): out of range, lost (delivery ratio), expired, or delivered.
6. When a message is delivered:
   - `core/simulation/ambulance/makeway.py:MakeWay.alert` (34-43; `release` 52-59);
   - `core/simulation/signals/preemption/sumo_adapter.py:SumoPreemption.request/step` (95-105, 117-143) → `emergency.py:EmergencyController.apply` (46-66) → `phases.py:SignalFSM` (62-101) → `trafficlight.setPhase`.
7. `run_v2x.py:gui_hook` (80-121) draws the ring, colours and label. `saved()` (59-62) and the check at 193-202 compare with `results/emergency/dhaka/rq2/runs*/…/metrics.json`, then write `evidence/live_runs/v2x/last_run.json`.
8. Web: `backend/app/live_jobs/router.py:start` (11-17) → `core/simulation/live_jobs/runner.py:Runner.start/_run` (89-118) → `jobs.py:v2x` (66-128) → `frontend/map/src/traffictwin/TtSimulation.vue` (`run`/`poll` 98-114) → `ttSim.ts:frameFeatures` (18-38).

**Upstream**

| Kind | What | Repo, commit, licence | SOURCES.md |
|---|---|---|---|
| Copied (header plus one import line) | `core/simulation/signals/preemption/{emergency,phases,upstream_types}.py`, checked by `backend/tests/signals/test_preemption_adapter.py:75-76` | adaptive-traffic-signal-rl `b62436b5…`, MIT | :163 |
| Unchanged | SUMO 1.27.1 (pip) | `7717f237…`, EPL-2.0 | :9 |
| Unchanged | Veins 5.3.1 (`~/.dhakaflow/upstream/veins`) | `6571085f…`, GPL-2.0+ | :195 |
| Unchanged | OMNeT++ 6.2.0 | Academic Public Licence | :194 |
| Ours | `scripts/live/run_v2x.py`, `run_veins.py`, `core/simulation/ambulance/{service,makeway,measures}.py`, `core/networking/v2x/model.py`, `sumo_adapter.py`, `core/simulation/live_jobs/*`, `research/veins_dhaka/src/AmbulanceAlert11p.*` (subclass of `DemoBaseApplLayer`, `.h:6`) | — | — |

**Questions**
- *Where is it decided whether a message arrives?* → `core/networking/v2x/model.py:75-86`; the values are in `configs/network_model.yaml:19-70`.
- *Which cars move aside, and how?* → `service.py:169-196` (100 m at 180-181), `makeway.py:34-43`, `configs/ambulance.yaml:13-20`.
- *Is green preemption safe?* → `service.py:197-207` → `sumo_adapter.py:95-143` → `phases.py:62-101` (minimum green, amber, all-red, from the copied state machine). How "REPRODUCED" is decided: `run_v2x.py:193-202`.

## 2. Crash SOS, car to car

**What Sir sees**
- The SOS rule is re-run on the three thesis traces: `REPRODUCED (evidence/sos/results.json)`.
- sumo-gui: the crashed car is red, warned cars blue, rerouted cars green; a label shows warned / rerouted / broadcasts.
- Final printout: warned cars, rerouted cars, delivery in range, and arrivals of the affected cars with and without the warning. It is said to be new: **there is no thesis number for car to car.**

**Run**
- `make run-sos-v2v ARGS="--share 0.2 --tech c_v2x --seed 12"` (Makefile:28-29). Veins view: `ARGS="--veins"`. Web: `POST /api/live/sos`.

**Data flow**
1. Inputs: `research/sos/traces/*.json`, `evidence/sos/results.json`, `service.scenario`, `network_model.yaml`.
2. `scripts/live/run_sos_v2v.py:rule_check` (45-57) → `core/safety/sos.py:detect` (43-56; 4 g at :25).
3. `run_sos_v2v.py:simulate(warn=True)` (60-157). The crash is at 90-105: one car stops, red, lane change off. The warning is flooded from 106-135: warned cars broadcast to equipped cars.
4. Each send goes through `core/networking/v2x/model.py:deliver` (75-86), called at `run_sos_v2v.py:119`.
5. A delivered warning causes a reroute, TraCIDemo11p style: `setAdaptedTraveltime(edge, 9999)` and `rerouteTraveltime` (`run_sos_v2v.py:126-135`).
6. `simulate(warn=False)` runs the same seed without warnings (200). The comparison is at 201-209, written to `evidence/live_runs/sos_v2v/last_run.json`.
7. Web: `core/simulation/live_jobs/jobs.py:sos` (132-169) → `ttSim.ts:frameFeatures` (28-31).

**Upstream**
- **Copied:** none.
- **Unchanged:** Veins `TraCIDemo11p` in the `--veins` view (`~/.dhakaflow/upstream/veins`, GPL-2.0+, SOURCES.md:195).
- **Ours:** `scripts/live/run_sos_v2v.py` (re-implements TraCIDemo11p's reroute logic), `core/safety/sos.py`, `model.py`, `jobs.py`. WreckWatch is a paper only (SOURCES.md:58).

**Questions**
- *What triggers the SOS?* → `core/safety/sos.py:43-56`, threshold at `:25`.
- *How does the warning spread, and who receives it?* → `scripts/live/run_sos_v2v.py:106-123`, using `model.py:75-86`.
- *How do warned cars reroute, and what if there is no other road?* → `run_sos_v2v.py:126-135`.

## 3. Smart signals: sumo-rl Q-learning vs fixed time

**What Sir sees**
- Two sumo-gui windows side by side: left "FIXED-TIME (SUMO programs)", right "Q-LEARNING (sumo-rl, frozen)", each counting cars halting at the corridor junctions.
- Final table: ambulance time, queue, time blocked, vehicle-hours. Seed 11, Dhaka level: ambulance 292 s → 188 s; all vehicles 532 → 794 vehicle-hours.
- Two `THESIS CHECK … REPRODUCED exactly` lines.

**Run**
- `make run-signals ARGS="--level x2 --seed 12"` (Makefile:31-32). The Q-learning side runs in `~/.dhakaflow/venvs/sumo-rl-np1` (`run_signals.py:26,137-138`).
- Training (already done): `python -m core.simulation.ambulance.rl_signals train --scale 2 --episodes 30`, which writes `results/emergency/dhaka/rq2/rl/q_*.pkl`.

**Data flow**
1. `scripts/live/run_signals.py:main` (114-157) starts two `side_main` processes (93-111).
2. Fixed side: `service.run_one` (297-350, `observe=True`), with `hook=display` (48-90).
3. Q-learning side: `core/simulation/ambulance/rl_signals.py:run` (127-180):
   - `_sumo_rl` (31-40) checks the pinned commit;
   - `corridor_signals` (43-53) picks the lights within 500 m;
   - `_env` (64-80) subclasses `sumo_rl.SumoEnvironment`, with `_sumo_step` at 69-74;
   - the frozen Q-tables are loaded with alpha 0 and epsilon 0 (155-166).
4. On both sides `measures.py:RouteObserver` (38-106) measures queue and blocked time, and `service.trip_metrics` (274-294) writes the results.
5. Check: `run_signals.py:saved` (42-45) and 148-155 compare with `results/emergency/dhaka/rq2/runs/…`. Aggregate: `results/emergency/dhaka/rq2/summary.json` (`findings.rl` :879, `qlearning_dhaka` :2062-2274).

**Upstream**
- **Copied:** none.
- **Unchanged:** sumo-rl at `86f0fc41…`, MIT (`~/.dhakaflow/upstream/sumo-rl`, SOURCES.md:156): `SumoEnvironment`, `QLAgent`, `EpsilonGreedy`. Its own example was reproduced first (`evidence/ambulance_rq2/reproduce/SUMMARY.json`).
- **Ours:** `rl_signals.py` (subclass and training loop), `run_signals.py`, `measures.py`, `jobs.py:signals` (210-258).

**Questions**
- *State, reward, settings?* → sumo-rl's defaults kept (alpha 0.1, gamma 0.99, epsilon 0.05→0.005, diff-waiting-time): `rl_signals.py:90-124`.
- *Which junctions, and is learning frozen during the demo?* → `rl_signals.py:43-53` and `:155-166`.
- *Why is the ambulance faster but everyone slower?* → `results/emergency/dhaka/rq2/summary.json:884` (also :2274): the lights did not hold the ambulance directly; the vehicle-hours cost is stated, not explained.

## 4. Forecasting RQ1, Model Lab, forecast layer

**What Sir sees**
- **Model Lab:** pick a METR-LA sensor, a moment and a model, then Run. It shows a chart (history, recorded, model, "no change"), the errors at 15, 30 and 60 min, and "this equals RQ1's saved prediction".
- **Map Forecast chip:** sensors coloured; a "best time to leave" only where the model has skill (Los Angeles).
- **Headline numbers** (`results/forecasting/rq1/summary.md`):
  - Los Angeles at 60 min: D2STGNN 3.779 mph against "no change" 6.506.
  - Dhaka at 60 min: Chronos-2 2.877 km/h against "no change" 2.717, so no skill an hour ahead.

**Run**
- `make run-forecast ARGS="--sensor 5 --at 2012-06-05T08:30 --model D2STGNN"` (Makefile:34-35).
- RQ1 pipeline: `research/forecasting_rq1/scripts/00_reproduce.sh`, then `01_protocol_b.sh` (ends with `python -m core.ml.forecasting.transfer_dhaka.run summary`).
- Forecast layer: `python -m core.ml.forecasting.layer.build_la`.

**Data flow (Model Lab: computed now)**
1. `frontend/src/features/forecast/ModelLabPage.tsx`: `go` (25-31) POSTs `/api/model-lab/run`.
2. `backend/app/forecasting/routers/layer.py:model_lab_run` (44-55) → `_lab` (28-34). Both catch `SystemExit`, so a missing data file is an answer, not a stuck server.
3. `core/ml/forecasting/layer/lab.py:run` (62-99) uses:
   - `axis` (32-36), reading `METR_LA.npz` through `protocol_b/data.py:load` (15-21) and the time axis from `METR-LA.h5`;
   - "no change" from `protocol_b/baselines.py:predict_persistence` (9-22);
   - the model from `evaluation/checkpoint_stage.py:predict_checkpoints` (58-97) → `_load_model` (40-55) → `infer_from_checkpoint.py:load_official_cfg` (53-87). This loads BasicTS's own config and the checkpoint from `results/forecasting/checkpoints/` (BasicTS path from `DHAKAFLOW_BTS`).
4. `lab.py:84-93` compares with RQ1's saved windows `results/forecasting/protocol_b/METR-LA_test_w120_n207_s*.npz`; the result is `rq1_check`.
5. `ModelLabPage.tsx:Result` (58-86) draws the chart, the errors and the RQ1 sentence.
6. Hosted: the same code runs from the packaged `third_party_runtime/` (BasicTS, OpenCity npz). A warm-up runs at start (`backend/app/main.py:_warm_model_lab`). Calls measured 0.48 s and 0.47 s, `rq1_check` equal (`evidence/hosting/2026-10-10/load_twin_modellab.txt`).

**Data flow (forecast layer: saved files, replayed)**
1. `build_la.py:main` (51-105) stops if any difference from RQ1's windows exceeds 1e-3 (66-73), then writes `results/forecasting/layer/{metr_la_replay.npz,summary.json}`.
2. `routers/layer.py:forecast_layer` (13-25) → `layer/service.py:layer` (118-125). Los Angeles uses `replay` (60-85, `best_time` 47-57); Dhaka uses `recorded_day` (88-115, `best_time: None`).
3. On the map: `frontend/map/src/traffictwin/TtForecast.vue` (`toggle` 109-127, `draw` 93-104).

**Upstream**
- **Unchanged:**
  - BasicTS legacy at `4c3e2d37…`, Apache-2.0 (`~/.dhakaflow/upstream/BasicTS_legacy`, SOURCES.md:148, :216): official architectures and configs. DCRNN's `random.randint` is fixed in memory at `infer_from_checkpoint.py:80-84`; the file on disk is not edited.
  - Chronos 2.3.1, Chronos-Bolt and TimesFM: pip packages, Apache-2.0 (SOURCES.md:134, :146, :147).
- **Copied:** OpenCity's `METR_LA.npz` as released, MIT, `eca64c9d…` (SOURCES.md:215). Its checkout keeps one config value from an unrestored run (`pretrain.conf`; `core/ml/forecasting/README.md`).
- **Ours:** `core/ml/forecasting/layer/*`, `evaluation/checkpoint_stage.py`, `evaluation/protocol_b/*`, `infer_from_checkpoint.py`, `transfer_dhaka/*`, `routers/layer.py`, `ModelLabPage.tsx`, `TtForecast.vue`.

**Questions**
- *Is the live number really the thesis's?* → `core/ml/forecasting/layer/lab.py:84-93`; for the layer, `build_la.py:66-73`.
- *Can the model see the future?* → `evaluation/checkpoint_stage.py:65-70` (z-score on the first 70 %) and `:85-94` (context only; the future speed is zeroed).
- *Why no "best time to leave" in Dhaka?* → `layer/service.py:47-57` and `:104-115` (no skill at every horizon). The RQ1 explanation is `docs/PAPER_MAP.md:114`: Dhaka's speeds jump.

## 5. Phone mesh (RQ4: PONS; The ONE as a second view)

**What Sir sees**
- A matplotlib window of Dhaka vehicle trails. Phones turn orange when another is within 10 m; counters show created, delivered and relayed.
- Terminal: `THESIS CHECK: REPRODUCED seed by seed`.
- Study results (SIMULATED):

| Router | Delivery | Delay |
|---|---|---|
| Epidemic | 0.028 | 65 s |
| Spray and Wait | 0.027 | 60 s |
| PRoPHET | 0.029 | 78 s |

**Run**
- `make run-mesh ARGS="--protocol epidemic --phones 8 --range 30"` (Makefile:37-38).
- `ARGS="--one"` opens The ONE's GUI.
- Study pipeline: `research/mesh_pons/scripts/01…04`, then `python -m core.networking.mesh.results --city dhaka`.

**Data flow**
1. `research/mesh_pons/scripts/02_export_movement.py:main` (36-104): SUMO `traceExporter` writes the ns2 trace, with its hash in `evidence/movement.json`.
2. `03_run_pons.py`: `read_ns2` (28-38) and `generator_with_metadata` (41-54), our two adapters; `make_router` (57-64); `run_one` (85-113) runs `pons.NetSim(...).run()` and writes `research/mesh_pons/evidence/runs/*.json`.
3. `core/networking/mesh/results.py:build` (36-92) writes `results/networking/mesh/dhaka/summary.json`. It is served by `backend/app/mesh/router.py:get_results` (11-14) and shown by `OfflineAlertsPage.tsx` (14-29).
4. Live run: `scripts/live/run_mesh.py:main` (112-179):
   - checks the trace sha256;
   - `simulate` (41-63) runs PONS;
   - `View.__call__` (88-109) draws each second;
   - the seed-by-seed check is at 166-175.
5. Second view: `scripts/live/run_mesh_one.py` (`movement` 28-39, `settings` 42-82, `main` 86-115) runs `java core.DTNSim` from `~/.dhakaflow/upstream/the-one`.

**Upstream**
- **Copied:** none.
- **Unchanged:**
  - PONS 0.2.1 = `2fd70381…`, MIT (SOURCES.md:176), identical to the tag;
  - The ONE v1.6.0 = `42b6e20f…`, GPL-3.0 (:197);
  - SUMO tools (:177).
- **Ours:** `research/mesh_pons/scripts/*`, `core/networking/mesh/*`, `scripts/live/run_mesh*.py`, `mesh_frames.py`, `OfflineAlertsPage.tsx`.

**Questions**
- *Did you modify PONS?* → `research/mesh_pons/scripts/03_run_pons.py:1-16` and `:28-54` (two adapters, each justified by a saved failure log).
- *Why only about 3 %?* → `core/networking/mesh/results.py:78-82` (17 of 277 vehicles; sparse, uncalibrated) and `research/mesh_pons/RESULTS.md:59-65` (PRoPHET never forwards).
- *Is the live run the thesis?* → `scripts/live/run_mesh.py:166-175`; the 10 m range comes from `research/mesh_pons/configs/dhaka.yaml:7-10`.

## 6. Live twin (live forecasting alongside the simulation)

**What Sir sees**
- **Map:** deck.gl vehicles on MapLibre: grey, orange making way, red crash, white ambulance with a green radio ring. Roads are coloured by the chosen forecaster's 15-minute prediction.
- **Controls:** click to place a crash or start an ambulance; a demand slider.
- **Counts:** messages, cars alerted, signals green, ambulance time.
- **Chart (uPlot):** the error of online (River), Chronos-Bolt and "no change".
- The seed is from the clock, labelled SIMULATION. The forecasts do **not** steer the simulation.

**Run**
- `make app`, then `http://127.0.0.1:8000/app/lab/live-twin` (`frontend/src/app/routes.tsx:59`). Hosted: the same path.
- API: `POST /api/live-twin/dhaka/start`, WebSocket `/api/live-twin/twins/{id}/ws?v=<browser id>`.
- Learning run: `PYTHONPATH=.:backend python scripts/live_twin/learning_run.py --minutes 180`.
- Crash check: `scripts/live_twin/crash_check.py --twins 20`.

**Data flow**
1. Input: `config/cities/dhaka.yaml:99-105` (`live_twin:` corridor net, routes, scale 0.78), validated by `core/common/data/city_config.py:LiveTwin` (163-172).
2. `backend/app/live_twin/router.py:start` (29-37; a visitor is the browser ID, else the IP) → `core/simulation/live_twin/manager.py:Manager.start` (39-51; one twin per visitor, at most 3) → `session.py:Session` (49-81).
3. `Session._prepare` (151-167):
   - `detectors.write_additional` (`detectors.py:24-36`) writes the E1 loops (Dhaka: 170 roads, 373 loops);
   - `demand.repeated` (`demand.py:13-25`) repeats the demand hour;
   - the bluelight device is off for the twin only (157-160).
4. `Session._run` (169-220) runs the TraCI loop and calls `_minute` (239-244) every 60 s.
5. `_minute` → `detectors.read_minute` (`detectors.py:39-45`) → `core/ml/forecasting/live/online.py:Forecasters.observe` (91-114):
   - River learns only when the true value arrives (`_score_and_learn` 150-177);
   - Chronos runs on a worker thread (117-135, `Chronos.predict` 47-56).
6. Clicks: `router.stream` (69-104) → `Session._do` (312-346) → `_crash` (356-370) / `_ambulance` (372-390) → `LiveAmbulance` (401-430), the RQ2 `AmbulanceRun` with only `add` changed.
7. `Session._publish` (257-283) computes `deltas.diff_dicts` (`core/simulation/live_twin/deltas.py:37-64`) → `frontend/src/features/livetwin/LiveTwinPage.tsx` (connect 72-92, draw 46-67), `liveTwin.ts`, `ErrorChart.tsx`.

**Upstream** (SOURCES.md:200-209)
- **Copied:** `core/simulation/live_twin/deltas.py`, from sumo-web3d `d89fe801…`, EPL-2.0, unchanged with its header.
- **Unchanged:** River 0.26.1, BSD-3; Chronos-Bolt revision `772f3d25…`, Apache-2.0; deck.gl 9.3.11, MIT; uPlot 1.6.32, MIT. Each one's own example was reproduced first (`evidence/live_twin/upstream/`).
- **Ours:** `core/simulation/live_twin/{session,manager,detectors,demand}.py`, `core/ml/forecasting/live/online.py`, `backend/app/live_twin/router.py`, `frontend/src/features/livetwin/*`.

**Questions**
- *Can the online model see the answer early?* → `core/ml/forecasting/live/online.py:150-177` (learns only at m+15); design notes at `:1-18`.
- *Where do the observed speeds come from?* → `core/simulation/live_twin/detectors.py:24-45`, called at `session.py:239-244`.
- *Is the ambulance the thesis one? Do forecasts steer it?* → `session.py:401-430` (subclass; only `add` differs) and `:157-160` (bluelight off, twin only). No: `docs/EXPLAIN.md:8-9`. The measured result is `docs/EXPLAIN.md` "What has been measured" (one run, 180 simulated minutes); the crash check, 0 of 20, is `evidence/live_twin/crash_check.json`.

## 7. Weak-signal prefetch (RQ5: Bartendr, BreadCrumbs)

**What Sir sees**
- `/app/trip` "Works with weak signal": a signal strip along the route, "Save this trip" with the MB saved, and estimated energy (now / as needed / Bartendr plan).
- A SIMULATED sentence: on 2G-like, the route shows in 7.4 s without the saved trip and 0.8 s with it.
- `make run-offline` cuts the network in a visible Chrome and lists what the service worker served.
- The energy saving (43–73 %) comes from **prefetching**: Bartendr's schedule adds nothing in 9 of 9 rows.

**Run**
- `make run-offline ARGS="--rq5"` (Makefile:40-41).
- Experiment: `node frontend/tests/weak_signal.experiment.cjs 3`, then `python -m core.networking.prefetch.results`.
- Offline map check: `node frontend/tests/qa/offline_home.cjs --with-route`.

**Data flow**
1. Route signal: `backend/app/routing/router.py:city_route_signal` (242-253) → `signal_predict.py:predict` (10-41) → `core/simulation/routing/signal.py` (`steps`, `combine`).
2. `frontend/src/features/today/TripPackPanel.tsx` (27-93; 48-53) → `frontend/src/lib/schedule.ts:bartendr` (24-50; `nowJ` 53, `asNeededJ` 56-66).
3. Save: `frontend/src/lib/pack.ts:savePack` (73-87) → `saveTile` (48-53), `packAssets.ts:ASSETS` (under `/app/`). Everything goes into Cache Storage `trip-pack-<city>`.
4. Along the drive: `useAlongTheDrive.ts` (11-34). Personal forecast: `useBreadcrumbs.ts` (25-51) → `lib/breadcrumbs.ts` (`learn` 26-36, `forecast` 47-55, `readiness` 60-63).
5. Offline serving:
   - `frontend/src/sw.ts` (13-23) for `/app/`; `pack.ts:registerPackProtocol` (30-45) serves our tiles;
   - `frontend/map/public/sw.js` (`fromPack` 49-56, `networkFirst` 58-72) for the map app;
   - offline, `components/MapView.tsx` uses our own style when the server cannot be asked.
6. Experiment: `weak_signal.experiment.cjs:oneRun` (85-149, throttling the service worker too, 40-78) → `core/networking/prefetch/results.py:build` (111-137; `energy_rows` 52-74 via `core/networking/v2x/energy.py:bartendr` 25-50) → `results/networking/prefetch/summary.json`.

**Upstream**
- **Copied:**
  - `frontend/public/liberty/`: OpenFreeMap style `cf9e8e72…`, BSD-3; source, sprite and glyph URLs changed (SOURCES.md:71).
  - `frontend/public/fonts/`: Noto glyphs from maplibre/demotiles (:72; two ranges added 2026-10-10 at `601ae607…`).
- **Unchanged:** Workbox 7.4.1, MIT (:73); PMTiles 4.5.0 (:20); Planetiler (:70). Bartendr and BreadCrumbs are papers only (:67, :68).
- **Ours:** `pack.ts`, `schedule.ts`, `breadcrumbs.ts`, `packAssets.ts`, `basemap.ts`, `sw.ts`, `features/today/*`, `core/networking/prefetch/results.py`, `core/networking/v2x/energy.py`, the test scripts.

**Questions**
- *Show me Bartendr's scheduling.* → `frontend/src/lib/schedule.ts:24-50`; the energy is ESTIMATED from Bartendr's Palm Pre figures (`:5-6`). In our runs it equals "download now" (9 of 9 rows).
- *How was 7.4 s vs 0.8 s measured; is the service worker throttled too?* → `frontend/tests/weak_signal.experiment.cjs:34-44` and `:113-123`.
- *What exactly works offline?* → `frontend/src/sw.ts:13-23`, `frontend/map/public/sw.js:58-72`; the check is `evidence/offline_home/offline_home_check.json` (6 of 6).

## 8. Crash detection on the phone (RQ6, WreckWatch rule)

**What Sir sees**
- Emergency page, "Crash SOS" (TEST): Arm, or replay one of three traces.
- A live 10-second graph of acceleration in g, with a red 4 g line.
- A jolt starts a 15-second countdown, then the alert path: detected → countdown → network or mesh → never sent.
- Traces:
  - normal ride: peak 1.54 g, not detected;
  - hard brake: peak 2.03 g, not detected;
  - crash jolt: **peak 6.37 g**, detected at 12.04 s (5.87 g when the rule fired).

**Run**
- Build the traces and results: `PYTHONPATH=.:backend python -m core.safety.sos build`.
- Live: `LOCAL_URL=http://127.0.0.1:8011/ node frontend/tests/live/sos_graph.cjs` (step 7 of `make present`).
- Web: `/app/emergency`; map trip SOS button.

**Data flow**
1. `core/safety/sos.py:synthetic` (59-74) generates the traces (50 Hz, 30 s, seed 7).
2. `sos.py:build` (82-104) writes the traces and `SHA256SUMS`, runs `detect` (43-56; `peak_g` is the true peak, `at_g` the value that fired the rule), and writes `evidence/sos/results.json`.
3. `backend/app/emergency/router.py`: `sos_results` (76-79), `sos_trace` (82-88).
4. `frontend/src/features/emergency/useMotion.ts:useMotion` (12-75) takes the sensor (26-38) or a replayed trace (53-72) → `sos.ts:isJolt` (14) and `reduce` (34-43).
5. `MotionGraph.tsx` (10-35); `SosCard.tsx` (23-87; countdown 68-73).
6. Path: `router.py:sos_path` (91-94) → `sos.path_steps` (119-143); `sos_test` (97-100) → `sos.raise_test` (146-161), kept in memory only, TEST. Since tonight a button press is tagged "button".
7. Map app: `frontend/src/maplink/index.ts:armCrashDetector` (112-141) → `frontend/map/src/traffictwin/tt.ts:armSos` (127-145).

**Upstream**
- **Copied:** none.
- **Unchanged:** the browser's DeviceMotion API.
- **Ours:** all of the above. WreckWatch (White et al. 2011) is a paper; the 4 g rule and speed floor were read from it, and the acoustic signal is not implemented (SOURCES.md:58).

**Questions**
- *Where is the rule; peak vs firing value?* → `core/safety/sos.py:43-56` (threshold :51, speed floor :53, `at_g` :54, `peak_g` :56).
- *Why 4 g, and is the speed floor used?* → `sos.py:25-28`. Every trace has `speed_checked: false` (no speed in the trace, `sos.py:94`).
- *Is anything sent?* → `sos.py:146-161` (in memory only) and `:119-143` (the number is shown, never dialled).

## 9. Hospital reach (isochrones)

**What Sir sees**
- Emergency page: the share of Dhaka's grid within 10, 20 and 30 minutes of the nearest hospital: **9.7 / 27.7 / 45.9 %** (2610 points, 500 m grid, 37 hospitals with an emergency department).
- Pick a hospital to draw its isochrones; click to list the nearest hospitals.
- The map app has a hospitals chip.

**Run**
- `PYTHONPATH=.:backend python -m core.safety.reach build --city dhaka --at 08:30` (needs `TRAFFICTWIN_VALHALLA_URL_DHAKA`).
- Valhalla: `infra/valhalla/launch.sh` (AWS, Dhaka on :8002).

**Data flow**
1. `infra/valhalla/user-data.sh` (16-34) runs `valhalla-scripted:3.9.0` on the Geofabrik extract.
2. `core/safety/reach.py:build` (125-179) → `chosen_hospitals` (60-70), `grid` (45-57) → `core/simulation/routing/valhalla.py:matrix` (156-178) → Valhalla `/sources_to_targets`.
3. Recorded variant: `recorded_sites` (73-88), per-site delta (139-146), `decompose` (91-105).
4. `_best` and `plain_numbers` (112-122) write `results/reach/dhaka/summary.json`.
5. API, `backend/app/emergency/router.py`:
   - `get_reach` (47-51; saved build);
   - `get_isochrone` (63-73) → `valhalla.isochrone` (141-153);
   - `get_nearest` (54-57) → `reach.nearest` (192-206).
6. `frontend/src/features/emergency/ReachCard.tsx` (18-69), `ReachMap.tsx` (16-65). Map app: `TtHospitals.vue:toggle` (98-117).

**Upstream**
- **Copied:** none.
- **Unchanged:** `ghcr.io/valhalla/valhalla-scripted:3.9.0`, MIT (`infra/valhalla/launch.sh:19`; SOURCES.md:184), pinned by tag, not digest.
- Request shape and colours only from gis-ops valhalla-app `439ea98f`, MIT (:50).
- **Ours:** `core/safety/reach.py`, `valhalla.py`, `router.py:47-73`, `ReachCard.tsx`, `ReachMap.tsx`, `reach.ts`, `TtHospitals.vue`, `infra/valhalla/*`.

**Questions**
- *How is "reached within 20 min" computed?* → `core/safety/reach.py:108-122` and `:45-57` (500 m grid, `STEP_M` :30).
- *Why is the recorded variant identical?* → `reach.py:139-150`. The two sites' corrections are only 8.0 s and 13.1 s on 62.5 m and 89.2 m stretches, so no grid point crosses a 10, 20 or 30-minute line. This is not yet written in the results ("Not analysed").
- *Is it live traffic?* → No. `core/simulation/routing/valhalla.py:27` (`TIME_SOURCE = "map speeds, not live traffic"`), `:141-153`.

## 10. Map app navigation (Headway, travelmux, Valhalla, Ferrostar)

**What Sir sees**
- At `/`, Headway's map app: search, place card, Directions with 2–3 alternatives, Start or "Try simulated" ×8.
- Ferrostar turn-by-turn banner, km and minutes (Bangla when the app is Bangla), "Trip saved for weak signal (N MB)", SOS button.
- Hosted QA: 48 pass, 0 fail (`evidence/qa/mapflow/`).

**Run**
- `make app`, then `/`. The map app is built with `quasar build` (`frontend/map/package.json:15`). Its bundle of our shared code is built with `vite build --config vite.maplink.config.ts`.
- QA: `HOSTED_URL=… node frontend/tests/qa/mapflow.cjs`.

**Data flow**
1. Search: Headway `SearchBox` → `/pelias/v1/*` → `backend/app/routing/headway_adapter.py:_search` (209-225; Photon, Nominatim). Style: `map_style` (136-145).
2. Directions: `frontend/map/src/models/Trip.ts:fetchBestTrips` (457-494) → `services/TravelmuxClient.ts:fetchPlans` (326-377) → `headway_adapter.py:travelmux_proxy` (268-288; `city_at` 70-82) → travelmux container → that city's Valhalla (`infra/app/setup.sh:45-52`).
3. Start: `AlternatesPage.vue:27-33` / `StepsPage.vue:24` → `traffictwin/TtStart.vue:go` (52-64) → `traffictwin/tt.ts:startTrip` (52-112) → `/tt/maplink.js`.
4. Navigation: `frontend/src/maplink/index.ts:startNavigation` (42-95) uses `FerrostarCore`, endpoint `/api/navigate/{city}/route` (46); Bangla banners (59); saves the trip for weak signal.
5. `backend/app/routing/router.py:navigate_route` (217-239) forwards Ferrostar's body unchanged (car or motorbike only, 213) → Valhalla `/route`.
6. Trip screen: `index.ts:62-75` → `tt.ts` `onState` (90-103) → `TtTrip.vue` (94-140), `armSos` and `pollAlerts` (`tt.ts:127-174`).

**Upstream**
- **Copied and edited in place:** Headway web frontend `d0b994e5…`, Apache-2.0 (SOURCES.md:99, `frontend/map/NOTICE`). 13 upstream files carry "TrafficTwin change":
  - `index.html`, `quasar.config.ts`;
  - `src/boot/i18n.ts`, `src/css/quasar.variables.scss`, `src/i18n/index.ts`, `src/utils/Config.ts`;
  - `src/components/{BaseMap,PlaceCard}.vue`, `src/layouts/MainLayout.vue`;
  - `src/pages/{BaseMapPage,AlternatesPage,StepsPage}.vue`, `src/models/ShieldQa.test.ts`.
- **Unchanged:**
  - travelmux `sha256:7b57fa04…`, Apache-2.0 or MIT (`infra/app/setup.sh:47`);
  - Valhalla 3.9.0;
  - Ferrostar 0.57.0, BSD-3 (SOURCES.md:80, :106-109);
  - Headway style `basic-v3` (:101), changed at serve time.
- **Ours ("TrafficTwin addition"):**
  - `frontend/map/src/traffictwin/*`, `src/boot/tt.ts`, `src/css/traffictwin.scss`, `src/i18n/{bn/*,en-US/tt.ts}`, `public/sw.js`;
  - also `frontend/src/maplink/index.ts`, `backend/app/routing/headway_adapter.py`, `router.py:213-239`, `frontend/tests/qa/mapflow.cjs`.

**Questions**
- *What did you change in Headway?* → `frontend/map/UPSTREAM.md:10-32` and `frontend/map/src/pages/BaseMapPage.vue:1-36`. The diff in `evidence/design/headway_reproduce/traffictwin_changes.patch` is older than tonight.
- *Is the route altered?* → `backend/app/routing/router.py:217-239` (Ferrostar's body forwarded unchanged) and `headway_adapter.py:268-288`.
- *What is Ferrostar's and what is ours?* → `frontend/src/maplink/index.ts:26-33` (Ferrostar's config), `:42-95` (our endpoint, Bangla banners, its voice off), and `frontend/map/src/traffictwin/tt.ts:52-112`.

---

## Known gaps a reviewer may find (gaps 1-4 answered in the docs on 2026-10-11; the code is unchanged)

1. **Crash detection naming.** `frontend/src/features/emergency/sos.ts:17-25` `detect()` does not return `at_g` as the Python one now does. The value that fired the rule (`joltG`) is still sent as `peak_g` to the alert path (`SosCard.tsx:35-36`, `tt.ts:138` → `sos.py:130,158`). **Answer (docs only):** the browser has both numbers: `reduce` keeps `peakG` (running peak) and `joltG` (the sample that fired the rule), and the trace `detect()` returns the true peak with `at_s`; only the alert request's field name is wrong: it carries the firing value under `peak_g`. The number is right, the label is not; the field name is kept so saved results and the API stay readable. `features/crash-detection/README.md` says this under Honest limits.
2. **Headway counts.** `third_party/SOURCES.md:99` said 9 changed files; now the grep count (12). `UPSTREAM.md` "Files added" now lists `TtForecast.vue`, `TtSimulation.vue`, `ttSim.ts` and `ttReach.ts`. Was: `headway_adapter.py:1-2` says "vendored unchanged". `UPSTREAM.md` "Files added" omits `TtForecast.vue`, `TtSimulation.vue` and `ttSim.ts`.
3. **Live twin Chronos path.** `SOURCES.md:207` now names `online.py` (was: it said the live twin's Chronos goes through `adapters/chronos_adapter.py`; `core/ml/forecasting/live/online.py:47-56` calls `BaseChronosPipeline` directly, with the same pinned revision).
4. **sumo-rl venv name.** `SOURCES.md:157` now names `sumo-rl-np1` (was `~/.dhakaflow/venvs/sumo-rl`); the live run uses `sumo-rl-np1` (`rl_signals.py:4`). Both exist.
5. **Web differences from the terminal:**
   - the web V2X job always uses `alert_preemption` (`core/simulation/live_jobs/jobs.py:113`);
   - `--veins` ignores `--tech` (802.11p only, `run_v2x.py:137-138`);
   - mesh and signals do not run on the hosted server (no PONS / sumo-rl there).
6. **Reach recorded variant.** Equal to map speeds, explained in feature 9 above but not yet in the results.
7. **Unused endpoint.** `/api/mesh/replay/{city}` exists (`core/networking/mesh/map_replay.py`), but no page calls it.
8. **Live twin not in `make present`.** `make run-twin` (2026-10-11) opens it; it is still not one of `present`'s timed steps.
