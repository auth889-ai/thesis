# Proposals

Things noticed while working that are outside the phase being worked on. Nothing here is built until it is agreed.

## From the city layer (2026-10-05)

The city layer moved the SUMO network, its demand and its scale behind `config/cities/<city_id>.yaml`. These
Dhaka-specific values are still written in code and were left alone because the phase did not cover them:

1. **Coordinates and corridors.** `core/common/data/reference_corridors.py` (16 places, 12 corridors),
   `data/live_providers/providers.py` (origin–destination pairs), `twin/live/settings.py` (`DHAKA_CENTER`),
   `twin/scenario_sync.py`, `routing/r1_router.py`, `routing/route_advisor.py`,
   `forecasting/live/run_live_capture.py`, `networking/mosaic/sweep/metrics.py` (a hazard rectangle),
   `data/live_providers/live_state.py` (the R1 box as a literal).
2. **Time zone as UTC+6.** `forecasting/live/live_state.py`, `forecasting/opencity/opencity_city_eval.py`,
   `forecasting/opencity/opencity_predict.py`, `lifeos/compiler/evaluate.py`. The config now carries the IANA zone.
3. **The id `dhaka_r1`** as a string in `twin/live/` (networks, settings, command handler, trip comparison),
   `data/live_providers/live_state.py`, `protocols/chains/`. The config carries it as `sumo.prebuilt.network_id`.
4. **Three paths into the deleted `paper_labs/` tree**: `common/city.py` (`DHAKA_R1.network_path`), `routing/r1_router.py`,
   `research/reports/build_asset_manifest.py`. One test (`tests/platform/test_p0_vertical_slice.py`) always skips because of it.
5. **The web app outside the shell and the City page** still writes its text in English in the components
   (about 55 files), and the Lab pages name METR-LA directly. Map centres in `NetworkMap.tsx` and `ReplayMap.tsx` are
   Los Angeles literals.
6. **Berlin has no bounding box.** The Berlin V2X paper and README give no coordinates. Downloading the dataset from
   IEEE DataPort and taking the box of its GPS traces would fill it.
7. **`/api/operate/cities` still marks the default city `forecast: true` unconditionally**, as it did before; it should
   come from whether the city has observed history.
8. **The app can launch paid AWS training from the Train page** (`operations/training_jobs.py`,
   `operations/prediction_jobs.py`). It is now spot-only and tagged, but it does not ask for cost approval first.

## Google-derived data: withdrawal, deletion and history (2026-10-05)

**Why.** Between 25 August and 6 September 2026 the project recorded Google Routes results for Dhaka and Nairobi, kept
values derived from them, and used them to test forecasts and to calibrate the Dhaka twin. Google Maps Platform Terms
3.2.3 forbid storing the content, creating content from it, and using it to "train, test, validate or fine-tune" models;
the Routes API terms allow caching only coordinates, for 30 days. Nothing derived from Google may appear as a result.
The inventory is `evidence/audit_2026-10-05/google_inventory.md` (names, counts, dates and hashes only).

Status, 2026-10-05: **A done. B done in a lean form** (cut at the source: there is no recorded series, Google rows are
never read, a model is given only our own observations; every affected feature answers "no observed traffic for this
city yet"). **C done** for README, RESULTS.md and MASTER_RESOURCE_INDEX.md. **D: the config is relabelled; the labels
where results are shown are still to do. E done: everything listed was deleted, with no backup. F waits for the final
commit.** Not done in the lean version: the five reworded texts in the last row of table B, the chains' default inputs,
and `/api/predict/{corridor}`, which now simply find no data.

### A. No Google API is called (done)
Every request site passes through `core/common/data/live_providers/google_guard.py`, which refuses; the Google service is
never selected as a provider. The API key itself was not touched.

### B. App features to disconnect (planned)
Each of these reads the recording or Google-derived rows today. Replacement: the city's own observed data where it
exists; otherwise "no observed traffic for this city yet". Dhaka keeps its free-flow route time, labelled free-flow.

| Feature | Reads | After |
|---|---|---|
| `GET /api/forecast/{city}` (recorded fallback) and its ledger scheduler | the recording | forecast only from own observed history; none yet → "no observed traffic for this city yet" |
| `GET /api/forecast/{city}/scoreboard`, `/accuracy`, `GET /api/history/{city}` | forecast log scored against the recording; `live_backtest.json` | "no observed traffic for this city yet" |
| City page map for Dhaka (`data/city_map.py`) | recorded corridor states and forecast | provider roads with free-flow times, labelled free-flow; no congestion level, no forecast |
| Trip analysis: "RECORDED corridor states" fallback and recorded-band travel time (`routing/trip/routes.py`, `pricing.py`, `corridors.py`) | the recording; bands inverted from Google ratios | free-flow route time, labelled; no accuracy figure |
| Live twin "observed" levels (`twin/live/launch.py`) | the recording's peak bin | simulated demand only, labelled synthetic what-if |
| Nairobi forecasts and history (`observatory.city_data`) | 206 Google-derived rows in its window | Google rows never read; no own data → "no observed traffic for this city yet" |
| `DHAKA-LIVE` dataset entry (`forecasting/operations/city_datasets.py`) and `/api/predict/{corridor}` (`live_reference.py`) | `series.npz`; the recording | removed from the dataset list; endpoint answers "no observed traffic for this city yet" |
| Integrated and impairment chains' default inputs (`protocols/chains/`) | the recording, `series.npz` | require an explicit synthetic input; no recorded default |
| Text that still describes the recorded profile (`docs/DEVPOST.md:14`, `SystemPage.tsx:23`, `docs/WORKFLOW.md`, `docs/ARCHITECTURE.md:54`, `agent/tools.py:4`) | — | reworded |

### C. Results to withdraw from README, RESULTS.md and thesis text (planned)
- `live_backtest` (Chronos against persistence on the Dhaka corridor): README lines 159–160 and 317.
- `live_floors` and "Live Google reference": `results/RESULTS.md` lines 23, 30, 48–71, 377–395.
- Forecast-ledger scores against the recording: wherever quoted (none found in README; `docs/REFERENCES.md:31`).
- The 20 `integrated_chain_*` results (40 files): any table or sentence quoting them.
- Mentions in `docs/RESOURCES.md:65`, `docs/WORKFLOW.md:38`, `docs/REFERENCES.md:188`, `docs/MASTER_RESOURCE_INDEX.md:58,60`
  (the last says Google Routes was "VERIFIED_NOT_USED", which is not true).
`results/RESULTS.md` is generated by `research/reports/build_results.py`, so the generator loses those sections too.

### D. Dhaka demand scale 0.584 (planned; the value does not change)
Label: "synthetic what-if, uncalibrated (earlier calibration used Google data and is withdrawn)". The city config says
so now. To do: the same label wherever a result made with this scale is shown (the routing arms `arms_h900/h1800/h7200`,
`SCALE_CHOICE.json`, `TWIN_SYNC_PASS.json`, the planner results, and the city-layer check of 218.92 vehicle-hours) and in
`twin/scenario_sync.py`, `protocols/chains/run_arms.py`, `data/make_twin_dataset.py`. 467 result files carry the number;
they are labelled where they are displayed and in one notice per folder, not edited one by one.
**Recalibration later, from our own field collection:** count vehicles and time traversals on the R1 corridor ourselves
(manual counts or opt-in phone traces at fixed hours), record the protocol and raw sheets under `evidence/`, then fit the
scale to those and report old and new side by side.

### E. Stored data proposed for deletion (nothing deleted yet)
Files:
1. `results/artifacts/live_dhaka/normalized/google_routes_runtime_reference.jsonl`
2. `results/artifacts/live_dhaka/normalized/recorder_errors_runtime_reference.jsonl`
3. `results/artifacts/live_dhaka/RECORDER_MANIFEST.json`
4. `results/artifacts/p_live/normalized/google_routes_runtime_reference.jsonl`
5. `results/artifacts/p_live/live_reference_summary.json` and `.md` (the `.md` is tracked)
6. `data/forecasting/live_dhaka/series.npz` and `MANIFEST.json` (both tracked). `corridor_edges.json` in the same folder is
   ours and stays.
7. `results/artifacts/twin_calibration_A.json`, `twin_calibration_A_history.jsonl`, `results/artifacts/peak_captures.log`
8. `results/forecasting/live_backtest.json`, `live_floors.json`, `live_floors.md` (tracked)
9. `results/live/route_advice.jsonl` (tracked; two Google advice records)
10. `results/routing/weights/forecast_weights.json` (tracked; built from the recording)
11. The 80 files in `results/runs/provenance/` whose `routing_provider` is `google_routes` (listed by name in the inventory)
12. The 40 `results/routing/integrated_chain_*` files except `integrated_chain_ideal.json` and `.md`
13. 31 run folders under `results/routing/runs/` and 246 run folders under `results/live/sim/` that used the recording
Database rows:
14. `results/live/observatory.sqlite`: `samples` where `provider = 'google'` (4,384 Dhaka rows, 744 Nairobi rows)
15. `results/forecasting/forecast_log.sqlite`: every row of `forecasts` (251,964: all were made from the recording or, for
    360 rows, from a buffer that only Google fed)
Open question before item 13: three of the 246 sim folders were created by my own test runs on 2026-10-04.

### F. Removing the data from git history (planned; no history rewritten, nothing pushed)
To do once, at the owner's final commit, not before:
1. Tell anyone with a clone or fork; ask GitHub Support to purge cached views and dangling commits after the rewrite.
2. On a fresh clone, with `git filter-repo`, remove every path that ever held the data:
   `artifacts/live_dhaka/`, `artifacts/p_live/`, `predict/data/live_dhaka/`, `data/forecasting/live_dhaka/series.npz` and
   `MANIFEST.json`, `results/artifacts/p_live/`, `artifacts/twin_calibration_A*.json*`, `results/forecasting/live_backtest.json`,
   `results/forecasting/live_floors.*`, `results/live/route_advice.jsonl`, `results/routing/integrated_chain_*` (except
   `integrated_chain_ideal.*`), `results/routing/runs/` (436 tracked summary files of 31 runs), `results/routing/weights/forecast_weights.json`. The exact list is regenerated from
   `git log --all --name-only` at that time, because paths moved during restructuring.
3. Verify with `git log --all -- <path>` that each path is gone, and that the working tree still builds and tests pass.
4. Force-push every branch and tag; delete stale remote branches; every other clone must be re-cloned, not pulled.
5. Check the Drive remote (`gdrive2tb:dhakaflow`) and any backup zip for the same files.
6. Revoke the Google Maps API key in the Google Cloud console (it was used by the recorder; the code no longer calls it).
A rewrite changes every commit id after the first affected commit, so it is done once, deliberately, and recorded here.

## From the simulated 3D twin (2026-10-05)

1. **Vehicle mix.** Every vehicle is one class because no published source for a city's shares of cars, buses,
   rickshaws and two-wheelers is recorded. With a cited modal split per city in its config, the demand could carry
   vehicle types and the view would draw the four shapes it already has.
2. **The twin sits in the Lab, which has no city or language switcher.** It follows the city chosen in the app shell.
   A switcher in the Lab bar, or a place for the twin outside the Lab, would make that visible.
3. **Scrolling over the map zooms it** instead of scrolling the page. Requiring a modifier key would fix that.
4. **Scene size.** Dhaka's scene is 6.6 MB of JSON (20,290 building outlines). It loads in about a second locally;
   on a hosted app it should be compressed or split into tiles.
5. **Buildings mapped as relations** (multipolygons) are not fetched, so some large buildings are missing.
6. **The old network id `dhaka_r1`** is still written in `twin/live/networks.py` and `settings.py`; new work uses the
   city id through the manifest.
7. **Real 3D models and "Ask the city"** are stretch goals not started. Orbit, street level and night lighting were
   added on 2026-10-05; lit windows, fog, rain and street lamps from the same reference were not.


## From "Add your city" (2026-10-05)

1. **The older `POST /api/city` is superseded.** It geocodes a name with OpenStreetMap's Nominatim and keeps an old
   kind of city record that the twin does not use. It is left in place and unchanged; it should be removed once
   nothing in the app calls it.
2. **Name matching is narrower than planned.** The plan said a place would be found by its name in any language.
   Matching every language took more than ten minutes for one search, so the search matches the place's main name,
   its English name and its names in the app's languages (now English and Bangla). A place known only by a name in
   another language is not found until that language is added to the app.
3. **Values left `null` in a generated city:** time zone, languages, emergency numbers, units, vehicle classes.
   Overture's divisions file holds none of them. Each needs a cited source before it is filled.
4. **A failed build still counts** in the day's limit, because the road request was sent. The config it wrote is
   kept, so pressing Build again retries the same city.
5. **Build progress is one stage,** not the five the plan listed: the pipeline runs as one call and does not report
   where it is. Splitting it would mean changing `twin/city_pipeline.py`.
6. **A busy road server.** The public Overpass server answered "504 Gateway Timeout" to two of the four road requests
   made on 2026-10-05. The build now waits 30 seconds and asks once more; a hosted app should use its own extract.
7. **The public server and the daily limit.** Eight new cities a day is at the edge of the Overpass guidance for one
   app. The AWS city builder planned with hosting should read roads from Overture's transportation theme instead.

## Before the SOS phase (2026-10-05)

**Fill time zone, languages, units and emergency numbers for generated cities, from recorded open sources, never
guessed.** A city added through "Add your city" has all four as `null`, because Overture's divisions file does not
hold them. The crash SOS demo shows the city's emergency numbers from its config and speaks the city's languages, so
it cannot work for a generated city until they are filled.

- Each value is taken from a named open source, and the source, its version or date, and its licence are written in
  the generated config beside the value and in `third_party/SOURCES.md` before the value is used.
- A value the source does not hold stays `null`, and the app says "no data for this city". Nothing is inferred from a
  neighbouring country, from the longitude, or from the language of the city's name.
- Emergency numbers are shown and never dialled, as `CLAUDE.md` requires.
- Which sources to use is not decided. They are to be chosen and their licences read in plan mode at the start of
  that work; none has been read yet.

## From the visual realism step (2026-10-05)

1. **Sharper or dated satellite imagery.** The picture shown is a 2016 composite at 10 m per pixel. Every sharp
   worldwide source found needs a paid licence or an account. Not added.
2. **OpenFreeMap has no availability promise** ("may discontinue it at any time without notice") and serves whatever
   tile set is current, so the base map is not pinned to a date. Fine on a laptop; for the hosted app, consider hosting
   the tiles ourselves (OpenFreeMap publishes how) and state the cost first.
3. **Dhaka's lane counts are all "not recorded"**, because its frozen network was kept without its OpenStreetMap
   extract. Fetching today's extract would not be the data the network was built from, so it was not done.
4. **`frontend/openapi.json` is out of date** against the running app on about 58 routes (it predates today's work).
   Only one sentence in it was corrected. Regenerating it and the two type files is a separate step.
5. **The Today page has no map** and the Add-your-city card's map appears only after a search; neither could be
   checked against the new base map the way the other pages were.

## From the everyday home (2026-10-05)

1. **The Map page's trip planner overlaps the home** and is tied to Dhaka and to a live provider
   (`routing/trip/`). It was left as it is. Retiring it, or pointing it at the home's router, is a separate decision.
2. **A phone's cells carry the city name from the person's profile** (the 3 stored cells say "Gazipur"), not a city
   id. The home therefore counts cells by position inside a city's box. `POST /api/probes` and the Map page's probe
   panel still use the name; they should use the same rule.
3. **The tag's sentences are English.** Source, basis and uncertainty are written by the backend; the translation
   phase should turn them into message keys. Units (min, km, cells) are not translated either.
4. **A third tag kind, "forecast", was added** beside real and simulated, because a forecast is neither. Rule 18 in
   the architecture plan names two kinds; it should name three, or the owner should say which of the two a forecast is.
   **Accepted by the owner on 2026-10-06; rule 18 now names three.**
5. **Chronos cannot be imported on this laptop** (a broken TensorFlow install; the same cause as six failing adapter
   tests). With data, the home would say "the forecast model cannot run on this machine". Repairing the install is
   outside this step. **Repaired on 2026-10-06** (`third_party/SOURCES.md`, "Forecasting model").
6. **The city config's new `live` block is optional with a default**, unlike the other fields, which must be written
   even when unknown. This avoided rewriting every generated city's file; making it required is a small follow-up.
7. **`config/cities/dhaka.yaml` declares field counts as a pending source.** With DhaTraX or other recorded data
   (see the next plan) this entry changes.

## From "real data without a crowd" (2026-10-05)

1. **Not built, no hours left for them** (the plan's steps 6 to 9): routeSampler calibration of the Dhaka twin from
   DhaTraX counts (3.0 h; two count points only), the WorldTrace replay (2.5 h; depends on the coverage scan), DRINF
   class counts on Colab (4.5 h), reading the Kaggle dataset's labels (0.5 h; recommended to drop).
   **Owner, 2026-10-06:** the calibration is approved as the first step of Phase 1, from its budget (26 → 23); the
   Kaggle dataset is dropped. WorldTrace replay and DRINF stay unfunded.
2. **Where is DhaTraX's BS site?** Its calibration has no GPS point. With its place it gives a third recorded site.
   **Owner, 2026-10-06: leave it out.** BS is not placed on a road.
3. **The METR-LA replay.** No plan document describes one. The recorded-source interface can carry it (2012 readings
   for Los Angeles shown under "Recorded day"); it needs its own short plan and hours.
   **Owner, 2026-10-06: stays here as a proposal for now; not built.**
4. **The live forecasting phase has 1 hour left** of its 10 after this step and the home. Its own remaining work
   (corridor speeds from phone cells, scoring forecasts against later readings, the measured 90 % band) is unfunded.
5. **A cell is matched to a road within 66 m** (the cell's real size) by direction. Two parallel roads closer than
   that, running the same way, cannot be told apart. Matching each position to a road before binning would fix it.
6. **Vehicle behaviour in the mix is SUMO's default per class.** Sizes, speeds and lane discipline of CNGs and
   rickshaws are not modelled; `core/simulation/twin/configs/dhaka_r1.yaml` holds older assumed values that are not used.
7. **`evidence/twin/record.json` names the Dhaka demand file by its hash before the mix was applied.** It is a record
   of that day's screenshots and was left as it is; the current hash is in `evidence/cities/dhaka/build.json`.
8. **One pre-existing test waits on the public Overpass server without a time limit** (`test_add_city.py`, the
   Sylhet build). On 2026-10-05 at about 22:20 the server did not answer and the test hung; it was left out of that
   evening's full run. It needs a timeout that turns into a skip.


## From the copy-first audit (owner, 2026-10-06)

1. **Google Photorealistic 3D Tiles: dropped.** Google Maps Platform Terms of Service: "Customer will not use the
   Google Maps Core Services with or near a non-Google Map in a Customer Application." Every map in the app is
   MapLibre with OpenFreeMap, Overture and EOX layers, so the tiles cannot be shown with them. The Overture buildings
   stay. Details: `docs/COPY_FIRST_AUDIT.md`, section 6.
2. **The SOS phase needs a different crash data source.** MeixinZhu/vehicle-crash-identification cannot serve: its
   data is not in the repository (a DataFountain competition behind an account, terms not read), its inputs are an
   electric vehicle's own operating signals, which we have for no city, and so its published result cannot be
   reproduced first (fidelity rule 3). No replacement is chosen; one must be found, with its licence read, before the
   SOS phase is planned. Details: `docs/COPY_FIRST_AUDIT.md`, section 5.

## From the walkthrough video (2026-10-09) — not done, for the owner to decide

1. **Search suggestions lag behind fast typing.** The map app asks for suggestions every 200 ms while a person types; the backend sends
   at most one Photon request per second (Photon's fair-use pacing) and serves them one by one, so after typing "Dhaka Medical College
   Hospital" quickly the matching suggestions arrive about 10 s later (server log, 2026-10-09). Proposed: in
   `core/simulation/routing/trip/places.py`, answer only the newest waiting query and drop older ones that are still queued.
2. **The Research page still uses the older question numbers** (the ambulance study is "RQ2" on the page, RQ3 in README and
   `docs/PAPER_MAP.md` since the renumbering of 2026-10-09). The video's captions give both. Proposed: relabel the page headings.
3. **Fixed during the video (not a proposal):** the map app's offline worker was never registered, because its boot file waited for a
   page `load` event that had already fired (`frontend/map/src/boot/tt.ts`, test in `src/traffictwin/tt.test.ts`). The hosted site
   still has the old build until the next deploy.

## AID extensions (owner's request, 2026-10-11 12:40; approved in the same message) — J1 GUI, J1 frontier, J2 camera sensor

**Done 2026-10-11 ~14:00** (`features/aid/README.md` "Frontier and the camera sensor"; the camera result is negative at Dhaka density).

1. **`make aid-gui` colours.** Each station pair drawn on the map as a polygon over its segment: green normal, yellow tentative
   (California #7 state 1, or the model's probability over half the alarm threshold), red alarm (5 min after a detection); the stopped
   incident vehicle red; the label counts detections and false alarms (a detection on a pair with no active incident). Display only;
   the detectors and the saved results are unchanged.
2. **Frontier plot.** On the held-out seeds (11-15, odd pairs) sweep the model's alarm threshold (0.05 to 0.99) and California #7's
   T1/T2/T3 grid; plot detection rate against false alarms per pair-hour for both, at Dhaka density (x0.78, from the saved test rows
   and incidents: no new simulation) and at low density (x0.3, new runs). Saved under `evidence/aid/frontier/`.
3. **J2 camera sensor** (IncidentNet, Sravan Chintareddy et al., arXiv 2408.00996; github.com/MPSLab-ASU/IncidentNet, Apache-2.0,
   commit `7d73a229…`, read through the GitHub API only, nothing cloned or run). Their sensing: per-junction edge mean speed, count and
   occupancy every step, per-vehicle id/lane/speed, rolling means, and the travel time between sensor pairs from vehicle ids seen at
   both (`data_preprocessing/process_raw_data.py`). Ours (`--sensor camera`): a camera on the approach edge of every signalised junction
   on the corridor, every 30 s per camera pair: vehicles seen, mean speed, stopped count, mean waiting time, and the mean travel time of
   the vehicles seen at both cameras in the window. Same seeds, incidents and protocol as the loops; the corridor has 2 signalised
   junctions, so there is one camera pair and the "unseen location" split holds only for the incidents, not for the sensor; said so in
   the results. Its points go on the frontier plot. Reported honestly either way.

## S: Max-Pressure signals + EV priority (owner's request, 2026-10-11 14:20; approved in the same message)

**Done 2026-10-11 (afternoon); result negative, recorded in `docs/LIVE_RUNS.md` and the feature README.**

Survey (GitHub API, read-only): **RESCO** github.com/Pi-Star-Lab/RESCO, commit `f1ed9a17…`, GPL-3.0, `resco_benchmark/agents/static/maxpressure.py`
(a one-line agent over its "wave"/pressure observation); **LibSignal** github.com/DaRL-LibSignal/LibSignal, commit `127af9f9…`, **no licence
file**, `agent/maxpressure.py` (pressure = sum over the phase's lane links of count_in − count_out, minimum phase time `t_min`);
**sumo-rl** (MIT, commit `86f0fc41…`, already ours) has no Max-Pressure agent. GPL-3.0 is incompatible with this MIT repo for copying and
LibSignal is unlicensed, so the controller is our own `core/simulation/signals/signal_baselines.MaxPressureController` (Varaiya 2013, written
for the signals gate: queue-based pressure, min/max green, the program's own yellow), checked by eye against both. New (ours):
`core/simulation/ambulance/mp_signals.py` with EV priority: the junction ahead of the driving ambulance (within the V2X alert's `ahead_m`)
prefers the green phase of the ambulance's approach, program-safe; no V2X message involved. Arms compared on the same seeds and level:
fixed time (saved), Q-learning (saved, sumo-rl venv), Max-Pressure, Max-Pressure + EV priority: ambulance travel time, mean time loss of
every other vehicle, vehicle-hours, queue at the signals. `make run-signals ARGS="--controller maxpressure"` (right window), `make
compare-signals` (headless, 5 seeds) → `evidence/signals/controllers/`. Defaults unchanged (`--controller rl`).

## P: The ONE's routers x phone count (owner's request, 2026-10-11 14:20; approved in the same message)

**Done 2026-10-11 (afternoon); result negative, recorded in `docs/LIVE_RUNS.md` and the feature README.**

`scripts/live/sweep_mesh.py` / `make sweep-mesh`: The ONE 1.6.0 (GPL-3.0, already fetched and built by `third_party/the-one/fetch.sh`, run
unchanged in batch mode) with its own EpidemicRouter, SprayAndWaitRouter (7 copies, as the study), ProphetRouter, MaxPropRouter on the
thesis window (research/mesh_pons/work/dhaka.fcd.xml, 900-1200 s), phones 17 / 50 / 100 / 200 ranked by presence in the window (17 =
the thesis's full-window set), seeds 1-3, radio 10 m; absent phones parked outside the map out of range. Delivery ratio and mean latency
per router -> `evidence/mesh/routers/sweep.{csv,json,png}`. The ONE's numbers, a second view; the thesis's PONS result is untouched.

## P2: delivery against radio range (owner's request, 2026-10-11 ~15:20; approved in the same message)

**Done 2026-10-11 15:30: delivery rises with range at both counts (contacts are the bottleneck).**

`make sweep-mesh ARGS="--range-sweep"`: The ONE, Epidemic (P's upper bound: every router was equal), 17 and 100 phones, radio 10 / 30 / 50 /
100 m, seeds 1-3 -> `evidence/mesh/range/range.{csv,json,png}`. If delivery rises with range, contacts are the bottleneck. Thesis numbers untouched.

## J3: IncidentNet's own code, reused with attribution (owner's request, 2026-10-11 ~16:00; approved in the same message)

Apache-2.0 (MPSLab-ASU/IncidentNet @ `7d73a229`). Plan: (1) read every file through the GitHub API, list what each does and any network /
shell / install calls, run nothing; (2) copy only the feature-extraction and model files unchanged into `third_party/incidentnet/` with
LICENSE and a NOTICE line, record in SOURCES.md; pytorch-tabnet only at the exact version their requirements pin, in a separate venv
`research/aid/.venv-incidentnet`, after telling the owner the package and version; (3) reproduce their pipeline on their own scenario if
it is in the repo and compare with the paper (urban detection 98 %, false alarms 6.26 %, time-to-detect 197 s): REPRODUCED / CLOSE /
DIFFERENT; (4) their model on our Dhaka corridor camera features, same train/test protocol, points added to `evidence/aid/frontier/`.
Stop and report if the reproduction fails or step 1 shows anything unsafe.

**Done 2026-10-11 17:15 as option A (owner, 15:58): step 3 impossible (no scenario/data/models/pins in the repo), five files copied unchanged, `make aid-incidentnet`, results in `docs/LIVE_RUNS.md` and `features/aid/README.md`; no install, TabNet not used.**

## Q: what is still static in the eleven features, and what would make it dynamic (owner's question, 2026-10-11 15:50; approved 15:58: crash-sos sweep and prefetch from OSM masts only, no OpenCellID; hospital reach skipped; J3 = option A; then a read-only hardcode audit docs/HARDCODE_AUDIT.md)

**J3 is still stopped** (step 1 showed the scenario, data and version pins are not in the IncidentNet repo; waiting for A / B / C).

Checked on 2026-10-11 15:50 from the feature READMEs and the live make targets. **Eight of the eleven features already run a real
simulation on demand** (SUMO + TraCI for V2X, signals, AID, crash SOS, live twin; The ONE / PONS for the mesh; headless Chromium for
the prefetch; RQ1's own models for forecasting) and the map app shows those results. What remains static is **data, not code**:

| Feature | Static part | Dynamic replacement | Needs | Est. |
|---|---|---|---|---|
| crash-sos | one saved live run (seed 11, 50 %) | `make sweep-sos`: seeds 11-15 x app shares 25/50/75/100 % x crash at 600/900 s, with the no-warning twin of each run; CSV + plot `evidence/sos/sweep/` | our code only (SUMO already) | 1.5 h |
| hospital-reach | map speeds (Valhalla), recorded variant equal to it | `make reach-sim`: the Dhaka-wide SUMO network (`data/cities/dhaka_r1`, randomTrips demand of the mesh study) run once at morning density, edge travel times -> sumolib Dijkstra from the 37 hospitals -> 10/20/30-min shares at **simulated** speed next to map speed, `evidence/reach/simulated/` | our code only (sumolib) | 3 h |
| weak-signal-prefetch | signal profile SYNTHETIC (weak stretches by seed) | signal along the route from real tower positions + a published path-loss model (COST-231 Hata, formula from the paper): OpenCellID towers (CC-BY-SA 4.0, needs an API key the owner registers) or OSM `man_made=mast` (ODbL, likely sparse in Dhaka) | owner's OpenCellID key, or accept OSM sparsity | 3 h |
| crash-detection | three SYNTHETIC traces built on either side of 4 g (circular) | **done 2026-10-11 (step M):** the rule evaluated unchanged on VZCrash's 24,174 recorded test events on the AWS instance (recall 45.6 %, precision 88.6 %, false alarms 1.24 %), next to the paper's baseline reproduced (AP 0.896 = 89.62 %) and a gradient-boosting model (AP 0.954); `features/crash-detection/README.md`, `evidence/sos/vzcrash/` | owner approved (gate accepted 2026-10-11) | `research/sos/vzcrash/run.py` |
| forecasting (Dhaka rows) | three DhaTraX site-days, zero-shot | no further Dhaka speed series exists; the live twin already forecasts live on simulated speeds | data | — |
| phone-mesh | ideal 10 m disc; alerts do not feed back into traffic | by design (phones, not cars); the car-to-car feedback is crash-sos | — | — |

GitHub search, read-only (`gh api search/repositories`, 2026-10-11 15:55): accelerometer crash detection repos are unlicensed student
apps or GPL-3.0 Android apps with no data; `dhanavanthesh/path_loss` (Hata, COST-231) has **no licence**, so the formulas are taken
from the papers instead; `i6015hdz/opencellid-downloader` (MIT) and `edipermadi/opencellid-importer` (MIT) only fetch/convert the
OpenCellID CSV; PowerTutor (`msg555/PowerTutor`, licence "other") is a 2010 phone power model like the one already used; nothing for
SUMO isochrones (sumolib's own Dijkstra suffices). No code needs copying for any row above. Recommended order if approved: crash-sos
sweep, hospital reach at simulated speed, then the prefetch signal if a key is available.

**Done 2026-10-11 17:40: Q1 (`make sweep-sos`), J3-A (`make aid-incidentnet`), Q3 (`make prefetch-masts`, OSM masts only); results in `docs/LIVE_RUNS.md` and the feature READMEs; hospital reach skipped as the owner said.** Same rules: new make targets default off,
tests + `make present` after each, revert on failure, saved thesis results untouched.

## R · "All features real and dynamic" before the redeploy (owner, 2026-10-11 19:12)

What is still a stand-in for a measurement in what the supervisor sees (docs/HARDCODE_AUDIT.md Part C.2), and what replaces it:

| # | Static or synthetic input | Replacement (behind a flag or target, saved thesis results untouched) |
|---|---|---|
| R1 | RQ6 crash trace "crash_jolt": a typed 6.5 g spike | A trace built from **SUMO's own collision record** (`collisions.xml`: colliderSpeed, victimSpeed) of `make run-sos-collide`: the closing speed becomes a 120 ms half-sine pulse (same pulse length as the synthetic trace, stated as ASSUMED); the collider's speed is the GPS speed, so the rule's speed floor is applied for the first time. Kind `sumo_collision`, served by the same trace API, a chip on Emergency ("collision from the simulation", tag Simulation), `make present` step 2 runs the collision and step 7 replays that trace. The three synthetic traces stay (the thesis's RQ6 table is unchanged). |
| R2 | Hosted app: the weak-signal prediction uses road type and probe history only | The hosted `.env` sets `TRAFFICTWIN_SIGNAL_MASTS=1` (code default stays off) and the package ships `data/cities/dhaka/masts.json` + `evidence/prefetch/masts/summary.json`. |
| R3 | Research RQ5 energy table: synthetic profiles only | One extra row from the real OSM mast profile (step Q3), read from `evidence/prefetch/masts/summary.json`, labelled as such; synthetic rows unchanged. |

Not changed, because they are model settings rather than stand-in data: rule constants, V2X parameters from papers, SUMO demand, mesh and Veins settings (each row in the audit names its source).
Order: R1, R2, R3; tests + `make present` after each; stop at 23:00; then the one redeploy.

**Done 2026-10-11 20:05: R1, R2, R3.** `make present` 7 of 7 (present_20261011_193708): step 2 is the SUMO collision (38 s), step 7 replays its trace (countdown at 12.02 s, as the run's own check said). Hosted flag and files take effect at the next deploy. Synthetic traces, RQ5 synthetic rows and every saved result unchanged.

## V · Ambulance V2X "as real and dynamic as possible" before the talk (owner, 2026-10-12 03:35; approved in the same message)

Five steps, hard stop 06:00. **Step 1** read-only audit of fixed values → `docs/HARDCODE_AUDIT.md` (2026-10-12 section).
**Step 2** a demand option at the FULL recorded DhaTraX counts (the corridor routes at scale 1.0 instead of the density-matched x0.78;
the counts summed from `calibration.json`, never typed); a 5-seed check, three arms, ITS-G5 → `evidence/ambulance_rq2/dhatrax_peak/`
(`scripts/ambulance/peak_check.py`). Saved results and their docs numbers untouched. **Step 3** `make run-v2x-live SEED= FROM= TO= DEMAND=`:
seed from the clock by default, route by edge ids or random, demand level; the screen prints seed, route, demand and the result; the
web job accepts the same parameters. **Step 4** tests, full suite, `make present`, two live runs. **Step 5** plain summary.
Defaults unchanged everywhere (`make run-v2x` still seed 11, the thesis trip, x0.78 → REPRODUCED exactly).

## A · ML + networking in one loop (owner, 2026-10-12 04:00; approved in the same message)

Part A done: `core/simulation/ambulance/rl_v2x_loop.py`, `make run-ambulance-loop`, `evidence/ambulance_loop/`, `features/ambulance-loop/README.md`. Part B (PRE-VE-style RSU dissemination on the LA twin, `--dissemination rsu`) and Part C (phone → gradient-boosting detector → SOS → V2V) not started by 06:00; scoped in HANDOFF row A.

## D-G · Live GUIs, radio-profile routing run, crash loop plan, final checks (owner, 2026-10-12 05:40; approved in the same message; deadline 10:00)

D `make gui-routing` (loop unchanged, display through its hooks) + ITS-G5 routing runs → `evidence/routing_profiles/`. E `make gui-ambulance-loop` (loop unchanged). F phone → gradient-boosting → SOS → V2V: plan given, waits for the owner's yes on the AWS commands (no model file exists on the instance yet; it must be re-fitted and copied). G suite alone, present 7/7, each GUI once, BPR in SOURCES, Live-demo README sections, demo cheat sheet.
