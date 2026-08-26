# DhakaFlow Nexus — Status Board (updated 2026-08-25)

> **ACTIVE SPRINT:** `docs/SPRINT_140H.md` — 140 project-hours, 2026-08-25 15:00 →
> 2026-08-31 11:00 Asia/Dhaka. Read that for the hour-by-hour order.
> Hard deadline inside it: **FA-MAPPO must launch by `H+60`** (2026-08-28 03:00).

Single source of truth for what is DONE / RUNNING / READY_FOR_KEY /
BLOCKED_EXTERNAL_KEY / PENDING_EXTERNAL_APPROVAL / TODO. A missing key is
**never** a project blocker: provider-dependent execution is skipped, all
other work continues. One consolidated activation pass exists:
`python scripts/verify_keys.py` (add `--live` once keys are inserted).

## DONE

| Item | Evidence |
|---|---|
| Control baselines (fair, 3 seeds): fixed-time 547.7s, Max-Pressure 619.0s (+13% worse — negative result motivating coordinated control) | `artifacts/control_baselines/` |
| FA-MAPPO stack: 17-agent env (smoke PASS) + official rMAPPO trainer (smoke PASS) + GWNet-in-loop forecaster | `research/control/` |
| Visual proof suite: rush detection video, corridor SUMO film, moved-traffic map, one-command case report (dynamic: jam→act / quiet→no-action) | `docs/media/`, `scripts/case_report.py` |
| Calibration part A executed (provisional scale 0.5; peak-capture rule active) | `artifacts/twin_calibration_A.json` |
| **P1 → WINNER: RT-DETR r50** — mAP50:95 **0.711** (BNVD paper's best YOLOv8: 0.643); AP50 rickshaw 0.904 / CNG 0.961 / easy-bike 0.965; official pipeline + official evaluator, fair 24-epoch budget, frozen split | `artifacts/p1_triage/triage.json`; ckpt sha `27852d84…` @ GCS `models/p1_winner/` |
| **P3 STID complete** — MAE 1.09 @15min vs 1.39 floor (simulated domain) | `artifacts/p3_results/stid_cpu.log` |
| **P2 → PASS** (24h × 3 seeds on GCP VM, all 7 acceptance checks green; floors on full data: persistence speed MAE 0.41 m/s @ 5min) | `artifacts/p2_sensor_graph_full/P2_PASS_EVIDENCE.json`, data sha256 `c5b1a9ba…`, node hash `8b173a4e…` |
| REACT demo v0: any video/stream → detect+track → traffic state (0.97× realtime, Mac CPU, validated on live clip) | `scripts/demo_react.py`, `artifacts/react_demo_v0/` |
| R1 congestion-aware router (real 6,527-edge network; jam-divert case: 47.9 s avoided) | `research/routing/r1_router.py` |
| P1 fine-tunes RUNNING on AWS GPUs (r18 loss 26.6→10.7 in epoch 0) | S3 `logs/p1-rtdetr-*` |
| P3 arms launch-ready (4 models, official configs, staged S3) | `research/forecasting/jobs/` |
| Labs 00–02 (UTD19/MFD · SUMO foundation · frozen Dhaka R1 network) | frozen @ `ca2ac81`, `6936ea9`+`c852e64`; `paper_labs/*/FREEZE.md` |
| P0 vertical slice + PREVENT/REACT operating modes | `artifacts/p0_vertical_slice`, commits `1cff854`, `3f9f235` |
| E4 routing: DUE vs DSO, 10 seeds, claim 19.5–22.2% (p≤1.3e-03) | `artifacts/due_dso_stats`, commit `88e7db3`; routing frozen until joint gate |
| P1 execution package: VOC→YOLO converter, benchmark schema, frozen splits, fair training-budget policy | `research/perception/*`, `notebooks/P1_perception_colab.ipynb`, commits `019b3f9`, `6c81be2` |
| P-LIVE code: Google Routes/Weather providers, reality labels, RUNTIME_REFERENCE compliance, live-state API | `dhakaflow/live/*`, commits `7039c17`, `5ceea59` |
| 511NY camera adapter + isolated activation step (fixture-tested) | `dhakaflow/live/ny511_provider.py`, `scripts/verify_511ny.py`, 6 tests |
| Consolidated key-activation board | `scripts/verify_keys.py` |
| P2 sensor-graph module: deterministic 250-sensor placement (largest-SCC), DCRNN-recipe adjacency, 5-min edgeData extraction, NaN-not-zero masking | `research/twin/sensor_graph.py`, `scripts/run_sensor_graph.py`, 10 tests |
| P2 smoke runs (2 sim-h): insertion 1.00, 100% reachable sensor pairs, coverage 63% at 0.3 demand scale | `artifacts/p2_sensor_graph_smoke*/MANIFEST.json` |
| P2 medium validation (8 h × 2 seeds @ 0.5 scale, T=192×N=250×C=4, ~5 min/seed) — full P2→P3 pipeline exercised end-to-end | `artifacts/p2_sensor_graph_medium/MANIFEST.json` |
| P3 floors validated on real P2 output (persistence speed MAE 1.03/1.39/1.88 m/s @ 5/15/30 min — validation numbers, NOT the gate floors) | `artifacts/p2_sensor_graph_medium/baseline_results.json` |
| P3 BasicTS exports validated on real P2 output (v1.0 + legacy formats) | `artifacts/p2_basicts_*_medium/` |
| BasicTS harness finding: v1.0 zoo lacks DCRNN/GWNet/STAEformer → dual pin, legacy benchmark checkout `4c3e2d3` runs the graph family; Graph WaveNet fresh-verified + pinned | `upstream/UPSTREAM_PINS.yaml` |

## BLOCKED_ON_USER (30 seconds)

* `! gcloud auth login` — IUT account session expired (org reauth policy);
  RL fleet launch staged in `scratchpad/launch_fleet.sh`, fires on auth.
  **Add to Day-6 checklist: re-auth on presentation morning.**

## RUNNING

| Item | Since | Detail |
|---|---|---|
| ~~P2 FULL generation~~ → **P2 PASS 2026-08-25 18:19 UTC** | done | Colab/Drive path RETIRED: runs terminal-launched on `dhakaflow-p2-gen` (c3d-standard-8, on-demand, us-central1-a), identical pipeline to the Drive notebook cells 1–5 (pip SUMO → smoke → full 24h×3 seeds → acceptance checks → P3 floors). Results land in `gs://dhakaflow-p2-direct-abacus/out/`; VM self-terminates. Monitor polls every 5 min |
| **road511 24/7 recorder** | 2026-08-25 08:49 UTC | `scripts/record_road511.py` (pid in `artifacts/road511_recordings/recorder.pid`). CO+WA incident timeline (deduped deltas) + 6 Denver camera snapshots/min. ~3 API calls/min vs 30/min limit. Stop: `touch artifacts/road511_recordings/STOP`. First sweep: 200 events, snapshots verified real PNG 352×240 |

## PENDING_EXTERNAL_APPROVAL

| Item | Detail |
|---|---|
| **511NY_CAMERAS** | Developer-key request submitted 2026-08-19, approval is human-gated on the 511NY side. Integration DONE; activation = `export NY511_API_KEY=…` → `python scripts/verify_511ny.py`. Classification locked: `PROVIDER_INTEGRATION_VALIDATION`, never `DHAKA_LIVE_CAMERA_VALIDATION`. |

## ACTIVATED 2026-08-25

| Provider | Env var | Verified by | Unlocks |
|---|---|---|---|
| **Kaggle** | `~/.kaggle/kaggle.json` | `kaggle datasets list -s traffic` returns results | BNVD + Poribohon-BD + TFP-BD download → P1 BNVD track no longer blocked |
| **AWS** | `AWS_ACCESS_KEY_ID`/`SECRET` (in `.env`) | STS verified (acct `915644996102`); training bucket `dhakaflow-train-915644996102` created (7-day ckpt lifecycle); GPU AMI pinned `ami-027de6aaa8774e722`; launcher `scripts/aws/launch_arm.py`. **Quota reality:** G-spot 8 vCPU us-east-1 (= 2 concurrent GPUs), 0 us-west-2; increase to 32 requested in BOTH regions 2026-08-25, PENDING. Spot prices measured: g5.xlarge $0.56–0.97 (east), g4dn.xlarge $0.24 (west)/$0.35 (east) — plan's $0.30–0.40 estimate was optimistic for g5-east. **One user action left: `! bash scripts/aws/bootstrap_iam.sh`** (IAM role for instance→S3 checkpointing; assistant-side IAM mutation is deliberately blocked) |
| **Google Cloud ($300 trial)** | `gcloud` authed as janaeva@iut-dhaka.edu | project `direct-abacus-505920-t8` renamed "DhakaFlow Nexus", trial billing linked, APIs enabled (compute/routes/weather/apikeys). **CPU quota 200 vCPUs us-central1** — the RL fleet (8 arms × 8 vCPU, SUMO is CPU-bound) runs HERE for ~$30–40, freeing all AWS GPU budget for detector+forecasting. Spot VM smoke: created RUNNING + deleted. NOTE: trial forbids GPUs — GPUs stay on AWS |
| **Google Routes+Weather** | `GOOGLE_MAPS_API_KEY` (restricted to routes+weather APIs, in `.env`) | **FIRST LIVE CAPTURE EXECUTED 2026-08-25 11:56 UTC** — 6 R1 corridors + Karwan Bazar weather (30.3°C, 69% RH, light rain), reality REAL_LIVE, 0 errors, RUNTIME_REFERENCE persistence honoured (`artifacts/p_live/normalized/google_routes_runtime_reference.jsonl`). Lab 02's READY_NOT_EXECUTED is now EXECUTED |
| **road511** | `ROAD511_API_KEY` (in `dhakaflow/.env`, gitignored) | adapter `dhakaflow/live/road511_provider.py` live-smoked (WA events + 64 Denver cams, raw+normalized persisted); 7 fixture tests green. Cloudflare requires a non-Python-urllib UA (encoded in transport) | live camera streams · incident feed with NL descriptions · real congestion labels (`cause: congestion`). **Classification: `PROVIDER_INTEGRATION_VALIDATION` + domain-shift measurement — never Dhaka validation.** Rate limit 30 req/min. Supersedes the pending 511NY request |

## READY_FOR_KEY (code done + tested with fixtures; real-provider validation on key insertion)

| Provider | Key (env var name only) | Activation step | Unlocks |
|---|---|---|---|
| Hugging Face (free) | `HF_TOKEN` | `verify_keys.py --live` | Chronos-2 at forecasting gate |
| Anthropic | `ANTHROPIC_API_KEY` | `verify_keys.py --live` | GenAI copilot (last gate) |
| AWS | `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` | `verify_keys.py --live` (STS) | long training runs ($200 credit, spot + S3 checkpoints) |

Rule 13 acknowledged: mock/fixture data verifies *integration only*; no
provider-dependent experiment is marked PASS on mocked data.

## FINDINGS 2026-08-25

* **BNVD license: CONFIRMED UNSPECIFIED at both sources** — Kaggle metadata
  `licenses: [{"name": "unknown"}]`; README still carries the unfilled template
  "released under the [insert license type] license". Action: author email
  drafted (`docs/BNVD_LICENSE_EMAIL_DRAFT.md`) for the user to send.
  Poribohon-BD (CC BY 4.0) is the licensed primary track meanwhile; BNVD usable
  for internal benchmarking only, publication claims flagged until clarified.
  BNVD download is 6.5 GB → Drive/Colab only, never local.
* **Upstream workspace complete:** 15/15 fetchable pins now present —
  Graph-WaveNet VERIFIED; D-FINE and RT-DETRv4 floating refs resolved to SHAs
  (recorded in `artifacts/upstream_fetch_record.json`).

## BLOCKED_EXTERNAL_KEY (execution only — nothing downstream is waiting idle)

* (none — the last execution blocker cleared 2026-08-25: first live Google
  capture executed. Remaining user actions are P2 Drive drag and
  `! bash scripts/aws/bootstrap_iam.sh`.)

## TODO (planned order, none key-blocked)

1. **P2 → PASS**: RUNNING on the GCP VM (see RUNNING) — no user action needed
   anymore. PASS is declared only after `P2_PASS_EVIDENCE.json` lands in GCS
   with all acceptance checks green and results are pulled into
   `artifacts/p2_sensor_graph_full/`.
2. **P3 forecasting gate execution**: `notebooks/P3_forecasting_colab.ipynb`
   (GPU) — floors → dual export → graph candidates on the legacy harness
   (STID → GWNet → DCRNN → STAEformer), official configs, no winner until all
   arms run.
3. **P1 Colab execution** the moment a Colab session + Kaggle token exist
   (Poribohon-BD track first — no credentials).
4. Twin calibration gate (needs P1 winner + Google live reference → partially
   READY_FOR_KEY).

## Standing rules honoured

* Frozen labs untouched (`git diff paper_labs/00* 01* 02*` stays empty).
* No fake keys; no secrets in git; env-var names only.
* Heavy compute on Colab; Mac runs smokes and CPU-light validation only.
* No PASS without its acceptance tests actually passing.
