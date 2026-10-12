# Crash detection on the phone (RQ6; the WreckWatch rule, and the phone's real accelerometer)

**Goal.** Detect a crash-like jolt from the phone's accelerometer with the published WreckWatch rule (4 g on the acceleration
magnitude, a speed floor when a speed is known), start a 15-second countdown the rider can cancel, and show the alert path
(detected → countdown → network or mesh) without ever sending anything. Since step D (2026-10-11) the map app can arm the phone's
real sensor from a tap. The thesis traces are SYNTHETIC; the sensor path is TEST and stays on the phone.

## Pipeline

```
three synthetic traces (50 Hz, 30 s, seed 7)        core/safety/sos.py:synthetic (59-74)   normal ride · hard brake · crash jolt
        │
        ▼  the rule: |a| ≥ 4 g (and speed > 24.1 km/h when a speed is known)
core/safety/sos.py:detect (43-56)                   peak_g = the trace's true peak, at_g = the reading that fired the rule, at_s
        │
        ▼  python -m core.safety.sos build
research/sos/traces/*.json + SHA256SUMS → evidence/sos/results.json
        │
        ▼  the browser, the same rule
frontend/src/features/emergency/useMotion.ts (sensor 26-38 | replayed trace 53-72) → sos.ts:isJolt (14), reduce (34-43)
        │                                                   MotionGraph.tsx (live 10 s graph, red 4 g line) · SosCard.tsx (countdown 68-73)
        ▼
backend/app/emergency/router.py: sos_path → sos.path_steps (119-143); sos_test → sos.raise_test (146-161)  in memory only, stamped TEST
        │
        ▼  the map app
frontend/src/maplink/index.ts:armCrashDetector (112-141) → frontend/map/src/traffictwin/tt.ts: onSosState (134), usePhoneSensor (156)
   SOS button → source "button" · automatic arming → "sensor" · the phone's real sensor → "phone-sensor": live g, never posted
```

## Upstream

| What | Where | Commit / version | Licence | How it is used |
|---|---|---|---|---|
| WreckWatch | White, Thompson, Turner, Dougherty, Schmidt, *Mobile Networks and Applications* 16(3), 2011 | the paper, read 2026-10-06 | © Springer, paper only | The rule: "ignores any acceleration events below 4G's" and an alarm only above 15 mph. Threshold and speed floor in `core/safety/sos.py:25-26`; the acoustic signal is not implemented (SOURCES.md:58) |
| DeviceMotion API | W3C Device Orientation and Motion; MDN `DeviceMotionEvent` | the browser's API (read 2026-10-06, 2026-10-11) | W3C spec; nothing copied | `devicemotion` with `accelerationIncludingGravity` (m/s²); `DeviceMotionEvent.requestPermission()` asked inside a tap on iOS (SOURCES.md:59, :227) |

Nothing is copied; all the code is ours.

## Files

- `core/safety/sos.py`: `detect` (43-56; threshold :51, speed floor :53, `at_g` :54, `peak_g` :56), `synthetic` (59-74), `build` (82-104), `path_steps` (119-143), `raise_test` (146-161; `phone-sensor` returned with `stored: False` at :152).
- `backend/app/emergency/router.py`: `sos_results` (76-79), `sos_trace` (82-88), `sos_path` (91-94), `sos_test` (97-100).
- `frontend/src/features/emergency/`: `sos.ts` (`isJolt` 14, `detect` 17-25, `reduce` 34-43), `useMotion.ts` (12-75), `MotionGraph.tsx` (10-35), `SosCard.tsx` (23-87).
- `frontend/src/maplink/index.ts:armCrashDetector` (112-141; `opts.source`, `opts.onSample`, `opts.permission`).
- `frontend/map/src/traffictwin/tt.ts`: `armSos` (127-145), `onSosState` (134), `usePhoneSensor` (156-166); `TtTrip.vue` (`data-tt="phone-sensor"`, `live-g`, `sos-local`); strings `tt.phoneSensor.*` EN/BN.
- Checks: `frontend/tests/live/sos_graph.cjs` (step 7 of `make present`), `frontend/tests/qa/phone_sensor.cjs`.

## Commands

    PYTHONPATH=.:backend python -m core.safety.sos build                       # rebuild the traces and evidence/sos/results.json
    make present ARGS="--only sos"                                              # LIVE: the crash graph with the three traces (step 7)
    LOCAL_URL=http://127.0.0.1:8011/ node frontend/tests/live/sos_graph.cjs
    LOCAL_URL=http://127.0.0.1:8011/ node frontend/tests/qa/phone_sensor.cjs    # headless check with synthetic DeviceMotionEvents → evidence/sos/phone_sensor/
    # on a phone over HTTPS (the hosted app): start a trip → "Use this phone's crash sensor" → iOS asks once → live g on screen

Web: `/app/emergency` ("Crash SOS", Arm or replay a trace); the map app's trip screen (SOS button, phone sensor button).

## Results (`evidence/sos/results.json`, sha256 `28cb4636…`, built 2026-10-10; rule 4.0 g, 24.1 km/h, countdown 15 s)

| Trace (SYNTHETIC) | Peak | Detected | At | Reading that fired the rule |
|---|---|---|---|---|
| normal ride (gravity plus road noise) | 1.54 g | no | — | — |
| hard brake (1.5 s pulse to 1.8 g) | 2.03 g | no | — | — |
| crash jolt (120 ms spike to 6.5 g) | **6.37 g** | **yes** | 12.04 s | 5.87 g |

Every trace has `speed_checked: false`: there is no speed in the traces, so the speed floor was not applied.

Phone sensor check (`evidence/sos/phone_sensor/phone_sensor_check.json`, sha256 `7550debc…`, 2026-10-11, local app, 390×844):
7 of 7: the button is a tap, not automatic; live g shown from the dispatched samples; a 5.8 g jolt starts the countdown through the
unchanged rule; after the countdown the detection is "kept on the phone", labelled TEST; **0 requests** to `/api/emergency/sos/test`;
no page errors.

## The finding

The published 4 g rule separates the three synthetic traces as designed: only the crash jolt crosses it, and the browser's rule and
the Python rule agree on the time (12.04 s). The real-sensor path works end to end in the map app without any network action: a
detection from the phone's accelerometer is shown, counted down and kept on the phone. This is a correct implementation of a
published rule, not an evaluation of it. The evaluation on recorded crashes is the next section (step M, VZCrash).

## VZCrash: the same rule on 24,174 recorded events (step M, 2026-10-11; REAL RECORDED, run on the AWS instance)

Dataset: VZCrash (Bianconcini et al., IEEE ITSC 2026), revision `42e1482d…`, CC BY-NC 4.0, gate accepted by the owner; 100 Hz
accelerometer in g, 1 Hz GPS speed, 16 s per event, labels crash / near-miss / normal from a three-reviewer consensus. The test and
validation splits (2.0 GB) were downloaded onto the AWS instance only; **nothing from the dataset is on the laptop or in this repo**,
only the numbers in `evidence/sos/vzcrash/` (`results.json`, `pr_curves.json`, `run.log`, `SHA256SUMS` written on the instance;
`pr_curves.png` drawn from them here). Script: `research/sos/vzcrash/run.py`; the three detectors were fixed before any number was seen.

| | Detector | Test split (4,221 crashes vs 19,953 near-miss + normal) | Published |
|---|---|---|---|
| A | the authors' physical baseline, reimplemented from their `pr_curve.ipynb` (one cell, read as text): peak over time of the x-y acceleration norm | **AP 0.8962** | **AP 89.62 %** (paper, Table I): reproduced |
| B | **the app's rule, unchanged** (`core/safety/sos.py`): first sample with \|a\| ≥ 4 g while the GPS speed > 24.1 km/h | recall **45.6 %** of crashes, precision **88.6 %**, false alarms **1.24 %** of negatives (near-miss 0.74 %, normal 1.35 %); validation split: 47.3 % / 88.8 % / 1.10 % | — (WreckWatch 2011 gives no recall) |
| C | gradient boosting (`HistGradientBoostingClassifier`, 14 hand features: peaks, jerk, gyro peak, speed before/after), trained on the validation split, tested on the test split | AP **0.954**; at the rule's false-alarm rate (1.24 %) it finds **77.9 %** of crashes (the rule: 45.6 %) | — (the paper's deep models: AP 96.2–97.6 %) |

What the rule misses and why (test split): the median crash peaks at 4.16 g and only 54.7 % of crashes ever cross 4 g (near-miss
0.83 %, normal 1.74 %), so the 4 g line itself caps recall near 55 %; a further 452 events crossed 4 g but were under 24.1 km/h, which
the speed floor suppressed (crashes among them count as misses). On the authors' horizontal-norm score, a 4 g line gives precision
0.934 at recall 0.418; 3 g gives 0.877 at 0.677; 2 g gives 0.797 at 0.888 (`pr_curves.json`). So the published threshold is a
high-precision, low-recall operating point on real crashes, and a learned model roughly doubles the recall at the same false-alarm rate.

    # on the instance (nothing is kept on the laptop); the dataset is gated: accept its terms on the Hub first
    HF_TOKEN=… python -c "from huggingface_hub import snapshot_download; snapshot_download('vzc-research-chapter/VZCrash', repo_type='dataset', revision='42e1482d005c0e545379d6cfa4939486c9fe4249', local_dir='/srv/vzcrash/data', allow_patterns=['data/test-*','data/validation-*','README.md','*.ipynb'])"
    /srv/vzcrash/venv/bin/python research/sos/vzcrash/run.py --data /srv/vzcrash/data/data --out /srv/vzcrash/out   # 2.5 min on 4 cores
    python -m pytest tests/sos/test_vzcrash_run.py -q                      # the rule and metrics on synthetic arrays + the fetched numbers' hashes

## Honest limits

- The three thesis traces are still built on either side of the threshold (`sos.py:33`); the VZCrash section above is the real
  evaluation, and it is the authors' split protocol (by vehicle), not ours.
- The speed floor is exercised only on VZCrash (every event there has a GPS speed); the synthetic traces carry none.
- VZCrash was recorded by in-vehicle IMUs (x forward, y left, z up), not by phones; the app's rule uses the phone's
  `accelerationIncludingGravity`, so the mounting and axis alignment differ. The model C is not in the app: the app keeps the
  published rule, and C is reported as what a learned detector would add.
- Field name (CODE_MAP known gap 1): the alert request carries the reading that fired the rule under the field name `peak_g`
  (`SosCard.tsx:35-36`, `tt.ts` → `sos.py:130,158`). The browser has both numbers (`sos.ts:reduce` keeps `peakG` and `joltG`; the
  trace `detect()` returns the true peak with `at_s`); the number is right, the label is not. Kept so saved results and the API stay
  readable.
- The phone sensor is checked only in headless Chrome with synthetic `DeviceMotionEvent`s and a stubbed `requestPermission`; it is
  **not yet checked on a real phone over HTTPS**. Over plain HTTP the button says the sensor needs HTTPS.
- WreckWatch's acoustic signal and its server-side notification are not implemented; nothing is ever sent, by design.

## Live demo (2026-10-12)

    make present ARGS="--only sos"                   # step 7: the phone-size SOS screen replaying the trace from the live collision through the 4 g rule
    LOCAL_URL=http://127.0.0.1:8011/ node frontend/tests/live/sos_graph.cjs --trace=sumo_collision

What to watch: the live g graph, the red 4 g line, the countdown starting when the line crosses it; on a phone over HTTPS, "Arm" uses the
real accelerometer (TEST mode, nothing is sent). Real recorded: the VZCrash numbers in the table above (computed on the instance). Simulated:
the traces replayed here. Fallback: the three synthetic trace chips on `/app/emergency`.
