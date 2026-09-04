# Reproduce every number

Fresh clone, Python 3.11+, SUMO 1.27 on PATH, `pip install -r requirements.txt`.
The Dhaka network ships as a 2 MB `.gz` and expands on first use; the recorded live series is in
`artifacts/live_dhaka/`. No API key and no GPU are needed for anything below.

| # | Claim in the thesis | Command | Evidence written | Time |
|---|---|---|---|---|
| E1 | 15-min class accuracy 87 %; the foundation model does **not** beat persistence on Dhaka (skill −23 %) | `make backtest` | `results/forecasting/live_backtest.json` | 15 s |
| E2 | The full chain: real forecast → 79 priced edges → duarouter → 3 SUMO arms, paired seeds, run id | `make chain` | `results/routing/runs/<run_id>/run.json`, `results/routing/integrated_chain_ideal.json` | 1 min |
| E3 | Chronos and random noise route **identically** (0 vehicles differ); pricing coverage, not the model, is the bottleneck; oracle −2.2 % | `make ablation` | `results/routing/ablation_forecast_quality.{json,md}` | 5 min |
| E4 | Pre-departure rerouting helps at 10–20 % penetration (−2.7 %, 5/5 seeds) and hurts above 40 % | `make sweep` | `results/routing/sweep_compliance.json` | 10 min |
| E5 | Is pricing coverage the bottleneck: the same model vs noise with the forecast propagated 0 / 3 / 8 hops from the observed corridors | `make coverage` | `results/routing/ablation_coverage.{json,md}` | 10 min |
| F | Figures F1–F4 | `make figures` | `results/figures/*.png` | 5 s |
| — | 291 tests | `make test` | — | 1 min |

Benchmark validation on public data (GWNet within 2 % of published on METR-LA / PEMS-BAY;
OpenCity reproduced on PEMS07M / TrafficSH) is regenerated on Colab — see `notebooks/` and
`results/forecasting/phase1_comparison.json`. Pinned upstreams: `upstream/UPSTREAM_PINS.yaml`.

Pre-rebuild claims and their commands (pNEUMA, I-70, MOSAIC gates) are kept in
`docs/REPRODUCE_2026-08_pre-rebuild.md`; those scripts were retired to `legacy/`.
