# Hardcode audit: where every number the supervisor sees comes from (read-only, 2026-10-11, owner's request at 15:58)

Three readers went through the code without changing anything: (A) the React app under `/app` and the backend routers it calls,
(B) the map app at `/` and its endpoints, (C) the live terminal runs (`make present`, `make demo`, every `make run-*` / `sweep-*` /
`aid-*` / `prefetch-masts`) and the inventory of synthetic or assumed inputs. Classes: **COMPUTED** = produced at request or run
time; **READ** = read from a results or evidence file (path → key); **HARDCODED** = a literal in the source (file:line). Nothing was
fixed; the owner decides what to change.

## Summary

- **Every result number on the everyday pages and the Research tables is READ from a results file or COMPUTED live.** The
  ambulance sentence reads `results/emergency/dhaka/rq2/summary.json → plain.*`, reach reads `results/reach/<city>/summary.json → plain.*`,
  the mesh sentence `results/networking/mesh/<city>/summary.json → plain`, the weak-signal sentence `results/networking/prefetch/summary.json → plain`;
  routes, hospital times, live reach, the live twin, the Model Lab, every Simulation-chip run and every live `make` run are computed
  at request time. No measured-looking value is typed into JSX, Vue or the locale files.
- **What is HARDCODED is rule constants, protocol settings and UI defaults restated in prose** (lists in each part): the 4 g / 24.1 km/h
  crash rule and the 15 s countdown, "×8" demand, "within 5 minutes" horizons, "15 min / 60 min ahead", the 10/20/30-minute reach lines,
  "8 readings 5 minutes apart", "30 % of drivers", "seeds 11, 23, 37", "207 sensors", Bartendr's energy constants, the scale 0.78
  typed in three live scripts, and three silent fallbacks (`help_pct ?? 10`, `|| 2700`, `?? [10, 20, 30]`). Two typed-in result-like
  numbers in the live scripts: the watch text "292 s -> 284 s" in `scripts/live/demo.py:34` (**fixed on the owner's order, 2026-10-11
  17:50:** now READ through `run_v2x.saved`, see the demo.py table) and the IncidentNet paper numbers printed as context in
  `scripts/aid/incidentnet_xgb.py`.
- **Synthetic or assumed inputs (Part C.2, 34 rows):** the three SOS traces (built on either side of 4 g), RQ5's signal profiles
  (seeded weak runs), Bartendr's Palm Pre energy constants, the V2X channel values (5GAA, Xu 2017, tinyLTE, ETSI; none from Dhaka),
  the corridor demand (DhaTraX counts at two sites scaled to 0.78) with SUMO's default vehicle parameters, the ASSUMED `dhaka_r1`
  vehicle parameters, randomTrips demand for the mesh movement, AID's seeded incidents, the mesh and Veins settings, the masts model's
  assumed EIRP and carrier, the hospital rule (`emergency=yes`), the closed-loop ×8 what-if demand and the RQ1 Dhaka zero-shot rows.
- **Two wiring observations (not numbers, not fixed):** the trip sheet filters alert kinds `ambulance` and `congestion`
  (`frontend/map/src/traffictwin/tt.ts:189`) while the feed emits `congestion_onset`, so recorded congestion alerts never reach it;
  the SOS and mesh result sentences say "within 5 minutes" while the horizon is the constant `after=300.0` in
  `core/simulation/live_jobs/jobs.py:139` and the mesh TTL, not interpolated.

---

### Part A: Audit A: every number a supervisor can see on the React app (/app) — COMPUTED / READ / HARDCODED

Read-only, 2026-10-11. Method: every page under `frontend/src` reached from `app/routes.tsx`, every API path in `frontend/src/lib/api.ts` followed to its router in `backend/app/*/router.py` and to the service/file it reads; the English locale `frontend/src/i18n/locales/en.json` (flat keys) scanned for digits inside sentences. Layout/style numbers, array indices and timeouts are left out. Pages that are LIFE OS leftovers (`/today`, `/plan`, `/goals`, `/messages`, `/map`, `/city`, `/activity`, `/you-lifeos`) are outside the owner's list and not audited here, except where the same component is reused.

Classes: **COMPUTED** = produced at request time; **READ** = read from a results/evidence/config file (path → key); **HARDCODED** = a literal in the source (file:line) or inside a translated sentence.

### Home `/` (FocusHome: SOS card, nearest hospital, navigate)

| Page | Number as shown | Class | Source | Note |
|---|---|---|---|---|
| Home | "about {min} min ({km} km)" nearest hospital, first and next two | COMPUTED | `GET /api/emergency/reach/{city}/nearest` → `core/safety/reach.py:nearest` (Valhalla time matrix at map speeds); shown via `features/home/NearestCard.tsx:45-47`, `minutes()` in `features/emergency/reach.ts:14` | map speeds, not traffic; said in the sentence |
| Home | "About {min} min for {distance} km" route sentence | COMPUTED | `GET /api/route/{city}` → `core/simulation/routing/valhalla.py:route`; `features/today/trip.ts:routePlain` (327-331) | map speeds |
| Home | "{mb} MB" saved for weak signal | COMPUTED | `lib/weakSignal.ts:saveForWeakSignal` (bytes counted while saving the pack), `NavigateCard.tsx:77` | browser-measured |
| Home | SIMULATION ×8 speed (simulated drive pill) | HARDCODED | `features/today/Navigate.tsx:24` `SIM_SPEED = 8`; sentence `nav.simulation` | a demo setting, labelled on screen |
| Home | "{km} km, {min} min, arrive {at}" while navigating | COMPUTED | Ferrostar `nav.progress.distanceRemaining/durationRemaining`, `Navigate.tsx:130-131` | from the live navigation session |
| Home / Emergency | SOS: "a crash-like jolt starts a 15-second countdown" (`focus.sos.sub`) | HARDCODED | `en.json` key `focus.sos.sub` ("15-second" typed into the sentence) | the real constant is `features/emergency/sos.ts:8` `COUNTDOWN_S = 15` and `core/safety/sos.py:23`; the sentence does not interpolate it |
| Home / Emergency | SOS countdown digits "15…0" | HARDCODED (constant) | `features/emergency/sos.ts:8` `COUNTDOWN_S = 15`, ticked in `useMotion.ts:39-43` | design constant, mirrors `core/safety/sos.py:23` |
| Home / Emergency | "{g} g" live acceleration and "4 g" line on the motion graph | COMPUTED | `useMotion.ts:28-34` from `DeviceMotionEvent`; threshold `sos.ts:6` `THRESHOLD_G = 4.0`, drawn in `MotionGraph.tsx:20-22` | the 4 g threshold is a HARDCODED constant (WreckWatch), the reading is live |
| Home / Emergency | SOS path step 1 "{peak_g} g detected (rule: at least {threshold_g} g)" | COMPUTED + READ | `GET /api/emergency/sos/path/{city}` → `core/safety/sos.py:path_steps` 130: `peak_g` from the device, `THRESHOLD_G` from `core/safety/sos.py:21` | threshold constant 4.0 |
| Home / Emergency | SOS step 2 "{seconds} seconds passed" | HARDCODED (constant) | `core/safety/sos.py:131` ← `COUNTDOWN_S` (`sos.py:23`) | |
| Home / Emergency | SOS step 3 ambulance number for the city | READ (config) | `core/safety/sos.py:129` ← `config/cities/<city>.yaml → emergency_numbers.ambulance` | never dialled |
| Home / Emergency | SOS step 3 (offline) "{vehicles} vehicles, {pct} % … after {delay_s} s" | READ | `core/safety/sos.py:135-139` ← `results/networking/mesh/<city>/summary.json → plain` (or `core/networking/mesh/results.py:plain_numbers` 95-100 from `rows`) | built by `research/mesh_pons/scripts/03_run_pons.py` + results.py |

### Trip `/trip` (Home.tsx: trip bar, map, leave-when, whole-city route, weak signal)

| Page | Number as shown | Class | Source | Note |
|---|---|---|---|---|
| Trip | "Route: {n} km over {sections} road sections" | COMPUTED | `GET /api/trip/{city}` → `backend/app/routing/city_trip.py:trip` (sections from the SUMO network, `length_m`), `LeaveWhen.tsx:35` | |
| Trip | travel time at now/15/30/60 with range and tag | COMPUTED | `city_trip.py:52-66`: probe readings (`probe_speeds.read`) + `core/ml/forecasting/operations/section_forecast.py:forecast` (Chronos-2 adapter) | shown only where readings exist |
| Trip | "{share} % of this route's length has traffic data" | COMPUTED | `city_trip.py:38` `covers_share_of_length`; `LeaveWhen.tsx:38` | |
| Trip | "About {min} min at the map's speed limits" | COMPUTED | `city_trip.py:64` `at_limits` (sum of section length / limit) | labelled "no traffic" |
| Trip | "a section needs 8 readings in a row, 5 minutes apart" (`home.why.too_few_readings`) | HARDCODED | `en.json` key `home.why.too_few_readings`; the backend reason is the string `"too_few_readings"` at `core/ml/forecasting/operations/section_forecast.py:42` with `MIN_READINGS` (`section_forecast.py:11`) | the "8" and "5 minutes" are typed into the sentence, not interpolated from `MIN_READINGS` / `BIN_MIN` (`backend/app/probes/service.py:18`) |
| Trip | "No drivable road … within 150 m of that point" | HARDCODED (constant) | `en.json` `home.refused.no_road_near`; constant `core/simulation/routing/city_router.py:21` `SNAP_RADIUS_M = 150.0` | sentence and constant agree but are not linked |
| Trip | "Leave by {depart} to arrive by {arrive}" | COMPUTED | `features/today/trip.ts:leaveBy` 39-48 from the trip's travel values | |
| Trip | "About {min} min for {distance} km by {profile}" and "alternative {n}: {min} min"; turn list "{m} m · {min} min" | COMPUTED | `GET /api/route/{city}` → `valhalla.route`; `CityRoute.tsx:31,35,44` | map speeds |
| Trip | "On {n} stretch(es) … recorded at {at} … about {min} min" | COMPUTED from READ data | `valhalla.route(at=…)` re-times stretches with DhaTraX medians (`core/simulation/routing/valhalla.py:~115-146`); `CityRoute.tsx:38-40` | DhaTraX = recorded dataset |
| Trip (recorded day) | "median of {vehicles} vehicles over a {metres} m stretch", tagged value | READ (data) | `city_trip.py` with `recorded_at` → DhaTraX per-section readings (`core/common/data/recorded/*`); `Recorded.tsx:14-15` | recorded dataset, its own day |
| Trip (real recorded traffic) | "Camera {site}: {metres} m of road … {n} tracked vehicles in this minute"; vehicles drawn | READ (data) | `GET /api/recorded/{city}/replay` → `core/common/data/recorded/replay.py:window` 59-64 (DhaTraX tracks) | replay of one day |
| Trip | weak-signal strip bins; "{bin}: {km} km"; "No signal history for {km} km" | COMPUTED | `GET /api/route/{city}/signal` → `backend/app/routing/signal_predict.py:predict` (Valhalla trace attributes + probe cells; `core/simulation/routing/signal.py`) | `MIN_READINGS = 3` (`signal.py:23`), `STEP_M = 100` (`signal.py:20`), `LOW_DENSITY = 2` are HARDCODED rule constants |
| Trip | "Saves … {n} map tiles (zoom {zooms})" | COMPUTED | `lib/pack.ts:tilesForRoute`; `ZOOMS` / `ZOOMS_LOW_DATA` constants in `lib/pack.ts` (HARDCODED zoom lists) | |
| Trip | "{done} of {total}" saving; "{mb} MB, {tiles} tiles" saved | COMPUTED | `lib/pack.ts:savePack` (bytes received), `TripPackPanel.tsx:74,80` | browser-measured |
| Trip | "Estimated radio energy: {now} J / {needed} J / {plan} J ({bursts} bursts)" | COMPUTED (model) | `lib/schedule.ts:bartendr/nowJ/asNeededJ` on the route's signal steps and the measured pack bytes; constants `P_DATA_W = 1.5` (`schedule.ts:10`), `POWER` (11), `TAIL_S = 3` (12), `CHUNK_BYTES` (14), `PRESET_THR` (70) | the constants are HARDCODED Bartendr/Palm-Pre figures (labelled "estimated") |
| Trip | "On a 2G-like network the route appeared after about {without} s … {with} s … {offline} … {offlineWithout}" | READ | `GET /api/networking/prefetch` → `core/networking/prefetch/results.py:read` ← `results/networking/prefetch/summary.json → plain.slow_without_s / slow_with_s / offline_with / offline_without` (built by `results.py:build` from `runs/*.json`) | |
| Trip | "This trip used {mb} MB so far" | COMPUTED | `lib/dataUsed.ts:useDataUsed` (PerformanceObserver) | browser-reported |
| Trip | BreadCrumbs "learning: {n} of {needed} trips" | COMPUTED + HARDCODED constant | `lib/breadcrumbs.ts:62` ← `MIN_TRIPS = 5` (`breadcrumbs.ts:10`), `TAU_S = 10` (`breadcrumbs.ts:9`) | on-device |
| Trip (simulated view) | vehicle count drawn | COMPUTED | `useSimulated.ts` ← `GET /api/sim/live/state` (SUMO live) | |
| Trip | alerts strip: "{alerted} vehicles alerted, {junctions} signals" / "about {ratio_pct} % … among {vehicles} vehicles, after about {delay_s} s" | COMPUTED / READ | `GET /api/alerts/feed` → `backend/app/alerts/service.py:101-102` (live sim state) and `:118-119` ← `results/networking/mesh/<city>/summary.json → rows[best].delivery_ratio.mean, delay_s.mean` | |
| Trip | "congestion forming in about {h} min ({now} now, {predicted} forecast, threshold …)" | COMPUTED / READ | `backend/app/alerts/service.py:72` from `results/forecasting/model_comparison.json`-backed onsets (`app/forecasting/routers/onset.py:13`) | only for road watches (METR-LA datasets) |

### 3D City `/3d` (LiveTwinPanel, AmbulancePanel; same panel as Research → Control Room tab 1)

| Page | Number as shown | Class | Source | Note |
|---|---|---|---|---|
| 3D City | status "{seconds} s simulated" | COMPUTED | `GET /api/sim/live/state` → `core/simulation/twin/live/loop.py` (`sim_time_s`) | |
| 3D City | on road / mean speed km/h / mean wait s / arrived; "{shown} of {all} vehicles are drawn" | COMPUTED | `core/simulation/twin/live/loop.py:176` (`mean_speed_kmh = mean(speeds)*3.6`), `vehicles_on_road`, `shown`, `arrived` | |
| 3D City | vehicle id / class / "{speed} km/h" | COMPUTED | live state vehicle tuple (`LiveTwinPanel.tsx:59`) | |
| 3D City | "{edges} road sections and {signals} signalised junctions" | READ (network) | `GET /api/twin/scene/{city}` → `backend/app/twin/router.py:98` (scene `network.edges`, `traffic_lights`) from the city's built SUMO network | |
| 3D City | lane widths "from an OSM lanes tag for {osm} sections, SUMO default for {byDefault}, not recorded for {unknown}" | READ (network) | scene `lanes.sections_by_source` | |
| 3D City | vehicle mix "{name} {share_pct} %, counted {counted}" (Research variant) | READ (config) | `GET /api/operate/cities` → `backend/app/routing/router.py:~49` `vehicle_mix` ← `config/cities/dhaka.yaml → vehicle_mix.classes[*].share_pct` (DhaTraX counts, `python -m core.common.data.recorded.dhatrax --mix`) | the everyday variant has no numbers |
| 3D City | ambulance panel: share options 0/25/50/100 % | HARDCODED | `features/twin/AmbulancePanel.tsx:5` `SHARES = [0, 25, 50, 100]` | UI choices, not results |
| 3D City | ambulance "{seconds} s" depart, alerted, making way now, "{delivered} / {sent}", preempted, "{arrived-departed} s" trip | COMPUTED | live run `emergency` block from `core/simulation/ambulance/service.py` via `core/simulation/twin/live/*` | |
| 3D City | one plain ambulance sentence (same as Emergency) | READ | see Emergency row below | |
| 3D City | start duration `duration_s: sc.demand.horizon_s ?? 1800`, `scale: 1.0`, `step_delay_ms: 1000` | HARDCODED fallbacks | `LiveTwinPanel.tsx:16`, `useSimulated.ts:36` | run settings, not shown as results |

### Add city `/add-city`

| Page | Number as shown | Class | Source | Note |
|---|---|---|---|---|
| Add city | "about {n} km" area buttons (2 / 4 / 7 km) | HARDCODED | `features/forecast/AddCityCard.tsx:5` `SIZES = [0.02, 0.04, 0.06]`, shown as `Math.round(s * 111)` at `:57` | a design choice (degrees → km) |
| Add city | "population {n}" | COMPUTED (external) | `GET /api/cities/search` → `backend/app/data/router.py:131` (Nominatim / geocoder answer) | |
| Add city | build stage text | COMPUTED | `GET /api/cities/jobs/{job}` | no numbers |

### Emergency `/emergency`

| Page | Number as shown | Class | Source | Note |
|---|---|---|---|---|
| Emergency | emergency numbers (ambulance, police, fire) | READ (config) | `config/cities/<city>.yaml → emergency_numbers` via `/api/operate/cities` (`backend/app/routing/router.py:~46`) | shown, never dialled |
| Emergency | ambulance sentence: "about {s} s sooner on a {trip} s trip", "smarter traffic lights … about {s} s" | READ | `GET /api/emergency/rq2` (`backend/app/emergency/router.py:126-131`) ← `results/emergency/dhaka/rq2/summary.json → plain.{trip_s, alert_s, signals_s, signals_more, not_every_time, slower_runs, alert_runs}`; computed into the file by `core/simulation/ambulance/summary.py:284-290` from the same table as the Research card; sentence assembled in `features/emergency/ambulanceSentence.ts:9-16` | the words "about" / "not every time" are rules in `summary.py:286-290` (`q25 > 0 and slower_runs == 0`; `>= 0.3` share) — HARDCODED thresholds for the wording, not for the numbers |
| Emergency | reach: "{p10} % within 10 minutes, {p20} % within 20, {p30} % within 30" (map speeds) and the recorded variant "at {at} on {day} at {n} spot(s)" | READ | `GET /api/emergency/reach/{city}` → `core/safety/reach.py:read` 183 ← `results/reach/<city>/summary.json → plain.map_pct["10"/"20"/"30"], plain.recorded_pct, recorded.at, recorded.sites[*].day` (built by `reach.py:build` with `plain_numbers` 119-124) | the bounds 10/20/30 are `BOUNDS_MIN` (`reach.py:30`) and are typed into the sentence `emergency.reach.plain` as well |
| Emergency | "pick a hospital ({n})" | READ | `rows.length` of the same file | |
| Emergency | reach map cells/polygons (10/20/30 min) | READ / COMPUTED | cells from `points` of the saved file (`reach.ts:cellFeatures`); the chosen hospital's polygons from `GET /api/emergency/reach/{city}/isochrone` → `valhalla.isochrone` (COMPUTED) | |
| Emergency | "from here": "{name}: about {min} min ({km} km)" | COMPUTED | `/nearest` → `reach.py:nearest` (Valhalla matrix) | |
| Emergency | SOS card: see Home rows (rule 4 g, 15 s, peak g, path steps) | — | — | `emergency.sos.rule` interpolates `THRESHOLD_G` and `COUNTDOWN_S` from `features/emergency/sos.ts:6,8` (HARDCODED constants, same as backend) |

### Offline alerts `/offline`

| Page | Number as shown | Class | Source | Note |
|---|---|---|---|---|
| Offline alerts | "in our test with {vehicles} vehicles, about {pct} % of messages got through, after about {delay} s" | READ | `GET /api/mesh/results/{city}` → `core/networking/mesh/results.py:read` 103 ← `results/networking/mesh/<city>/summary.json → plain.{vehicles, reached_pct, delay_s}` (built by `results.py:plain_numbers` 95-100 from `rows`, best router by mean delivery ratio) | PONS study, seeds 1-5 |

### Settings `/settings`

| Page | Number as shown | Class | Source | Note |
|---|---|---|---|---|
| Settings | "alerts once a minute" (low-data mode) | HARDCODED | `en.json` `settings.lowDataOn`; the behaviour is `AlertsStrip.tsx:19` `refetchInterval: lowData() ? 60_000 : 10_000` | sentence and code agree |
| Settings | voice / privacy cards | — | no numbers | |

### Research `/lab/evidence` (ResultsPage: routing verdict, RQ1, ambulance tables, RQ2, reach, SOS, prefetch, mesh)

| Page | Number as shown | Class | Source | Note |
|---|---|---|---|---|
| Evidence | verdict "{pct} % shorter than no advice" / "{pct} % against reactive routing"; the three big "% " cards with CI and W/L/T; "{n} unseen random days" | READ | `GET /api/experiment/stress` → `backend/app/protocols/routers/stress.py:39-68` ← `results/v2x/stress/la_c4_central_wide/summary_*.json`, `scenario{A,B}_oracle_gate_*.json`, the pointed `report.json` (`results/v2x/closed_loop/<run>/report.json → arms[*].vs_baseline/vs_reactive.{mean_pct, ci95, wins/losses/ties}`), `results/v2x/controller_status.json`; verdict rule in `features/results/verdict.ts:9-16` | gates from `GET /api/research/status` → `core/simulation/closed_loop/protocols/research_status.py:21-57` (`results/forecasting/verify_GWNet_METR-LA_207.json`, `results/v2x/stress/.../scenarioA_oracle_gate_eval.json`, `results/v2x/controller_status.json`, closed-loop `report.json`, `results/final_validation/metrics.json`) |
| Evidence | congested-demand table (demand, vehicles, arrived %, lost %, TTI, mean trip, stable, congested); "chosen scale {scale}, gate {gate}" | READ | same stress endpoint → `sweeps[*].points[*]` ← `results/v2x/stress/<city>/summary_*.json` | |
| Evidence | "rule frozen …: travel-time index ≥ 1.3, standing jams, ≤ 1 % lost vehicles" (`lab.ev.how1`) | HARDCODED | `en.json` `lab.ev.how1`; the real rule lives in `core/simulation/closed_loop/protocols/controller_config.json` (read at `stress.py:46`) | the sentence restates the rule by hand |
| Evidence | "Only 30 % of drivers are connected" (`lab.ev.how3`); "paired 95 % confidence interval" (`lab.ev.how4`) | HARDCODED | `en.json`; penetration is in the closed-loop `PROTOCOL.json` (`research.py:30-34`) | restated by hand |
| Evidence | dev/eval oracle gate %, CI; controller status seeds | READ | stress endpoint `scenarios.A.dev.oracle_gate…`, `controller_status` | |
| Evidence (RQ1) | MAE/RMSE/MAPE ± sd per model and horizon; Dhaka table; unseen-city table; "{v} mph … against {p} for persistence"; "Dhaka's speeds jump: {sg0}-{sg1} % …" | READ | `GET /api/forecasting/rq1` (`backend/app/forecasting/routers/rq1.py:16-22`) ← `results/forecasting/rq1/summary.json → lab[ds][model][h].{mae,mae_sd,rmse,mape_pct}`, `dhaka`, `unseen_city`, `character[ds].{stop_and_go_share, cv, acf_12}.median`, `character.DhaTraX.sites`; selection rules in `features/results/rq1.ts` (`best`, `moveCost`, `siteRange`) | built by `research/forecasting_rq1/scripts/01_protocol_b.sh` + `core/ml/forecasting/transfer_dhaka/run.py` |
| Evidence (RQ1) | "15, 30 and 60 minutes ahead" (`lab.rq1.sub`), "seeds 11, 23, 37" (`lab.rq1.labTitle`), "more than 30 % of free-flow" and "5-minute steps" (`lab.rq1.whyText`), "fixed to Los Angeles's 207 sensors" (`lab.rq1.cannot`) | HARDCODED | `en.json`; horizons also `features/results/rq1.ts:8` `HORIZONS = ["15","30","60"]` | protocol facts typed into text; the seeds/thresholds are not interpolated from the summary |
| Evidence (ambulance tables) | per-arm mean ± sd travel time, saved s, saved %, others' loss, alerted, crashed; "{total} runs, {crashed} crashed, {metres} m route, {signals} signals" | READ | `GET /api/emergency/results/{city}` → `core/simulation/ambulance/results.py:read` 91-95 ← `results/emergency/<city>/<demand>/summary.json → rows[*], runs, route_m, signals_on_route` | `demand != "dhaka_density"` (router.py:43) |
| Evidence (RQ2) | every number of the RQ2 card: medians (25-75 %), slower runs, ladder (vehicles, density, siren time), Dhaka-density row, Spearman rho / CI / n, Q-learning totals, make-way distance, density gap, old-vs-new | READ | `GET /api/emergency/rq2` ← `results/emergency/dhaka/rq2/summary.json → saved[arm][share][level].{saved_s_median, saved_s_q25, saved_s_q75, saved_pct_median, seeds, slower_runs}`, `ladder[*]`, `dhaka_level`, `why.*.{rho, ci95, n}`, `why_dhaka`, `qlearning_dhaka`, `makeway.current.distance_m`, `density_gap.numbers`, `old_vs_new`, `frontier`, `help_pct` | built by `core/simulation/ambulance/summary.py` (`python -m core.simulation.ambulance.study`) |
| Evidence (RQ2) | "the 3 signals near the route" (`lab.rq2.findRl`), "more than 5 s slower" (`lab.rq2.findSlower`), "07:00-08:00" and "about 90 m" (`lab.rq2.gap`), "within 100 m of a traffic light" (`lab.rq2.qlearning`), "50 m and 100 m were piloted" (`lab.rq2.makeway`) | HARDCODED | `en.json`; the 5 s is `WORSE_S` in `core/simulation/ambulance/summary.py` (used at `:289`), the 100 m is the key string `"no light within 100 m ahead"` in the summary file (`AmbulanceRq2.tsx:59`), the signal count is `signals_on_route` in the emergency results file | sentences restate constants by hand; values agree today but are not linked |
| Evidence (RQ2) | `help_pct ?? 10` fallback | HARDCODED fallback | `AmbulanceRq2.tsx:42-43` | only if the summary lacks `help_pct` |
| Evidence (reach table) | km² within 10/20/30 min per hospital (map and recorded), points changed; "{hospitals} hospitals, grid {step} m, {points} points"; site rows "median {median} km/h, map {map}, {stretch} m, Δ {delta} s, {vehicles} vehicles" | READ | `/api/emergency/reach/{city}?points=false` ← `results/reach/<city>/summary.json → rows[*].map_km2/recorded_km2/points_changed, hospitals_file.count, grid.{step_m, points}, recorded.sites[*]` | |
| Evidence (reach table) | "detour through it costs at most {tol} s" with `tol: 30` | HARDCODED | `features/results/ReachTable.tsx:19` `{tol: 30}` | the backend tolerance lives in `core/safety/reach.py` (detour rule); the page types 30 |
| Evidence (reach table) | bounds fallback `[10, 20, 30]` | HARDCODED fallback | `ReachTable.tsx:8` `r.bounds_min ?? [10, 20, 30]` | file carries `bounds_min` |
| Evidence (SOS table) | rule "{g} g, {kmh} km/h, {seconds} s"; generator "{hz} Hz, {seconds} s, seed {seed}, sd {sd} g"; per-trace samples, peak g, detected, at s; "{traces} traces, {detected} detected" | READ | `GET /api/emergency/sos/results` → `core/safety/sos.py:read` ← `evidence/sos/results.json → rule.{threshold_g, min_speed_kmh, countdown_s}, generator.{rate_hz, seconds, seed, noise_sd_g}, rows[*], plain` | the file's values come from constants `core/safety/sos.py:21-25` (4.0, 24.1, 15, 50 Hz, 30 s, seed 7) — SYNTHETIC traces, labelled |
| Evidence (prefetch table) | per condition: route shown, median time (range), MB, map-view MB, continues offline; "{n} runs"; pack {mb} MB; energy rows (weak share %, seed, now J, as-needed J, Bartendr J (bursts), saving %) | READ | `GET /api/networking/prefetch` ← `results/networking/prefetch/summary.json → rows[*], runs_total, pack_bytes_median, energy.rows[*]` (built by `core/networking/prefetch/results.py:build` from `runs/*.json`; energy via `energy_rows` with `THR` `results.py:27`, `WEAK_SHARES`, `SEEDS`, synthetic `profile()` 36-52) | energy constants HARDCODED in `core/networking/v2x/energy.py:10-14` (1.5 W, ×1.2/×1.5, 3 s tail) |
| Evidence (prefetch table) | "plus a 3 s tail per burst" (`prefetchRes.method`) | HARDCODED | `en.json`; constant `energy.py:12` `TAIL_S = 3` | restated by hand |
| Evidence (prefetch table) | since R3 (2026-10-11 evening): the "From real mast positions" line (sites, masts in box, weak %, nearest-site median, now / as-needed / Bartendr J, saving %) | READ | `evidence/prefetch/masts/summary.json` → `radio_sites`, `elements_in_box`, `metres`, `distance_to_nearest_site_m.median`, `energy.on_this_profile.*` (`core/networking/prefetch/results.py:masts_row`, `PrefetchTable.tsx`) | the file is `make prefetch-masts`'s output (Part C.2 rows "Mast model", "Radio sites") |
| Evidence (mesh table) | per router: n seeds, delivery ratio mean ± sd (min–max), delay s, copies, overhead; scope "{vehicles} of {seen} vehicles, seconds {from}–{to}, {range} m radio, {ttl} s lifetime, {seeds} seeds" | READ | `GET /api/mesh/results/{city}` ← `results/networking/mesh/<city>/summary.json → rows[*].{delivery_ratio, delay_s, copies_per_message, overhead_ratio}, scope.{vehicles_simulated, vehicles_seen, window_s, radio.range_m, messages.ttl_s, seeds}` | |
| Evidence (mesh table) | "one 100-byte message per second" (`mesh.scope`) | HARDCODED | `en.json` `mesh.scope`; the file carries `scope.messages.size_bytes` and `interval_s` (`features/emergency/mesh.ts:8`) which the sentence does not interpolate | |

### Research `/lab/control-room` (LiveTwinPanel research variant, Recorded twin, Fresh execution, Recorded replay)

| Page | Number as shown | Class | Source | Note |
|---|---|---|---|---|
| Control room (twin tab) | same as 3D City; plus the simulated tag words "calibrated to …" | COMPUTED / READ (config) | as above | |
| Control room (recorded tab) | "{n} tracked vehicles", "{metres} m of road", frames in window, recorded hours | READ (data) | `/api/recorded/{city}/replay` → `core/common/data/recorded/replay.py:window` (DhaTraX tracks); `WINDOW_S = 60`, `STEP_MS = 500` in `useRecorded.ts:16` (HARDCODED replay pacing) | |
| Control room (fresh execution) | simulation time, active vehicles, applied reroutes, TX/RX, teleports; forward pass s; priced edges; vehicle-hours, mean trip s, arrivals; PDR %, latency ms; V2X latency/loss/TTL; seed; hashes | COMPUTED (this run) / READ (frozen protocol) | `GET/POST /api/research/executions` → `core/simulation/closed_loop/control/jobs.py` (a fresh SUMO run) and `results/v2x/closed_loop/<REFERENCE>/PROTOCOL.json` (`backend/app/protocols/routers/research.py:30-34`) | intervention defaults `cap 2 m/s`, `ttl 60 s` in `ExecutionPanel.tsx:63` are HARDCODED form defaults |
| Control room (recorded replay) | every ticker/table number (vehicle-hours, "vs no advice" %, p95 trip s, arrived, stuck, reroutes, rounds, latency ms, detection delay s, "{penetration} % connected") | READ | `GET /api/experiment/v2x_closed_loop(/timeline)` → `backend/app/networking/router.py:14-70` ← `results/v2x/closed_loop/<run>/report.json`, `<arm>/arm_result.json` and the run's logs | `max = T.duration_s || 2700` (`ReplayPanel.tsx:32`) is a HARDCODED fallback |

### Research `/lab/models` (ModelsPage) — out of the owner's list of named pages but reachable; the tabs read `results/forecasting/model_comparison.json`, `conformal.json`, `imputation.json` (`backend/app/forecasting/routers/onset.py:13,52,97`) and `results/forecasting/live_backtest.json` (`predictions.py:123`); every shown number is READ or COMPUTED by those routers; not itemised here.

### Research `/lab/model-lab`

| Page | Number as shown | Class | Source | Note |
|---|---|---|---|---|
| Model Lab | history/recorded/forecast/no-change series; 15/30/60-min errors; "computed in {s} s"; RQ1 check "largest difference {d} mph, window {w}" | COMPUTED | `POST /api/model-lab/run` → `backend/app/forecasting/routers/layer.py:44-56` → `core/ml/forecasting/layer/lab.py:run` (the model's checkpoint, RQ1's code); `took` measured in the browser (`ModelLabPage.tsx:18-22`) | the check compares with RQ1's saved window file |
| Model Lab | "METR-LA (207 loop detectors, recorded 2012)" (`modelLab.intro`); default `at = "2012-06-07T14:30"`, default model `D2STGNN` | HARDCODED | `en.json` `modelLab.intro`; `ModelLabPage.tsx:11-12` | dataset facts typed in; test window from/to come from the server (`info.test_from/to`) |

### Research `/lab/live-twin`

| Page | Number as shown | Class | Source | Note |
|---|---|---|---|---|
| Live twin | seed; sim time; "Traffic: {demand}. Base scale {scale}"; vehicles; crashes; ambulance messages sent/delivered, alerted, making way, green signals, time so far; "{roads} roads, {loops} detectors"; MAE last 10 min / all; error chart; "{n} learned"; steer counts | COMPUTED | WebSocket `/api/live-twin/twins/{id}/ws` → `core/simulation/live_twin/session.py` (`status` 105-110, `_counts`, `_minute` 259-261), forecasters `core/ml/forecasting/live/online.py`; `base_scale` = `self.lt.demand_scale` from `config/cities/<city>.yaml → live_twin` (READ config, 0.78 for Dhaka) | seed from the clock (`session.py`) |
| Live twin | "warms up for 15 simulated minutes" (`liveTwin.notStarted`), "15 minutes ahead"/"15-minute prediction" (`liveTwin.fcHow`, `liveTwin.colours`, `liveTwin.steer.note`), "last 10 minutes" (`liveTwin.mae10`), "5 seeds" (`liveTwin.steer.note`), "×0.5 … ×2", "1 to 20" | HARDCODED | `en.json`; constants `core/simulation/live_twin/session.py:34` `WARMUP_MIN = 15`, `core/ml/forecasting/live/online.py:25` `HORIZON = 15`, slider bounds `LiveTwinPage.tsx:138` (0.5–2), speed list `:144` ([2,4,8,12,20]), `fetch(... {speed: 8})` `:77` | the server sends `warmup_min` and `horizon_min` (`session.py:108`, forecast block) but the sentences do not use them |
| Live twin | steer share "{pct} %" default 30 % | HARDCODED default | `SteerControl.tsx:9` `useState(0.3)` | a control, not a result |
| Live twin | road colour thresholds 0.6 / 0.3 of the limit | HARDCODED | `features/livetwin/liveTwin.ts:22` | display rule, stated in the legend text |

### Research `/lab/references` and `/lab/system`

| Page | Number as shown | Class | Source | Note |
|---|---|---|---|---|
| References | "{count} references", group counts | READ | `GET /api/references` ← `docs/references.json` (`backend/app/protocols/routers/references.py:13`) | |
| System | gate statuses | READ | `GET /api/research/status` (files listed above) | |
| System | "30 % penetration", "TTI ≥ 1.3, standing jams, ≤ 1 % lost vehicles" in the "What is ours" bullets | HARDCODED | `features/system/SystemPage.tsx:12-13` (English literals, not even in i18n) | restated protocol facts |

### Shared components

| Component | Number | Class | Source | Note |
|---|---|---|---|---|
| `features/today/trip.ts:21` | colour classes at 0.7 / 0.4 of the speed limit | HARDCODED | display rule (legend says so) | |
| `features/today/Cards.tsx:7`, `Stats.tsx:17` (LIFE OS `/today`) | risk grades at 0.8 / 0.5; "{pct} % on time" | HARDCODED thresholds / COMPUTED | LIFE OS page, outside the named list | |
| `features/today/Welcome.tsx:25` | on-time targets 80 / 90 / 95 % | HARDCODED options | LIFE OS | |

### HARDCODED numbers that look like results (what a reviewer would notice)

1. **`en.json` `home.why.too_few_readings`: "a section needs 8 readings in a row, 5 minutes apart"** — typed into the sentence; the backend's rule is `MIN_READINGS` in `core/ml/forecasting/operations/section_forecast.py:11` and `BIN_MIN = 5` in `backend/app/probes/service.py:18`; neither is interpolated, so a change in code would leave the sentence wrong.
2. **`en.json` `focus.sos.sub`: "15-second countdown"** — typed; `COUNTDOWN_S` exists on both sides (`features/emergency/sos.ts:8`, `core/safety/sos.py:23`) and is interpolated elsewhere (`emergency.sos.rule`, step 2) but not here.
3. **`en.json` `mesh.scope`: "one 100-byte message per second"** — typed; the results file carries `scope.messages.size_bytes` and `interval_s` and they are not used.
4. **`en.json` `lab.ev.how1` / `lab.ev.how3` / `lab.ev.how4` and `features/system/SystemPage.tsx:12-13`: "TTI ≥ 1.3", "≤ 1 % lost", "30 % of drivers", "95 % confidence"** — protocol constants restated by hand; the sources are `core/simulation/closed_loop/protocols/controller_config.json` and `results/v2x/closed_loop/<REFERENCE>/PROTOCOL.json → penetration`.
5. **`en.json` `lab.rq2.findSlower` "more than 5 s slower"; `lab.rq2.qlearning` "within 100 m of a traffic light"; `lab.rq2.findRl` "the 3 signals near the route"; `lab.rq2.gap` "07:00-08:00", "about 90 m"; `lab.rq2.makeway` "50 m and 100 m were piloted"** — restate `WORSE_S` (`core/simulation/ambulance/summary.py`), the by-light key string, `signals_on_route`, and the DhaTraX window; values agree today but are not linked to the file.
6. **`en.json` `lab.rq1.labTitle` "seeds 11, 23, 37"; `lab.rq1.whyText` "30 % of free-flow", "5-minute steps"; `lab.rq1.cannot` "207 sensors"; `modelLab.intro` "207 loop detectors, recorded 2012"** — dataset/protocol facts typed in; the RQ1 summary does not carry them.
7. **`features/results/ReachTable.tsx:19` `{tol: 30}`** — the detour tolerance shown in the method sentence is typed on the page, not read from `results/reach/<city>/summary.json`.
8. **`en.json` `liveTwin.notStarted` "15 simulated minutes", `liveTwin.fcHow` / `liveTwin.colours` / `liveTwin.steer.note` "15 minutes", `liveTwin.mae10` "last 10 minutes", `liveTwin.steer.note` "5 seeds"** — the server sends `warmup_min` and `horizon_min`; the sentences type them.
9. **`en.json` `prefetchRes.method` "3 s tail"** and the Bartendr constants in `lib/schedule.ts:10-14` / `core/networking/v2x/energy.py:10-14` (1.5 W, +20 %/+50 %, 3 s tail, 64 KiB chunks) and throughput `PRESET_THR` (`schedule.ts:70`, `results.py:27`) — model inputs from a 2010 paper; every energy figure on Trip and Evidence rests on them (labelled "estimated").
10. **`features/forecast/AddCityCard.tsx:5` `SIZES` → "about 2 / 4 / 7 km"** — `Math.round(0.02*111)` etc.; a UI choice shown as a number.
11. **`features/twin/AmbulancePanel.tsx:5` `SHARES = [0, 25, 50, 100]`** and **`LiveTwinPanel.tsx:16` `duration_s ?? 1800`, `scale: 1.0`** — run settings, not results, but visible as numbers.
12. **`en.json` `emergency.reach.plain` / `reachRes.sub` "10, 20 and 30 minutes"** — the bounds are also in the file (`bounds_min`) and in `core/safety/reach.py:30`; the sentence types them (and `ReachTable.tsx:8` falls back to `[10, 20, 30]`).
13. **`en.json` `probe.consent` "70 m road-direction cells", "every five minutes", "deleted after 24 hours"** — restate `H3_RES`, `BIN_MIN = 5` and `RETAIN_HOURS` in `backend/app/probes/service.py` (lines 18 and ~111); the cell size (70 m) is an approximation of the H3 resolution, not a value the code carries.
14. **`en.json` `settings.lowDataOn` "alerts once a minute"** — restates `AlertsStrip.tsx:19` (`60_000`).
15. **`features/results/AmbulanceRq2.tsx:42-43` `help_pct ?? 10`** and **`ReplayPanel.tsx:32` `duration_s || 2700`** — silent fallbacks that would show a typed number if the file lacked the key.

Everything presented as a **result** on the everyday pages (ambulance seconds, reach percentages, mesh percentage/delay, prefetch seconds, nearest-hospital minutes, route minutes, trip travel times) is READ from a results file or COMPUTED at request time; no measured-looking result value is typed into JSX or the locale files. The typed numbers are rule constants, protocol facts and UI settings restated in prose.

---

### Part B: Audit B: numbers shown in the map app (`/`), read-only, 2026-10-11

Scope: `frontend/map/src/traffictwin/*`, `frontend/map/src/i18n/{en-US,bn}/tt.ts`, the backend endpoints they call, the modules those read.
Classes: COMPUTED = produced at request time; READ = read from a saved results file (path → key); HARDCODED = a literal in source (file:line).

### Directions page (Headway, unchanged) and Start

| Panel | Number as shown | Class | Source | Note |
|---|---|---|---|---|
| Directions (Headway) | route distance, duration, alternatives | COMPUTED | `backend/app/routing/headway_adapter.py:269` `travelmux_proxy` → travelmux → the city's Valhalla | map speeds, not live traffic |
| Start → "Simulated drive, ×{x}" badge | ×8 | HARDCODED | `frontend/map/src/traffictwin/TtTrip.vue:33` (`{ x: 8 }`); the warp itself `frontend/src/maplink/index.ts:34` `SIM_SPEED = 8` | the two literals are not linked: the badge would say 8 even if `SIM_SPEED` changed |
| Start | "no directions server covers this place" | COMPUTED | `headway_adapter.py:84-93` `map_city` → `city_at` (nearest routed city within `CITY_RADIUS_KM`) | `CITY_RADIUS_KM` is a constant in `headway_adapter.py` (not shown) |

### Trip sheet (`TtTrip.vue`)

| Panel | Number as shown | Class | Source | Note |
|---|---|---|---|---|
| ETA clock, "{km} km · {min} min" | distance and time left | COMPUTED | `frontend/src/maplink/index.ts:74,94` from Ferrostar `nav.progress.distanceRemaining/durationRemaining` on the Valhalla route | simulated drive: positions from `SimulatedLocationProvider` at `SIM_SPEED` (`index.ts:50-51`) |
| "Trip saved for weak signal ({mb} MB)" | MB saved | COMPUTED | `tt.ts:72-73` from `saveForWeakSignal` (`frontend/src/lib/weakSignal.ts:9-13`: tile + api + asset bytes actually cached) | zoom set `ZOOMS`/`ZOOMS_LOW_DATA` are constants in `weakSignal.ts` |
| SOS countdown ring and "Sending a TEST alert in {s} s" | 15 | HARDCODED | `frontend/src/features/emergency/sos.ts:8` `COUNTDOWN_S = 15`; ring max `TtTrip.vue:70` (`:max="15"`); initial `tt.ts:24,114` (`left: 15`) | three separate literals of the same 15; backend copy `core/safety/sos.py:27` |
| crash rule behind the countdown | 4 g, 24.1 km/h | HARDCODED | `sos.ts:6-7` `THRESHOLD_G = 4.0`, `MIN_SPEED_KMH = 24.1` (WreckWatch 2011); backend `core/safety/sos.py:25-26` | the speed floor never fires: the phone path carries no speed |
| "Crash sensor on: {g} g" | live g | COMPUTED | `tt.ts:138` `onSample` from `DeviceMotionEvent` via `maplink armCrashDetector` (`index.ts:112`) | real sensor, phone only |
| "TEST: a {g} g jolt…" / `peak_g` posted | jolt g | COMPUTED | `tt.ts:97,113` `s.joltG` → `POST /api/emergency/sos/test` (`backend/app/emergency/router.py:115-118` → `core/safety/sos.py:146 raise_test`) | field named `peak_g` carries the reading that fired the rule (CODE_MAP gap 1) |
| emergency numbers in the SOS dialog | e.g. 999 | READ (config) | `headway_adapter.py:84-93` → `config/cities/<city>.yaml` `emergency_numbers` (dhaka.yaml:15) | shown, never dialled |
| alert strip: "simulated ambulance on the twin: {alerted} vehicles alerted, {junctions} signals…" | alerted, junctions | COMPUTED | `backend/app/alerts/service.py:90-102` from the live twin's state (`live_sim.state()`), sentence `frontend/src/i18n/locales/en.json:300` | only while a twin ambulance is driving |
| alert strip, congestion | "{road}: congestion forecast in about {minutes} min" | READ (db) | `alerts/service.py:133-144` from the alerts DB rows (`RoadAlertRow.horizon_min`, `predicted_speed`), `en.json:250` | the trip sheet filters kinds `ambulance` and `congestion` (`tt.ts:189`) but the feed's kind is `congestion_onset`, so this item never shows on the trip sheet |
| alert strip, mesh | ratio %, delay s, vehicles | READ | `alerts/service.py:105-121` ← `core/networking/mesh/results.read` ← `results/networking/mesh/dhaka/summary.json` → `rows[*].delivery_ratio.mean`, `delay_s.mean`, `scope.vehicles_simulated` | kind `mesh` is filtered out on the trip sheet (`tt.ts:189`), shown on `/app` pages only |

### Hospitals sheet (`TtHospitals.vue`)

| Panel | Number as shown | Class | Source | Note |
|---|---|---|---|---|
| "about {min} min away · {km} km" per hospital | drive time, distance | COMPUTED | `GET /api/emergency/reach/{city}/nearest` (`emergency/router.py:54-57`) → `core/safety/reach.py:193-207 nearest` → `valhalla.matrix` (`core/simulation/routing/valhalla.py:156-178`) | map speeds (`valhalla.py:27`); hospitals from `data/cities/dhaka/hospitals.json` (OSM) |
| pins 1…5 | ordinal | COMPUTED | `TtHospitals.vue:34` index | `k=5` request literal `TtHospitals.vue:174`, `k=3` for live `:138` |
| Live reach: "Computed live by Valhalla in {s} s" | seconds | COMPUTED | `reach.py:235` `computed_s` (perf_counter) | — |
| "Nearest hospital, {name}: … in about {min} min" | minutes | COMPUTED | `reach.py:231-232` `to_point_s` from a second `valhalla.matrix` (hospital → tapped point), rounded `ttReach.ts:26` | — |
| 10 / 20 / 30-minute polygons and legend | 10, 20, 30 | HARDCODED | contours requested by `valhalla.isochrone` (`core/simulation/routing/valhalla.py:141-153`, minutes list there), legend text `i18n/en-US/tt.ts` `reach.legend`, colours `ttReach.ts:10` | the polygons themselves are COMPUTED by Valhalla; the three horizons are fixed |
| "Thesis (saved build): {a} % / {b} % / {c} % … within 10 / 20 / 30 min" | three shares | READ | `reach.py:236` ← `reach.read(city)` ← `results/reach/dhaka/summary.json` → `plain.map_pct["10"|"20"|"30"]` | built by `python -m core.safety.reach build` (`reach.py:11,173`); the recorded variant equals the map variant (feature README) |

### Traffic (forecast layer) sheet (`TtForecast.vue`), Dhaka = `recorded_day`

| Panel | Number as shown | Class | Source | Note |
|---|---|---|---|---|
| "Site {site}: {v} km/h at this hour on {day}" | speed now | READ | `core/ml/forecasting/layer/service.py:88-100` `dhatrax.reading_at(site, hh:mm)` → DhaTraX's recorded day (`core/common/data/recorded/dhatrax.py`) → `median_kmh` | real recorded, one day per site; "recorded 06:00 to 18:00" in `tt.ts` `fc.site_none` is a HARDCODED string matching the dataset |
| "Site {site}: 15 min ahead off by {m15} (no change: {p15}); 60 min…" | MAE values | READ | `service.py:101-107` ← `config/cities/dhaka.yaml:98` `forecast_layer.summary` = `results/forecasting/rq1/summary.json` → `dhaka[<model>]["15"|"60"].per_site[<site>]`, `dhaka.persistence[...]` | best of the three zero-shot models per site (`ZERO_SHOT`, `service.py:25`); 15 and 60 are HARDCODED horizons in the string (`tt.ts` `fc.site_err`, `bn/tt.ts:75` with Bangla digits) |
| "+{min} min" views, "{min} min ahead: off by {m}; no change {p}" (replay cities, e.g. LA) | 15/30/60; MAE | READ | `service.py:60-85` ← `results/forecasting/layer/summary.json` → `card[h].mae`, `no_change_mae` (built by `layer/build_la.py:84-101`), horizons `service.py:22` `HORIZONS` | unit conversion ×1.609 `service.py:23` |
| "Best time to leave: in {min} min" | minutes | COMPUTED from saved | `service.py:47-57 best_time` on the replay's saved forecasts in the map's bbox; `CLEAR_DIFF = 1.0` `service.py:24` | Dhaka: always `best_time: None` (`service.py:114`) → the "no best time" sentence |
| dot colours | — | COMPUTED | `ttPure.ts:speedColour` thresholds 0.4/0.6/0.8 of the fastest dot | HARDCODED ratios, display only |

### Simulation sheet (`TtSimulation.vue`), every run computed now on the server

| Panel | Number as shown | Class | Source | Note |
|---|---|---|---|---|
| form defaults: share 100 %/50 %, seed 11, 17 phones, 10 m, seed 1 | defaults | HARDCODED | `TtSimulation.vue:52-55` `DEFAULTS` | mirror the thesis settings; the user can change them |
| "Thesis setting: ITS-G5, 100 %, seed 11…", "17 phones, 10 m, seeds 1 to 5", "Dhaka density, seed 11" | settings in text | HARDCODED | `i18n/en-US/tt.ts` `sim.thesis.*`, `bn/tt.ts:104` | descriptive, not results |
| level "Dhaka's recorded density" | scale 0.78 | HARDCODED (hidden) | `scripts/live/run_v2x.py:33`, `run_sos_v2v.py` `LEVELS`, `run_signals.py:27` (`"dhaka": ("dhaka_density", 0.78)`) | the 0.78 is never shown; it comes from the calibration (`config/cities/dhaka.yaml:63`) |
| live counts: sent, delivered, lost, out of range, alerted, making way, signals green | counts | COMPUTED | `core/simulation/live_jobs/jobs.py:66-128 v2x` hook from `service.run_one` (SUMO + `core/networking/v2x/model.deliver`) | V2X ranges/loss in `configs/network_model.yaml` (constants) |
| V2X result: "{a} s without, {b} s with ({pct} % sooner)", "alerts sent {s}, delivered {d}; alerted {al}; green {g}" | all | COMPUTED | `jobs.py:120-128` (`saved_pct` from the two runs' `travel_time_s`) | — |
| V2X badge REPRODUCED / DIFFERENT / new | check | READ (comparison) | `jobs.py:120-124` ← `run_v2x.saved` (`scripts/live/run_v2x.py:60-63`) ← `results/emergency/dhaka/rq2/{runs,runs_v2}/dhaka/<demand>/<run>/metrics.json` → `ambulance.travel_time_s`, `messages`, `vehicles_alerted` | only settings the study ran have a saved run |
| SOS counts: warned, rerouted, broadcasts, received, lost | counts | COMPUTED | `jobs.py:132-169 sos` via `run_sos_v2v.simulate` | crash at 600 s, 300 s after (`jobs.py:139`, HARDCODED; the CLI default is 600 s after) |
| SOS result: "Cars warned {w}, rerouted {r}; delivery {d}", "Of {n} cars … within 5 minutes {aw} with, {an} without" | all | COMPUTED | `jobs.py:160-169` (`delivery_in_range` = delivered / (delivered + lost)) | "5 minutes" in the sentence (`tt.ts` `sim.res.sos2`, `bn/tt.ts:118` "৫ মিনিটে") is HARDCODED and matches `after=300.0` (`jobs.py:139`) only by hand |
| SOS badge "REPRODUCED (the SOS rule on the thesis traces); car-to-car numbers are new" | check | READ (comparison) | `jobs.py:169` ← `run_sos_v2v.rule_check` ← `evidence/sos/results.json` → `rows[*].detected/at_s/peak_g` | the traces are SYNTHETIC (`core/safety/sos.py:59-74`) |
| mesh counts: created, copies passed, pairs in range | counts | COMPUTED | `jobs.py:176-205` ← `scripts/live/mesh_frames.py` (PONS, mesh venv) | research machine only (`jobs.py:178`) |
| mesh result: "Delivered {pct} % within 5 minutes; delay {d} s; {c} copies" | ratio, delay, copies | COMPUTED | `mesh_frames.py:62-64` summary over the study seeds | "within 5 minutes" is the TTL 300 s HARDCODED in the sentence (`tt.ts` `sim.res.mesh`) |
| mesh badge | check | READ (comparison) | `mesh_frames.py:66-71` ← `results/networking/mesh/dhaka/summary.json` → `rows[router].delivery_ratio.mean` | "new" when phones ≠ 17 or range ≠ 10 m |
| signals: "halting, fixed-time / Q-learning" live | counts | COMPUTED | `jobs.py:210-240` ← two `run_signals.py` processes (`display` hook, `run_signals.py:48-60`) | Q-learning in the sumo-rl venv |
| signals result: "{fa} s fixed, {ra} s Q-learning; queue {fq} vs {rq}; {fh} vs {rh} hours" | all | COMPUTED | `jobs.py:244-258` from `evidence/live_runs/signals/last_{fixed,rl}.json` written by that run | — |
| signals badge | check | READ (comparison) | `jobs.py:251-257` ← `run_signals.saved` (`run_signals.py:43-46`) ← `results/emergency/dhaka/rq2/runs/dhaka/<demand>/{no_alert,rl_signals}_s<seed>[_x0.78]/metrics.json` → `KEYS` (`run_signals.py:29`) | — |

### Place card actions (`TtPlaceActions.vue`), menu (`TtMenu.vue`)

No result numbers; only categories, links and geolocation timeouts (`TtPlaceActions.vue:54`, not counted).

### HARDCODED numbers that look like results (a reviewer would ask)

1. **"×8" simulated drive** — `TtTrip.vue:33` literal `8`, separately from `SIM_SPEED = 8` in `frontend/src/maplink/index.ts:34`; a setting, but typed twice.
2. **"within 5 minutes" (crash SOS result sentence)** — `i18n/en-US/tt.ts` `sim.res.sos2` and `bn/tt.ts:118`; the horizon is `after=300.0` in `core/simulation/live_jobs/jobs.py:139`, not passed to the sentence.
3. **"within 5 minutes" (mesh result sentence)** — `tt.ts` `sim.res.mesh`; the TTL of 300 s lives in the mesh study's settings, not in the job's result.
4. **"15 min ahead … 60 min ahead" (Dhaka forecast card)** — `tt.ts` `fc.site_err` / `bn/tt.ts:75`; the horizons are keys `"15"`/`"60"` of `results/forecasting/rq1/summary.json`, chosen in the template, not read.
5. **"recorded 06:00 to 18:00"** — `tt.ts` `fc.site_none`; true of DhaTraX but typed, not read from the dataset metadata.
6. **10 / 20 / 30 minutes (reach legend, thesis sentence)** — fixed horizons in `valhalla.isochrone` and the i18n strings; the shares and polygons behind them are READ / COMPUTED.
7. **15 s countdown, 4 g, 24.1 km/h** — rule constants (WreckWatch 2011) typed in `frontend/src/features/emergency/sos.ts:6-8` and again in `core/safety/sos.py:25-27`, plus `:max="15"` in `TtTrip.vue:70` and `left: 15` in `tt.ts:24,114`.
8. **Thesis settings in `sim.thesis.*` strings** ("ITS-G5, 100 %, seed 11", "17 phones, 10 m, seeds 1 to 5") — descriptive text typed in i18n, not read from the results files they describe.
9. **Form defaults** `TtSimulation.vue:52-55` (share 1 / 0.5, seed 11, 17 phones, 10 m, seed 1) — settings, typed to match the thesis.
10. **Scale 0.78 ("Dhaka's recorded density")** — `run_v2x.py:33`, `run_sos_v2v.py` `LEVELS`, `run_signals.py:27`: typed in three scripts; the calibration source is `config/cities/dhaka.yaml:63` / `evidence/cities/dhaka/calibration.json`.

Out of scope but seen: the trip sheet's alert filter (`tt.ts:189`) keeps kinds `ambulance` and `congestion`, while the feed emits `congestion_onset`, so recorded-data congestion alerts never appear on the trip sheet (a wiring gap, not a number).

---

### Part C: Audit C — live runs (what the terminal prints) and the synthetic / assumed inputs (read-only, 2026-10-11)

Classes: **COMPUTED** = produced by a run at that moment; **READ** = read from a saved file (path + key); **HARDCODED** = a literal in the
source (file:line). "Protocol" = a setting copied from the thesis run so the live run can be checked against it; "choice" = a value
chosen by us with the reason given in the file; "arbitrary" = no reason recorded.

### Part 1 — numbers printed to the supervisor

### `scripts/live/present.py` (make present)
| Number printed | Class | Source | Note |
|---|---|---|---|
| slot seconds per step (80/70/110/20/25/95/25) | HARDCODED | `present.py:30-36` STEPS | planning estimates only |
| `--speed 10/14/40`, `--after 300`, `--sensor 5`, `--protocol epidemic` | HARDCODED | `present.py:30-36` | display pace / demo choices; `--after 300` shortens the SOS run (the saved live run used 600) |
| exit code, seconds per step, total minutes, "N of 7" | COMPUTED | `present.py:70-83` | wall clock |
| every other number | see the step's script below | | |

### `scripts/live/demo.py` (make demo)
| Number printed | Class | Source | Note |
|---|---|---|---|
| "seed 11, 292 s -> 284 s" in the watch text of part 1 | READ (was HARDCODED at `demo.py:34`; fixed 2026-10-11 17:50 on the owner's order) | `demo.py:v2x_saved_text` → `run_v2x.saved` → `results/emergency/dhaka/rq2/runs/dhaka/dhaka_density/no_alert_s11_x0.78/metrics.json` and `runs_v2/.../alert_preemption_its_g5_p100_s11_x0.78/metrics.json`, key `ambulance.travel_time_s` | test `test_make_demo_watch_text_reads_the_v2x_numbers_from_the_saved_rq2_metrics` checks the text against the files and that no travel time is typed in demo.py |
| `--speed 8/14`, `--after 300` | HARDCODED | `demo.py:33-43` | display pace |

### `scripts/live/run_v2x.py` (make run-v2x; also the web V2X job via `core/simulation/live_jobs/jobs.py:72-120`)
| Number printed | Class | Source | Note |
|---|---|---|---|
| level `dhaka` = demand `dhaka_density`, scale 0.78; x0.5…x4 = `generated` scale 0.5…4 | HARDCODED | `run_v2x.py:33` LEVELS | 0.78 is protocol: chosen by `core/simulation/ambulance/corridor.py:58-67 match()` and recorded in `evidence/ambulance_rq2/dhaka_density/match.json` key `chosen_scale` (0.78, density 54.37); the x-levels are what-if choices |
| seed 11, share 1.0, tech its_g5, arm | HARDCODED defaults | `run_v2x.py:160-165` | protocol (the study's seeds 11-15, `core/simulation/ambulance/configs/ambulance.yaml:23`) |
| range 425 / 625 m, delivery 0.90 / 0.96 | READ | `core/networking/v2x/configs/network_model.yaml` → `technologies.<tech>.range_m.value`, `.delivery_ratio_in_range.value` (5GAA P-190033; Xu 2017) | not Dhaka measurements (file header) |
| "ambulance travel time, no alert: t0 s", "with alert t1 s", "% sooner/later" | COMPUTED | `service.run_one` (`core/simulation/ambulance/service.py:297-350`), `run_v2x.py:184-208` | |
| messages sent / delivered / lost / out of range, delivery ratio, cars alerted, junctions green | COMPUTED | `core/networking/v2x/model.py:deliver` (75-86), `service.py:133-213`; printed `run_v2x.py:209-212` | |
| THESIS CHECK "no alert 292 s, alert_preemption 284 s, messages {…}, cars alerted 30" | READ | `results/emergency/dhaka/rq2/runs/dhaka/dhaka_density/no_alert_s11_x0.78/metrics.json` → `ambulance.travel_time_s`; `runs_v2/dhaka/dhaka_density/alert_preemption_its_g5_p100_s11_x0.78/metrics.json` → `ambulance.travel_time_s`, `messages`, `vehicles_alerted` (`run_v2x.py:60-62`, 213-222) | REPRODUCED / DIFFERENT is COMPUTED (equality) |
| live counter in sumo-gui (alerted, delay, delivered of sent) | COMPUTED | `run_v2x.py:117,134` | |
| `ahead_m` 1000, make-way 100 m, depart 900 s, horizon 3600 | HARDCODED | `core/simulation/ambulance/configs/ambulance.yaml:14-22` | choice: 100 m by a rule fixed before the pilot (`evidence/ambulance_rq2/makeway_v2/choice.json` `chosen_distance_m`); 1000 m "the alert's reach", no citation |

### `scripts/live/run_sos_v2v.py` (make run-sos-v2v, make run-sos-collide)
| Number printed | Class | Source | Note |
|---|---|---|---|
| rule check "peak x.xx g, alarm yes at s" per trace | COMPUTED | `core/safety/sos.py:detect` (43-56) on `sos.trace()` (the saved synthetic traces) | |
| rule check "(thesis: …)" | READ | `evidence/sos/results.json` → `rows[kind].detected / at_s / peak_g` (`run_sos_v2v.py:46-55`) | |
| 4 g, 24.1 km/h, 15 s countdown | HARDCODED | `core/safety/sos.py:25-27` | WreckWatch 2011 (cited at :28) |
| share 0.5, seed 11, crash at 600 s, after 600 s, speed 8 | HARDCODED defaults | `run_sos_v2v.py:218-223` | arbitrary (no thesis SOS run exists; the README says so) |
| crash edge = the middle route edge | HARDCODED rule | `run_sos_v2v.py:93` | arbitrary |
| REACH_M 1000 (receivers considered) | HARDCODED | `run_sos_v2v.py:39` | choice: beyond every radio range |
| warned, half warned by s, rerouted, no other road, broadcasts, in range, received, lost, delivery ratio, affected, arrived with/without, mean s to arrive with/without, teleports | COMPUTED | `run_sos_v2v.py:simulate` (76-199), printed 245-252 | |
| "the model's delivery ratio is 0.9" | READ | `network_model.yaml` → `technologies.its_g5.delivery_ratio_in_range.value` | |
| SUMO's collision record (collider, victim, lane, pos, time) | COMPUTED | SUMO `--collision-output` (`run_sos_v2v.py:86,194-196`) | |
| collision.stoptime = after − 10, rammer speed 20 m/s, leader within 150 m | HARDCODED | `run_sos_v2v.py:86,110-113` | arbitrary |

### `scripts/live/run_signals.py` (make run-signals) and `core/simulation/ambulance/mp_signals.py`
| Number printed | Class | Source | Note |
|---|---|---|---|
| level/scale, seed 11, speed 8 | HARDCODED defaults | `run_signals.py:122-126`; LEVELS imported from run_v2x | protocol (seed 11 is a study seed) |
| table: ambulance travel time, arrived, queue at signals, vehicle-hours, mean time loss (others), EV requests, for fixed-time and the right window | COMPUTED | fixed: `service.run_one(..., observe=True)` (`run_signals.py:105`); rl: `rl_signals.run` (`core/simulation/ambulance/rl_signals.py:127-180`) in the sumo-rl venv; MP: `mp_signals.run` (`mp_signals.py`); `measures()` `run_signals.py:36-41` | |
| THESIS CHECK (fixed) "[292.0, 4.0, 49, 532.33]", (Q-learning) "[188.0, 0.0, 2, 793.946]" | READ | `results/emergency/dhaka/rq2/runs/dhaka/dhaka_density/no_alert_s11_x0.78/metrics.json` and `rl_signals_s11_x0.78/metrics.json` → keys of `measures()` (`run_signals.py:43-46`) | |
| Q-learning alpha 0.1, gamma 0.99, epsilon 0.05→0.005, delta_time 5, 30 episodes | HARDCODED | `rl_signals.py:90-124` | sumo-rl's example settings (said in the docstring) |
| MIN_GREEN 10 s, MAX_GREEN 60 s (Max-Pressure) | HARDCODED | `core/simulation/signals/signal_baselines.py:21-22` | choice, no citation; the preemption profile uses 10/45 s (`core/common/interfaces/safety.py:66-71`, a synthetic Lab 01 junction) |
| EV priority within `ahead_m` 1000 | READ | `ambulance.yaml` → `alert.ahead_m` (`mp_signals.py:77`) | |
| `--scale 0.78`, `--demand dhaka_density` | HARDCODED defaults | `mp_signals.py:126-129` | protocol |

### `scripts/live/compare_signals.py` (make compare-signals)
| Number printed | Class | Source | Note |
|---|---|---|---|
| seeds 11-15, workers 3 | HARDCODED defaults | `compare_signals.py:60-62` | protocol seeds |
| per-arm means (ambulance s, others' time loss, vehicle-hours, queue), arrived of runs, paired differences vs fixed, "N of M REPRODUCED", real seconds, sha256 | COMPUTED | `compare_signals.py:67-112` (fixed/MP in-process, rl via the sumo-rl venv) | |
| the saved side of each check | READ | `rs.saved()` → the metrics.json files above, per seed (`compare_signals.py:76`) | |

### `core/ml/forecasting/layer/lab.py` (make run-forecast; the Model Lab page)
| Number printed | Class | Source | Note |
|---|---|---|---|
| sensor 0 (present passes 5), model D2STGNN, `--at` default = first moment of RQ1's seed-11 test windows | HARDCODED defaults | `lab.py:104-106` | choice |
| recorded values per 5 min, the model's forecast, "no change" | recorded: READ `results/forecasting/layer/metr_la_replay.npz` (`lab.py:47`); forecast: COMPUTED by the model (`lab.py` `forecast()`), no change: COMPUTED | | METR-LA is RECORDED Los Angeles data |
| error at 15/30/60 min (model, no change) | COMPUTED | `lab.py:54-…` | "one window, not the thesis average" is printed |
| THESIS CHECK "largest difference 0.00e+00 mph" | READ + COMPUTED | saved prediction READ from `results/forecasting/protocol_b/METR-LA_test_w120_n207_s11.npz` (`lab.py:27,91`), difference computed | |

### `scripts/live/run_mesh.py` (make run-mesh) and `scripts/live/run_mesh_one.py` (make gui-mesh)
| Number printed | Class | Source | Note |
|---|---|---|---|
| 17 phones, radio 10 m, seed 1, speed 30, protocol | HARDCODED defaults | `run_mesh.py:127-131` | protocol: 10 m = The ONE's default Bluetooth range (`research/mesh_pons/configs/dhaka.yaml:7-10`, source quoted); 17 = vehicles present the whole window |
| message interval 1 s, size 100 B, TTL 300 s, seeds 1-5, window 900-1200 s | READ | `research/mesh_pons/configs/dhaka.yaml` → `messages.*`, `seeds`, `window.*` (`run_mesh.py:137`) | choices "fixed before any result was seen" |
| alerts created / delivered / relayed, latency, delivery probability, hops, pairs in range, per seed | COMPUTED | PONS `NetSim.run` (`run_mesh.py:41-64`) | |
| THESIS CHECK "delivery 0.028 -> REPRODUCED seed by seed" | READ | `results/networking/mesh/dhaka/summary.json` (per-router, per-seed delivery) | |
| The ONE: bufferSize 5M, msgTtl, Events1 interval/size, transmitRange | HARDCODED/READ | `run_mesh_one.py:62-83` (5M arbitrary; the rest READ from the mesh config) | |
| The ONE's delivery/latency (gui-mesh, sweep-mesh) | COMPUTED | The ONE batch run, MessageStatsReport | "a second view, not the thesis's" is printed |

### `scripts/live/sweep_mesh.py` (make sweep-mesh)
| Number printed | Class | Source | Note |
|---|---|---|---|
| phones 17/50/100/200, seeds 1-3, ranges 10/30/50/100 m, PARK_GAP 50 m, 300 messages, window 900-1200 | HARDCODED | `sweep_mesh.py:39-41,167` and the main() defaults | choices stated in the docstring (ranked by presence; parked out of range) |
| delivery ratio, latency, hops per router/count/range; `delivery_rises_with_range` | COMPUTED | The ONE 1.6.0 batch, parsed MessageStatsReport | |

### `frontend/tests/live/run_offline.cjs` (make run-offline)
| Number printed | Class | Source | Note |
|---|---|---|---|
| 4G 4000/3000 kbit/s 20 ms; 3G 400/400 400 ms; 2G 50/20 1000 ms | HARDCODED | `run_offline.cjs:20-21` | protocol: the RQ5 experiment's Chrome DevTools presets |
| 60 s wait for the "MB" chip, "the 6 MB pack" | HARDCODED | `run_offline.cjs:64` | comment only |
| answers served by the service worker after the cut (37 of 47), pack MB, time to route | COMPUTED | Playwright run | |
| THESIS CHECK against the 2G-like with-prefetch row | READ | `evidence/prefetch/summary.json` → `rows[condition=2g_like, arm=with_prefetch].median_time_to_route_s` (`run_offline.cjs:95`) | |

### `frontend/tests/live/sos_graph.cjs` (present step 7)
| Number printed | Class | Source | Note |
|---|---|---|---|
| graph values, countdown started yes/no | COMPUTED | the app's own rule on the replayed trace (`useMotion.ts`, `sos.ts`) | the trace itself is SYNTHETIC (Part 2) |
| "(thesis: yes at s, g when fired, peak g)" | READ | `evidence/sos/results.json` → `rows[kind=crash_jolt].detected/at_s/at_g/peak_g` (`sos_graph.cjs:10,28`) | |
| since R1 (2026-10-11 evening), present step 7 `--trace=sumo_collision`: the expected outcome | READ | `evidence/live_runs/sos_v2v/collision_trace.json` → `detection.detected/at_s/at_g/peak_g`, `collision.*` (`sos_graph.cjs`) | the trace is built by step 2 from SUMO's `collisions.xml` speeds (Part 2) |

### `scripts/live/run_veins.py` (make gui-veins; `--veins` in run_v2x / run_sos_v2v)
| Number printed | Class | Source | Note |
|---|---|---|---|
| share 1.0, txPower 20 mW, seed 0, window 300 s, crash node 10, crash at 60 s, ambulance at 20 s, make-way 100 m | HARDCODED defaults | `run_veins.py:148-155` | 20 mW = Veins's example (`research/veins_dhaka/omnetpp.ini:76`); 100 m = the thesis's make-way distance; the rest arbitrary |
| Veins ini: bitrate 6 Mbps, maxInterfDist 2600 m, beacon 1 s, obstacle shadowing on, penetrationRate 1 | HARDCODED | `research/veins_dhaka/omnetpp.ini:35,44,71,76-77,98,108-109` | Veins's example values, read not edited |
| cars, WSMs generated/received, alerts sent/received, cars that made way, ambulance time | COMPUTED | OMNeT++ scalar output parsed `run_veins.py:198-205` | printed as "Veins's numbers", not the thesis's |

### `scripts/live/run_routing_quick.py` (make run-routing-quick)
| Number printed | Class | Source | Note |
|---|---|---|---|
| SETTINGS: la_c4_central_wide, ideal, penetration 0.3, prepeak, round 300 s, horizon 15 min, status 10 s, 4800 s, fork 1200 s, demand x8 peak arterial | HARDCODED | `run_routing_quick.py:26-27` | protocol: copied from the saved run's PROTOCOL (`results/v2x/closed_loop/la_c4_…_x8_peak_arterial/report.json`); x8 is the thesis's what-if stress level (`closed_loop.py:124-128` PROFILES_DEMAND "peak") |
| seeds 201, 202 | HARDCODED defaults | `run_routing_quick.py:47` | protocol seeds |
| vehicle-hours, arrivals, teleports, wall s per seed/arm | COMPUTED | `closed_loop.run_point(reuse=False)` | |
| the saved side of each check | READ | the report.json above → `per_seed[].arms[arm].metrics.total_vehicle_hours_incl_never_inserted / arrived / teleports` (`run_routing_quick.py:31-42`) | |

### `scripts/live/sweep_v2x.py` (make sweep-v2x)
| Number printed | Class | Source | Note |
|---|---|---|---|
| shares 0/25/50/75/100 %, seeds 11-15, arm alert_preemption, its_g5, workers 4 | HARDCODED | `sweep_v2x.py:28,51-55` | protocol shares (`ambulance.yaml:22` has 0/0.25/0.5/1.0; 0.75 is new) |
| travel time per run, saving vs no alert, medians, no-arrival counts, messages | COMPUTED | `service.run_one` per cell (`sweep_v2x.py:32-46`) | |
| the saved side ("REPRODUCED exactly" / "saved …") | READ | `rv.saved()` → `results/emergency/dhaka/rq2/runs*/…/metrics.json` → `ambulance.travel_time_s`, `ambulance.arrived` | |

### `scripts/live/sweep_sos.py` (make sweep-sos)
| Number printed | Class | Source | Note |
|---|---|---|---|
| shares 25/50/75/100 %, crash at 600/900 s, AFTER 600 s, seeds 11-15 | HARDCODED | `sweep_sos.py:28-30` and main() defaults | arbitrary (no thesis SOS protocol) |
| per cell: warned, rerouted, arrivals, means, censored means, delivery | COMPUTED | `run_sos_v2v.simulate` per cell | |
| CHECK "REPRODUCED the saved live run (seed 11, 50 %, 600 s)" | READ | `evidence/live_runs/sos_v2v/last_run.json` → `with_warning.*`, `without_warning.*` (`sweep_sos.py:saved_check`) | a saved LIVE run, not a thesis number (printed) |

### `scripts/aid/aid.py` (make aid-train / aid-eval / aid-gui / aid-frontier)
| Number printed | Class | Source | Note |
|---|---|---|---|
| train seeds 1-5, test seeds 11-15, 4 incidents per seed, horizon 3600 s, warm-up 600 s, stations every 300 m, period 30 s, alarm gap 300 s, 15 thresholds, Cal#7 grid 8x7x6, `--low-scale 0.3` | HARDCODED | `aid.py:33-34,377-378`; `core/simulation/aid/run.py:25-26`; `stations.py:10-11`; `aid.py` frontier parser | choices of ours (the AID design is "our own", README) |
| incident times/places/durations | COMPUTED from the seed | `run.py:36-46 plan_incidents` (rng `aid-incidents-{seed}`, 400-700 s apart, 180-300 s long) | SYNTHETIC incidents (Part 2) |
| detection rate, time to detect, false alarms per pair-hour, loop/camera rows | COMPUTED | `aid.py` `metrics`, `metrics_any`, `pooled` | |
| the saved side of aid-eval checks (model threshold 0.9, Cal#7 T1/T2/T3, test CSV sha) | READ | `results/aid/train_summary.json` → `model.threshold`, `cal7_thresholds`; `evidence/aid/summary.json`; `data/aid/test.csv` sha | |
| gui tentative band thr/2 ≤ p < thr | HARDCODED | `aid.py` gui | display choice |

### `scripts/aid/incidentnet_xgb.py` (make aid-incidentnet)
| Number printed | Class | Source | Note |
|---|---|---|---|
| their df[299:] drop, 80/20 split, prediction_rate 1, 1 000-row look-back, threshold 0.5 | HARDCODED | their files `third_party/incidentnet/models/xgboost/...` (unchanged); prediction_rate 1 chosen in `incidentnet_xgb.py:our_way` | theirs; the 1 is our adaptation to 30 s rows (printed caveat) |
| their-way accuracy/precision/recall/f1 x5, our-protocol DR/FA/TTD per threshold, their-protocol detection %/FA %/TTD | COMPUTED | `incidentnet_xgb.py` | not a reproduction (printed) |
| paper 98 % / 6.26 % / 197 s | HARDCODED | `incidentnet_xgb.py:PAPER` | printed as "context only, not comparable" |
| J2 camera model best point | READ | `evidence/aid/frontier/frontier.json` → `densities.dhaka.camera_model[]` | |

### `core/networking/prefetch/masts.py` (make prefetch-masts)
| Number printed | Class | Source | Note |
|---|---|---|---|
| 1.8 GHz, EIRP 56 dBm, hUT 1.5 m, hBS 25 m, 10 m-5 km, bins −70/−90 dBm | HARDCODED | `masts.py:36-41` | ASSUMED (said in LABEL); −70/−90 = Bartendr's anchors already in `core/simulation/routing/signal.py` MAPPING |
| radio sites 8 of 40, nearest-site distances, step bins, metres per bin | COMPUTED | `masts.py:radio_sites, step_bins` on `data/cities/dhaka/masts.json` + `evidence/routing/live_routes.json` | the masts file is READ (OSM, Overpass, query recorded) |
| energy now / as needed / Bartendr J, bursts, saving % | COMPUTED | `masts.py:energy_on` with `energy.py` constants and `results.THR` | |
| pack bytes 10 201 674 | READ | `results/networking/prefetch/summary.json` → `pack_bytes_median` | |
| "saved synthetic rows 62.0-131.6 J, 35.1 J" | READ | same file → `energy.rows[].as_needed_j / bartendr_j` | |

### Part 2 — synthetic or assumed inputs that feed a shown result

| Input | Where (file:line) | How generated / paper or method | Which shown result it feeds |
|---|---|---|---|
| Three accelerometer traces (normal ride, hard brake 1.8 g, crash jolt 6.5 g; 50 Hz, 30 s, seed 7, noise sd 0.15 g) | `core/safety/sos.py:33,59-74` | ours: gravity + Gaussian noise, a half-sine pulse, a 120 ms spike; built on either side of WreckWatch's 4 g (circular, README) | RQ6 crash table (`evidence/sos/results.json`), the rule check in run-sos-v2v; the SOS graph (present step 7) replayed `crash_jolt` until R1 |
| R1 (2026-10-11 evening): the `sumo_collision` trace: closing speed from SUMO's `collisions.xml` (`colliderSpeed`, `victimSpeed`) as a 120 ms half-sine (ASSUMED length), noise sd 0.15 g, the crashed car's speed on every sample | `core/safety/sos.py:from_collision`; written by `scripts/live/run_sos_v2v.py --collide` | SUMO's own record (not ours) for the speeds; the pulse shape and length ours | Emergency chip "collision from the simulation", Research RQ6 line, present step 7 |
| WreckWatch rule constants 4 g, 24.1 km/h, 15 s | `core/safety/sos.py:25-27` | White et al. 2011 (cited :28) | every crash-detection result, the app's countdown |
| Weak-signal profiles (weak runs 3-10 steps until 10/30/50 % weak, one 2-step tunnel, seeds 1-3) | `core/networking/prefetch/results.py:35-48` | ours, random by seed; labelled SYNTHETIC in the summary | RQ5 energy rows (`results/networking/prefetch/summary.json` `energy.rows`) |
| Radio power 1.5 W, +20 % at medium, +50 % weak, tail 3 s = 4.5 J, chunk 64 KiB | `core/networking/v2x/energy.py:9-14` | Bartendr (Schulman et al., MobiCom 2010) Palm Pre measurements, "estimated, not measured on our phones" (LABEL) | RQ5 energy rows; Q3 masts energy |
| Throughput per bin 500 / 250 / 125 kB/s | `core/networking/prefetch/results.py:27` | strong = the fast-4G preset; ratios 1/2 and 1/4 from Bartendr's measured throughput | RQ5 and Q3 energy |
| Emulated networks 4G/3G/2G presets (kbit/s, ms) | `frontend/tests/live/run_offline.cjs:20-21`, `frontend/tests/weak_signal.experiment.cjs` | Chrome DevTools presets, "2G-like" | RQ5 time-to-route table, run-offline |
| Mast model: 1.8 GHz, EIRP 56 dBm, hBS 25 m, hUT 1.5 m | `core/networking/prefetch/masts.py:36-38` | ASSUMED typical macro-cell values; path loss 3GPP TR 38.901 Table 7.4.1-1 | Q3 profile and energy (`evidence/prefetch/masts/summary.json`) |
| Radio sites = OSM mast/tower with communication tags (8 of 40) | `core/networking/prefetch/masts.py:radio_sites`; `data/cities/dhaka/masts.json` `selection_rule` | OSM via Overpass (query, OSM base recorded); OSM lists a tiny fraction of real sites | Q3 |
| V2X ranges 425 / 625 m, delivery 0.90 / 0.96, delays 16.2 / 14 / 37.5 ms, 1 s interval, 600 s lifetime | `core/networking/v2x/configs/network_model.yaml` (each key has `source` and `quote`) | 5GAA P-190033 (proving ground, 2018), Xu et al. 2017 (Xi'an test track), tinyLTE 2018, ETSI EN 302 637-2/-3; "none of these measured Dhaka" | every RQ3 message/delivery number, crash SOS delivery, AID closed-loop warnings |
| Make-way distance 100 m, `ahead_m` 1000 m, ambulance depart 900 s, horizon 3600 s, lateral resolution 0.8 m, teleport 300 s, speedFactor 1.5 bluelight | `core/simulation/ambulance/configs/ambulance.yaml:5-20` | choices: 100 m by a pre-fixed rule (`evidence/ambulance_rq2/makeway_v2/choice.json`, "no published distance found"); 1000 m uncited; SUMO docs for the vtype and sublane | RQ3 ambulance times |
| Preemption safety profile min 10 s / max 45 s / yellow 3 s | `core/common/interfaces/safety.py:66-74`, `ambulance.yaml:25` | "Lab 01 synthetic unit junction … synthetic scenario values, no Dhaka regulation" | RQ3 alert_preemption arm |
| Max-Pressure MIN_GREEN 10 s, MAX_GREEN 60 s | `core/simulation/signals/signal_baselines.py:21-22` | choice, no citation (Varaiya 2013 gives none) | compare-signals, run-signals --controller maxpressure |
| Q-learning alpha 0.1, gamma 0.99, epsilon 0.05→0.005, delta 5 s, 30 episodes, training seeds ≠ evaluation seeds | `core/simulation/ambulance/rl_signals.py:90-124` | sumo-rl's example settings | RQ3 Q-learning side (188 s vs 292 s) |
| "Dhaka density" demand: DhaTraX counts at INT and BM 07:00-08:00 sampled onto a 300 m corridor, scaled to 0.78 | `core/simulation/ambulance/corridor.py:28-33,58-67`; `evidence/ambulance_rq2/dhaka_density/match.json` `chosen_scale` | DhaTraX v1.0 (Roy 2026, CC BY 4.0) counts at two sites on different days; randomTrips pool + routeSampler; the scale picked so the INT median density sits inside the recorded IQR; everything off the two sections is generated | every RQ2b/RQ3 run, crash SOS, AID, live twin, signals, Veins corridor |
| Vehicle mix shares (Car 33.15 %, motorcycle 29.88 %, CNG 22.46 %, …) driven as the nearest SUMO class with SUMO defaults | `config/cities/dhaka.yaml:47-62` | DhaTraX class composition (3 sites, 69 083 crossings); "no Dhaka-specific size, speed or lane behaviour is modelled" | the same runs |
| Older twin vehicle parameters (length/accel/decel/sigma per class), sublane model | `core/simulation/twin/configs/dhaka_r1.yaml:13-21` | ASSUMED (marked) | the frozen dhaka_r1 twin runs (3D City), the mesh movement |
| Dhaka-wide generated demand: randomTrips seed 11, period 2 s, horizon 1800 s, fringe factor 5 | `config/cities/dhaka.yaml:43-46`; `research/mesh_pons/scripts/02_export_movement.py:57-61` | SUMO randomTrips, "uncalibrated, never a measurement" | RQ4 mesh movement (17 phones), x0.5…x4 "generated" levels of run-v2x / live jobs |
| Old twin demand_scale 0.584 | `config/cities/dhaka.yaml:38-42` | fitted 2026-08-26 to Google Routes ratios, calibration withdrawn; kept only for reproducibility | nothing new; older frozen runs |
| Corridor calibration window 07:00, 300 s intervals, seed 11, pool period 0.25 s, fringe 5 | `config/cities/dhaka.yaml:63-70`; `evidence/cities/dhaka/calibration.json` | our chain on DhaTraX counts; "four-point calibration, not validated by the authors" | demand = calibrated (RQ2b) |
| AID incidents: 4 per run, after 600 s warm-up, 400-700 s apart, 180-300 s long, random pair; a vehicle stopped in lane | `core/simulation/aid/run.py:36-46,157-170` | ours (seeded random) | AID DR/FA/TTD, frontier, camera results |
| AID low-density level x0.3 | `scripts/aid/aid.py` frontier `--low-scale 0.3` | arbitrary | frontier "low" panel |
| Mesh: 17 phones, 10 m radio, 1 msg/s of 100 B, TTL 300 s, window 900-1200 s, seeds 1-5, SprayAndWait copies 7 | `research/mesh_pons/configs/dhaka.yaml:4-15` | The ONE default_settings.txt line 19-23 (10 m Bluetooth, quoted); PONS defaults; choices fixed before results | RQ4 delivery 0.028 |
| Mesh sweeps: phones 50/100/200 parked 50 m apart out of range when absent; ranges 30/50/100 m; 300 messages; bufferSize 5M | `scripts/live/sweep_mesh.py:39-41,167`; `scripts/live/run_mesh_one.py:72` | ours (stated in docstrings; 5M arbitrary) | sweep-mesh, range sweep (The ONE's numbers) |
| Veins: txPower 20 mW, 6 Mbps, maxInterfDist 2600 m, SimpleObstacleShadowing, beacon 1 s, penetrationRate 1, crash node 10 at 60 s | `research/veins_dhaka/omnetpp.ini:35,44,71,76-77,98,108-109`; `scripts/live/run_veins.py:148-155` | Veins 5.3.1 example values; crash node/time arbitrary | gui-veins "second view" numbers |
| Emergency trip origin (Airport Road, OSM way 13848342) and destination (Dhaka Medical College Hospital, OSM way 1049690948) | `config/cities/dhaka.yaml:71-73` | chosen by us so the trip crosses the counted section (sources recorded) | every ambulance result |
| Closed-loop stress demand x8 "peak" shape (0.5/0.8/1.0 by time), OD rule "arterial", fork at 1200 s, penetration 0.3 | `core/simulation/closed_loop/control/closed_loop.py:124-132`; `scripts/live/run_routing_quick.py:26-27` | SYNTHETIC what-if randomTrips on the real LA OSM network (labelled in the report) | RQ2 closed-loop vehicle-hours (3750.9 / 3770.7) |
| Live twin: seed from the clock, 15 min warm-up, base scale from the city config, slider 0.5-2x, 8 sim s per s | `core/simulation/live_twin/session.py:34,62`, `demand.py` | ours (display and protocol choices) | live-twin page counters, steer_compare (`evidence/live_twin/steer_compare.json`) |
| Live jobs levels x0.5…x4 on generated demand | `core/simulation/live_jobs/jobs.py:21`, `scripts/live/run_v2x.py:33` | what-if multipliers on randomTrips demand | map app Simulation panel levels |
| Hospitals = OSM `emergency=yes` (37 of 477), 500 m grid, 10/20/30 min bounds, pass tolerance 30 s, at most 60 hospitals | `core/safety/reach.py:28-31,61-70` | OSM tags (completeness unchecked, README); grid and bounds ours | hospital reach shares (`results/reach/dhaka/summary.json`), map "live reach" |
| Reach "recorded" variant: two DhaTraX site deltas 8.0 s and 13.1 s | `core/safety/reach.py:139-146` (computed from DhaTraX speeds) | DhaTraX recorded speeds at two sites at 08:30 | the recorded reach column (equals the map column, README) |
| RQ1 Dhaka rows: 3 DhaTraX site-days, 5-min median speed, zero-shot only, no historical average | `core/ml/forecasting/transfer_dhaka/dhaka.py:1-5` | DhaTraX recorded video → the authors' detection model → speeds; models unchanged | forecasting Dhaka rows |
| Weak-signal step 100 m, bins strong/medium/weak at ≥2 / ≥0.5 Mbit/s or 4g/3g/2g, density ≤ 2 = open country, 3 readings minimum | `core/simulation/routing/signal.py:27-33` | Bartendr's 100 m step; the downlink mapping is ours (MAPPING says so) | the trip's signal strip, refresh points |
| Camera sensor: one per signalised junction, stopped < 0.1 m/s, 30 s windows | `core/simulation/aid/cameras.py:17`, `stations.py:10` | IncidentNet's sensing design re-implemented | J2 camera results |
| California #7 thresholds (grid search on training seeds, not the paper's freeway values) | `scripts/aid/aid.py:378` CAL7_GRID; `results/aid/train_summary.json` `cal7_thresholds` | Payne & Tignor 1978 algorithm, thresholds ours | AID baseline |
| IncidentNet paper numbers 98 % / 6.26 % / 197 s | `scripts/aid/incidentnet_xgb.py:PAPER` | arXiv 2408.00996, typed in as context | printed "not comparable" only |
| demo.py watch text "292 s -> 284 s" | `scripts/live/demo.py:v2x_saved_text` | fixed 2026-10-11 17:50: READ from the saved RQ2 metrics (see Part A, demo.py) | no longer typed in |

Out of scope but noticed: `core/ml/nlp/get_data.py` writes a `SYNTHETIC_SEED` corpus fallback and `core/ml/perception/*` carry many `ASSUMED` facts; neither feeds a result shown in the talk's live runs.

## Ambulance V2X and signals: fixed values (read-only audit, 2026-10-12 03:40, owner's Step 1; agent-read, line numbers as of that time)

Where 0.78 comes from: computed by `corridor.match()` (`core/simulation/ambulance/corridor.py:58-70`), which tries scales 0.4 to 0.8
on seeds 11-15 and keeps the one whose median INT density sits inside DhaTraX's recorded 07:00-08:00 range closest to the recorded
median; written to `evidence/ambulance_rq2/dhaka_density/match.json` (`chosen_scale` 0.78, `chosen_density` 54.37). `study.py` and
`summary.py` read that file; the live scripts typed it (fixed in `run_v2x.py` on 2026-10-12, Step 3; the others are listed below).

| file:line | value | what it is | where it should come from | verdict |
|---|---|---|---|---|
| `scripts/live/run_v2x.py:33` (+ help `:163`) | `("dhaka_density", 0.78)` | Dhaka-density scale | `match.json chosen_scale` | real gap: typed copy of a computed value. **Fixed 2026-10-12** (`dhaka_scale()`) |
| `scripts/live/run_signals.py:27` | 0.78 | same | match.json | real gap (duplicate), reported only |
| `scripts/live/run_veins.py:78` | `<scale value="0.78"/>` | scale in the Veins sumo.cfg | match.json | real gap (duplicate; ignores the level), reported only |
| `core/simulation/ambulance/mp_signals.py:15,:128` | `--scale` default 0.78 | CLI default | match.json | gap (overridable), reported only |
| `run_v2x.py:33-34`, `run_signals.py:27-28`, `jobs.py:21` | x0.5 … x4 | generated-demand ladder | `study.LEVELS` / config | legitimate what-if ladder, copied in three places |
| `corridor.py:58` | scales 0.4-0.8, seeds 11-15 | grid searched for the Dhaka scale | config | legitimate method parameter; every tried value saved in match.json |
| `corridor.py:33`, `measures.py:10,:22` | INT `691209729#5`, BM `235293033#10` | DhaTraX counted-section edge ids | `calibration.json sites[].section` (snapped by `calibration.site_counts`) | real gap: duplicates a computed snap (currently equal), reported only |
| `corridor.py:28` | BUFFER_M 300 | corridor cut radius | config | legitimate choice, recorded in calibration.json, no source |
| `corridor.py:34` | DENSITY_SEEDS 11-20 | density-check seeds | config | legitimate, recorded |
| `corridor.py:35-36` | lateral gaps 0.1/0.15/0.2 m, minGap 1.0/1.5 m | two-wheeler, rickshaw, CNG spacing | config with a source | parameter from the density-gap check, no citation: weak |
| `corridor.py:139-140,:132,:157,:163`; `summary.py:109` | lateral-resolution 0.8, teleport 300, horizon 3600, warm-up 300 s, hour "07" | SUMO options and the recorded hour in the density check | `ambulance.yaml`, `dhaka.yaml calibration window` | gaps: duplicated literals, reported only |
| `core/simulation/ambulance/configs/ambulance.yaml:5,:8,:10,:11,:12` | lateral 0.8, teleport 300 s, speedFactor 1.5 + bluelight, depart 900 s, horizon 3600 s | experiment settings | config | legitimate (SUMO docs cited for the vType and sublane) |
| `ambulance.yaml:14` | ahead_m 1000 | how far ahead the ambulance addresses cars and junctions | config | parameter with no source beyond a comment |
| `ambulance.yaml:19` | make-way 100 m | make-way distance | config + `evidence/ambulance_rq2/makeway_v2/choice.json` | legitimate (50/100 m piloted, rule fixed beforehand) |
| `ambulance.yaml:22-24` | technologies, shares [0, .25, .5, 1], seeds 11-15 | study grid | config | legitimate; `study.py:28` and `sweep_v2x.py:28` add 0.75 |
| `ambulance.yaml:25` | LAB01 safety profile (min green 10 s, max 45 s, yellow 3 s) | preemption limits | a Dhaka regulation | gap for Dhaka, stated as a synthetic junction's values |
| `core/networking/v2x/configs/network_model.yaml:9,:14,:21-67` | interval 1 s, lifetime 600 s, ranges 425/625 m, delivery 0.90/0.90/0.96, delays 16.2/14/37.5 ms, hops 1/1/2 | radio parameters | config with sources (ETSI CAM/DENM, 5GAA P-190033, Xu 2017, tinyLTE) | legitimate published parameters, not Dhaka measurements |
| `network_model.yaml:59` | 4G range infinite | no coverage model | mast coverage data | documented limitation |
| `core/networking/v2x/model.py` | none | — | — | clean: everything read from the yaml |
| `service.py:92` | "DhaTraX counts at INT and BM, 07:00-08:00, on a 300 m corridor" | demand label | calibration.json, dhaka.yaml, `corridor.BUFFER_M` | gap: typed label, reported only |
| `service.py:244,:313,:364-365,:383` | LIVE_DEPART_S 60, edgedata 300, PAIRS_WANTED 5, MAX_SEEDS 60, first seed from config | display and sweep rules | config | legitimate (typed in code) |
| `core/simulation/twin/runtime.py:45-47` | md5(id) % 10000 < share | which cars are equipped | — | legitimate deterministic rule |
| `makeway.py:21,:42` | lane-change mode 1605, lcStrategic -1 | bluelight make-way settings | SUMO source (MSDevice_Bluelight.cpp cited) | legitimate |
| `measures.py:17-21` | LOOK 50 m, SLICE 5 m, BLOCKED 2 m/s, QUEUE 200 m, DENSITY_FROM 300 s | analysis definitions | config | parameters with no source, typed |
| `rl_signals.py:24,:26,:27,:106,:158,:186-188` | pinned sumo-rl commit, CORRIDOR_M 500, training seeds 101-999, alpha 0.1, gamma 0.99, eps 0.05→0.005, CLI defaults | Q-learning settings | config / sumo-rl example (cited) | legitimate; CORRIDOR_M has no source |
| `rl_signals.py:122-123` | delta 5, yellow 2, min green 5, max green 50 written as "settings" | the RL record | the SumoEnvironment object | gap: typed record, may not reflect what ran, reported only |
| `study.py:26-33` | TECH its_g5, LEVELS 0.5-8, SHARES, SEEDS_WANTED 5, PAIRS 10, seeds 11-60, GRIDLOCK_FAILS 3, teleport share 0.05 | study grid and gridlock rule | config | parameters typed in code; RQ2 saved its_g5 only |
| `study.py:35` | absolute SUMO_HOME path | machine path | environment | real gap (portability), reported only |
| `summary.py:19-20,:289,:67` | HELP_PCT 10, WORSE_S 5, share 0.3, bootstrap 2000 seed 11 | verdict thresholds, bootstrap | pre-registered rule / config | thresholds typed; 0.3 undocumented |
| `signal_baselines.py:21-22` | min green 10 s, max 60 s | Max-Pressure limits | config | parameter, typed |
| `run_v2x.py:162`, `run_signals.py:123`, `sweep_v2x.py:53`, `jobs.py:38,:52` | seed 11 (sweep 11-15) | default seed | user input / the clock for a live demo | legitimate study default. **run_v2x: default now the clock, printed (2026-10-12)** |
| `run_v2x.py:160-161,:164-165`, `jobs.py:35,:38` | its_g5, share 1.0, arm alert_preemption, speed 8 | CLI defaults | user input | legitimate; the web job has no arm choice (`jobs.py:111,:113`) |
| `run_v2x.py:28`, `jobs.py:78`, `run_signals.py:59,:105`, `mp_signals.py:30` | city "dhaka" | city id | config | fixed by design (only Dhaka has a corridor) |
| `run_v2x.py:29`, `run_signals.py:25` | `results/emergency/dhaka/rq2/runs(_v2)` | saved-run lookup | results file | legitimate; saved dhaka_density runs exist for its_g5 only |
| `run_v2x.py:88,:96,:99,:105,:116,:133,:198,:31-32` | depart − 20 s, zoom 600/450/1400, HUD +140 m, 15 s print cadence, window 1600×1000, colours | display | display | display only |
| `run_v2x.py:114` | GUI label "rerouted 0 (no rerouting in this run)" | a literal shown as a live count | a counted value or nothing | real gap. **Fixed 2026-10-12** (removed) |
| `run_v2x.py:175` | "Eclipse SUMO 1.27.1" | version in console | `sumo --version` | gap. **Fixed 2026-10-12** (`sumo_version()`) |
| `run_v2x.py:175` | "the 100 m alert distance is our choice" | make-way distance in console | `ambulance.yaml alert.makeway.distance_m` | real gap. **Fixed 2026-10-12** (read from config) |
| `sweep_v2x.py:35,:28,:53-57` | Dhaka level only; SHARES with 0.75; seeds 11-15, quick = 2, workers 4 | sweep grid | `--level`; `ambulance.yaml equipped_shares` | gap: no level option; share list differs from config; reported only |
| `run_veins.py:33,:34,:148-155,:77-78,:113,:163` | port 9999, BEGIN 600 s + ambulance at 20 s, makeway 100, txpower 20 mW, seed 0, window 300 s, step 0.1 s, lateral 0.8, teleport 300, maxInterfDist 2600 m, version strings | the Veins view's scenario | `ambulance.yaml depart_s` 900 etc. | real gaps: the Veins ambulance departs at 620 s, not the study's 900 s; make-way and SUMO options duplicated; interference distance unsourced; reported only |
| `run_veins.py:134,:168` | legend "within 100 m turns yellow", "released (30 s)"; console "blue = ambulance, orange = making way" | legend text | `--makeway`, the actual release rule | real gap: literals ignore the flag and the two legends disagree; reported only |
| `run_signals.py:101,:134,:138,:139` | `900 - 60`, "min green 10 s, max 60 s", "SUMO 1.27.1", "pinned 86f0fc41", "Traffic: generated, uncalibrated." | console text | `depart_s`, `signal_baselines`, version, `rl_signals.PINNED`, the level | gaps; the last is a **mislabel** at the default dhaka level; reported only (not touched: `make present` runs this script) |
| `run_signals.py:26,:78,:99-100` | sumo-rl venv path, zoom 900, window positions | machine path, display | environment, display | display / environment |
| `jobs.py:18,:20,:139` | NEAR_M 600, TECHS, SOS crash at 600 s after 300 s | web display and the SOS job | display / config | display; SOS job outside this scope |
| `Makefile:25,:49,:64,:73` | ARGS examples, "~10 min", "~4 min" | help text | — | text, matches the code |

Real gaps in one list: (1) the typed 0.78 in `run_signals.py`, `run_veins.py`, `mp_signals.py` (and outside the scope `run_sos_v2v.py:36`,
`scripts/demo/ambulance.py:23`, `scripts/aid/aid.py:495`); (2) the INT/BM edge ids and the hour "07" typed instead of read;
(3) console and legend literals in `run_signals.py` and `run_veins.py`, including the "generated, uncalibrated" mislabel;
(4) the Veins view's departure at 620 s, not 900 s; (5) `ahead_m`, the safety profile, `maxInterfDist` and the RL settings record
without a source or read-back; the absolute SUMO_HOME path in `study.py`. Fixed on 2026-10-12 in `run_v2x.py` only (Step 3).
