# TrafficTwin

## 1. Research Question

**Can predicted future traffic, communicated through a V2X system, improve routing compared with reactive traffic management?**

## 2. Architecture

`REAL METR-LA OBSERVATIONS -> Graph WaveNet -> future edge costs -> optimizer -> SIMULATED V2X EMULATOR -> SUMO route action -> paired outcome`

The canonical evaluation uses a frozen OSM/SUMO scenario and identical-state BASELINE, REACTIVE, and ORACLE arms. A learned model is evaluated only after the oracle establishes future-information headroom. Google Routes is a **live external reference** for the Dhaka prototype; it is not the DL forecasting engine.

## 3. Contributions

1. An evidence-backed Graph WaveNet forecasting contract with checkpoint, shape, runtime, error, and persistence-skill provenance.
2. A causal V2X-to-SUMO loop that logs status uplink, channel delivery/drop/TTL, inference, optimization, recommendation, and actual TraCI route change.
3. An oracle-first, identical-state routing protocol that retains negative results rather than replacing them with a more favorable scenario.

## 4. Primary Results

- Graph WaveNet is validated on the **public METR-LA** held-out split, not on Dhaka.
- A valid congested-but-stable LA stress case exists and the simulated V2X channel has delivered, applied reroutes in causal logs.
- The computed gates distinguish predictive control versus reactive routing from learned forecasting advantage versus persistence. Read the current evidence through `/api/research/status`; a passed first comparison does not imply a passed second comparison.
- Dhaka is a live-data deployment prototype; local DL forecasting and twin validation have not passed their gates.

## 5. One-Command Reproduction

```bash
make canonical
```

This runs the oracle-first Scenario A evaluation and packages `report.json`, `summary.md`, `plots/`, `vehicle_trace.json`, and `provenance.json` under `results/current/closed_loop/`. To package the frozen evidence without running SUMO, use `make canonical-package`.

## 6. Limitations

The scientific closed loop combines public METR-LA observations with a synthetic-demand OSM/SUMO scenario and a **simulated V2X emulator**. It is not a field deployment or a Dhaka local-forecast result. Learned control beating reactive control does not establish superiority over persistence.

## Run the Web Application

Install the local Python packages once after installing the runtime dependencies:

```bash
python -m pip install --no-deps -e packages/traffictwin
```

This is a workspace/editable installation. It does not download datasets or start training.

```bash
make app
```

Open http://127.0.0.1:8000. Use `make app PORT=8003` if that port is occupied.

No API key is needed. Without a Google Routes key (or when the key is denied or over quota) the Home
page routes on the project's own frozen Dhaka road network (`apps/api/app/routing/local_routes.py`,
sumolib shortest paths with penalty-method alternatives) priced with the last RECORDED corridor
states, and every screen says so; nothing recorded is ever called live. The **References** page
(`/api/references`, `docs/REFERENCES.md`) lists every paper, dataset, standard, tool and service the
code uses, with the files that use it.
For an evidence-only session without background live API sampling:
`DHAKAFLOW_NO_OBSERVATORY=1 make app`.

In **Control Room -> Fresh execution**, choose a frozen seed and information source,
then start a local SUMO run. Progress, forecast hashes, vehicle samples, V2X counters,
and route actions come from the running worker. Completed comparisons label the
fresh arm separately from frozen same-seed references. **Recorded replay** remains
a separate mode. These single-seed execution checks never update research gates.

## Where the Code Lives

| Path | Responsibility |
| --- | --- |
| [backend/](backend/README.md) | FastAPI server: small entry point, `api/`, and domain-grouped adapters |
| [apps/web/](apps/web/README.md) | Four primary `pages/`, preserved legacy pages, shared components, API client, CSS |
| `packages/traffictwin/src/traffictwin/forecasting/` | Deep-learning inference contract and checkpoint registry |
| `packages/traffictwin/src/traffictwin/networking/` | Simulated V2X channel and online state correction |
| `packages/traffictwin/src/traffictwin/optimization/` | Edge costs, route optimization, coverage diagnostics |
| `packages/traffictwin/src/traffictwin/digital_twin/` | SUMO runtime and traffic measurement helpers |
| `packages/traffictwin/src/traffictwin/orchestration/` | Closed-loop controller and execution jobs |
| `research/` | Research commands and sensitivity/sweep runners |
| `src/pipeline/` | Transitional research dependencies; the Python import name remains `pipeline` |
| `research/notebooks/` | Preserved exploratory notebooks and Colab builders |
| `data/`, `results/` | Inputs and generated evidence; former root artifacts are in `results/artifacts/` |
| `configs/`, `.env` | Non-secret settings and optional gitignored local credentials, respectively |
| `apps/api/tests/`, `tests/` | API, scientific, compatibility, and architecture tests |

See [the feature contract and seven-phase build order](BUILD_PLAN.md) for current
capabilities, ownership, acceptance checks and remaining work. Structure changes
do not themselves validate a feature or turn replay into fresh execution.
Some old tests/callers still reference the removed `dashboard.backend` package;
that compatibility migration is not yet complete.
