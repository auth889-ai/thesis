# Lab 02 — Real Dhaka OSM → Validated SUMO Network

**Goal:** a reproducible, validated SUMO network of a real central-Dhaka
corridor (Farmgate–Karwan Bazar–Bangla Motor–Shahbagh box) — the geographic
foundation of the later calibrated digital twin. Original DhakaFlow module on
official OSM + SUMO tooling. **No API key required.**

Start with `LEARNING_GATE.md` (17 concepts in dependency order), then
`METHOD_SPEC.md` (pipeline + pre-registered pass thresholds).

## Layout (implementation lives in src/, notebooks orchestrate)

- `src/osm/` Overpass acquisition with provenance manifest
- `src/network/` netconvert wrapper + warning classifier
- `src/validation/` censuses, Kosaraju SCC connectivity, TLS safety checks,
  representative O-D routing
- `src/demand/` seeded randomTrips → duarouter (error census) → deterministic run
- `src/metrics/` tripinfo/summary summaries
- `src/visualization/` network + junction-zoom figures
- `scripts/run_lab02.py --config configs/{smoke,full}.yaml` end-to-end
- `tests/` unit (SUMO-free) + integration (tiny handcrafted OSM fixture,
  runs wherever SUMO exists — full gate runs in Colab)

## Execution policy

Mac/git: code, configs, manifests, lightweight evidence. Colab: all heavy
execution (pinned `eclipse-sumo==1.27.1`). Drive
(`DhakaFlow-Nexus-Data/Lab02_DhakaOSM/`): raw OSM extract, full outputs.

## Reproduce

1. `python3 -m pytest tests -q`
2. `bash scripts/make_colab_zip.sh` → upload zip to Drive `Lab02_DhakaOSM/`
3. Open `notebooks/Lab02_DhakaOSM_Colab.ipynb` in Colab → Run all
4. Evidence bundle returns to `outputs/`; REPRODUCTION_REPORT completed from it.
