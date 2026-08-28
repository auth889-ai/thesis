# INTERVIEW CARDS — per-component defense preparation

Format per component: what/why/how (official source), the result we ACTUALLY
obtained, protocol, evidence file, main weakness (stated before the committee
finds it), and the answer to the hardest expected question.

---

## 1 · Perception (RT-DETR r50, Dhaka fine-tune)
- **What/why:** transformer detector (CVPR 2024) fine-tuned so the system sees
  rickshaw/CNG/easy-bike — classes absent from COCO; without them no Dhaka
  traffic state exists.
- **Official source:** `lyuwenyu/RT-DETR` @ `068dfde6`, authors' configs and
  COCO+Objects365 checkpoint; official evaluator's own `eval.pth`.
- **Result obtained:** mAP50:95 **0.711** (dataset paper's best published:
  0.643); AP50 rickshaw 0.904 / CNG 0.961 / easy-bike 0.965.
- **Protocol:** Poribohon-BD official (CC BY 4.0, 9,058 imgs, audited to the
  paper's count), frozen split `300aabc8`, fair 24-epoch budget.
- **Evidence:** `artifacts/p1_triage/triage.json`; ckpt sha `27852d84…`.
- **Main weakness:** single dataset track so far (BNVD licence unresolved →
  internal-only); night/rain slices not separately reported.
- **Hardest question — "your mAP beats the paper; why?"** Different
  architecture generation (DETR-family vs YOLOv5-8) + COCO+Objects365
  pretraining; same-protocol comparison, not cherry-picking — the per-class
  breakdown is in the same file.

## 2 · Forecasting (Graph WaveNet et al. via BasicTS)
- **What/why:** predict each road segment 5/15/30 min ahead — PREVENT mode's
  eyes; horizons map to real actuation lead times.
- **Official source:** BasicTS legacy harness @ `4c3e2d3` (published
  fair-comparison pipeline); official model configs, only dataset name +
  node count patched.
- **Result obtained:** GWNet MAE **0.44 m/s @15 min** vs persistence floor
  1.39 (3.2×); DCRNN 0.53; STID 1.09; STAEformer incomplete on CPU
  (reported as such).
- **Protocol:** chronological split, masked metrics, 250-sensor twin graph.
- **Evidence:** `artifacts/p3_results/`, GCS `out/p3/`.
- **Main weakness:** simulated-domain training data (twin), declared
  `DHAKA_SIMULATED_SENSOR_GRAPH`; real-site validation anchors are the
  planned follow-up.
- **Hardest question — "simulated data, so what does 0.44 mean?"** It means
  the model learns the twin's dynamics 3× better than the floor — the claim
  is *graph models beat naive forecasting on realistic Dhaka topology*, never
  "we predict real Dhaka at 0.44"; that separation is enforced in code
  (`real_world_claim_supported == False`).

## 3 · Digital twin (SUMO 1.27.1, frozen R1 network)
- **Result obtained:** 24 h × 3 seeds × 250 sensors generated; 7/7 acceptance
  checks; calibration part A → demand scale **0.584** from 3 live captures.
- **Evidence:** `artifacts/p2_sensor_graph_full/P2_PASS_EVIDENCE.json`,
  `artifacts/twin_calibration_A.json`.
- **Main weakness:** synthetic structured demand (calibrated network-level,
  not OD-level yet — part B pending); signal programs are
  `IMPORTED_HEURISTIC`, never claimed as real Dhaka timings.
- **Hardest question — "why should we believe your twin?"** Every claim from
  it is labelled simulated; its topology is checksummed real OSM; its
  network-level congestion is matched to live Google Routes captures; and the
  first pre-peak capture was *rejected by our own tooling* as unrepresentative
  — the calibration record shows the machinery refusing to cheat.

## 4 · Routing (system-optimal vs selfish)
- **Result obtained:** **−19.5% mean delay** (p = 1.3×10⁻⁵, Cohen's d 2.98,
  10 seeds/arm, 3,000 identical trips); corridor demo: 209 s→161 s.
- **Evidence:** `artifacts/due_dso_stats/v200/result.json`;
  `research/routing/r1_router.py`.
- **Main weakness:** DSO assumes compliance (everyone accepts assigned
  routes); partial-compliance sensitivity is future work.
- **Hardest question — "how is total delay reduced when trapped cars can't
  move?"** Rerouting stops the jam being FED: upstream vehicles divert, the
  queue stops growing at the back and drains from the front — and diverted
  vehicles spend less time on the road, so total vehicle-hours fall (measured:
  199 veh·h lifted, 129 absorbed, 70 eliminated).

## 5 · Signal control (baselines + learned, at-checkpoint)
- **Result obtained:** fixed-time 547.7 s; classical Max-Pressure **619.0 s
  (+13% WORSE — uncoordinated greed causes spillback at network scale)**;
  learned MAPPO 558.9 s; MAPPO+pressure **551.3 s** at 400k steps — ties
  fixed-time, beats classical adaptive by 11%; forecast/fp/full rungs
  training, reported at-checkpoint.
- **Evidence:** `artifacts/control_baselines/`, `artifacts/rl_eval/`.
- **Main weakness:** 400k steps ≈ early training (TSC literature uses
  millions); single training seed per rung so far.
- **Hardest question — "your RL doesn't beat fixed-time, is it a failure?"**
  At this budget it *matches* tuned static plans while the classical adaptive
  method degrades 13% — the coordination hypothesis is confirmed against the
  right baseline; the ladder's trend (+pressure > plain) shows features
  helping. Honest at-checkpoint reporting is the protocol, pre-declared.

## 6 · PREVENT mode
- **Result obtained:** persistence-trigger nets **+1.2%** (variance −9.8% to
  +10.9%); v1's unbounded diversion backfired +66% (bug found, fixed,
  documented). **Finding: prevention value is gated by forecast quality** —
  the direct motivation for GWNet-in-the-loop and the learned controller.
- **Evidence:** `artifacts/prevent_experiment/result.json`.
- **Main weakness:** GWNet-trigger variant still queued for compute.
- **Hardest question — "so prevention doesn't work?"** Naive prevention with a
  floor-grade forecast breaks even — exactly the negative control the thesis
  needs: it isolates *forecast quality* as the active ingredient.

## 7 · Live pipeline & domain shift
- **Result obtained:** any-input demo at near-real-time (dense rush clip:
  10/11 windows CONGESTED → reroute triggered; quiet clip → correctly no
  action). Domain shift measured: on US cameras confidence 0.60 and **40
  phantom CNGs/60 frames** — the quantified cost of foreign deployment.
- **Evidence:** `artifacts/react_demo_rush/`, `artifacts/case_*/`,
  `artifacts/domain_shift/report.json`.
- **Main weakness:** camera→edge mapping uses a configured location per
  camera (no auto-geolocation).
- **Hardest question — "is the demo scripted?"** Same command, two inputs,
  opposite verdicts (act vs no-action) — a script cannot produce the
  no-action branch; run it live on any video you supply.
