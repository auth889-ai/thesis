# Pipeline: Transitional Research Code

This directory predates the canonical `traffictwin` package. It is neither the web
backend nor the frontend, and it is not safe to delete wholesale.
Its physical location is now `src/pipeline/`. The installed Python import name
remains `pipeline`; run `python -m pip install --no-deps -e .` once from the root.

| Directory | What remains here |
| --- | --- |
| `forecasting/` | Active BasicTS training/inference adapter, dataset preparation, and older model experiments |
| `routing/` | Compatibility imports for migrated algorithms; older routing protocols, gates, and helpers still used by experiments |
| `v2x/` | Compatibility imports for channel/controller; active network assignment, diagnostics, and gates awaiting extraction |
| `city/` | Active dataset, graph, mapping, and SUMO scenario adapters |
| `networking/` | Earlier MOSAIC-related experiment tooling, separate from the Python V2X emulator |
| `core/`, `adapters/` | Earlier shared abstractions with remaining callers; not automatically inactive |
| `live/`, `nlp/`, `federated/` | External-reference prototypes and earlier research branches; not the canonical Scenario A claim |
| `results/`, `audit/`, `upstream/` | Reporting, auditing, and upstream provenance utilities |

## Active Ownership

- Web API: `backend/app/`.
- Browser: `frontend/`.
- Canonical forecasting: `src/traffictwin/forecasting/`.
- Canonical optimization: `src/traffictwin/optimization/`.
- Canonical V2X emulator: `src/traffictwin/networking/`.
- SUMO runtime and loop: `src/traffictwin/digital_twin/` and `orchestration/`.
- Experiment entry points: `experiments/`.

## Moved Sweep Commands

| Compatibility path (relative to this directory) | Canonical implementation |
| --- | --- |
| `routing/chain_sweep.py` | `experiments/routing/chain_sweep.py` |
| `routing/scale_sweep.py` | `experiments/routing/scale_sweep.py` |
| `routing/r1_sensitivity.py` | `experiments/routing/predeparture_sensitivity.py` |
| `routing/r2_sensitivity.py` | `experiments/routing/online_sensitivity.py` |
| `v2x/sweep.py` | `experiments/networking/channel_sweep.py` |
| `v2x/stress_sweep.py` | `experiments/networking/traffic_stress_sweep.py` |

These are experiment tools, not commands to tune the frozen evaluation seeds.
Configuration contents and stored evidence remain unchanged. File commands must
use `src/pipeline/`; historical artifact paths map to `results/artifacts/`.
New production algorithms should not be added here. Migrate remaining code only
with dependency checks, compatibility tests, and unchanged scientific behaviour.
