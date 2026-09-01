# Project Structure

This repository has two layers:

1. **Existing DhakaFlow source code**: reusable package code, research modules,
   scripts, frozen network assets, tests, and evidence.
2. **120-hour rebuild layer**: a small, clear execution surface for the current
   thesis goal: traffic prediction + predictive route optimization + V2X/NLP
   evidence.

The rebuild layer does not replace the existing project. It imports and reuses
the existing project so the thesis can be understood and reproduced quickly.

## Read First

| File | Purpose |
|---|---|
| `README.md` | one-page project overview |
| `PROJECT_MAP.md` | fast map of active code paths |
| `docs/REBUILD_120H_PLAN.md` | 5-day execution plan |
| `docs/KEYS_AND_COMPUTE.md` | required keys, Colab/Drive/AWS setup, and secret rules |
| `results/RESULTS.md` | every result, command, and evidence file |
| `docs/ASSET_MANIFEST.md` | checksums for evidence assets restored by `download_assets.sh` |
| `docs/CURRENT_SYSTEM_GAP_AUDIT.md` | known weaknesses and honesty limits |

## Canonical Source Trees

| Path | Role | Modify? |
|---|---|---|
| `dhakaflow/` | main Python package: shared interfaces, services, registries, labels | yes, for reusable platform fixes |
| `research/` | experiment implementations: twin, forecasting, routing, control, perception, networking | yes, for algorithm fixes |
| `scripts/` | runnable gate/demo commands around the older DhakaFlow pipeline | yes, only when the old gate path is needed |
| `paper_labs/` | frozen foundation labs and real Dhaka R1 SUMO network | do not edit except with a deliberate freeze update |
| `configs/` | subsystem configuration | yes |
| `tests/` | architecture and platform tests | yes |
| `artifacts/` | evidence outputs, small manifests, generated run records | add small evidence only; keep large files out of git |
| `archive/` | old scaffolds and historical material | read-only unless explicitly reviving something |
| `upstream/` | manifests only; official repos live outside the repo | do not vendor upstream code here |

There must be no top-level `src/`. The source package is `dhakaflow/`.

## Active Rebuild Layer

| Path | Owns | Reuses |
|---|---|---|
| `predict/` | twin sensor dataset, forecasting floors, forecast-to-SUMO weights | `research/twin/sensor_graph.py`, `research/forecasting/*`, BasicTS pins |
| `route/` | static/reactive/predictive/DUE/DSO routing arms and paired-seed stats | `research/routing/r1_router.py`, SUMO, `artifacts/gates/routes_repeat_1h.rou.xml.gz` |
| `network/` | MOSAIC V2X penetration and latency/loss sweeps | `artifacts/mosaic_dhaka/dhaka_r1`, `research/networking/v2x_bus.py` |
| `nlp/` | incident text classifier and event-to-edge weight injection | `dhakaflow/nlp`, R1 edge mapping, routing weight format |
| `demo/` | presentation demo using generated results | `predict/`, `route/`, `network/`, `nlp/` outputs |
| `results/` | final result index and generated summary tables | all active modules |
| `paper/` | thesis chapters, slides, speaker notes | `results/RESULTS.md` |
| `model_registry/` | metadata-only model registry | remote checkpoints only |
| `dashboard/` | lightweight dashboard source/stub | generated heavy dashboards stay in `artifacts/` |
| `deployment/` | deployment manifests | pinned runtime versions |

## How The Existing Project Will Be Fixed

| Existing issue | Fix direction | Files |
|---|---|---|
| Reader cannot find the project entrypoint | Use `README.md`, `PROJECT_MAP.md`, and this file as the navigation surface | `README.md`, `PROJECT_MAP.md`, `docs/PROJECT_STRUCTURE.md` |
| Too many old gates and scripts | Keep them, but make the rebuild layer the active thesis path | `predict/`, `route/`, `network/`, `nlp/`, `demo/` |
| Forecasting result not easy to reproduce | Put forecasting commands and tables behind `make predict` and `results/RESULTS.md` | `predict/`, `Makefile`, `results/` |
| Route optimization mixed with older demos | Put the paired-seed routing harness in one place | `route/predictive_routing.py`, `route/run_arms.py`, `route/stats.py` |
| Large generated files tracked in git | Keep heavy outputs on disk/Drive/S3, remove from git index, add ignore rules | `.gitignore`, `artifacts/`, `results/` |
| Claims can overreach the evidence | Keep labels: simulated Dhaka twin, provider integration, live reference only | docs, result JSON, model registry |

## Git Policy

Track:

- source code
- configs
- small JSON/CSV/Markdown evidence
- manifests with sha256 hashes
- notebooks needed to reproduce cloud jobs

Do not track:

- model weights
- raw datasets
- large SUMO XML/FCD outputs
- generated movies
- large embedded HTML reports
- API keys or `.env`

Large assets belong in Drive/S3/GCS with a checksum and a download step.

## Asset Bootstrap

`download_assets.sh` is the safe restore/check entrypoint. It never calls Google
Routes or spends API quota. With no environment variables it verifies the assets
already present in the clone. With `DHAKAFLOW_ASSET_ROOT=/path/to/DhakaFlow-assets`
it copies missing files from a local Drive/S3/GCS export that mirrors repository
relative paths, then verifies sha256 checksums from `docs/ASSET_MANIFEST.json`.

Regenerate the manifest only after producing a new accepted evidence set:

```bash
python scripts/build_asset_manifest.py
```

## Main Commands

```bash
python scripts/build_asset_manifest.py
bash download_assets.sh
PYTHONPATH=. pytest tests/platform/test_interfaces.py tests/platform/test_repo_architecture.py -q
make route
make nlp
make results
```

For the 5-day rebuild, `make results` is the main evidence index command. It
does not run simulations or spend API quota. Use `make local-results` for local
non-billed regeneration, and `make live-capture` only when a live Google
reference capture is intended. Older gate commands under `scripts/` remain
available for appendix evidence.
