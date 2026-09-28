# DhakaFlow — every result, one target each. `make` with no argument lists them.
#
# The four experiments below are the thesis. Each reads real inputs, runs the real chain and writes
# results/<area>/<name>.json; `make figures` draws those files and nothing else.
PY    ?= python
SEEDS ?= 11,12,13,14,15
H     ?= 1800

.DEFAULT_GOAL := help
.PHONY: help status test app canonical canonical-package backtest chain ablation coverage sweep sweep-v2x opencity-smoke opencity figures results all clean-runs

help:            ## list targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-12s %s\n", $$1, $$2}'

status:          ## what exists, what is real, what is missing
	$(PY) main.py status

test:            ## the test suite: pipeline + backend API (~1 min, no SUMO, no live API)
	$(PY) -m pytest -q

app:             ## the dashboard on http://127.0.0.1:8000
	$(PY) -m uvicorn backend.app.main:app --host 127.0.0.1 --port $(or $(PORT),8000)

canonical:       ## oracle-first canonical closed-loop evaluation, then package log-derived evidence
	$(PY) experiments/closed_loop/canonical.py --execute --stage oracle

canonical-package: ## package the frozen canonical evidence without rerunning SUMO
	$(PY) experiments/closed_loop/canonical.py

# ---------------------------------------------------------------- the four experiments
backtest:        ## E1 how accurate is the forecast on Dhaka's own recorded data (rolling origin, ~15 s)
	$(PY) src/pipeline/forecasting/live_backtest.py

chain:           ## E2 forecast -> edge costs -> routing -> SUMO, three arms, paired seeds (~1 min)
	$(PY) src/pipeline/routing/integrated_chain.py --seeds $(SEEDS) --horizon $(H) --as-of peak --tag _ideal

ablation:        ## E3 does forecast QUALITY reach the road: oracle / model / persistence / random (~5 min)
	$(PY) src/pipeline/routing/forecast_quality_ablation.py --seeds $(SEEDS) --horizon $(H)

coverage:        ## E5 is pricing COVERAGE the bottleneck: model vs noise at 0 / 3 / 8 hops (~10 min)
	$(PY) src/pipeline/routing/forecast_quality_ablation.py --seeds $(SEEDS) --horizon $(H) \
	    --hops 0,3,8 --conditions Chronos-Bolt,random --out results/routing/ablation_coverage.json

sweep:           ## E4 penetration curve: compliance 0..100 % x seeds (~10 min)
	$(PY) src/pipeline/routing/chain_sweep.py --grid compliance --seeds $(SEEDS) --horizon $(H)

sweep-v2x:       ## E4b V2X condition x compliance heatmap (~45 min)
	$(PY) src/pipeline/routing/chain_sweep.py --grid v2x --compliance 0.1,0.2,0.4 --seeds $(SEEDS) --horizon $(H)

opencity-smoke:  ## OpenCity-plus forward pass through the authors' harness on this CPU (12-node slice, ~2 min)
	$(PY) src/pipeline/forecasting/opencity_city_eval.py --source metrla-smoke

train-city:      ## E7 train the official STID baseline on an uploaded / observed city through the pinned BasicTS harness (CPU)
	$(PY) src/pipeline/forecasting/basicts_train.py --dataset $(or $(DATASET),user:los_angeles_two_weeks) --arch $(or $(ARCH),STID) --epochs $(or $(EPOCHS),30)

train-city-gpu:  ## E7 on an AWS spot GPU (g5.xlarge): same harness, 100 epochs; the app's "run on: AWS GPU" does this
	$(PY) src/pipeline/forecasting/aws_train.py --launch --city-dataset $(or $(DATASET),user:los_angeles_two_weeks) --models $(or $(ARCH),STID) --epochs $(or $(EPOCHS),100) --allow-on-demand --max-hours 1
	@echo "watch: $(PY) src/pipeline/forecasting/aws_train.py --status --job city-...; collect: --collect-city city-..."

opencity:        ## E6 OpenCity-plus zero-shot on the persisted live window (needs ~4 days of observation)
	$(PY) src/pipeline/forecasting/opencity_city_eval.py --source observatory --city dhaka

figures:         ## F1-F5 from the JSON evidence -> results/figures/
	$(PY) src/pipeline/results/make_figures.py

results:         ## audit every evidence file and rebuild results/RESULTS.md (no simulation)
	$(PY) results/evidence_audit.py
	$(PY) results/build_results.py

all: backtest chain ablation coverage sweep figures results   ## everything above, in order (~30 min)

clean-runs:      ## remove per-run SUMO outputs (the JSON summaries stay)
	rm -rf results/routing/runs/chain_*
