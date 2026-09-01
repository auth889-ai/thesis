# DhakaFlow Nexus

**Current active thesis path:** real-time Dhaka route advice plus prediction
benchmarks. The clean execution layer is `live/`, `predict/`, `route/`,
`network/`, `nlp/`, `demo/`, and `results/`; it reuses the existing
`dhakaflow/`, `research/`, `scripts/`, and `paper_labs/` code instead of
starting a new project. `live/` is the no-fixed-seed real pilot path; SUMO and
MOSAIC are repeatable appendix stress tests.

Start here:

1. `docs/PROJECT_STRUCTURE.md` — what each folder means and what is active.
2. `docs/REBUILD_120H_PLAN.md` — 5-day rebuild plan.
3. `docs/KEYS_AND_COMPUTE.md` — required keys and Colab/Drive/AWS setup.
4. `results/RESULTS.md` — every result, command, and evidence file.
5. `PROJECT_MAP.md` — quick code map.

Main verification:

```bash
bash download_assets.sh
PYTHONPATH=. pytest tests/platform/test_interfaces.py tests/platform/test_repo_architecture.py -q
python live/route_advisor.py --dry-run --corridor farmgate_to_shahbagh
make results
```

`make results` only aggregates existing evidence. Use `make local-results` to
regenerate local non-billed evidence, and `make live-capture` only when you
intentionally want to spend a small number of Google API requests.

---

**Existing evidence chain kept from the earlier DhakaFlow build:** real UAV
trajectories → same-street SUMO twin → published cycle-level
calibration (−27% discharge error, authors' code) → held-out validation
(speed MAE 3.0 m/s, 0 teleports) → causal same-state control experiments
under network-honesty guards.

See `REPRODUCE.md` for the one-command path to every number, and
`PROJECT_MAP.md` for the tour.

**AI traffic management for Dhaka:** observe real traffic → predict congestion
before it forms → prevent/react with signal control and routing → prove the
delay reduction inside a SUMO digital twin of the real road network.

---

## Appendix Demo — any video in, traffic intelligence out

![REACT demo — dense rush-hour traffic detected as CONGESTED](docs/media/react_demo_rush.gif)

*Dense evening rush hour on I-70: ~14 vehicles per frame tracked, 10 of 11
windows flagged **CONGESTED**, `congestion_detected: true` handed to the
routing layer — the moment the system decides to intervene.*

*Real output, unedited: a live US traffic-camera clip run through
`scripts/demo_react.py` with the **Dhaka-fine-tuned RT-DETR r50** winner.
Vehicles detected and tracked, per-window traffic state (banner), timeline and
routing verdict written as JSON. The input slot takes anything — a file, a URL,
an HLS live stream, or a webcam:*

```bash
python scripts/demo_react.py --detector rtdetr \
    --weights artifacts/p1_winner/rtdetr_r50_poribohon_best.pth \
    --source <video | stream-url | webcam-index>
```

| frame | | |
|---|---|---|
| ![f1](docs/media/react_frame_1.jpg) | ![f2](docs/media/react_frame_2.jpg) | ![f3](docs/media/react_frame_3.jpg) |

Demo run stats (from `summary.json`, produced by the run above): 450 frames,
near-real-time on a laptop CPU, detector label `DHAKA_FINETUNED_RTDETR_R50`
(Poribohon-BD 15-class head: rickshaw, CNG, easy-bike, leguna, …).

---

## The proof, moving — same trips, only the routing differs

![SUMO twin before/after](docs/media/twin_before_after.gif)

*The SUMO digital twin on the real Dhaka R1 network: left — selfish routing,
jams form and 1,224 vehicles are still crawling at minute 24; right — DhakaFlow
system routing, the same trips spread over spare capacity, only 930 still on
the road (the rest already arrived). Full statistics: −19.5% mean delay,
p = 1.3×10⁻⁵ (`artifacts/due_dso_stats/v200/result.json`).*

![Where the traffic moved](docs/media/fig_traffic_moved.png)

## Active Rebuild Status (updated 1 Sep 2026)

| Component | Method (official code, pinned) | Result | Comparison |
|---|---|---|---|
| **Prediction data** | Eclipse SUMO 1.27.1 on frozen Dhaka R1 + 250 virtual sensors | 8 h × 3 seeds, 288 timesteps, 84.3 % valid speed coverage | `predict/data/dhaka_twin/MANIFEST.json` acceptance PASS |
| **Forecasting floors** | Persistence + historical average | MAE@15 min: 0.724 / 0.570 m/s | `predict/results/twin_floors.md` |
| **Deep forecasting** | BasicTS STID/GWNet/STAEformer on Colab Pro | pending | `notebooks/Predict_BasicTS_Colab.ipynb` then `predict/pull_colab_results.py` |
| **Real route advice** | Google Routes live runtime call, route scoring in memory only | 1 real Dhaka advisory written; no Google route content persisted | `live/results/route_advice.jsonl` |
| **Real user pilot** | 3 users record start/arrival around advisories | pending | `live/user_trip_logger.py` |
| **Routing appendix** | SUMO paired seeds, static/reactive/DUE/predictive arms | decision guard can select an arm or honestly block unsafe action | `route/results/decision_guard.md` |
| **Live reference** | Google Routes runtime-reference capture | 6 Dhaka corridors captured; Google route content is not persisted | `artifacts/p_live/live_reference_summary.md` |
| **Evidence audit** | machine-readable artifact check | PASS with Colab benchmark pending | `results/evidence_audit.md` |

## Architecture

```
live OD request ─► Google Routes runtime options ─► route advisor ─► 3-user pilot log
real benchmark datasets ─► Colab STGNN benchmark ─► model comparison table
Dhaka twin sensors ─► forecast-to-weights ─► SUMO/MOSAIC appendix stress tests
```

## Honesty labels (enforced in code, not prose)

* Simulated results carry `DHAKA_SIMULATED_SENSOR_GRAPH` and can never support
  a real-world claim (`ModelEntry.real_world_claim_supported == False`, tested).
* US live data (road511) is `PROVIDER_INTEGRATION_VALIDATION` + domain-shift
  measurement — never Dhaka validation.
* Every upstream repo is pinned by commit (`upstream/UPSTREAM_PINS.yaml`);
  official code is never modified — adapters translate formats only.

## Where things live

* `docs/STATUS_BOARD.md` — live single source of truth
* `docs/SPRINT_140H.md` — the hour-by-hour execution plan
* `docs/INTEGRATED_BUILD_PLAN.md` — full research design, gates, policies
* `paper_labs/` — frozen foundations (UTD19 science, SUMO platform, Dhaka network)
* `research/`, `dhakaflow/` — components and platform contracts
