# PROJECT MAP — read this first (5 minutes)

The active thesis path is the **120-hour rebuild layer**: real-time Dhaka route
advice, real benchmark forecasting on Colab, a small user pilot, and SUMO/MOSAIC
as repeatable appendix stress tests. It reuses the existing DhakaFlow source
code; it is not a second project.

Read `docs/PROJECT_STRUCTURE.md` for the folder contract.

## Active rebuild path

| Folder | What it is |
|---|---|
| `live/` | no-fixed-seed route advisor and 3-user real pilot logger |
| `pipeline/forecasting/` | twin sensor data, forecasting floors, BasicTS/Graph WaveNet outputs, forecast-to-weight XML |
| `pipeline/routing/` | SUMO static/reactive/predictive/DUE/DSO appendix harness and paired-seed stats |
| `pipeline/networking/` | MOSAIC V2X penetration and latency/loss appendix sweeps |
| `pipeline/nlp/` | incident text classifier and event-to-edge weight injection |
| `demo/` | Streamlit/presentation viewer for generated evidence |
| `results/` | single source for final tables and reproducibility links |

Main command for the rebuild layer:

    make results

This aggregates existing evidence into `results/RESULTS.md`. To regenerate
local non-billed evidence, run `make local-results`. To call Google live
reference APIs, run `make live-capture` deliberately.

No-fixed-seed real path:

    python live/route_advisor.py --live --yes --corridor farmgate_to_shahbagh
    python live/user_trip_logger.py start --participant p1 --advice-id <id> --corridor farmgate_to_shahbagh
    python live/user_trip_logger.py complete --trip-id <trip_id>

## Existing gate chain

The older DhakaFlow gate chain is still useful for appendix evidence: a real
video goes in, a network-guarded decision comes out, and each stage has a PASS
artifact you can open.

## THE command (the whole system, one line)

    python scripts/dhakaflow_run.py --source <video> --camera 070E28355CAM1RP2

video -> detect+track -> physical state -> synchronized SUMO twin ->
GWNet forecast -> candidate futures from ONE saved t0 (paired seeds) ->
network guards -> decision (sometimes honestly NO ACTION) -> four-pane page.

## Existing source files reused by the rebuild

| # | File | What it is |
|---|------|------------|
| 1 | `research/perception/pipeline.py` | EYES — RT-DETR + official ByteTrack -> tracks |
| 2 | `research/perception/state_estimator.py` | JUDGE OF STATE — physical queue/stops/flows (works on stationary-start video) |
| 3 | `research/twin/scenario_sync.py` | TWIN SYNC — observed state CONFIGURES SUMO (Geneva DT-GM pattern, GEH accept) |
| 4 | `research/control/gwnet_in_loop.py` | PROPHET — GWNet +5/10/15 min, history preloaded, availability logged |
| 5 | `scripts/predictive_planner.py` | BRAIN — candidate futures from one saved state, network objective + guards |
| 6 | `research/control/signal_baselines.py` | SIGNALS — stock actuated + Varaiya max-pressure, correct semantics |
| 7 | `research/routing/r1_router.py` | MAP — the frozen 6,527-edge Dhaka network |

## The gates (each is a command + a PASS artifact)

| Gate | Command | Artifact |
|---|---|---|
| 1 REAL_STATE | `python scripts/gate1_real_state.py` | artifacts/gates/REAL_STATE_PASS.json |
| 2 TWIN_SYNC | `python scripts/gate2_twin_sync.py` | artifacts/gates/TWIN_SYNC_PASS.json |
| 3 FORECAST | `python scripts/gate3_forecast.py` | artifacts/gates/FORECAST_PASS.json |
| 4+5+8 PLANNER | `python scripts/predictive_planner.py --sync … --emit-gates` | COUNTERFACTUAL / NETWORK_GUARD / PREDICTIVE_PLANNER _PASS.json |
| 6 SIGNALS | `python scripts/gate6_signal_control.py` | SIGNAL_CONTROL_PASS.json |
| 7 ROUTING | `python scripts/gate7_dynamic_routing.py` | DYNAMIC_ROUTING_PASS.json |

## The two headline findings (memorize these)

1. **The intervention window is congestion ONSET**: at the forming jam,
   max-pressure wins in all 3 paired seeds (−4.1% network delay, +4.8%
   arrivals). At saturation, NO candidate safely improves the network and
   the system says NO ACTION — proof it is not scripted.
2. **Local relief is not success**: candidates that clear one queue while
   the network worsens are labeled LOCAL_RELIEF_NETWORK_FAIL and rejected.

## Evidence & docs

- `docs/PROJECT_STRUCTURE.md` — active layout and what each folder owns
- `docs/REBUILD_120H_PLAN.md` — current 5-day execution plan
- `results/RESULTS.md` — active result table index
- `docs/RESULTS_MATRIX.md` — every number + the gate table (generated)
- `docs/RESEARCH_ARCHITECTURE_REVIEW.md` — the published systems each part follows
- `docs/CURRENT_SYSTEM_GAP_AUDIT.md` — 28 defects found and adjudicated
- `docs/PRESENTER_GUIDE.md`, `docs/INTERVIEW_CARDS.md` — what to say
- `app.py` -> http://localhost:8080 — upload a video, watch the chain run

## What not to edit first

Do not mass-move source folders into `legacy/` before the rebuild path passes.
Treat `paper_labs/` as frozen foundations, `archive/` as historical material,
and large `artifacts/` outputs as evidence or regenerated run products.
