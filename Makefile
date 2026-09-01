# DhakaFlow rebuild command surface.
#
# `make results` only aggregates existing evidence into results/RESULTS.md.
# `make local-results` regenerates local, non-billed evidence.
# `make live-capture` deliberately spends a small number of Google API requests.
PY ?= python
SEEDS ?= 11,12,13
HORIZON ?= 7200

.PHONY: all data predict route network nlp live-advice live-advice-real live-summary live-capture results local-results clean

all: results

data:            ## twin sensor dataset (Dhaka R1, 250 sensors, 5-min) -> predict/data/dhaka_twin
	$(PY) predict/make_twin_dataset.py --seeds $(SEEDS)

predict:         ## forecast -> SUMO weight tables (route/weights/*.xml)
	$(PY) predict/forecast_to_weights.py --source oracle --seeds $(SEEDS) --horizon $(HORIZON)

route:           ## all routing arms x paired seeds -> route/results/arms.json
	$(PY) route/run_arms.py --seeds $(SEEDS) --horizon $(HORIZON)
	$(PY) route/stats.py --horizon $(HORIZON)
	$(PY) route/decision_guard.py --horizon $(HORIZON)

network:         ## MOSAIC V2X penetration sweep -> network/results/penetration.csv
	$(PY) network/penetration_sweep.py

nlp:             ## incident-text classifier + event feed -> nlp/results/
	$(PY) nlp/train_classifier.py
	$(PY) nlp/event_feed.py --demo

live-advice:     ## free fixture route-advisor smoke; no API calls
	$(PY) live/route_advisor.py --dry-run --corridor farmgate_to_shahbagh --out live/results/route_advice_fixture.jsonl

live-advice-real: ## one real Google Routes advisory; stores compliant metadata only
	$(PY) live/route_advisor.py --live --yes --corridor farmgate_to_shahbagh --out live/results/route_advice.jsonl

live-summary:    ## summarize compliant runtime-reference records; no API calls
	$(PY) predict/summarize_live_reference.py

live-capture:    ## deliberate billed live reference capture, then summarize
	$(PY) predict/run_live_capture.py
	$(PY) predict/summarize_live_reference.py

results:         ## audit and collect existing tables into results/RESULTS.md; no simulations/API calls
	$(PY) results/evidence_audit.py
	$(PY) results/build_results.py

local-results: data predict route network nlp live-summary results

clean:
	rm -rf route/results/*_s*_h* predict/results/* network/results/* nlp/results/*
