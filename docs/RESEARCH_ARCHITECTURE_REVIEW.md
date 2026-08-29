# RESEARCH_ARCHITECTURE_REVIEW — DhakaFlow Nexus

Date: 2026-08-29. Scope: closest REAL published systems for each of the 10 pipeline
components (video → traffic state → SUMO digital twin → forecast → same-state
counterfactual planner → signal control + rerouting, for Dhaka).

Provenance: every SHA below was resolved live via the GitHub API on 2026-08-29 unless
marked as an existing pin from `upstream/UPSTREAM_PINS.yaml` (those keep their pinned
SHA and verified date). Per the resource-traceability policy, any repo adopted from
this review must be added to `UPSTREAM_PINS.yaml` and fetched via
`scripts/fetch_upstream.py` before its gate opens — links alone do not count.

---

## Summary table

| # | Component | Chosen reference (primary) | Repo / pin |
|---|-----------|---------------------------|------------|
| 1 | Video → microscopic traffic state | Azfar et al., *Traffic Co-Simulation Framework Empowered by Infrastructure Camera Sensing and RL* (JITS 2025); OpenVTER (T-ITS 2025) for the trajectory stack; ByteTrack for association | ByteTrack @d1bf019 (pinned); `XinkaiJi/OpenVTER` @8f67ecd |
| 2 | Measurements → synchronized SUMO twin | Kušić et al., *A digital twin in transportation* (Adv. Eng. Informatics 2023) — Geneva DT-GM | `SiLab-group/DigitalTwin_GenevaMotorway` @5d2f6c2 |
| 3 | Online / rolling twin sync | DT-GM rolling DFC (IEEE 2022 + AEI 2023); DTSUMO (JITS 2025); DiTAT (SUMO Conf 2025) | same repo as #2; DTSUMO/DiTAT: no public code found |
| 4 | Forecasting in the control loop | PRGLight (IJCAI 2021 wksp) / GNN-prediction DRL (arXiv 2009.14627); FLight (Machine Learning 2025). Forecast models via BasicTS | BasicTS legacy @4c3e2d3 (pinned); Graph-WaveNet @6b162e8 (pinned); STAEformer @fc49d39 (pinned) |
| 5 | Same-state / what-if simulation | SUMO SaveAndLoad + `traci.simulation.saveState/loadState`; DiTAT window-wise try-and-pick loop as published precedent | SUMO 1.27.1 (pinned) |
| 6 | Adaptive signal control baselines | Varaiya 2013 max-pressure (TR-C); RESCO benchmark (NeurIPS 2021 D&B); SUMO actuated logic | `Pi-Star-Lab/RESCO` @f1ed9a1 (v2.0); `docwza/sumolights` @62a4f4c |
| 7 | Dynamic / predictive rerouting | SUMO rerouting device (official); TOMACS 2023 metropolitan rerouting; TR-C 2024 non-compliance study; URB benchmark | SUMO 1.27.1 (pinned); URB @0f929ed (pinned; HEAD now 87a8451) |
| 8 | Network-wide objectives | SUMO tripinfo `timeLoss`; Varaiya 2013 throughput stability; capacity-aware back-pressure (finite queues/spillback); MP + perimeter two-layer (TR-C 2023) | metric defs in SUMO 1.27.1; algorithms via RESCO/own gate code |
| 9 | MARL / MAPPO signal control | MAPPO (Yu et al., NeurIPS 2022); RESCO; sumo-rl env layer | on-policy @de66d7a4 (pinned); sumo-rl @86f0fc4 (pinned = current HEAD) |
| 10 | Weak-lane-discipline traffic | Chowdhury & Chakraborty, Khulna SUMO calibration (Transp. Eng. 2024); SUMO sublane model (Semrau & Erdmann 2016) | SUMO 1.27.1 sublane; BNVD @b4e74d1 (pinned, license blocker) |

---

## 1. Roadside video → microscopic traffic state / trajectories

PAPER (primary, closest end-to-end match):
*Traffic Co-Simulation Framework Empowered by Infrastructure Camera Sensing and
Reinforcement Learning* — Azfar, Huang, Tracy, Misiewicz, Liu, Ke / 2024 (rev. 2025) /
Journal of Intelligent Transportation Systems / https://arxiv.org/abs/2412.03925

ARCHITECTURE: input = pole-mounted infrastructure cameras (YOLOv5/YOLOv8 detection) ·
traffic-state representation = per-vehicle detections mapped into simulation
coordinates · synchronization = real-time detection feed into SUMO (+CARLA for 3D) ·
forecasting = none · controller = multi-agent RL signal control with four reward
structures · routing = SUMO default · evaluation = network flow under
perfect-vs-imperfect detection · metrics = waiting time, queue, throughput; key
finding: MARL still improves control under imperfect detection.

CODE: no public repository found (checked arXiv page and search) — if adopted as a
methodology reference only, record "no code" in the manifest; do not reimplement and
attribute.

PAPER (trajectory-extraction stack with code):
*OpenVTER: An Open Vehicle Trajectory Extraction Framework Based on Rotated Bounding
Boxes* — Ji, Han, Mao, Huang, Yu, Liu / 2025 / IEEE T-ITS 26(1):59–76 /
https://ieeexplore.ieee.org/document/10736977/

ARCHITECTURE: input = fixed/aerial video · representation = rotated-bbox vehicle
tracks → continuous trajectories (position, speed, heading, class) · sync = n/a ·
stack = stabilization → tiling → YOLOX-R rotated detection → tracking →
post-processing/denoising · evaluation = trajectory accuracy vs ground truth.

CODE: https://github.com/XinkaiJi/OpenVTER @ 8f67ecdb2dcf161de85fc5fa496320b0fcf5720a
(2024-12-10, Apache-2.0).

CODE (association, already pinned): ByteTrack official
https://github.com/FoundationVision/ByteTrack @ d1bf0191adff59bc8fcfeaa0b33d3d1642552a99
(pinned, FETCHED). Detector: RT-DETR @068dfde (pinned) with D-FINE / RT-DETRv4 /
DEIM-recipe challengers per existing pins.

WHAT WE REUSE: tracking-by-detection paradigm (detections in → tracks out) with the
official ByteTrack association untouched; OpenVTER's module decomposition
(stabilization → detection → tracking → smoothing → world-coordinate mapping) as the
Gate-1 pipeline blueprint; Azfar et al.'s evidence that imperfect roadside detection
still supports downstream control (justifies the Dhaka camera-quality budget).

DHAKA ADAPTER: homography calibration for Dhaka roadside camera poses (pixel → GPS →
SUMO coordinates); BNVD class taxonomy (rickshaw/CNG/leguna...) fed to the pinned
detector; queue/speed/count aggregation per approach — thin adapter code only.

## 2. Real traffic measurements → synchronized SUMO digital twin

PAPER: *A digital twin in transportation: Real-time synergy of traffic data streams
and simulation for virtualizing motorway dynamics* — Kušić, Schumann, Ivanjko / 2023 /
Advanced Engineering Informatics 55:101858 / DOI 10.1016/j.aei.2022.101858
(https://www.sciencedirect.com/science/article/pii/S1474034622003160)

ARCHITECTURE: input = minute-resolution traffic-counter streams (Swiss ODPMS/FEDRO) ·
representation = per-detector flow/speed · synchronization = Dynamic Flow Calibration
(DFC): SUMO `calibrator` objects driven at run-time through TraCI, fusing live counts
into the running twin every minute; runtime demand generation from external data ·
forecasting = none in-loop · controller = none (enables sim-based optimization) ·
routing = dynamic rerouting via TraCI · evaluation = twin vs field detector
flows/speeds over continuous operation · metrics = flow/speed error per detector per
interval.

CODE: https://github.com/SiLab-group/DigitalTwin_GenevaMotorway @
5d2f6c2b62c7f8162f60db7b8f8f228e31994794 (2025-02-25). Contains the SUMO Geneva
network, real traffic data, and Python runtime demand-generation/calibration code.

WHAT WE REUSE: the DFC pattern exactly — SUMO calibrators + TraCI runtime control as
the official synchronization mechanism (calibrators are stock SUMO 1.27.1, already
pinned); the repo's demand-generation loop as the reference implementation for Gate 2.

DHAKA ADAPTER: replace counter streams with Gate-1 video-derived counts/speeds per
approach; per-class calibrator flows (heterogeneous fleet); Dhaka network from Lab 02
OSM→SUMO. Nothing in the sync algorithm changes.

## 3. Online / rolling digital-twin synchronization

PAPER (conference precursor): *Building a Motorway Digital Twin in SUMO: Real-Time
Simulation of Continuous Data Stream from Traffic Counters* — Kušić, Schumann,
Ivanjko / 2022 / IEEE (MT-ITS) / https://ieeexplore.ieee.org/document/9899796/
Also: *Make it Real: On-the-Fly Synchronized Digital Twin of Geneva Motorway* (2022).

PAPER (newer, network-wide): *A "digital twin" traffic simulation tool for
network-wide real-time traffic monitoring and management* (DTSUMO) / 2025 / Journal of
Intelligent Transportation Systems / DOI 10.1080/15472450.2025.2553287

ARCHITECTURE (DTSUMO): input = detector data feeds · representation = high-resolution
network-wide traffic state · synchronization = short-window rolling simulation
re-seeded from live data, trajectories joined across consecutive windows; reflects
congestion and road closures · evaluation = computational efficiency + accuracy vs
stock SUMO tooling.

PAPER (video-driven, control-in-loop — the DiTAT item): *Digital Twin-Aided Municipal
Traffic Control* — Pradhananga et al. / 2025 / SUMO User Conference Proceedings /
https://www.tib-op.org/ojs/index.php/scp/article/view/2619

ARCHITECTURE (DiTAT): input = roadside surveillance video → per-vehicle start time,
speed, in-zone, out-zone · representation = extracted volumes per zone-pair per
window · synchronization = window-by-window re-simulation in SUMO as the digital
twin · controller = try candidate signal settings in the twin, deploy the best to the
field, repeat each window (bidirectional physical↔twin loop) · metrics = transport
performance lift under real traffic.

CODE: Geneva repo as in §2 (@5d2f6c2). DTSUMO: described as a Python package; no
public repository located — pin at clone time if the authors release it. DiTAT: no
public code found (methodology reference).

WHAT WE REUSE: rolling-window re-synchronization cadence (DT-GM: 1-minute fusion;
DiTAT: per-window re-simulate → evaluate → deploy) as the Gate-2 loop skeleton; DiTAT
is the closest published match to DhakaFlow's overall video→twin→control concept and
is the primary "we differ by X" citation (DiTAT has no learned forecasting, no
saveState-based same-state counterfactuals, no MARL, no heterogeneous-traffic model).

DHAKA ADAPTER: window length tuned to Dhaka camera latency; state divergence monitor
(twin vs live counts) that triggers re-sync — small supervisory script only.

## 4. Traffic forecasting integrated into control

PAPER: *PRGLight: A novel traffic light control framework with Pressure-based RL and
GNN prediction* — Zhao, Wang / 2021 / IJCAI 2021 RL4ITS workshop (SSRN 4040526,
https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4040526)
Related: *A Traffic Light Dynamic Control Algorithm with Deep Reinforcement Learning
Based on GNN Prediction* / 2020 / https://arxiv.org/abs/2009.14627
Newer: *FLight: optimization algorithm for traffic lights based on short-term traffic
state forecast* / 2025 / Machine Learning (Springer) / DOI 10.1007/s10994-025-06785-2

ARCHITECTURE (PRGLight): input = lane-level counts · representation =
pressure (PRCOL: pressure with remaining capacity of outgoing lane — also
spillback-aware, relevant to §8) · forecasting = GNN predicts future volume ·
controller = RL picks phase (PRCOL reward), predicted state sets green duration ·
evaluation = simulation benchmarks vs SOTA TSC · metrics = travel time, throughput,
speed, queue.

CODE: no maintained official PRGLight/FLight repo located — treat as architecture
references. The forecasting models themselves come from existing pins:
BasicTS-legacy @4c3e2d373c647667c2123e1591f2d79c229dfcc6 (GWNet/DCRNN/STAEformer under
the fair harness), STAEformer @fc49d39, Graph-WaveNet @6b162e8 (PINNED_NOT_FETCHED),
chronos-forecasting @8589d19.

WHAT WE REUSE: the decomposition "forecast module → augmented controller state /
duration decision" (forecast informs, controller decides); BasicTS as the only
training/eval harness (no per-model loops, per pins policy).

DHAKA ADAPTER: Forecast-Aware MAPPO = pinned MAPPO with forecast features appended to
the observation vector (extension, not reimplementation, per the MAPPO pin's `why`);
Dhaka dataset adapter for BasicTS already exists
(`research/forecasting/basicts_adapter.py`).

## 5. Same-state / what-if simulation (counterfactual planner)

PAPER/DOC (mechanism, official): SUMO *SaveAndLoad* documentation —
https://sumo.dlr.de/docs/Simulation/SaveAndLoad.html and
`traci.simulation.saveState/loadState` (implemented via
https://github.com/eclipse-sumo/sumo/issues/6201). Options `--save-state.rng` (exact
stochastic reproducibility), `--save-state.transportables`.

PAPER (published precedent for what-if-in-the-twin): DiTAT (§3) — evaluates candidate
signal settings in the SUMO twin before field deployment, window by window.
Also: *UCATSC: Uncertainty-Aware Constrained Traffic Signal Control Under Vision-Based
Partial Observability* / 2026 / arXiv https://arxiv.org/abs/2602.07784 — finite-horizon
counterfactual rollouts in belief space with matched seeds in SUMO (no code found).

ARCHITECTURE (the methodology): snapshot the synchronized twin state (saveState with
RNG) · branch N counterfactual runs (candidate signal plans / routing policies) from
the identical state via loadState · roll each forward over the planning horizon ·
score on §8 objectives · deploy argmax; matched seeds make branch differences causal,
not stochastic.

CODE: entirely stock SUMO 1.27.1 (already pinned). No third-party code needed — this
is the one component where the "official implementation" is SUMO itself.

WHAT WE REUSE: saveState/loadState with `--save-state.rng` as the exact same-state
branching mechanism; UCATSC's matched-seed evaluation protocol as the honesty
standard for counterfactual claims.

DHAKA ADAPTER: a thin branch-manager (snapshot cadence, horizon, candidate set,
scoring) — pure orchestration around TraCI calls.

## 6. Adaptive traffic-signal control (classical baselines)

PAPER (algorithmic source of truth, original): *Max pressure control of a network of signalized
intersections* — Varaiya / 2013 / Transportation Research Part C 36:177–195 / DOI
10.1016/j.trc.2013.08.014. Provable network throughput stability
(maximum stability region), decentralized, model-free per intersection.

PAPER (benchmark with SUMO implementations): *Reinforcement Learning Benchmarks for
Traffic Signal Control (RESCO)* — Ault, Sharon / 2021 / NeurIPS 2021 Datasets &
Benchmarks / https://github.com/Pi-Star-Lab/RESCO. Ships non-learning baselines
Fixed-Time, Max-Pressure, Max-Wave on real scenarios (Cologne, Ingolstadt/Luxembourg,
Salt Lake City) via SUMO subscription API.

ARCHITECTURE (RESCO protocol): input = SUMO scenario + detector subscriptions ·
controller = per-intersection agent or static baseline · evaluation = fixed real
scenarios, standardized episode protocol · metrics = avg delay/wait, queue,
trip time.

CODE:
- RESCO: https://github.com/Pi-Star-Lab/RESCO @ f1ed9a174f8de41fc9d8689373b836bc882570dc
  (RESCO v2.0, 2025-10-28) — NOTE v2.0 is a major update; verify protocol
  compatibility vs the papers before pinning.
- sumolights (Webster's, Max-pressure, SOTL, DQN, DDPG):
  https://github.com/docwza/sumolights @ 62a4f4cecd5a10555e40e53afd91156139b0fe1e (2019).
- SUMO built-in actuated control (gap-based, `tlLogic type="actuated"`): stock
  SUMO 1.27.1, https://sumo.dlr.de/docs/Simulation/Traffic_Lights.html.
- LibSignal (IDQN/CoLight/PressLight): https://github.com/DaRL-LibSignal/LibSignal @
  127af9f93902778e556de2eedb2b606c4c9447e6 — fills the null URL in the pin file;
  GPL-3.0, isolated-process-only per existing pin policy.
- CoLight @04440b7 already pinned.

WHAT WE REUSE: Varaiya's pressure definition and switching rule exactly as published;
RESCO's baseline implementations + evaluation protocol as the Gate-6 comparison
harness; SUMO actuated as the zero-learning baseline.

DHAKA ADAPTER: pressure computed from video-derived per-class queue estimates
(PCU-weighted) instead of induction loops; Dhaka phase diagrams. The MP update law is
untouched.

## 7. Dynamic / predictive rerouting

PAPER/DOC (mechanism, official): SUMO Automatic Routing / rerouting device —
https://sumo.dlr.de/docs/Demand/Automatic_Routing.html and
https://sumo.dlr.de/docs/Simulation/Routing.html. `device.rerouting.probability`
(bounded equipment/compliance share), periodic re-planning on smoothed edge travel
times, times overridable via TraCI (`edge.adaptTraveltime`) — the hook for
forecast-informed routing.

PAPER (scale study): *Simulating the Impact of Dynamic Rerouting on
Metropolitan-scale Traffic Systems* / 2023 / ACM TOMACS / DOI 10.1145/3579842 —
mixed rerouting/non-rerouting fleets at metropolitan scale, varying rerouting ratios.

PAPER (compliance): *Navigating the non-compliance effects on system optimal route
guidance using reinforcement learning* / 2024 / Transportation Research Part C /
https://www.sciencedirect.com/science/article/pii/S0968090X24002420 — users may
deviate from TMC guidance; models mixed equilibrium under partial compliance.

PAPER (benchmark, pinned): *URB: Urban Routing Benchmark* / NeurIPS 2025 D&B /
https://arxiv.org/abs/2505.17734 / https://github.com/COeXISTENCE-PROJECT/URB @
0f929ed18f5f8f3993df29853e32b0ece3ae2f6d (pinned; upstream HEAD 87a8451 on
2026-08-27 — re-verify at gate open per pin policy).

ARCHITECTURE (composite): input = live/forecast edge travel times · routing = SUMO
rerouting device with probability p as the compliance knob; predictive variant
injects forecast travel times via TraCI before each re-planning round · evaluation =
sweep p ∈ {0, 10, …} vs metrics · metrics = network travel time, time loss,
per-OD fairness.

WHAT WE REUSE: the stock rerouting device as the entire routing engine (no custom
router); `adaptTraveltime` as the only forecast-injection point; TOMACS/TR-C studies
for the bounded-compliance experimental design; URB scenarios for external validity.

DHAKA ADAPTER: compliance prior for Dhaka (low smartphone-navigation share, per-class
p: cars vs buses vs rickshaws); forecast-to-edge-travel-time mapping from Gate-4
outputs.

## 8. Network-wide congestion-management objectives

PAPER/DOC (metric, official): SUMO tripinfo `timeLoss` — time lost to driving below
free-flow speed (https://sumo.dlr.de/docs/sumo.html, tripinfo output); network total
time loss = Σ over vehicles; throughput = arrived vehicles per interval.

PAPER (throughput objective, theory): Varaiya 2013 (§6) — max-pressure maximizes
network throughput (stability region).

PAPER (spillback-aware objective): *Capacity-aware back-pressure traffic signal
control* — Gregoire, Qian, Frazzoli, de La Fortelle, Wongpiromsarn / 2014 (arXiv
2013) / IEEE TCNS / https://arxiv.org/abs/1309.6484 — back-pressure corrected for
finite queue capacity, i.e. explicit spillback penalty; PRGLight's PRCOL (§4) is the
learned-control analogue.

PAPER (network-level layered objective): *Two-layer adaptive signal control...
combining efficient Max Pressure with Perimeter Control* — Tsitsokas, Kouvelas,
Geroliminis / 2023 / Transportation Research Part C / https://arxiv.org/abs/2210.10453
— MFD-based perimeter control on top of local MP for dynamically congested networks
(direct bridge to Lab 00 UTD19/MFD work).

CODE: metrics are stock SUMO outputs (tripinfo/edgedata, SUMO 1.27.1 pinned);
capacity-aware BP and perimeter layer have no canonical maintained repo — implement
inside the gate from equations, cite, and record "no official code" in the manifest.

WHAT WE REUSE: objective = network total timeLoss (primary) + throughput + spillback
penalty from finite-queue-capacity terms (capacity-aware BP form); MFD/perimeter
framing reuses Lab 00 estimators.

DHAKA ADAPTER: PCU-weighted timeLoss and queue-capacity terms for the heterogeneous
fleet; spillback detection from video queue-length estimates at short Dhaka links.

## 9. MARL / MAPPO traffic-signal control

PAPER: *The Surprising Effectiveness of PPO in Cooperative Multi-Agent Games* (MAPPO)
— Yu, Velu, Vinitsky, Gao, Wang, Bayen, Wu / 2022 / NeurIPS 2022 /
https://arxiv.org/abs/2103.01955

CODE: official https://github.com/marlbenchmark/on-policy @
de66d7a4b23fac2513f56f96f73b3f5cb96695ac (pinned, FETCHED).
Env layer: https://github.com/LucasAlegre/sumo-rl @
86f0fc41401eeca724b2e8878f5020dc6d70c9b4 (pinned; confirmed 2026-08-29 this is still
upstream HEAD). Benchmark: RESCO @f1ed9a1 (§6).

ARCHITECTURE: input = per-intersection local observation (queues, phase, +Gate-4
forecast features in our variant) · representation = PettingZoo parallel env
(sumo-rl) · controller = MAPPO centralized-critic/decentralized-actors, parameter
sharing · routing = fixed during training · evaluation = RESCO-style fixed scenarios,
multiple seeds, vs Fixed-Time/actuated/MP baselines · metrics = avg delay, queue,
timeLoss, throughput.

PAPER (recent application, confirms viability): *Smart Traffic Signal Control in
Urban Environments Leveraging SUMO and Curiosity-Enhanced MAPPO* / 2026 / IET
Intelligent Transport Systems / DOI 10.1049/itr2.70247 — MAPPO variants on a 16-signal
real Helsinki network in SUMO; establishes vanilla MAPPO as a recognized SUMO TSC
baseline.

WHAT WE REUSE: official MAPPO trainer unmodified (extension only, per pin); sumo-rl
env API; RESCO protocol + its published baseline numbers for sanity ranges.

DHAKA ADAPTER: observation/reward builders on video-derived per-class state;
forecast-augmented observation (Forecast-Aware MAPPO); Dhaka SUMO scenario as a new
sumo-rl environment definition — adapters only.

## 10. Heterogeneous / weak-lane-discipline traffic

PAPER: *Calibration of SUMO Microscopic Simulation for Heterogeneous Traffic
Condition: The Case of the City of Khulna, Bangladesh* — Chowdhury, Chakraborty /
2024 / Transportation Engineering 18:100281 / DOI 10.1016/j.treng.2024.100281

ARCHITECTURE: input = field video (queue length, travel time) at a Bangladeshi CBD
intersection · representation = SUMO with mixed fleet (motorized + non-motorized) ·
method = calibrate car-following params by minimizing RMSE of queue length and travel
time; reported σ=0.3, τ=1.4 for weak-lane-discipline aggressive mixed traffic ·
metrics = RMSE queue length, travel time.

PAPER/DOC (lateral behavior, official mechanism): SUMO sublane model —
https://sumo.dlr.de/docs/Simulation/SublaneModel.html; Semrau & Erdmann (2016),
mixed-traffic simulation by lane→sublane resolution; `--lateral-resolution` ≤ width
of the narrowest vehicle (motorcycles/rickshaws → ≈0.4 m), per-vType `latAlignment`,
`minGapLat`, `lcSublane` — supports side-by-side motorcycles and lateral seepage.

Related: *Towards simulating non-lane based heterogeneous road traffic of less
developed countries using authoritative polygonal GIS map* (Simulation Modelling
Practice and Theory, 2020); Sri Lanka SUMO calibration (2021) for regional parameter
ranges.

CODE: sublane model is stock SUMO 1.27.1 (pinned) — no third-party code. Khulna
paper has no code; its calibrated parameter values are the reusable artifact. Vehicle
taxonomy: BNVD @b4e74d1 (pinned — license still UNSPECIFIED, blocker before use).

WHAT WE REUSE: sublane model as the official lateral-behavior mechanism; Khulna
σ/τ values as calibration priors; RMSE-on-queue-and-travel-time as the Gate-2
calibration objective (it matches exactly what Gate-1 video measures).

DHAKA ADAPTER: per-class vTypes (bus, car, CNG auto-rickshaw, cycle-rickshaw,
motorcycle) with widths/latAlignment/speed factors; re-fit σ, τ, lateral params
against Dhaka video trajectories rather than adopting Khulna values blind.

---

## Build implications — what each gate must call

**Gate 1 (perception):** RT-DETR @068dfde (or D-FINE/RT-DETRv4 challengers per pins)
for detection → official ByteTrack @d1bf019 for association, both executed from the
pinned upstream workspace; OpenVTER @8f67ecd as the pipeline-structure reference
(consider pinning if its stabilization/post-processing modules are executed rather
than reimplemented). Adapter surface: homography + BNVD class map + queue/speed/count
aggregation. Azfar et al. 2024 is the citation that imperfect detection still supports
control.

**Gate 2 (twin-sync):** stock SUMO 1.27.1 calibrator objects + TraCI, driven by the
DT-GM demand-generation pattern — pin `SiLab-group/DigitalTwin_GenevaMotorway`
@5d2f6c2 and call its runtime-calibration code where it applies; DiTAT and DTSUMO are
protocol citations (no code). Calibration objective = Khulna-style RMSE(queue, travel
time); sublane config per §10. Counterfactual branching (Gate 5 function) is pure
SUMO saveState/loadState with `--save-state.rng`.

**Gate 6 (signal baselines):** SUMO built-in actuated (stock); Max-Pressure per
Varaiya 2013 via RESCO's implementation — pin `Pi-Star-Lab/RESCO` @f1ed9a1 (verify
v2.0 protocol vs paper; `docwza/sumolights` @62a4f4c is the fallback MP/Webster's
implementation); LibSignal @127af9f (URL now resolved — update the null-URL pin)
strictly as an isolated GPL process. MAPPO from on-policy @de66d7a4 + sumo-rl
@86f0fc4; evaluation on the RESCO protocol with network timeLoss/throughput/spillback
objectives (§8).

**Gate 7 (routing):** stock SUMO rerouting device with `device.rerouting.probability`
as the compliance knob; forecast injection only via TraCI `adaptTraveltime`; URB
@0f929ed (pinned; re-verify — upstream moved to 87a8451) for benchmark scenarios;
TOMACS 2023 + TR-C 2024 define the bounded-compliance sweep design.

**Pin-file actions:** add DigitalTwin_GenevaMotorway @5d2f6c2, RESCO @f1ed9a1,
OpenVTER @8f67ecd (if executed), sumolights @62a4f4c (fallback); fill LibSignal URL
= https://github.com/DaRL-LibSignal/LibSignal @127af9f; note sumo-rl pin re-verified
2026-08-29 (= HEAD) and URB upstream drift.
