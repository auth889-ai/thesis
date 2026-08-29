# PROJECT MAP — read this first (5 minutes)

The project is a GATED CAUSAL CHAIN: a real video goes in, a network-guarded
decision comes out, and every stage has a PASS artifact you can open.

## THE command (the whole system, one line)

    python scripts/dhakaflow_run.py --source <video> --camera 070E28355CAM1RP2

video -> detect+track -> physical state -> synchronized SUMO twin ->
GWNet forecast -> candidate futures from ONE saved t0 (paired seeds) ->
network guards -> decision (sometimes honestly NO ACTION) -> four-pane page.

## The 7 main source files (the brain)

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

- `docs/RESULTS_MATRIX.md` — every number + the gate table (generated)
- `docs/RESEARCH_ARCHITECTURE_REVIEW.md` — the published systems each part follows
- `docs/CURRENT_SYSTEM_GAP_AUDIT.md` — 28 defects found and adjudicated
- `docs/PRESENTER_GUIDE.md`, `docs/INTERVIEW_CARDS.md` — what to say
- `app.py` -> http://localhost:8080 — upload a video, watch the chain run

## Safe to IGNORE

`paper_labs/` (frozen foundations) · `dhakaflow/` (plumbing) · `upstream/`
pins · old `scripts/case_report.py` / `demo_react.py` era files (superseded
by the gate chain; kept for history) · anything in artifacts/ you don't
recognize (run outputs).
