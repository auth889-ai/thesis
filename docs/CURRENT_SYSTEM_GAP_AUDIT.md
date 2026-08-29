# CURRENT SYSTEM GAP AUDIT

Read-only trace of the actual runtime path, 2026-08-29:
`app.py` (upload) → `scripts/case_report.py` → `scripts/demo_react.py:run_rtdetr` →
`research/perception/rtdetr_bridge.py`/`rtdetr_dhaka.py` → `research/routing/r1_router.py` →
`scripts/same_state_counterfactual.py` → `scripts/four_pane_report.py` → back into `app.py` UI.
Training/eval side: `research/control/{sumo_marl_env,train_sumo_signals,eval_policy,gwnet_in_loop}.py`.

Gate mapping (auditor's judgment against docs/SYSTEM_DESIGN.md gate table):
G1 REAL_STATE · G2 REAL_ROUTE · G3 TWIN_SYNC/CALIBRATION · G4 SAME_STATE_COUNTERFACTUAL ·
G5 FORECAST_IN_LOOP · G6 SIGNAL_CONTROL_BASELINES · G7 EVAL_PAIRING ·
G8 REPORT/UI HONESTY · G9 MAPPO CLAIMS.

Decisions: **REPLACE** (mechanism must change) · **REMOVE** (delete) ·
**KEEP-WITH-LABEL** (acceptable if explicitly declared where it is shown).

## Summary table

| # | Finding | Severity | Gate | file:line | Decision |
|---|---------|----------|------|-----------|----------|
| F1 | Stationary-queue video reads FREE: congestion is self-referenced to this video's own 95th-pct speed | BLOCKER | G1 | scripts/demo_react.py:98,109–119,286,296–307 | REPLACE |
| F2 | Congestion verdict computed from `_IoUTracker` IDs on the real app path (ByteTrack only on unused YOLO path) | BLOCKER | G1 | scripts/demo_react.py:170–210,250,272; scripts/case_report.py:75–76 | REPLACE |
| F3 | No physical speed anywhere — only `mean_speed_norm` (px/diag/s); pixel motion is NOT mislabeled as m/s (defect 6 REFUTED as stated), but no metric evidence exists either | MINOR | G1 | scripts/demo_react.py:93,122,281 | KEEP-WITH-LABEL |
| F4 | Frame stride 5 (~1 of 5 frames analysed) undeclared in any report | MINOR | G1 | scripts/demo_react.py:249,263 | KEEP-WITH-LABEL |
| F5 | Registered-camera coordinate table hard-coded and triplicated | MINOR | G1/G2 | app.py:27; scripts/case_report.py:38–43; scripts/same_state_counterfactual.py:50–51 | KEEP-WITH-LABEL |
| F6 | Detector weights + pinned-conda python paths hard-wired | MINOR | G1 | scripts/case_report.py:46; scripts/demo_react.py:167 | KEEP-WITH-LABEL |
| F7 | Hard-coded Shahbagh destination — every trip in every case report ends at Shahbagh; shahbagh camera ⇒ origin≈destination degenerate route | MAJOR | G2 | scripts/case_report.py:45,107,115 | REPLACE |
| F8 | Arbitrary ×5.0 jam multiplier on 10 edges regardless of measured severity | MAJOR | G2 | scripts/case_report.py:111–112 (also r1_router.py:140 demo) | REPLACE |
| F9 | Karwan Bazar hard fallback: REFUTED on app path (honest LOCATION_REQUIRED); only a standalone CLI default remains | MINOR | G2/G3 | scripts/same_state_counterfactual.py:240 | REMOVE (the default) |
| F10 | Twin demand is a fixed pre-baked route file `trips_003.rou.xml.gz` (E4 v200), not derived from the video | BLOCKER | G3 | scripts/same_state_counterfactual.py:40,81 | KEEP-WITH-LABEL now / REPLACE at next gate |
| F11 | Calibration scale 0.584 displayed but consumed by NO scenario generation (twin, control, prevent all use uncalibrated demand) | MAJOR | G3 | scripts/build_results_matrix.py:82–87; docs/RESULTS_MATRIX.md:18 vs same_state_counterfactual.py:40, sumo_marl_env.py:31, run_control_baselines.py:32, prevent_experiment.py:34 | REPLACE |
| F12 | `seed=11`, `T0_TRIGGER_STOPPED=250`, `T0_MAX_S=7200`, `HORIZON_S=600`, `ACT_MIN_QUEUE=20` hard-wired: identical twin numbers for every congested video at a given camera | MAJOR | G3 | scripts/case_report.py:155–157; scripts/same_state_counterfactual.py:42–48 | REPLACE/KEEP-WITH-LABEL |
| F13 | t₀ is when the canned demand jams the network, and the intervention TLS is retargeted to the most-queued junction anywhere — yet the report says "the twin reproduced this camera's congestion" | MAJOR | G3/G8 | scripts/same_state_counterfactual.py:109–127; scripts/case_report.py:199–200 | REPLACE wording + mechanism |
| F14 | "queue −75%" declared success while network metrics worsen (stopped 692→706, arrivals 997→994; seed-13 run even has control queue 38 vs 8) | BLOCKER | G4 | scripts/case_report.py:197–206; scripts/four_pane_report.py:56–57,109; artifacts/same_state/case_rush_live/result.json | REPLACE |
| F15 | Precomputed DUE/DSO v200 (−19.5%, Aug 15) attached to every fresh video's report; HTML labels it OFFLINE but `case.json` names it `network_scale_proof` and app KPI banner shows it as a system stat | MAJOR | G4/G8 | scripts/case_report.py:171,185–188,248–255; app.py:87 | KEEP-WITH-LABEL (strengthen) |
| F16 | Forecast feature is zero for essentially the whole training episode: 12×300 s = 3600 s warm-up = the entire default 3600 s episode; first third of eval too | BLOCKER | G5/G9 | research/control/gwnet_in_loop.py:24,96–99; research/control/train_sumo_signals.py:69; research/control/eval_policy.py:41 | REPLACE (history preload) |
| F17 | GWNet checkpoint/scaler live only under `/workspace`-or-`BasicTS_legacy` (absent from repo) — FA arms unrunnable/unverifiable here; MAE 0.44 traceable only to a log | MAJOR | G5 | research/control/gwnet_in_loop.py:20–23,41–43,62–68; artifacts/p3_results/GWNet_cpu.log:1462 | KEEP-WITH-LABEL + pin checkpoint |
| F18 | `vfree` = first-observed-bin speeds and time-of-day = sim-bin index %288 — both self-referential, misaligned with training normalization | MINOR | G5 | research/control/gwnet_in_loop.py:97–98,101 | REPLACE |
| F19 | Action 0 "hold/extend current green" is a NO-OP: SUMO's fixed program auto-advances regardless; the documented Discrete(2) hold semantics do not exist | BLOCKER | G6/G9 | research/control/sumo_marl_env.py:9–13,112–115 | REPLACE |
| F20 | Off-by-one seed pairing: policy eval "seed s" actually simulates SUMO seed s+1 (`reset()` starts with `seed0 + episode`), baselines use s directly — "PAIRED held-out seeds 11–13" is 12–14 vs 11–13 | MAJOR | G7 | research/control/sumo_marl_env.py:99–100 vs research/control/run_control_baselines.py:41–44; docs/RESULTS_MATRIX.md:9–13 | REPLACE |
| F21 | Stale hard-coded baselines 547.7/619.0 embedded in eval JSON + printed % (paired reruns are 535.9/586.7) | MAJOR | G7 | research/control/eval_policy.py:119,124; artifacts/rl_eval/eval_mappo.json | REMOVE |
| F22 | Eval horizon 10800 s vs training 3600 s — policy evaluated far outside its training distribution, undeclared | MINOR | G7 | research/control/eval_policy.py:41; research/control/train_sumo_signals.py:69 | KEEP-WITH-LABEL |
| F23 | Forecasting matrix rows hard-coded string literals despite "reads only result files (never invents)" docstring | MAJOR | G7/G8 | scripts/build_results_matrix.py:5,32–36 | REPLACE |
| F24 | Model-number claims: mAP 0.711 EVIDENCED (triage.json + pinned ckpt + sha256); −19.5% EVIDENCED (v200/result.json); MAE 0.44 log-only (no ckpt in repo); −75% is the misleading F14 number | MAJOR | G8 | artifacts/p1_triage/triage.json; artifacts/p1_winner/checkpoint.sha256; app.py:85–89 | KEEP-WITH-LABEL / fix −75% |
| F25 | UI claims "nothing pre-baked / no mockups / every number regenerates / Steps 1–5 computed fresh — including the twin prediction" while the twin runs canned demand + fixed seed and the KPI banner is static HTML | BLOCKER | G8 | app.py:8–11,82,85–89; scripts/case_report.py:230–231; scripts/four_pane_report.py:121–122 | REPLACE wording |
| F26 | Dead "bundled sample" (`SAMPLES` → prebuilt artifacts/react_demo_rush) promised in docstring, unused in UI | MINOR | G8 | app.py:28–30 | REMOVE |
| F27 | Front-page "Latest proof" iframe shows the most-recent four-pane from ANY previous run, regardless of the input just uploaded | MINOR | G8 | app.py:110–113,145–148 | KEEP-WITH-LABEL |
| F28 | Pre-recorded `corridor_before_after.mp4` embedded in every congested report (labeled offline — acceptable) | MINOR | G8 | scripts/case_report.py:217,249 | KEEP-WITH-LABEL |

---

## Detail by gate

### Gate 1 — REAL_STATE (perception → state)

**F1 (BLOCKER) — relative-speed congestion logic fails on a video that starts jammed.**
The reference speed is the rolling 95th percentile of speeds observed *in this same
video* (`scripts/demo_react.py:98` and `:286`; verdict at `:109–119` / `:296–307`).
A video that opens on a stationary queue produces `ref ≈ 0`; the tests
`mean_v < SLOW_FRACTION * ref` and `ref and mean_v < ...` then classify total
gridlock as **FREE** — the single most important input class for a Dhaka congestion
system is the one the detector logic cannot see. `n_stopped` (`:99–100`, `:287–288`)
is likewise gated on `ref > 0`. SYSTEM_DESIGN.md line 48 already lists
"stationary-queue absolute evidence" as v2 — so this is a *declared* gap, but it
blocks Gate 1 regardless.
Fix: absolute evidence — track-persistence duration + occupancy + (once F3 v2 lands)
calibrated metric speed; percentile reference only as a secondary signal.

**F2 (BLOCKER) — the app path measures state through the toy IoU tracker.**
`case_report.py:75–76` always calls `run_rtdetr`, which uses `_IoUTracker`
(`demo_react.py:170–210`, instantiated at `:250`, IDs consumed at `:272–284`).
The class docstring says "for OVERLAY continuity only (never a benchmark)"
(`:171`), but the IDs feed `frame_speeds`/`speeds` (`:277–284`), which feed the
congestion verdict — i.e., it *is* load-bearing on the exact path the examiner's
upload takes. ByteTrack is wired only into the YOLO/COCO path (`:78`) that
`case_report.py` never uses. Greedy IoU matching in dense, occluded Dhaka traffic
fragments IDs, which inflates apparent motion (new ID = no speed sample) and
corrupts the stopped-fraction statistic.
Fix: run official ByteTrack on the RT-DETR detections in the bridge loop
(detections are already boxes+scores; ByteTrack is detector-agnostic).

**F3 (MINOR) — defect "pixel motion presented as physical speed": REFUTED as stated.**
All speeds are normalized pixel units, honestly named `mean_speed_norm` /
`ref_speed_norm` (`demo_react.py:93,120–124,281,308–312`); nothing on the runtime
path renders them as m/s or km/h. The real gap is the *absence* of any metric
speed (needed for F1's absolute thresholds and for twin part-B calibration).
Keep the label; add per-camera homography when Gate 1 v2 lands.

**F4 (MINOR)** — `stride = 5` (`demo_react.py:249`) analyzes ~20% of frames for CPU
budget; nothing in `case_report.html` or `summary.json` declares it. Label it.

**F5 (MINOR)** — `REGISTERED_CAMERAS` coordinates duplicated in three files
(app.py:27; case_report.py:38–43; same_state_counterfactual.py:50–51). One drifting
copy silently desynchronizes UI, router and twin. Single source (JSON registry).

**F6 (MINOR)** — `WEIGHTS` absolute artifact path (case_report.py:46) and
`RTDETR_PY = ~/miniconda3/envs/rtdetr/bin/python` (demo_react.py:167). Fine for a
demo box, breaks anywhere else; keep but declare/parametrize.

### Gate 2 — REAL_ROUTE (map + routing)

**F7 (MAJOR) — every case report routes to hard-coded Shahbagh.**
`DEST = (23.7389, 90.3958)` (case_report.py:45) with the comment "representative
trip destination"; used at `:107` and `:115`. The route map, "delay avoided per
vehicle" and the whole Step 3–4 narrative are for one fixed OD that no user chose.
Selecting camera=shahbagh makes origin and destination the same point.
Fix: destination as a form/CLI input, or evaluate a small OD *set* along the
corridor and report the distribution.

**F8 (MAJOR) — jam = ×5.0 on exactly 10 edges, invented, not measured.**
`jam = {e: 5.0 for e in naive[k:k+10]}` (case_report.py:112). Perception measured
`mean_v / ref` per window — that measured slowdown ratio is discarded and an
arbitrary constant substituted, so "delay avoided 
= f(5.0)" is scripted, not derived from the video. (Same constant in the
`r1_router.py:140` self-test — harmless there.)
Fix: multiplier = clamp(ref/mean_v) from the CONGESTED windows; extent from
which approaches are congested, not "next 10 edges".

**F9 (MINOR) — Karwan Bazar fallback: REFUTED on the app path.**
No silent camera fallback exists in app.py (user must choose; blank ⇒ "unknown —
perception only") or case_report.py (no `--location` ⇒ honest LOCATION_REQUIRED,
`:89–99`). The only remnant is `--camera default="karwanbazar"` when
`same_state_counterfactual.py` is run standalone (`:240`). Remove the default
(make it required) so a forgotten flag can't fabricate a location.

### Gate 3 — TWIN_SYNC / CALIBRATION

**F10 (BLOCKER at next gate; declared v1) — the twin's demand is a canned file.**
`ROUTES = artifacts/due_dso_stats/v200/DUE/003/trips_003.rou.xml.gz`
(same_state_counterfactual.py:40, loaded at `:81`). The video contributes only the
camera name; every vehicle in the "twin of this moment" comes from the Aug-15 E4
experiment. This *is* declared in the module docstring (`:20–22`) and in
four_pane_report.py:83–84 — the honest label exists. It stops being acceptable the
moment any page says "computed fresh from this input" (see F25).
Fix direction: keep v1 label; next gate = seed demand from detector counts
(calibration part B).

**F11 (MAJOR) — calibrated demand scale 0.584 is display-only.**
Produced by `scripts/calibrate_twin_a.py` → `artifacts/twin_calibration_A.json`
(`calibrated_demand_scale_A: 0.584`), surfaced in `build_results_matrix.py:82–87`
and RESULTS_MATRIX.md:18 — and consumed by **nothing**: same_state uses v200
routes (`:40`), MARL env uses `/tmp/due_routes.rou.xml.gz` (sumo_marl_env.py:31),
control baselines the same (run_control_baselines.py:32), prevent uses v200
(prevent_experiment.py:34). SYSTEM_DESIGN.md declares "calibration scale 0.584 not
yet consumed" — declared, but the RESULTS_MATRIX row reads like a wired capability.
Fix: generate a 0.584-scaled route set and point every control/twin scenario at it;
until then annotate the matrix row "NOT YET CONSUMED".

**F12 (MAJOR) — the "twin proof for THIS video" is a deterministic constant.**
`case_report.py:155–157` invokes the counterfactual with `--seed 11` hard-wired;
combined with F10's fixed demand and `T0_TRIGGER_STOPPED=250`, `T0_MAX_S=7200`,
`HORIZON_S=600`, `ACT_MIN_QUEUE=20` (same_state_counterfactual.py:42–48), every
congested upload at the same camera yields byte-identical twin numbers
(verified: `artifacts/same_state/case_rush_live` ≡ `kb_mild_gated`: 32/8/692/706).
Fix: multi-seed (the 3-seed protocol already exists — kb_mild_s12/s13 are on disk)
and t₀/threshold parameters surfaced as declared config, not constants.

**F13 (MAJOR) — t₀ and the intervention junction are not actually the video's.**
Warm-up runs until *network-wide* stopped ≥ 250 (`:109–117`), then the target TLS
is re-picked as the most-queued junction **anywhere in the network** (`:120–127`)
— possibly far from the chosen camera. Yet case_report.py:199–200 renders "The
twin reproduced this camera's congestion (t₀=…)". The scope note inside
result.json (`:214–216`) is honest; the HTML sentence is not.
Fix: constrain retargeting to TLS within the camera corridor, and re-word the
report to "the twin's fair demand reaches congestion at t₀; the camera selects
the corridor".

### Gate 4 — SAME_STATE_COUNTERFACTUAL

**F14 (BLOCKER) — local queue win headlined while the network got worse.**
`artifacts/same_state/case_rush_live/result.json` (the run behind the current
reports and the app's "−75%" KPI): target queue 32→8 (−75%) **but** network
stopped 692→706 (worse) and arrivals in horizon 997→994 (worse).
`case_report.py:197–206` computes and headlines `queue −{qpct}%` in green with the
network numbers shown as a parenthetical, never judged; `four_pane_report.py:56–57`
computes the same delta and `:109` prints it as the pane-4 verdict in success
green. `kb_mild_s13/result.json` is starker: control queue 38 vs no-action 8 —
the action made even the *local* queue worse on that seed, and no report surfaces
seed variance. The system's own design principle #6 ("local greed harms networks")
is violated by its own front page.
Fix: verdict = network-level composite (Δ network stopped, Δ arrivals, Δ mean
timeLoss of horizon arrivals) across ≥3 seeds; local queue is a diagnostic,
colored red when network metrics regress.

**F15 (MAJOR) — Aug-15 DUE/DSO result attached to every fresh report.**
`case_report.py:171` unconditionally reads
`artifacts/due_dso_stats/v200/result.json` (file dated Aug 15) and embeds
−19.5%/p=1.3e-05 into `case.json` under the key `network_scale_proof`
(`:185–188`). The HTML *does* label it "separate OFFLINE experiment" (`:231`,
`:248`) — partially fixed — but the JSON key name, the "PROVE" step-5 framing in
the module docstring (`:13–15`), and the app KPI tile (app.py:87) all present it
as part of this input's result.
Fix: keep with stronger label — rename key to `offline_network_experiment`, stamp
its date, and drop it from the per-run KPI framing.

### Gate 5 — FORECAST_IN_LOOP

**F16 (BLOCKER) — the forecast the FA arms are named after is zero almost always.**
`STEP_S = 300` and a 12-bin history (`gwnet_in_loop.py:24,96–99`) ⇒ first real
prediction at t = 3600 s. Training episodes default to `episode_sim_s = 3600`
(train_sumo_signals.py:69) ⇒ **the forecast slot is 0 for the entire training
episode** — `mappo_forecast` is trained as plain MAPPO with a dead input. Eval
(end_s = 10800, eval_policy.py:41) has it zero for the first third. The docstring
calls this "fallback honesty" (`:9–11`) and SYSTEM_DESIGN.md declares "preload fix
pending — FA arms relabeled" — declared, but it blocks any FA-MAPPO claim. No
`forecast_available_fraction` metric is logged anywhere (grep confirms), so the
dead-input condition is invisible in outputs.
Fix: preload 12 bins from a logged warm-up trace of the same demand+seed before
the first decision, and log forecast-available fraction per episode.

**F17 (MAJOR) — forecaster depends on artifacts outside the repo.**
Checkpoint glob `checkpoints/GraphWaveNet/**/GraphWaveNet_best_val_MAE.pt` under
`/workspace` or `<repo>/BasicTS_legacy` (`gwnet_in_loop.py:20–23,41–43`) plus
scaler stats from `data.dat` (`:62–68`): none exist in this repo (verified).
MAE 0.44 traces to `artifacts/p3_results/GWNet_cpu.log:1462` (0.4435, horizon 3)
— a log, with the checkpoint unpinned. Pin the checkpoint + desc.json into
artifacts with a sha256 like p1_winner.

**F18 (MINOR)** — `vfree` is whatever speeds the first bin happened to show
(`:97–98`, floor 5.0), and the time-of-day channel is the sim bin index mod 288
(`:101`) — both diverge from the training-data conventions. Derive vfree from edge
speed limits; align tod with the dataset's clock.

### Gates 6–7 — SIGNAL_CONTROL baselines & EVAL_PAIRING

**F19 (BLOCKER) — the "hold" action does not hold.**
Contract: "0 = hold/extend current green" (sumo_marl_env.py:9). Implementation:
action 1 forces phase advance via `setPhaseDuration(tls, 0.0)`; action 0 does
nothing — "let SUMO's program continue (extend implicitly)" (`:112–115`). SUMO's
fixed-time program auto-advances on its own timings, so under all-zero actions the
lights simply run fixed-time; nothing is extended, and the agent cannot keep a
green beyond the program's phase length. Half the action space is a placebo; the
learned policies are effectively "fixed-time + optional early skip", which also
explains results hovering near the fixed-time baseline (558.9/551.3 vs 535.9).
Fix: on hold, `setPhaseDuration(tls, remaining + DECISION_S)` (bounded by
max-green), or take explicit program control.

**F20 (MAJOR) — off-by-one breaks the "PAIRED seeds 11–13" claim.**
`reset()` increments `_episode` then starts SUMO with `self._seed0 +
self._episode` (sumo_marl_env.py:99–100), so `eval_policy.py --seeds 11 12 13`
actually simulates SUMO seeds **12, 13, 14**; baselines pass the seed straight to
SUMO (run_control_baselines.py:41–44) and their banked summary is genuinely
seeds [11,12,13] (artifacts/control_baselines/summary_fixed_time.json). The
RESULTS_MATRIX "PAIRED held-out seeds 11-13" rows (`docs/RESULTS_MATRIX.md:11,13`)
are therefore unpaired by one seed. Fix: in eval, construct the env so the first
episode uses exactly the requested SUMO seed; re-run the three evals.

**F21 (MAJOR) — stale baselines burned into eval outputs.**
`eval_policy.py:119` embeds `{"fixed_time": 547.7, "max_pressure": 619.0}` and
`:124` prints `vs_fixed_time_pct` against 547.7 — numbers from an older seed set;
the current paired baselines are 535.9/586.7. Both stale numbers sit inside
`artifacts/rl_eval/eval_mappo*.json` today. (`build_results_matrix.py:53–54`
already guards correctly — partially fixed downstream.) Remove the constants; read
the baseline summaries.

**F22 (MINOR)** — trained on 3600 s episodes, evaluated on 10800 s
(train_sumo_signals.py:69 vs eval_policy.py:41): out-of-distribution eval,
undeclared. Label or align.

**F23 (MAJOR) — matrix builder invents rows.**
Docstring: "Reads only result files (never invents)" (build_results_matrix.py:5);
lines 32–36 hard-code the GWNet/DCRNN/STID rows as string literals. If P3 is
re-run, the matrix will silently keep the old numbers. Parse
`artifacts/p3_results/*.log` (the 0.4435 line exists) or a banked metrics JSON.

### Gates 8–9 — REPORT / UI honesty & MAPPO claims

**F24 (MAJOR) — claimed numbers vs evidence, itemized.**
- mAP 0.711: **evidenced** — artifacts/p1_triage/triage.json (winner
  p1-rtdetr-r50) + artifacts/p1_winner/rtdetr_r50_poribohon_best.pth +
  checkpoint.sha256. OK.
- −19.5% delay, p=1.3e-05: **evidenced** — artifacts/due_dso_stats/v200/result.json
  (10 seeds). OK, but offline (F15).
- MAE 0.44: log-only (p3_results/GWNet_cpu.log:1462); checkpoint not pinned in
  repo (F17).
- −75% queue: real artifact, misleading metric (F14) — the one indefensible KPI.
- mappo/mappo_pressure numbers: actor.pt + tripinfo present in artifacts/rl_eval —
  evidenced, but tainted by F19/F20/F21.

**F25 (BLOCKER) — "computed from this input" claims that are false today.**
- app.py:8–11 (docstring): "nothing pre-baked".
- app.py:82: "real pipeline · no mockups · every number regenerates" — directly
  above a KPI banner (app.py:85–89) of five hard-coded numbers that never
  regenerate, including the F14 "−75%" and the offline "−19.5%".
- case_report.py:230–231: "Steps 1–5 are computed fresh from this input —
  including the twin prediction and same-state proof for THIS road" — the twin
  runs canned demand + fixed seed 11 (F10/F12); only steps 1–4 are fresh.
- four_pane_report.py:121–122: "Every number regenerates" — panes 3–4 regenerate
  to the *same* values for any input (F12).
Fix: rewrite the three sentences to the honest v1 scope (which
four_pane_report.py:83–84 already states correctly one paragraph earlier), and
render the KPI banner from artifact files with dates.

**F26 (MINOR)** — `SAMPLES = {"rush hour …": "artifacts/react_demo_rush"}`
(app.py:28–30) is dead code; the docstring's "or pick a bundled sample" promise
has no UI. Remove or wire with a PREBUILT tag.

**F27 (MINOR)** — the "Latest proof" iframe (app.py:110–113) always shows the
most-recent `four_pane.html` from any prior run (app.py:145–148), including next
to a brand-new unrelated upload. Caption it with its case name and timestamp.

**F28 (MINOR)** — `docs/media/corridor_before_after.mp4` is a pre-recorded video
embedded in every congested report (case_report.py:217,249); the surrounding text
labels it as the offline experiment's render — acceptable, keep the label.

---

## Cross-cutting note

The repo's honesty *labels* are unusually good (LOCATION_REQUIRED path, scope_v1
strings, SYSTEM_DESIGN "Known limitations") — most gaps are **declared somewhere**.
The failures are where the marketing sentence and the mechanism diverge on the
same page: F25's "every number regenerates" one line above hard-coded KPIs, F14's
green "−75%" beside a worsening network column, and F13's "reproduced this
camera's congestion" over a canned-demand t₀.
