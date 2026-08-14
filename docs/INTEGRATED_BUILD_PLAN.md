# DhakaFlow Nexus — Integrated Research Build Plan

**Mode change (2026-08-14):** the workflow "finish all paper labs → then build the
project" is retired. From here there is **one system**, and every paper enters it
as a **component qualification gate**. Labs 00–02 and Sprint A remain frozen
foundations.

**Research goal:** predict congestion before it happens and proactively
coordinate signals and routes to reduce network-wide delay under heterogeneous
Bangladeshi urban traffic.

All URLs below were fresh-verified on **2026-08-14**. Nothing here is written
from memory; anything unverified is marked `UNVERIFIED` and must be re-checked
when its gate opens.

---

## 1. INTEGRATED_DHAKAFLOW_ARCHITECTURE

```
 REAL BANGLADESH VIDEO / IMAGES          LIVE EXTERNAL REFERENCE
 (BNVD, TFP-BD, Poribohon-BD)            (Google Routes API)
            │                                      │
            ▼                                      │
   [P] DETECTOR  (RT-DETR family winner)           │
            │                                      │
            ▼                                      │
   [P] TRACKER   (ByteTrack)                       │
            │                                      │
            ▼                                      │
   [S] TRAFFIC SENSOR EXTRACTION                   │
       flow · count · speed proxy · queue ·        │
       occupancy proxy · turning · vehicle mix     │
            │                                      │
            ▼                                      │
   ┌──► LIVE STATE LAYER  (TrafficObservation) ◄───┘
   │        │                    ▲
   │        ▼                    │ calibration + validation
   │  [F] FORECAST SERVICE       │
   │   ML · DL · Graph-ML        │
   │        │                    │
   │        ▼                    │
   │  [T] DHAKA DIGITAL TWIN  ───┘   ← frozen Lab 02 network
   │        │   replay · what-if · controller eval
   │        ▼
   │  [C] FORECAST-AWARE CONTROL   ← ablated against MAPPO/CoLight/FRAP/MP
   │        │
   │        ▼
   │  [SAFETY SHIELD]  (hard constraints, non-bypassable)
   │        │
   │   ┌────┴────┐
   │   ▼         ▼
   │ SIGNALS   ROUTING          → priority: ambulance / bus / pedestrian
   │   │         │
   │   └────┬────┘
   │        ▼
   └─── SYSTEM OUTCOMES (delay, queue, throughput, safety, equity)
            │
            ▼
   provenance · metrics · model registry · experiment tracking
            │
            ▼
   OPERATOR DASHBOARD + GENAI COPILOT (grounded, tool-calling)
```

**The one structural correction to the pipeline you sketched.** Your diagram is
correct end-to-end, with one thing it does not yet show, and it is the single
most important design fact in this project:

> **The four real Bangladesh camera sites are insufficient for a convincing
> large-network Graph-ML benchmark.** DCRNN, Graph WaveNet, STAEformer and STID
> are defined over a graph of many spatially-distributed sensors — METR-LA has
> **207 loop detectors**; TFP-BD has **4 camera locations**. These models *may
> still be run* on four nodes, and we will report those results — but **no strong
> spatial-generalisation claim may rest on four nodes alone.**

**Resolution (this is what makes the thesis defensible):** the **digital twin is
promoted from consumer to producer**. The frozen Lab 02 R1 network carries
simulated detectors on every approach — a **100–300 node sensor graph with real
Dhaka topology** — whose demand, composition and speeds are *calibrated from the
real camera-derived measurements at the 4 real sites* plus the live Google Routes
speed reference. The forecasting benchmark then runs on a Dhaka graph that is
real in topology and calibrated in behaviour, with the 4 real sites held out as
the **real-data validation anchor**.

So the corrected data flow has a loop your diagram draws as a straight line:

```
real video (4 sites) → real measurements ─┐
                                          ├─→ CALIBRATED TWIN → 100–300 node
live Google Routes speeds ────────────────┘        │            sensor graph
                                                   ▼
                                    forecasting benchmark + control benchmark
                                                   │
                              held-out real 4-site measurements validate it
```

This is stated as an assumption to defend, not a trick: **forecasting is trained
on calibrated-synthetic sensor series and validated against real measurements at
the sites we actually observe.** Any paper claim will say exactly that.

### The three forecasting evidence domains (never merged)

Every number this project reports declares which domain it came from. The
`model_registry` refuses a metric block without one.

| Domain | What it is | What it may support |
|---|---|---|
| **`OFFICIAL_REAL_BENCHMARK`** | METR-LA, PEMS-BAY, COCO, MOT17 — the authors' own benchmark data | REPRODUCTION_PASS: proof our harness matches published numbers |
| **`DHAKA_SIMULATED_SENSOR_GRAPH`** | 100–300 SUMO detectors on the real frozen Dhaka topology | High-dimensional graph forecasting and control integration. **Always labelled SIMULATED.** Never described as real sensor measurements |
| **`DHAKA_REAL_VALIDATION_ANCHORS`** | Real Bangladesh observation sites, real BD datasets, permitted external live references | The only domain that can support a real-Dhaka claim |

**Simulator-circularity guard (enforced in code).** A model trained only on SUMO
data and evaluated only on the same simulation family supports **no real-Dhaka
forecasting claim**. `ModelEntry.real_world_claim_supported` returns False for
such a model, and
`tests/platform/test_taxonomy_and_evidence.py::test_simulated_only_model_supports_no_real_world_claim`
keeps it that way.

---

### Operating modes — what the system actually does

The goal decomposes into **two modes with different triggers, actions, metrics
and burdens of proof**. Both are required; both consume the same forecast.

| | **Mode A — PREVENT** | **Mode B — REACT** |
|---|---|---|
| Trigger | Forecast: junction/link will exceed critical density in *h* minutes | Measurement: queue / spillback exceeds threshold **now** |
| Signal action | Shift green toward the approach that *will* load, before the queue forms | Pressure-based discharge; protect the downstream link from spillback |
| Routing action | Divert a fraction of demand before the bottleneck saturates | Route around the existing jam, using the forecast so the alternate is not congested on arrival |
| Success metric | The predicted congestion does not materialise | Recovery time, queue clearance rate, delay during the event |
| Proof | **Counterfactual only** (see below) | Directly measurable |

**Forecast horizon must exceed actuation lead time.** This is why the benchmark
uses 5 / 15 / 30 min — each maps to a real lead time, not to aesthetics:

| Action | Lead time before it changes anything | Minimum useful horizon |
|---|---|---|
| Signal timing change | ~1–2 cycles ≈ 2–4 min | **5 min** |
| Fleet rerouting redistribution | 5–15 min | **15 min** |
| Planning / operator advisory | — | 30 min |

**Proving prevention requires the twin.** A jam that was prevented cannot be
observed in reality — there is no real-world counterfactual. The proof is:

```
identical network + demand + seed
  ├── branch 1: baseline control   → jam forms,     total delay D1
  └── branch 2: forecast-aware     → jam prevented, total delay D2
claim = (D1 - D2) over N seeds, with a statistical test
```

This is the reason the digital twin sits in the middle of the architecture rather
than at the end, and the reason Mode A cannot be validated on live data alone.

## 2. CURRENT_FROZEN_FOUNDATIONS

| Asset | Status | What it gives the system |
|---|---|---|
| **Lab 00 — UTD19/MFD** | PASS, frozen | Traffic-science units, MFD, critical point; `evaluation/traffic_science.py`. torino numbers are a regression fixture, never a Dhaka threshold |
| **Lab 01 — SUMO Foundation** | PASS, frozen @ `ca2ac81` | `SimulationBackend`, `SignalActuator`, `TrafficScenario`, `SafetyShield`, fair benchmark matrix, provenance |
| **Lab 02 — Real Dhaka network** | PASS, **FROZEN** @ `6936ea9` + `c852e64` | The geographic substrate: R1 Farmgate–Karwan Bazar–Bangla Motor–Shahbagh, 6527 edges / 7865 lanes / 2956 junctions / 17 TLS, left-hand verified, checksummed |
| **Sprint A platform** | Active | 13 modules, shared interfaces, `LiveTrafficReference` protocol, registry, provenance |
| **Lab 03 work-in-progress** | Absorbed, not discarded | Candidate registry + class taxonomy become `PERCEPTION_RESEARCH_GATE` inputs (see §4) |

Frozen means: `git diff` over `paper_labs/00_utd19`, `01_sumo_foundation`,
`02_dhaka_osm` must stay empty. Only a genuine integration-test defect reopens
them.

---

## 3. END_TO_END_RUNNING_SKELETON_PLAN

**Rule: a running system exists from day one and never stops running.** Every
component starts as the dumbest defensible baseline, then is *replaced* by a
qualified winner. Nothing waits for research to finish.

| Stage | v0 baseline (built first, ~10 h) | Replaced by |
|---|---|---|
| Detector | COCO-pretrained RT-DETR, no fine-tune | Perception gate winner |
| Tracker | ByteTrack default params | Tuned on Dhaka density |
| Sensor | Counting line + track-length speed proxy | Calibrated homography |
| State | `TrafficObservation` (Lab 01 type, unchanged) | — (contract is already right) |
| Forecast | Persistence + historical average | Forecast gate winner |
| Twin | Lab 02 network + synthetic demand | Calibrated twin |
| Control | Fixed-time, then Max-Pressure | Control gate winner → Forecast-Aware MAPPO |
| Routing | Dijkstra current-fastest | Forecast-fastest / system-aware |
| Safety | Lab 01 `SafetyShield` | + fallback, timeout, robustness |
| Serving | CLI + JSON artifacts | FastAPI + dashboard + copilot |

**Vertical-slice acceptance:** one command runs *real Dhaka video → detections →
tracks → measurements → forecast → twin → controlled signals → metrics JSON*.
Until that command exists, no research gate opens.

---

## 4. PERCEPTION_RESEARCH_GATE

**Verified official resources**

| Resource | URL | Verified |
|---|---|---|
| RT-DETR (CVPR 2024, official) | https://github.com/lyuwenyu/RT-DETR | ✅ Apache-2.0 repo, PyTorch + Paddle |
| RT-DETR paper | https://arxiv.org/abs/2304.08069 | ✅ |
| RT-DETRv2 (bag-of-freebies) | same repo | ✅ v2-S 48.1 AP @ 217 FPS |
| **RT-DETRv4** (Nov 2025) | https://arxiv.org/pdf/2510.25257 | ✅ newest family member — must be evaluated, not assumed best |
| YOLO challengers (v10–v13) | to fresh-verify at gate | ⚠️ named in v4 comparisons |
| **BNVD** dataset | https://arxiv.org/abs/2405.12150 · https://github.com/bipin-saha/BNVD @ `b4e74d1` | ✅ 17,326 img / 81,542 inst / 17 classes; **license UNSPECIFIED — blocker** |
| Poribohon-BD | https://data.mendeley.com/datasets/pwyyg8zmk5/2 | ✅ **CC BY 4.0**, 9,058 img |
| TFP-BD | https://pmc.ncbi.nlm.nih.gov/articles/PMC11919376/ | ✅ 23,678 img, elevated foot-over-bridge, 4 Dhaka sites, 60 fps |
| BadODD | https://arxiv.org/abs/2401.10659 | ✅ 9,825 img, 9 districts, dashcam |

**Gate procedure**
1. Fetch BNVD (needs Kaggle token), Poribohon-BD, TFP-BD; checksum, audit real files.
2. Reproduce RT-DETR's official COCO eval on a subset — sanity that our harness matches published numbers before we fine-tune anything.
3. Fine-tune RT-DETR + RT-DETRv2/v4 + one YOLO challenger on BNVD via the **authors' own configs and pipeline**.
4. Benchmark: mAP50, mAP50:95, per-class AP, precision, recall, latency, FPS, memory — **per-class AP on rickshaw/CNG is the decisive metric**, not overall mAP, because those classes are what makes Dhaka different.
5. Cross-dataset validation on Poribohon-BD (different distribution) and TFP-BD (different viewpoint).
6. Winner integrates behind `dhakaflow.perception.Detector`.

**Class taxonomy is already built** (`paper_labs/03_bd_traffic_data/src/taxonomy/`)
with EXACT/MERGED/AMBIGUOUS/UNSUPPORTED tags. Two open decisions you must make
from real crops, not names: **"Van"** (in Bangladeshi usage often a *pedal
rickshaw-van*, not a motor van) and **"Easybike"** (battery three-wheeler with no
slot in the taxonomy).

---

## 5. FORECASTING_RESEARCH_GATE

**Verified official resources**

| Model | Official repo | Verified |
|---|---|---|
| DCRNN (ICLR'18) | https://github.com/liyaguang/DCRNN | ✅ TensorFlow |
| Graph WaveNet (IJCAI'19) | https://arxiv.org/pdf/1906.00121 (repo `nnzhan/Graph-WaveNet`) | ⚠️ repo URL to re-verify at gate |
| STID (CIKM'22) | https://github.com/GestaltCogTeam/STID | ✅ |
| STAEformer (CIKM'23) | https://github.com/XDZhelheim/STAEformer | ✅ |
| **Chronos-2** (Oct 2025) | https://github.com/amazon-science/chronos-forecasting · https://huggingface.co/amazon/chronos-2 | ✅ 120M encoder-only, zero-shot, covariate-aware |
| **BasicTS** — fair benchmark toolkit | https://github.com/GestaltCogTeam/BasicTS | ✅ **this is the harness**: already implements STID, GWNet, DCRNN under one pipeline |

**Why BasicTS matters for your 100 hours:** it is a published *fair-comparison*
harness that already hosts several of your required models. Adopting it removes
the single biggest time sink — writing 9 training loops — and removes the biggest
credibility risk: unfair comparison. We add a Dhaka dataset adapter, not new
training code.

**Model families (none may be dropped without a KEEP/REJECT experiment)**

| Family | Models |
|---|---|
| Classical | Persistence, Historical Average, Random Forest, XGBoost |
| Deep temporal | LSTM, GRU |
| Graph / spatiotemporal | DCRNN, Graph WaveNet, STID, STAEformer |
| Foundation challenger | Chronos-2 (zero-shot + fine-tuned) |

**Protocol:** one leakage-free Dhaka benchmark; chronological split (never
random); horizons **5 / 15 / 30 min**; metrics MAE, RMSE, MAPE (only where the
denominator is safely non-zero — Dhaka has genuine zero-flow intervals, so MAPE
is reported *with* its validity mask). Winner → `dhakaflow.forecasting.TrafficForecaster`.

---

## 6. DIGITAL_TWIN_GATE

Uses the **frozen Lab 02 network unchanged**. Calibrates:

| Quantity | Evidence source | Honesty label if evidence is absent |
|---|---|---|
| Demand | Camera counts at 4 real sites + OD estimation | `ESTIMATED_DEMAND` |
| Vehicle composition | Detector class mix (rickshaw/CNG/bus/car/motorcycle/truck/microbus) | measured |
| Speeds | Track-derived speed + Google Routes reference | `EXTERNAL_LIVE_REFERENCE`, not ground truth |
| Turning fractions | Tracks through junctions | measured where cameras exist, else estimated |
| Headways / lane behaviour | Literature + fitted to observed throughput | `ASSUMED` + cited |
| **Signal timings** | **No real DMP plans yet** | stays `IMPORTED_HEURISTIC` — **never** called real Dhaka timing |

Heterogeneous vehicle types get distinct SUMO `vType`s (length, accel, `sigma`,
lateral behaviour) — the sublane model matters here because Dhaka traffic is not
lane-disciplined. Twin must support replay, what-if, controller eval, routing eval.

---

## 7. CONTROL_RESEARCH_GATE

| Controller | Official source | Verified |
|---|---|---|
| Fixed-time / Actuated | SUMO native | ✅ |
| Max-Pressure | Lab 01 baseline (already implemented) | ✅ |
| **LibSignal** — cross-simulator TSC library (IDQN, CoLight, PressLight) | https://arxiv.org/pdf/2211.10649 | ✅ GPL-3.0 — **license must be checked before linking into our runtime** |
| CoLight | https://github.com/wingsweihua/colight | ✅ |
| PressLight / FRAP | via LibSignal + author repos | ⚠️ re-verify at gate |
| **SUMO-RL** — Gymnasium/PettingZoo env | https://github.com/LucasAlegre/sumo-rl | ✅ our SUMO↔MARL bridge |
| **MAPPO** (official) | https://github.com/marlbenchmark/on-policy | ✅ paper arXiv 2103.01955 |

**Our contribution: Forecast-Aware MAPPO**, with a real ablation ladder — and the
full model is *not* assumed best:

```
MAPPO  →  +forecast  →  +pressure  →  +forecast+pressure  →  full FA-MAPPO
```

Features under test: current state, forecast, pressure, queue, downstream
capacity, spillback, neighbour state, heterogeneous vehicle mix, **forecast
uncertainty**. Same scenario, demand, seed set, horizon and metrics for every arm
(`BenchmarkSpec.assert_fair()` from Lab 01 enforces it).

---

## 8. ROUTING_GATE

Baselines: Dijkstra, A\*, current-fastest, forecast-fastest, system-aware.
Challengers: **URB** (NeurIPS 2025 D&B) https://github.com/COeXISTENCE-PROJECT/URB
— 29 real networks, MARL routing, integrates **RouteRL**. ✅ verified.

**Hard evaluation rule:** routing is judged **network-wide**, never on the routed
vehicles alone. A route policy that speeds up its own users while pushing delay
onto everyone else is recorded as a **FAIL**, with the externality quantified.

---

## 9. SAFETY_PRIORITY_GATE

Non-negotiable, extends Lab 01's `SafetyShield`: min-green, yellow/all-red
transitions, conflicting-movement prevention, action validation, **fallback
controller**, controller-timeout behaviour, forecast-uncertainty handling,
domain randomisation. **No learned controller may bypass the shield** — it wraps
the write side of `SignalActuator`, which is why Lab 01 separated them.

Priority (later): emergency vehicle, bus/person-delay, pedestrian-aware.
EMVLight (AAAI) and VLMLight (NeurIPS 2025, https://arxiv.org/abs/2505.19486 —
reports up to 65% EMV waiting-time reduction) to fresh-verify at gate.

---

## 10. NLP_GENAI_GATE

**NLP:** incident extraction — location, type, severity, blocked lanes, time,
confidence. Bangla+English sources. Ground truth anchor: Bangladesh Road Traffic
Accident Dataset 2007–2024 (49,566 records, ARI/BUET + BRTA + DMP + MP),
https://figshare.com/articles/dataset/Bangladesh_Road_Traffic_Accident_Dataset_2007_2024_Multi-Source_Integration_/30631292 ✅

**GenAI:** grounded copilot with RAG + tool calling, explaining current state,
forecast, controller action, route decision, performance change. Related work to
verify at gate: LA-Light https://github.com/Traffic-Alpha/LLM-Assisted-Light ✅,
VLMLight ✅.

**Hard rule:** the LLM explains and queries; it **never becomes an unrestricted
low-level signal controller**. Any LLM-issued action passes the same SafetyShield.

---

## 11. LIVE_EXTERNAL_DATA_GATE

### Paid camera APIs — verified, and the honest verdict

You asked about Argus AI, Vizzion, TrafficLand, GoodVision. Here is what actually
checks out:

| Provider | What it really is | Dhaka reality |
|---|---|---|
| **Vizzion** | Aggregates 100k+ cameras via 200+ **transport agencies**, "30+ countries" / "40 countries" (their own pages disagree) | ⚠️ **Bangladesh/Dhaka is not listed in Vizzion's public Asia coverage.** Their model is DOT partnerships; Bangladesh has no public DOT camera-feed programme |
| **TrafficLand** | US **DOT** video feeds | ❌ US-centric |
| **Argus AI** | Incident detection on traffic/dashcam feeds | ❌ no BD coverage evidence |
| **GoodVision** | Analytics **on a stream you supply** — it is not a camera source | ❌ needs a Dhaka camera first; it cannot create one |

**The decisive fact:** Dhaka's AI traffic cameras went live May 2026 operated by
**Dhaka Metropolitan Police** for Road Transport Act violation detection
(https://globalvoices.org/2026/06/03/ai-cameras-are-surveilling-the-roads-in-dhaka-bangladesh/).
That is a **police enforcement system, not a public API**. Access would require
institutional agreement, not a credit card.

**So: do not buy any camera API yet.** Buying before verifying coverage would
spend real money on zero Dhaka frames. Required before any purchase: Dhaka
coverage, AI-processing rights, retention rights, academic access, latency,
update rate — in writing. Action: email `busdev@vizzion.com` asking specifically
"do you have any Bangladesh/Dhaka camera coverage?" — free, and it settles it.

### What we use instead — and why the project is still strong

| Track | Source | Status |
|---|---|---|
| **Recorded real Dhaka video** | TFP-BD (elevated, 4 sites, 60 fps, day/dusk/night/rain) | The perception + sensing backbone |
| **Live speed/travel-time** | **Google Routes API** via `GOOGLE_MAPS_API_KEY` | `READY_NOT_EXECUTED` — code written, tested with mock, never executed |
| **Live video (to research at gate)** | Public Dhaka YouTube live streams, university/BUET partnership | ⚠️ ToS check required first |

**Directly answering "without API key it will be fully poor and weak":** not
true, and it matters that you know why. The Google Routes key adds a *live speed
reference* — valuable for calibration and for a live demo. It adds **nothing** to
detection, tracking, forecasting benchmark, RL control, or routing, which is
where the entire scientific contribution lives. A live key makes the demo
impressive; the frozen real network + real BD datasets + honest benchmarks make
the *thesis* strong. Get the key — just don't believe the project depends on it.

### Foreign-data policy (what "test on another country" may and may not mean)

Three uses of non-Bangladeshi data, deliberately kept separate:

| Use | Data | Legitimate? |
|---|---|---|
| **A. Official reproduction** — prove our harness matches published numbers | COCO (RT-DETR), MOT17/MOT20 (ByteTrack), **METR-LA / PEMS-BAY** (DCRNN, Graph WaveNet, STID, STAEformer) | ✅ **Required.** This is how REPRODUCTION_PASS is earned; all are free, no key |
| **B. Live-systems demonstration** — prove the pipeline ingests a real live stream in real time | A free public DOT camera feed (see below) | ✅ Legitimate as an *engineering* claim: "the runtime consumes live camera streams" |
| **C. Scientific claim about Dhaka** | foreign cameras | ❌ **Never.** Foreign traffic cannot validate Dhaka control, Dhaka demand, or heterogeneous-vehicle behaviour |

**Free live camera sources beat paid ones for use B** (verified 2026-08-14):

| Source | Access | Note |
|---|---|---|
| **511NY** https://511ny.org/developers/help | **Free developer key** | Cameras + speeds + incidents — the richest free option |
| **TfL JamCams** https://api.tfl.gov.uk/Place/Type/JamCam/ | **Free app key**, ~900 London cameras | ⚠️ `UNVERIFIED`: secondary sources report JamCams offline since a Sept-2024 cyber attack — check liveness before relying on it |
| GDOT / Open Data DC (ArcGIS Hub) | Free | Regional US feeds |

⇒ **Vizzion/TrafficLand/Argus/GoodVision are not needed at all.** A paid aggregator
would buy us foreign cameras we can get free, and still no Dhaka coverage.

**If Vizzion trial/API access is obtained anyway**, it is validated on a market
they actually serve (e.g. Jakarta or Bangkok) and the result is classified:

* ✅ `PROVIDER_INTEGRATION_VALIDATION` — "our `CameraProvider` adapter ingests a
  commercial live feed correctly"
* ❌ **never** `DHAKA_LIVE_CAMERA_VALIDATION`

**The Dhaka core must remain fully independent of Vizzion availability.** No gate,
benchmark or claim may depend on a commercial provider; the dependency is
declared `configs/live/external_reference.yaml: camera_providers.vizzion.status:
NOT_PURCHASED` and the permitted/forbidden uses are written into that config.

**Running a Dhaka-trained detector on a foreign live feed is itself a finding**,
not a demo trick: BNVD has rickshaw/CNG/easybike classes that do not exist in New
York, so degradation there is expected and is reported as a *domain-shift
measurement*, never as a failure of the detector.

### Paid keys, final list

**Three keys required. Two of them free. Everything else is optional or refused.**

| # | Key | Cost | Needed for | When |
|---|---|---|---|---|
| 1 | **Kaggle token** | **free** | BNVD download | 🔴 **now — blocking** |
| 2 | **Google Routes** `GOOGLE_MAPS_API_KEY` | paid, ~$5/1k req | Dhaka live speed reference | 🟡 twin calibration |
| 3 | **Anthropic Claude** | paid, usage | GenAI copilot | 🟡 last gate |
| 4 | HuggingFace token | free | Chronos-2 / checkpoint pulls without rate limits | 🟢 forecasting gate |
| 5 | 511NY developer key | free | live-stream demonstration track | 🟢 optional |
| 6 | AWS (held, $200 credit) | credited | **long training runs** | ✅ have |
| 7 | Colab Pro (held) | subscription | interactive dev, short jobs | ✅ have |
| — | Vizzion / TrafficLand / Argus / GoodVision | paid | nothing we cannot get free | ⛔ **refused** |

**Compute split (Colab Pro is not enough alone).** Colab Pro's compute-unit
allowance and session limits suit *development and short jobs*; the 250–400
GPU-hour training budget belongs on **AWS spot with checkpointing to S3**.
Rough credit maths (`ESTIMATE`, region- and market-dependent — verify at setup):
`g4dn.xlarge` (T4) spot ≈ $0.16–0.21/h → the $200 credit buys on the order of
**~1000 GPU-hours**; `g5.xlarge` (A10G) spot ≈ $0.30–0.40/h → **~500–650 hours**.
Either way the held credit plausibly covers the whole training budget, provided
every job checkpoints (spot instances can be reclaimed mid-run).

---

## 12. SOFTWARE_SYSTEM_TRACK

### Repository architecture (implemented, tested)

```
dhakaflow/        THE source tree — stable runtime interfaces + adapters +
                  our original integration. No duplicate src/ anywhere.
  common/ perception/ tracking/ sensing/ forecasting/ digital_twin/
  control/ safety/ routing/ priority/ nlp/ genai/ evaluation/
  visualization/ services/
research/         Official reproduction · fair benchmark · ablation.
  perception/ tracking/ sensing/ forecasting/ twin/ control/ routing/
configs/          Config hierarchy, one dir per subsystem (§5 below)
model_registry/   Model METADATA only — entries/*.yaml, never weights
upstream/         MANIFESTS ONLY — UPSTREAM_PINS.yaml; no clones, ever
scripts/          fetch_upstream.py and other entrypoints
tests/            Architecture + unit + integration
dashboard/        Operator UI
deployment/       Docker, IaC, service config
docs/             This plan, architecture, graduation map, resource index
artifacts/        Run outputs (gitignored except small JSON/MD evidence)
paper_labs/       FROZEN Labs 00–02 — cited, never edited
```

**research/ vs dhakaflow/ is the load-bearing split.** `research/` reproduces and
compares official algorithms; `dhakaflow/` holds the stable runtime. Official
algorithms stay official upstream code — DhakaFlow adapters translate inputs and
outputs, they never rewrite the algorithm.

Justified additions only: Docker, structured logging, health checks, experiment
tracking (MLflow), model/version provenance, FastAPI service, artifact registry,
tests, CI, S3/CloudWatch. **No decorative microservices.**

### Configuration hierarchy

`configs/{perception,tracking,forecasting,twin,control,routing,live,deployment}/`
— each non-empty, each value tagged `OFFICIAL` (from upstream's own config),
`MEASURED` (from our audit of real data), or `ASSUMED` (our choice, to be
justified or ablated). **No important hyperparameter may live only as an
unexplained hard-coded constant**; `test_config_subsystem_exists_and_is_not_empty`
fails an empty config directory.

### Model registry

`model_registry/entries/*.yaml`, loaded and validated by
`dhakaflow/common/model_registry.py`. Records architecture, paper, official repo
+ SHA, config, dataset, **remote** checkpoint URI, metrics with their evidence
domain, status and decision rationale. Two rules enforced at load:

* `checkpoint_uri` must be remote (`s3://`, `hf://`, Drive, https) — a path
  inside the repo raises.
* `WINNER` / `CHALLENGER` / `REJECTED` require **measured metrics** plus a
  written rationale, and a `WINNER` must name the benchmark it won. **No model is
  promoted on reputation.**

### Upstream fetch policy

`upstream/UPSTREAM_PINS.yaml` holds manifests only (13 repos pinned as of
2026-08-14). `scripts/fetch_upstream.py` clones each into the **gitignored
external workspace** `$DHAKAFLOW_WORKSPACE` (default `~/.dhakaflow/upstream`) —
outside the repository, so a nested repo cannot be committed even by accident —
and verifies the checked-out SHA against the pin. A floating `ref` is resolved
and must be written back before the repo may be marked `USED`. GPL upstream
(LibSignal) must carry `license_risk: HIGH` and is executed only as an isolated
benchmark process.

### Storage

| Kind | Location |
|---|---|
| Code, configs, manifests, small JSON/CSV evidence, figures | git |
| Datasets, checkpoints, training caches, large experiment outputs | **Google Drive / S3** |
| Official upstream clones | `$DHAKAFLOW_WORKSPACE` (gitignored, outside repo) |

Enforced by `test_no_model_weights_committed` and `test_no_large_tracked_files`
(10 MB ceiling).

---

## 13. OFFICIAL_REPOS_RESOURCE_POLICY

1. Official author code **is used, not reimplemented**. A hand-rolled
   approximation is never labelled a reproduction.
2. `upstream/<repo>` @ **exact SHA/tag**, unmodified. Adapters live in `dhakaflow/`.
3. Fresh-verify every resource **when its gate opens** — never from memory.
4. Per-component `RESOURCE_MANIFEST.md/.yaml` + `docs/MASTER_RESOURCE_INDEX.md`.
5. Classify USED / VERIFIED_NOT_USED / OPTIONAL / FUTURE / REJECTED. `USED`
   requires fetched **and** audited **and** actually used.
6. **License is checked before code enters the runtime.** Two live flags already:
   BNVD license `UNSPECIFIED`; LibSignal is **GPL-3.0**, which is viral — it may
   be used for benchmarking in an isolated process, but linking it into the
   DhakaFlow runtime would impose GPL on the whole platform.

---

## 14. MODEL_CANDIDATE_TO_WINNER_POLICY

```
candidates → fresh literature check → official repo @ SHA → reproduce official
result → Dhaka adapter → COMMON Dhaka benchmark → fair compare → winner(s)
→ integrate → losers retained as named baselines/challengers
```

The runtime holds **justified winners only**; every loser stays in the repo as a
reproducible baseline with its numbers. No Frankenstein model. No model deleted
without a KEEP/REJECT experiment.

---

## 15. PASS POLICY (per component)

| Gate | Meaning |
|---|---|
| **CODE_PASS** | Adapter + tests green; upstream pinned; runs on smoke config |
| **REPRODUCTION_PASS** | Official experiment reproduced within a pre-declared tolerance, or the deviation is *measured and explained* (Lab 02 precedent: explained deviation passes, unexplained fails) |
| **DHAKA_BENCHMARK_PASS** | Evaluated on the common Dhaka benchmark, fairly, against baselines |
| **INTEGRATION_PASS** | Live in the end-to-end vertical slice behind its platform interface |
| **LEARNING_PASS** | `INTERVIEW_CARD.md` complete — the 12 questions, including *the result we actually obtained* and *main weakness* |

A component is done only when **all five** are recorded.

---

## 16. 100_HOUR_EXECUTION_PLAN

**Human hours ≠ compute hours.** The 100 h is *your* focused time; GPU jobs run
in parallel on Colab/AWS and are never counted as your hours.

| Block | Human h | Deliverable |
|---|---|---|
| 0 · Skeleton vertical slice | 10 | End-to-end baseline command runs |
| 1 · Perception gate | 15 | Detector winner + per-class AP on rickshaw/CNG |
| 2 · Tracking + sensing | 10 | Tracks → flow/speed/queue/turning/mix |
| 3 · Forecasting gate (BasicTS) | 18 | 11 models, 3 horizons, winner |
| 4 · Digital twin calibration | 12 | Calibrated twin + 100–300 node sensor graph |
| 5 · Control gate + FA-MAPPO | 20 | Baselines + ablation ladder + winner |
| 6 · Routing gate | 6 | Network-wide evaluation incl. externality |
| 7 · Safety + priority | 4 | Shield hardening, fallback, robustness |
| 8 · NLP + GenAI | 6 | Incident extractor + grounded copilot |
| 9 · System, deploy, writing | 9 | API, dashboard, provenance, INTERVIEW_CARDs |
| **Total** | **110** | trims to 100 by dropping Block 8 to a demo if needed |

**Compute wall-time (parallel, not your hours):** detector fine-tunes ~30–60 GPU-h;
forecasting 11 models × 3 horizons ~60–100 GPU-h; RL 5 ablation arms ~100–200
GPU-h. **Total ≈ 250–400 GPU-hours.** This is why Colab Pro+ is the real
constraint, and why the plan front-loads baselines that produce a defensible
system even if the heaviest RL arms are still running.

---

## 17. FIRST_10_HOURS_PLAN

| # | Task | h | Blocked by |
|---|---|---|---|
| 1 | Fetch BNVD + Poribohon-BD + TFP-BD to Drive; checksums, license capture, real-file audit | 2 | **Kaggle token** |
| 2 | Resolve the two taxonomy traps (`Van`, `Easybike`) from real annotated crops | 1 | task 1 |
| 3 | `upstream/` pin: RT-DETR, ByteTrack, BasicTS, SUMO-RL, MAPPO @ exact SHAs | 1 | — |
| 4 | Vertical slice v0: COCO RT-DETR → ByteTrack → counting line → `TrafficObservation` on a real TFP-BD clip | 3 | task 1 |
| 5 | Wire v0 state → persistence forecast → Lab 02 twin → fixed-time → metrics JSON | 2 | task 4 |
| 6 | `INTERVIEW_CARD.md` for RT-DETR + ByteTrack, written from what we actually ran | 1 | task 4 |

**Exit criterion:** one command produces real numbers from real Dhaka video
through the frozen Dhaka network. Everything after that is replacing baselines
with winners.

---

## 18. RISKS_AND_BLOCKERS

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| R1 | **Sensor-graph cardinality** — 4 real camera sites cannot support graph forecasting | 🔴 **critical, structural** | Twin-generated 100–300 node graph on real topology, calibrated by real sites; real sites held out for validation. Stated openly in the paper |
| R2 | **Kaggle token missing** → no BNVD | 🔴 blocking today | You place `~/.kaggle/kaggle.json` |
| R3 | **BNVD license UNSPECIFIED** | 🔴 legal | Read Kaggle license field; if unclear, email the author. Poribohon-BD (CC BY 4.0) is the fallback primary |
| R4 | **No Dhaka live camera exists publicly** | 🟡 | Recorded TFP-BD + Google Routes; do not buy camera APIs |
| R5 | **LibSignal is GPL-3.0** | 🟡 legal | Benchmark in an isolated process; never link into runtime |
| R6 | **GPU budget** 250–400 h | 🟡 | Colab Pro+; checkpoint everything; baselines first so a defensible system exists early |
| R7 | **TFP-BD may release only frames, not videos** | 🟡 | If no temporal continuity, ByteTrack cannot be evaluated on it → tracking evaluated on the twin + declared `NOT_PUBLICLY_AVAILABLE` for real BD MOT ground truth |
| R8 | **No real Dhaka signal timings** | 🟡 | Stays `IMPORTED_HEURISTIC`; never claimed as real. Seek DMP/DTCA plans via institution |
| R9 | Scope: 20 models × 5 gates | 🟡 | BasicTS + LibSignal + SUMO-RL supply most implementations; we write adapters, not training loops |
| R10 | Zero-flow intervals break MAPE | 🟢 | Report MAPE with a validity mask; lead with MAE/RMSE |

---

**Status: DESIGN ONLY — nothing executed. Awaiting approval.**
