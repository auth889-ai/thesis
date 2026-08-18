# DhakaFlow Nexus — Status Board (updated 2026-08-19)

Single source of truth for what is DONE / RUNNING / READY_FOR_KEY /
BLOCKED_EXTERNAL_KEY / PENDING_EXTERNAL_APPROVAL / TODO. A missing key is
**never** a project blocker: provider-dependent execution is skipped, all
other work continues. One consolidated activation pass exists:
`python scripts/verify_keys.py` (add `--live` once keys are inserted).

## DONE

| Item | Evidence |
|---|---|
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

## RUNNING

(nothing — local queue drained; next heavy step is Colab)

## PENDING_EXTERNAL_APPROVAL

| Item | Detail |
|---|---|
| **511NY_CAMERAS** | Developer-key request submitted 2026-08-19, approval is human-gated on the 511NY side. Integration DONE; activation = `export NY511_API_KEY=…` → `python scripts/verify_511ny.py`. Classification locked: `PROVIDER_INTEGRATION_VALIDATION`, never `DHAKA_LIVE_CAMERA_VALIDATION`. |

## READY_FOR_KEY (code done + tested with fixtures; real-provider validation on key insertion)

| Provider | Key (env var name only) | Activation step | Unlocks |
|---|---|---|---|
| Google Routes+Weather | `GOOGLE_MAPS_API_KEY` | `python scripts/run_live_capture.py` (6 R1 corridors + 1 weather, RUNTIME_REFERENCE mode) | live speed reference for twin calibration + demo |
| Kaggle (free) | `~/.kaggle/kaggle.json` or Colab secret | P1 notebook §3–4 | BNVD download → P1 BNVD track |
| Hugging Face (free) | `HF_TOKEN` | `verify_keys.py --live` | Chronos-2 at forecasting gate |
| Anthropic | `ANTHROPIC_API_KEY` | `verify_keys.py --live` | GenAI copilot (last gate) |
| AWS | `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` | `verify_keys.py --live` (STS) | long training runs ($200 credit, spot + S3 checkpoints) |

Rule 13 acknowledged: mock/fixture data verifies *integration only*; no
provider-dependent experiment is marked PASS on mocked data.

## BLOCKED_EXTERNAL_KEY (execution only — nothing downstream is waiting idle)

* P1 fine-tuning runs (Colab GPU; BNVD track additionally needs the Kaggle
  token; the Poribohon-BD CC-BY-4.0 track needs **no** credentials and is the
  first cell to run when a Colab session opens).
* First live Google capture (`BLOCKED_NO_KEY` report already implemented).

## TODO (planned order, none key-blocked)

1. **P2 → PASS** (needs one 2-minute user action — the repo is PRIVATE, so
   Colab cannot clone it and GitHub OAuth was deliberately left for you to
   decide):
   a. Drag `artifacts/colab_bundle/bundle_part_aa…ad` (4 files, 30 MB total)
      and `notebooks/P2_sensor_graph_colab_drive.ipynb` into Google Drive
      (**anastasiasaat81** account, MyDrive root or `MyDrive/dhakaflow/` —
      both work).
   b. Open the notebook in Colab (`authuser=1`), CPU runtime, Run all.
   It reassembles the bundle, verifies the frozen-network checksum, smokes,
   generates 24 h × 3 seeds to Drive, and refuses PASS unless the acceptance
   checks pass. Wall-time: budget a few hours of Colab CPU (full-scale peaks
   jam — a killed local attempt is why this lives on Colab).
   Alternative: authorise Colab's GitHub access once, then the plain
   `P2_sensor_graph_colab.ipynb` git-clone flow works too.
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
