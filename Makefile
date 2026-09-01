# DhakaFlow rebuild — every result is one target. `make results` regenerates all tables.
PY ?= python
SEEDS ?= 11,12,13
HORIZON ?= 3600

.PHONY: all data predict route network nlp results clean

all: results

data:            ## twin sensor dataset (Dhaka R1, 250 sensors, 5-min) -> predict/data/dhaka_twin
	$(PY) predict/make_twin_dataset.py --seeds $(SEEDS)

predict:         ## forecast -> SUMO weight tables (route/weights/*.xml)
	$(PY) predict/forecast_to_weights.py --source oracle --seeds $(SEEDS) --horizon $(HORIZON)

route:           ## all routing arms x paired seeds -> route/results/arms.json
	$(PY) route/run_arms.py --seeds $(SEEDS) --horizon $(HORIZON)
	$(PY) route/stats.py

network:         ## MOSAIC V2X penetration sweep -> network/results/penetration.csv
	$(PY) network/penetration_sweep.py

nlp:             ## incident-text classifier + event feed -> nlp/results/
	$(PY) nlp/train_classifier.py
	$(PY) nlp/event_feed.py --demo

results: route nlp ## collect every table into results/RESULTS.md
	$(PY) results/build_results.py

clean:
	rm -rf route/results/*_s*_h* predict/results/* network/results/* nlp/results/*
