# DhakaFlow — every result, one target each. `make` with no argument lists them.
#
# The four experiments below are the thesis. Each reads real inputs, runs the real chain and writes
# results/<area>/<name>.json; `make figures` draws those files and nothing else.
PY    ?= python
export PYTHONPATH := backend
SEEDS ?= 11,12,13,14,15
H     ?= 1800

.DEFAULT_GOAL := help
.PHONY: prefetch-masts aid-incidentnet sweep-sos help status test openapi mobile-install mobile-start web-install web-dev web-build web-test app canonical canonical-package backtest chain ablation coverage sweep sweep-v2x opencity-smoke opencity figures results all clean-runs fetch-data offload-verify check demo-ambulance demo-forecast demo-mesh run-v2x run-sos-v2v run-mesh run-signals run-forecast run-offline present

check:           ## supervisor demo kit: is this laptop ready? (offline; prints the fix for each failure)
	@$(PY) scripts/demo/check.py

demo-ambulance:  ## demo: SUMO window, ambulance on the Dhaka corridor without and with the V2X alert, same seed (~1.5 min)
	@$(PY) scripts/demo/ambulance.py

demo-forecast:   ## demo: one figure, forecast error against "no change" in Los Angeles and Dhaka, and Dhaka's stop-and-go (saved results)
	@$(PY) scripts/demo/forecast.py

demo-mesh:       ## demo: phone-to-phone alerts, delivery against number of phones, three protocols (PONS, seconds)
	@research/mesh_pons/.venv/bin/python -W ignore scripts/demo/mesh.py

run-v2x:         ## LIVE RQ3: ambulance + V2X alert in sumo-gui, computed now; ARGS="--tech c_v2x --share 0.5 --seed 12 --level x2" (docs/LIVE_RUNS.md)
	@$(PY) scripts/live/run_v2x.py $(ARGS)

run-v2x-live:    ## LIVE RQ3 with the viewer's own values: SEED=<n> (default: the clock) FROM=<edge|random> TO=<edge|random> DEMAND=current|dhatrax-peak; prints seed, route, demand and the result
	@$(PY) scripts/live/run_v2x.py --gui-colours --seed $(or $(SEED),clock) --from $(or $(FROM),random) --to $(or $(TO),random) --demand $(or $(DEMAND),current) $(ARGS)

run-sos-v2v:     ## LIVE: a crash on the Dhaka corridor, SOS rule + car-to-car warning and reroute in sumo-gui; ARGS="--share 0.2 --tech c_v2x --seed 12"
	@$(PY) scripts/live/run_sos_v2v.py $(ARGS)

aid-train:       ## AID (step J): 5 training seeds in SUMO, 30 s station rows -> data/aid/train.csv, HistGradientBoosting model + California #7 thresholds -> results/aid/
	@PYTHONPATH=.:backend $(PY) scripts/aid/aid.py train $(ARGS)

aid-eval:        ## AID: 5 held-out seeds on unseen station pairs: detection rate, time-to-detect, false alarms/h (model and California #7), trip time with vs without the closed loop -> evidence/aid/summary.json
	@PYTHONPATH=.:backend $(PY) scripts/aid/aid.py eval $(ARGS)

aid-frontier:    ## AID frontier: detection rate vs false alarms over the thresholds (loop model, California #7, J2 camera model) at Dhaka density (saved rows) and x0.3 (new runs) -> evidence/aid/frontier/
	@PYTHONPATH=.:backend $(PY) scripts/aid/aid.py frontier $(ARGS)

aid-gui:         ## AID LIVE: sumo-gui with the trained model: station pairs green/yellow/red (normal/tentative/alarm), incident red, warned yellow, rerouted blue; counter of detections and false alarms; ARGS="--seed 12"
	@PYTHONPATH=.:backend $(PY) scripts/aid/aid.py gui $(ARGS)

aid-incidentnet: ## AID J3-A: IncidentNet's own XGBoost detection code (third_party/incidentnet, Apache-2.0, unchanged) on our camera rows, their random row split and our held-out seeds side by side -> evidence/aid/frontier/incidentnet.{json,png}; not a reproduction
	@PYTHONPATH=.:backend $(PY) scripts/aid/incidentnet_xgb.py $(ARGS)

prefetch-masts:  ## RQ5 Q3: weak-signal profile of the real Dhaka route from real OpenStreetMap mast positions + 3GPP UMa path loss (assumed EIRP), energy of the three schedules on it -> evidence/prefetch/masts/ (seconds); ARGS="--fetch" refreshes the masts from Overpass
	@PYTHONPATH=.:backend $(PY) -m core.networking.prefetch.masts $(ARGS)

sweep-v2x:       ## LIVE RQ3 sweep: V2X share 0/25/50/75/100 % x 5 seeds at Dhaka density, each run checked against the saved study -> evidence/sweeps/ (CSV + plot, ~10 min); ARGS="--quick" = 2 seeds (~4 min)
	@PYTHONPATH=.:backend $(PY) scripts/live/sweep_v2x.py $(ARGS)

compare-signals: ## RQ3 signals, headless: fixed time, Q-learning, Max-Pressure, Max-Pressure + EV priority on the same 5 seeds -> evidence/signals/controllers/ (CSV, PNG, JSON); ARGS="--quick" = 2 seeds
	@PYTHONPATH=.:backend $(PY) scripts/live/compare_signals.py $(ARGS)

sweep-sos:       ## crash SOS car to car, headless: app share 25/50/75/100 % x crash at 600/900 s x 5 seeds, each paired with the no-warning twin -> evidence/sos/sweep/ (CSV, PNG, JSON, ~25 min); ARGS="--quick" = 2 seeds, crash at 600 s (~5 min); no thesis number
	@PYTHONPATH=.:backend $(PY) scripts/live/sweep_sos.py $(ARGS)

gui-routing:     ## Part D (2026-10-12): RQ2 forecast routing LIVE in sumo-gui (LA twin, loop unchanged): connected yellow, uplink flash green, rerouted blue, lost downlink red, slow-forecast edges red; PROFILE=ideal|its-g5|c-v2x|4g (default ideal); ARGS="--minutes 15 --seed 201"
	@PYTHONPATH=.:backend $(PY) scripts/live/gui_routing.py --profile $(or $(PROFILE),ideal) $(ARGS)

demo-routing:    ## 2026-10-12: the forecast-routing loop as a two-window demo (LEFT baseline, RIGHT predictive + 4g, same fork and seed), base station, message lines, speed bands, matplotlib window, narration; ARGS="--minutes 15 --delay 120"
	@PYTHONPATH=.:backend $(PY) scripts/live/demo_routing.py $(ARGS)

run-routing-quick: ## LIVE RQ2 closed loop on the LA twin, thesis settings, checked seed by seed (2 seeds x 3 arms ~25 min); ARGS="--quick" = 1 seed, 2 arms (~6.5 min)
	@PYTHONPATH=.:backend $(PY) scripts/live/run_routing_quick.py $(ARGS)

run-sos-collide: ## LIVE: a real collision inside SUMO (one car ignores the safe-speed rules and hits the car ahead; SUMO detects it), then the car-to-car SOS path; crashed cars red; ARGS="--share 0.5 --seed 12"
	@$(PY) scripts/live/run_sos_v2v.py --collide --gui-colours $(ARGS)

run-ambulance-loop: ## Part A (2026-10-12): Q-learning signals + V2X alert + V2I pre-emption in ONE run, 4 arms x 5 seeds, ITS-G5 -> evidence/ambulance_loop/; ARGS="--seeds 11 --arms rl_v2i --tech c_v2x"
	@PYTHONPATH=.:backend $(HOME)/.dhakaflow/venvs/sumo-rl-np1/bin/python core/simulation/ambulance/rl_v2x_loop.py $(ARGS)

veins-ambulance-loop: ## Phase 1 (2026-10-12): Q-learning signals + IEEE 802.11p DENM in Veins, ONE SUMO (--num-clients 2), OMNeT++ Qtenv + sumo-gui windows (press RUN in Qtenv); SEED=<n>|clock (default 11); ARGS="--no-gui --seeds 11 12 13 14 15 --arms fixed rl rl_v2i --out evidence/veins_ambulance_loop" = the evidence run
	@PYTHONPATH=.:backend $(HOME)/.dhakaflow/venvs/sumo-rl-np1/bin/python core/simulation/ambulance/veins_loop.py --seeds $(or $(SEED),11) $(ARGS)

prove-forecast-routing: ## 2026-10-13: PROOF by running: forecast routing over Veins with a clock seed, then PASS/FAIL checks read from the run's own files (real inputs, fresh forecast per round, different seed -> different draw/moment/decisions, loop counters = Veins scalars); SEED=<n>|clock RSUS=<n>; ARGS="--minutes 10"
	@PYTHONPATH=.:backend $(PY) scripts/live/prove_forecast_routing.py --seed $(or $(SEED),clock) --rsus $(or $(RSUS),20) $(ARGS)

veins-forecast-routing: ## Phase 2 (2026-10-12): the Graph WaveNet routing server + RSUs + 802.11p in Veins on the LA twin (PRE-VE design), ONE SUMO, baseline then predictive, Qtenv + sumo-gui (press RUN twice); SEED=<n>|clock (default 201) RSUS=<n> (default 20); ARGS="--no-gui --minutes 15" -> evidence/veins_forecast_routing/<stamp>/
	@PYTHONPATH=.:backend $(PY) -m core.simulation.routing.veins_routing_loop --seed $(or $(SEED),201) --rsus $(or $(RSUS),20) $(ARGS)

gui-ambulance-loop: ## Part E (2026-10-12): the ML + V2X ambulance loop in sumo-gui (rl_v2x_loop.py unchanged): ambulance red, alerted cars yellow while making way, junction labels Q-learning / V2X override / released; ARGS="--seed 11 --arm rl_v2i"
	@PYTHONPATH=.:backend $(HOME)/.dhakaflow/venvs/sumo-rl-np1/bin/python scripts/live/gui_ambulance_loop.py $(ARGS)

run-signals:     ## LIVE RQ3 signals: fixed-time vs sumo-rl Q-learning (or ARGS="--controller maxpressure|maxpressure_ev"), two sumo-gui windows side by side; ARGS="--level x2 --seed 12"
	@$(PY) scripts/live/run_signals.py $(ARGS)

run-forecast:    ## LIVE RQ1 model: one forecast computed now (CLI); ARGS="--sensor 5 --at 2012-06-05T08:30 --model D2STGNN". Page: /app/lab/model-lab
	@PYTHONPATH=.:backend $(PY) -m core.ml.forecasting.layer.lab $(ARGS)

run-mesh:        ## LIVE RQ4: PONS phone-to-phone mesh drawn as it runs; ARGS="--protocol epidemic --phones 8 --range 30"
	@research/mesh_pons/.venv/bin/python -W ignore scripts/live/run_mesh.py $(ARGS)

gui-veins:       ## LIVE RQ3, second view: our V2X ambulance scenario in Veins under OMNeT++ Qtenv (frames animated) next to sumo-gui, alerted yellow / ambulance green; prints what to watch; ARGS="--share 0.5 --seed 2"
	@$(PY) scripts/live/run_veins.py v2x --sumo-gui --gui-colours $(ARGS)

sweep-mesh:      ## RQ4 second view: The ONE's routers (Epidemic, Spray-and-Wait, PRoPHET, MaxProp) x phones 17/50/100/200 x 3 seeds -> evidence/mesh/routers/ (CSV, PNG, JSON); ARGS="--quick" = 1 seed
	@$(PY) scripts/live/sweep_mesh.py $(ARGS)

gui-mesh:        ## LIVE RQ4, second view: The ONE's own GUI (no batch flag) on the thesis mesh setting (17 phones, 10 m, PRoPHET, seed 1); prints the legend; ARGS="--protocol epidemic --seed 3"
	@$(PY) scripts/live/run_mesh_one.py --legend $(ARGS)

run-offline:     ## LIVE RQ5: Chrome with DevTools, plan + start a trip, go OFFLINE, reopen; lists answers served by the service worker; ARGS="--rq5" adds the thesis check
	@LOCAL_URL=$${LOCAL_URL:-http://127.0.0.1:8011/} node frontend/tests/live/run_offline.cjs $(ARGS)

run-twin:        ## LIVE: the live twin in the browser (starts the app server if needed, opens /app/lab/live-twin, prints what to do)
	@$(PY) scripts/live/run_twin.py $(ARGS)

demo:            ## LIVE for the talk: every live part one after another, each started on Enter (V2X colours, Veins, signals, twin + steering, The ONE, collision, AID, Model Lab, map app); ARGS="--only v2x,veins"
	@$(PY) scripts/live/demo.py $(ARGS)

present:         ## LIVE: every feature in the order of the talk, timed (~7 min); ARGS="--only v2x,mesh" or "--dry" (docs/LIVE_RUNS.md)
	@$(PY) scripts/live/present.py $(ARGS)

help:            ## list targets
	@grep -E '^[a-z0-9-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-12s %s\n", $$1, $$2}'

status:          ## what exists, what is real, what is missing
	$(PY) -c "import json; from core.simulation.closed_loop.protocols.research_status import compute_research_status as c; print(json.dumps(c(), indent=1))"

test:            ## the test suite: pipeline + backend API (~1 min, no SUMO, no live API)
	$(PY) -m pytest -q

openapi:         ## export the API's OpenAPI document for the web and mobile clients
	$(PY) -c "from app.main import app; import json; json.dump(app.openapi(), open('frontend/openapi.json','w'), indent=1)"

mobile-install:  ## install the mobile toolchain (Expo)
	cd mobile && npm install --no-audit --no-fund

mobile-start:    ## Expo dev server (scan the QR with Expo Go; set expo.extra.apiUrl in mobile/app.json to this machine's LAN address)
	cd mobile && npm start

web-install:     ## install the web toolchain (Vite, Vitest, TypeScript, OpenAPI client generator)
	cd frontend && npm install --no-audit --no-fund

web-dev:         ## web app with live reload on http://127.0.0.1:5173 (proxies the API on :8000)
	cd frontend && npm run dev

web-build:       ## production bundle -> frontend/dist (served by the API)
	cd frontend && npm run build

web-test:        ## web unit tests (Vitest) and type check
	cd frontend && npm test && npm run typecheck

app:             ## the API + web app on http://127.0.0.1:8000 (serves frontend/dist when built, else the sources)
	$(PY) -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port $(or $(PORT),8000)

canonical:       ## oracle-first canonical closed-loop evaluation, then package log-derived evidence
	$(PY) research/closed_loop/canonical.py --execute --stage oracle

canonical-package: ## package the frozen canonical evidence without rerunning SUMO
	$(PY) research/closed_loop/canonical.py

# ---------------------------------------------------------------- the four experiments
backtest:        ## E1 how accurate is the forecast on Dhaka's own recorded data (rolling origin, ~15 s)
	$(PY) -m core.ml.forecasting.live.live_backtest

chain:           ## E2 forecast -> edge costs -> routing -> SUMO, three arms, paired seeds (~1 min)
	$(PY) -m core.simulation.closed_loop.protocols.chains.integrated_chain --seeds $(SEEDS) --horizon $(H) --as-of peak --tag _ideal

ablation:        ## E3 does forecast QUALITY reach the road: oracle / model / persistence / random (~5 min)
	$(PY) -m core.simulation.closed_loop.protocols.chains.forecast_quality_ablation --seeds $(SEEDS) --horizon $(H)

coverage:        ## E5 is pricing COVERAGE the bottleneck: model vs noise at 0 / 3 / 8 hops (~10 min)
	$(PY) -m core.simulation.closed_loop.protocols.chains.forecast_quality_ablation --seeds $(SEEDS) --horizon $(H) \
	    --hops 0,3,8 --conditions Chronos-Bolt,random --out results/routing/ablation_coverage.json

sweep:           ## E4 penetration curve: compliance 0..100 % x seeds (~10 min)
	$(PY) src/pipeline/routing/chain_sweep.py --grid compliance --seeds $(SEEDS) --horizon $(H)

opencity-smoke:  ## OpenCity-plus forward pass through the authors' harness on this CPU (12-node slice, ~2 min)
	$(PY) -m core.ml.forecasting.opencity.opencity_city_eval --source metrla-smoke

train-city:      ## E7 train the official STID baseline on an uploaded / observed city through the pinned BasicTS harness (CPU)
	$(PY) -m core.ml.forecasting.training.basicts_train --dataset $(or $(DATASET),user:los_angeles_two_weeks) --arch $(or $(ARCH),STID) --epochs $(or $(EPOCHS),30)

train-city-gpu:  ## E7 on an AWS spot GPU (g5.xlarge): same harness, 100 epochs; the app's "run on: AWS GPU" does this
	$(PY) -m core.ml.forecasting.training.aws_train --launch --city-dataset $(or $(DATASET),user:los_angeles_two_weeks) --models $(or $(ARCH),STID) --epochs $(or $(EPOCHS),100) --phase city-training --max-hours 1
	@echo "watch: $(PY) -m core.ml.forecasting.training.aws_train --status --job city-...; collect: --collect-city city-..."

opencity:        ## E6 OpenCity-plus zero-shot on the persisted live window (needs ~4 days of observation)
	$(PY) -m core.ml.forecasting.opencity.opencity_city_eval --source observatory --city dhaka

figures:         ## F1-F5 from the JSON evidence -> results/figures/
	$(PY) -m core.simulation.closed_loop.protocols.figures

results:         ## audit every evidence file and rebuild results/RESULTS.md (no simulation)
	$(PY) research/reports/evidence_audit.py
	$(PY) research/reports/build_results.py

all: backtest chain ablation coverage sweep figures results   ## everything above, in order (~30 min)

fetch-data:      ## restore the data kept off this Mac (data/MANIFEST.yaml): public data from its source, our outputs from Google Drive
	$(PY) scripts/storage/offload.py fetch

offload-verify:  ## check every file of data/MANIFEST.yaml against its Google Drive copy -> evidence/storage/verify.json
	$(PY) scripts/storage/offload.py verify

clean-runs:      ## remove per-run SUMO outputs (the JSON summaries stay)
	rm -rf results/routing/runs/chain_*
