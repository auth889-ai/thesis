# Architecture plan

Plan only. Nothing here is built unless the text says "exists". **Approved by the owner on 2026-10-05**, with the
answers recorded in section 6. Each phase still starts in plan mode. The city layer (phase 0.5) is accepted; this
covers everything after it.

Each phase section says what I understood the phase to be. The repository holds no description of these phases, so
those opening lines are my reading and the first thing to correct.

## Contents

1. The whole system
2. Architecture rules every phase follows (2b: real data wherever it exists)
3. The network model: one interface, two implementations
4. Phases: 0.6 live 3D twin · 1 ambulance alert · 3 offline mesh simulation · 2 crash SOS demo · live forecasting ·
   integration · translation · story mode and hosting · user study
5. Hours (the final 50-hour plan of 2026-10-06, then the earlier budgets as record)
6. Decisions that block or shape the phases
7. Live forecasting for any city (full section)

---

## 1. The whole system

```
                         config/cities/<city_id>.yaml            (one file per city: area, languages, units,
                                     │                             emergency numbers, datasets, network, corridors)
                                     ▼
 ┌──────────────────────────── backend/app (FastAPI, one package per domain) ────────────────────────────┐
 │                                                                                                        │
 │  data/            city_config · city pipeline inputs · observatory (history store)                     │
 │  probes/          opt-in phone positions → 70 m cells → corridor speeds          ◄── phones (opt-in)   │
 │  forecasting/     Chronos-2 / trained models · conformal bands · forecast log                          │
 │  twin/            OSM → SUMO network · runtime · live simulation · 3D scene (0.6)                      │
 │  networking/      NetworkModel interface ─┬─ Python model (now)                                        │
 │                                           └─ ns-3 trace reader (later, optional)                       │
 │                   mesh/ store-carry-forward simulation (3)                                             │
 │  emergency/       ambulance alert scenarios on the twin (1)            ── calls NetworkModel           │
 │  sos/             crash / SOS events, TEST mode only (2)               ── calls NetworkModel, alerts   │
 │  alerts/          one alerts feed for the app (integration)                                            │
 │  routing/ commute/ plan/ lifeos/ agent/ mcp/ …   (exist, unchanged by these phases)                    │
 │                                                                                                        │
 │  router.py registers every domain router; the route list is pinned by a test                           │
 └───────────────┬───────────────────────────────────────────────────────────────┬────────────────────────┘
                 │ /api/*                                                         │ files
                 ▼                                                                ▼
   frontend/src (React, MapLibre)                                 results/<domain>/   generated outputs
     app/        shell, city + language switchers, story mode     evidence/<area>/    log + hashes behind a number
     i18n/       one file per language                            third_party/SOURCES.md   what is reused, exact version
     features/   today plan assistant goals activity you          data/cities/<id>/   built networks (not tracked)
                 mobility forecast twin results references system

   Where things run:  laptop (everything by default) · AWS CPU spot (simulation sweeps, after a stated cost is
   approved) · AWS GPU spot (model training only) · one small AWS host (the app, in the hosting phase)
```

## 2. Architecture rules every phase follows

Enforced by tests today (`tests/platform/test_repo_architecture.py`, `backend/tests/test_structure_migration.py`):

1. **API routes are pinned.** `backend/tests/fixtures/api_routes_pre_structure.json` must equal the app's route list
   exactly. A phase that adds a route adds exactly those lines to the fixture in the same change, and this plan lists
   them in advance.
2. **Frontend feature folders are a fixed set:** today, plan, assistant, goals, activity, you, mobility, forecast,
   twin, results, references, system. No phase below adds a folder; new screens go into an existing one. If one ever
   must be added, the set in the test and `docs/PROJECT_STRUCTURE.md` change together and the plan says so first.
3. **No frontend source file over 200 lines; TypeScript only.**
4. **`backend/app/*.py` is exactly ten global modules.** New code goes in a domain package laid out as `router.py`,
   `service.py`, optional `schemas.py`, `db.py`, `configs/`. Routers hold no algorithms.
5. **Top-level folders are fixed.** `config/` holds only `cities/`; every other YAML sits in `<domain>/configs/`.
6. **`upstream/` holds manifests only; no nested git repositories; no model weights and no file over 10 MB in git.**
   A GPL source is marked high risk and never imported at runtime.

From `CLAUDE.md`, applied by review and by a test wherever one can be written:

7. **No city in code.** Every city-specific value comes from the city config through `data/city_config.py`. A city
   without data for a feature gets "no data for this city", never another city's result.
8. **Every number has evidence.** A result shown in the app or the thesis has its log and output hash under
   `evidence/`, and says which city and dataset it comes from.
9. **Reused work is recorded** in `third_party/SOURCES.md` (URL, exact commit, licence, paper, files used or changed)
   before it is used; the original result is reproduced unchanged first.
10. **User-facing text goes through `frontend/src/i18n`**, English and Bangla.
11. **Safety:** no real SMS, call or alert to real people or emergency services; a marked TEST mode; emergency numbers
    come from the city config and are shown, never dialled. **Privacy:** opt-in, hashed device ids, raw positions
    deleted after 24 hours.
12. **AWS cost rules:** stated type, hours and cost approved before any paid launch; spot for training and sweeps with
    checkpoints; `project` and `phase` tags; self-shutdown; ap-south-1 except training in us-east-1.

Added by this plan:

13. **Provider data.** Results from a third-party map or traffic provider are used for the request that asked for
    them and nothing else: not stored beyond the provider's limit, never a training set, test set or "observed"
    value. Only our own observations are.
14. **One network model.** Any phase that needs to know whether a message arrives calls the interface in section 3.
    No phase carries its own delay or loss numbers.
15. **Simulated is labelled simulated.** Twin output is "simulated", with its demand's origin stated; the word "live"
    is used only for something observed now.
16. **Hours.** Each phase ends with its actual hours reported beside its budget.
17. **No commit or push** until the owner says so, and no branch is created, switched or merged (`CLAUDE.md`).
18. **Real, simulated or forecast, always said.** Every value the app shows is tagged "real" (with its source and the
    time it refers to), "simulated" (with what it is calibrated to, or "uncalibrated") or "forecast" (with the model,
    when it was issued, the real data it rests on and its uncertainty). Nothing is shown untagged. (The third kind,
    "forecast", was accepted by the owner on 2026-10-06.)
19. **Several seeds.** Every reported result is run on several seeds and shown as a mean with its spread, never as a
    single run.

## 2b. Real data wherever it exists

**Principle (owner, 2026-10-05): real data wherever it exists, clearly labelled, never invented.** Plan only; nothing
in this section is built, and the Phase 0.6 work is not changed by it.

### The tag

One small record travels with every value from the backend to the page:

- `real` — `source` (who measured it), `as_of` (the time it refers to), and the dataset or station.
- `simulated` — `calibrated_to` (which real counts the demand was fitted to, with the match achieved) or `uncalibrated`.
- `forecast` — `model`, `issued_at`, `based_on` (the real data it rests on) and `uncertainty`.

A page renders the tag beside the value; a value arriving without one is not shown, and a test checks every response
model that carries numbers has the field. Today's state, for honesty: the twin says SIMULATED and "uncalibrated"; the
leaderboard rows are real benchmark datasets; Dhaka has no real traffic value at all.

### Los Angeles: Caltrans PeMS

PeMS is the source behind METR-LA and PEMS-BAY. 24 of the 207 METR-LA stations lie inside our Los Angeles box, and
their ids are PeMS station ids (for example 769402, 717490, 764760).

What its pages say (read 2026-10-05):

- Access: "To use this site, you must apply for an account. Registering only takes a few minutes. Accounts are
  typically approved within one to two business days." (pems.dot.ca.gov). The owner is registering.
- What it holds: "collected in real-time from over 39,000 individual detectors … also an Archived Data User Service
  (ADUS) that provides over ten years of data for historical analysis", including "Traffic Detectors … Census Traffic
  Counts, Vehicle Classification, Weight-In-Motion".
- Use and storage, from the Caltrans Conditions of Use (dated 19 July 2021) linked from the PeMS page: "In general,
  information presented on this website, unless otherwise indicated, is considered in the public domain. It may be
  distributed or copied as permitted by law." It adds that copyrighted items Caltrans does not own need their owner's
  permission, and it disclaims accuracy: "makes no claims, promises, or guarantees about the absolute accuracy,
  completeness, or adequacy".

**Not established, and to be read before any use:** anything shown only after login (a click-through at registration,
rules for the Data Clearinghouse or for automated download), whether a research-use or citation condition applies, and
**how fresh the downloadable data is**. PeMS shows real-time values on its own map, but I have not verified that an
account can fetch the current five minutes by program. If the downloadable files lag (for example by a day), Los
Angeles gets real data that is recent, not live, and it is labelled with its real time either way. Fetching is done
the way PeMS provides, never by scraping its pages.

Plan: a `pems` provider beside the others; station speeds and flows for the stations in the city's box, stored as
`real` rows with source and time; vehicle classification from its census or weigh-in-motion stations, if any lies in
the box, as the first published vehicle mix for a city (the twin's one-class limit today).

### Calibration with SUMO's routeSampler

SUMO ships `tools/routeSampler.py` (present in the pinned SUMO 1.27.1): given candidate routes and counts per road
section and interval, it picks routes so the simulated counts match, and writes the mismatch.

- Los Angeles: counts from the PeMS stations in the box, each matched to its road section.
- Dhaka: counts from the owner's field collection. Until those exist, Dhaka stays `uncalibrated`.
- Reported every time: counts simulated against counts observed, per station and overall (for example the share of
  stations within a stated tolerance), saved under `evidence/`. A calibration that misses is reported as a miss.
- The tag then reads `simulated, calibrated to <source> counts of <date>, match <figure>`.

### Seeds

The experiment harness already runs arms by seed. From now on a result is a mean over at least five seeds with its
spread; a table without the spread is not a result. Sweeps over seeds are what the AWS CPU spot runs are for, each
with its cost approved first.

### Hours

| Item | Hours | Where they come from |
|---|---|---|
| PeMS as a real source for Los Angeles (provider, stations in the box, stored real rows) | 3.5 | **Inside the 10-hour live forecasting phase.** It replaces "road matching on our own network" and part of "corridor speed from phone cells" (4 h) there |
| Tag on every value (backend field, page rendering, the test) | 2 | Integration phase (10 h), which was going to touch every page anyway |
| routeSampler calibration for Los Angeles, with the match report | 4.5 | **New. Not funded by any phase.** |
| Dhaka field-count intake and calibration | 2, plus the field work itself | **New. Not funded.** Field work is people's time outside this plan |
| Mean-and-spread reporting in the harness | 1 | Phase 1 (its harness work) |

So: **PeMS fits inside the 10 hours**, and Los Angeles becomes a city with real data from the first day of that phase,
at a price: the phone-sensing pipeline for cities without a provider (Dhaka) is cut back to what exists today, so a
Dhaka forecast stays "no observed traffic for this city yet" for longer.

**Calibration adds about 6.5 hours to Phase 1** (28 → about 34.5) if the ambulance results are to run on calibrated
Los Angeles demand, plus more simulation runs because of the seeds rule. The buffer has 4 hours and the base-map and
add-your-city steps also draw on it, so this needs a decision: take the hours from a named phase, or run Phase 1 on
uncalibrated demand and say so.

## 3. The network model: one interface, two implementations

**Decision (owner, 2026-10-05).** The ambulance and mesh phases, and anything later, ask one question through one
interface:

> given a sender, a receiver, a time and a technology → was the message delivered or lost, and after what delay?

```
networking/model.py

  deliver(sender, receiver, time_s, technology) -> Delivery
      sender, receiver : id and position (and speed, when the model needs it)
      time_s           : simulation time of the send
      technology       : one of the names in networking/configs/network_model.yaml
      Delivery         : delivered (yes/no) · delay_s (when delivered) · reason (in range, lost, out of range, expired)
```

**Implementation now: a Python model.** It lives beside the interface. Every parameter (range, loss against distance,
delay and its spread, message lifetime, per technology) is one entry in `networking/configs/network_model.yaml` with
its value, unit and source: a paper, a standard, or one of our own reproduced measurements. A parameter without a
source is written `null` and the model refuses that technology. It reuses what exists: the delay, jitter, loss and
lifetime profiles in `networking/channel.py`, and the ITS-G5 latencies reproduced from MOSAIC's Barnim scenario
(`networking/mosaic/`). Results are deterministic for a given seed.

**Implementation later, only if time remains: an ns-3 (ms-van3t) trace reader.** ms-van3t runs on an AWS Linux machine
for the same scenario and writes per-message traces; a reader in `networking/` answers the same `deliver` calls from
those traces. Callers do not change: the implementation is chosen in the config. ns-3 is **not installed now**, on the
laptop or on AWS. Before it is: its licence is read and recorded (a GPL licence means trace files only, never an
import), the machine type, hours and cost are stated and approved, and ms-van3t's own example result is reproduced
unchanged first.

**Technologies (decided).** The ambulance phase compares three: ITS-G5 (IEEE 802.11p), C-V2X, and plain cellular 4G.
The mesh phase uses Bluetooth Low Energy. Every parameter of every technology needs a paper or a standard as its
source; a value without one stays `null` and that technology is refused. ITS-G5 is the only one with reproduced
numbers in the repository today (MOSAIC's Barnim scenario); the other three start with no parameters at all.

**Tests for the interface (written with the Python model):** same answer for the same seed; nothing is delivered
beyond a technology's range; an "ideal" technology delivers everything with zero delay; a "none" technology delivers
nothing; a technology with a `null` parameter is refused with the parameter's name; both implementations pass the same
test file.

## 4. Phases

### Phase 0.6 — live 3D twin (18 h)

*My reading:* the running SUMO simulation of the selected city, shown in the browser in 3D, updating as it runs.

| | |
|---|---|
| Backend | `twin/`: a new `scene.py` that turns a city's built network into drawable geometry (lanes, junctions, and building footprints from the same OpenStreetMap extract). Reuses `twin/city_pipeline.py` (extended to fetch buildings and record their hash), `twin/live/` (`LiveSim` already publishes every vehicle each second), `data/city_config.py` |
| API routes | New: `GET /api/twin/scene/{city_id}` (static geometry). Vehicles come from the existing `GET /api/sim/live/state`. Fixture: +1 line |
| Frontend | Existing `twin` folder. MapLibre is already a dependency and draws extruded buildings and a tilted camera, so no new library. No new folder |
| Data, results, evidence | Geometry in `data/cities/<id>/sumo/` (not tracked); `evidence/cities/<id>/build.json` gains the buildings file's hash and OSM date |
| Third party | OpenStreetMap buildings through Overpass (ODbL), added to `third_party/SOURCES.md`. Nothing else |
| Runs on | Laptop |
| Tests | Scene builds for the fixture city (Vaduz) with no city name in code; a city without a network (Berlin) returns "no data for this city"; the page says "simulated" and names the demand's origin; frontend file limits |
| Depends on | City layer |

Label: this is a simulation with generated demand. It is called "simulated twin" in the app, not "live traffic".

Demand (decided): Dhaka uses uncalibrated generated demand, built the same way as for every other city. The old 0.584
scale is used only to reproduce old results and is labelled withdrawn. Los Angeles is the second city; Berlin has no
area and produces nothing.

Visual references and stretch goals: the owner mentioned sending these earlier. They are not in the conversation this
plan was written from, so they are **not included**; they need to be sent again before this phase is planned in detail.

### Everyday user home (14.5 h; built 2026-10-05 except the PeMS provider)

The top of the Today page, which `/` now opens: the selected city on the worldwide 3D map, a trip across it, when to
leave, and the alerts strip.

| | |
|---|---|
| Backend | `common/tag.py` (the tag: real, simulated, forecast); `routing/city_router.py` (a route on any built city's own network; Phase 1 reuses it); `data/real_speeds.py` (one interface for real speeds: opt-in phones now, PeMS and field counts declared and pending); `forecasting/operations/section_forecast.py` (Chronos-2 per section, only from 8 readings in a row); `routing/city_trip.py`; `alerts/service.feed`; `data/station_matching.py`; city config gains an optional `live.real_sources` |
| API routes | New: `GET /api/trip/{city_id}`, `GET /api/alerts/feed`. Fixture: +2 lines (169) |
| Frontend | `today` folder (`Home`, `HomeMap`, `TripBar`, `LeaveWhen`, `AlertsStrip`, `useSimulated`, `trip.ts`); `components/Tagged.tsx`. No new folder |
| Data, results, evidence | `evidence/home/record.json` and screenshots; `evidence/home/los_angeles/station_matching.json` (24 PeMS stations matched to road sections; no reading) |
| Third party | None new. Place search uses the existing Nominatim call; the station list is the DCRNN file already recorded |
| Runs on | Laptop |
| Tests | `backend/tests/city/test_city_home.py` (9), `today/trip.test.ts` (5), `components/Tagged.test.tsx` (2) |

State on 2026-10-05: **no city has traffic data**, so every route is the grey dashed "no traffic data" line and no
travel time in traffic is shown. Three things differ from the plan and are listed in `docs/proposals.md`: a third tag
kind "forecast" (rule 18 names two); phone cells are counted by position inside the city's box, not by the name the
phone sent; the `live` block of the city config is optional. Not yet built: the PeMS provider (account pending).

### Real data without a crowd (steps 1 to 5 built 2026-10-05)

Real measurements that need no crowd of phones, each used only as its licence allows and shown with its own date.
Plan: `/Users/jannatulferdouseva/.claude/plans/wise-swinging-pillow.md`. Licences and versions: `third_party/SOURCES.md`.

| | |
|---|---|
| Backend | `data/recorded/dhatrax.py` (reads DhaTraX's published tables; fetch with checksum); `data/real_speeds.py` (`recorded`, `recorded_sources`: a recorded reading has its own field and never reaches "now", a travel time or a departure); `twin/city_pipeline.apply_mix` (a city's `vehicle_mix` applied to its generated demand, only where a class may drive); `probes/researcher.py` (one locally listed device exempt from the three-phone rule); city config gains `vehicle_mix` and the `recorded` source kind |
| API routes | None new. `GET /api/trip/{city_id}` takes `recorded_at=HH:MM`; `GET /api/operate/cities` lists each city's recorded sources and vehicle mix |
| Frontend | `today/Recorded.tsx` and the "Recorded day" switch; typed coordinates in the trip bar; the twin page states the mix's source |
| Data, results, evidence | `data/recorded/dhatrax/` (not tracked); `evidence/recorded/record.json`; `evidence/cities/dhaka/build.json` (mix asked and achieved); `research/notebooks/WorldTrace_coverage_colab.ipynb` |
| Third party | DhaTraX (CC BY 4.0), used. DRINF (CC BY 4.0), WorldTrace (ODbL 1.0), Kaggle Bangladesh Traffic Flow (CC0): read and recorded, not used |
| Runs on | Laptop; the WorldTrace scan on Colab |
| Tests | `backend/tests/city/test_city_home.py` (15 in all), `today/trip.test.ts`, `twin/vehicleShapes.test.ts` |

State: Dhaka shows DhaTraX's recorded speeds at two sites (Bangla Motor on 20 Apr 2026, INT on 19 Apr 2026) under
"Recorded day"; the Dhaka twin runs the counted mix; "now" is still without data in every city. The Dhaka twin stays
**uncalibrated**: the mix changes which vehicles are drawn and driven, not how many or where.

### Phase 1 — ambulance alert (28 h)

*My reading:* an ambulance drives through the twin and announces its approach to vehicles ahead over a wireless
link; vehicles that receive the message make way. The result is the ambulance's travel time, and the cost to other
traffic, with and without the alert, across technologies and shares of equipped vehicles.

| | |
|---|---|
| Backend | New package `emergency/` (`router.py`, `service.py`, `schemas.py`, `configs/`). First task of the phase: the network model of section 3 in `networking/`. Reuses `twin/runtime.py` (the seeded experiment harness), `twin/route_application.py` (TraCI), `interfaces/priority.py` (`PriorityKind.EMERGENCY`, defined but unused today), `common/types.py` (`VehicleClass.EMERGENCY`), `routing/local_router.py` (routes on our own network) |
| API routes | New: `POST /api/emergency/runs`, `GET /api/emergency/runs/{run_id}`, `GET /api/emergency/results/{city_id}`. Fixture: +3 lines (172; exists since 2026-10-06) |
| Frontend | `twin` folder (start a run, watch it in the 3D view); result tables in `results`. No new folder |
| Data, results, evidence | Scenario in `emergency/configs/`; outputs in `results/emergency/<run>/`; `evidence/emergency/<city_id>/` per reported number |
| Third party | SUMO (recorded). Make-way behaviour (decided): SUMO's own emergency-vehicle support, the bluelight device, used as SUMO documents it; the SUMO documentation page and version are recorded in `third_party/SOURCES.md` as the source |
| Runs on | Laptop for single runs. A sweep over seeds, technologies and equipped shares: AWS CPU spot, after its cost is stated and approved |
| Tests | With the "none" technology the run equals the no-alert baseline exactly; same seed, same result; equipped share 0 equals baseline; no notification leaves the machine; a city without a network is refused |
| Depends on | City layer; the network model; 0.6 only for the visual |

Demand (owner, 2026-10-06): **the first step of this phase is a routeSampler calibration of the Dhaka twin on
DhaTraX's two located count points (BM, INT), 3 hours from this phase's budget (26 → 23 for the rest).** The match is
reported per point and a miss is reported as a miss; two points on one day each constrain little of a city, and the
tag says exactly what it was calibrated to. Every other city stays on uncalibrated generated demand. Technologies
(decided): ITS-G5 (802.11p), C-V2X and plain cellular 4G.

Two constraints: the ambulance is routed on our own road network, never through Amazon Location (AWS Service Terms
82.7 exclude "hazardous environments or critical systems"); and nothing in this phase contacts a real service.

### Phase 3 — offline mesh simulation (24 h)

*My reading:* when there is no mobile network, a message hops from device to device as people and vehicles move.
The result is how many devices it reaches and how fast, against density, range and technology.

| | |
|---|---|
| Backend | A subpackage `networking/mesh/` (as `networking/mosaic/` is today): a store-carry-forward simulation over the positions the twin already outputs. Every hop is one `deliver` call on the network model. Reuses `twin/runtime.py` for seeded mobility |
| API routes | New: `POST /api/mesh/runs`, `GET /api/mesh/runs/{run_id}`, `GET /api/mesh/results/{city_id}`. Fixture: +3 lines |
| Frontend | `results` folder (shown on the network results page built in integration). No new folder |
| Data, results, evidence | `networking/configs/mesh.yaml`; outputs in `results/networking/mesh/`; `evidence/mesh/<city_id>/` |
| Third party | None required. Range and loss values come from papers or standards, each recorded with the parameter |
| Runs on | Laptop for one scenario; sweeps on AWS CPU spot after cost approval |
| Tests | Range zero reaches nobody; an ideal link reaches everyone connected in one step; reach does not fall as density rises (same seeds); same seed, same result; identical interface use as the ambulance phase |
| Depends on | City layer; the network model (from phase 1) |

Technology (decided): Bluetooth Low Energy, parameters from papers or the Bluetooth specification. Demand (decided):
uncalibrated generated demand. No mesh, store-and-forward or Bluetooth code exists today; this phase starts from
nothing but the twin.

### Phase 2 — crash SOS demo (12 h)

*My reading:* the phone notices a crash-like jolt, or the person presses SOS; the app shows the city's emergency
numbers, sends a TEST message to test contacts, and shows how the message would travel by mesh if the network were
down.

| | |
|---|---|
| Backend | New package `sos/` (`router.py`, `service.py`, `schemas.py`, `db.py`). Reuses `data/city_config.py` (emergency numbers), `plan/notifications.py` (`publish`; a TEST-mode switch is added, none exists today), the mesh simulation for the offline illustration |
| API routes | New: `POST /api/sos/events`, `GET /api/sos/events/{event_id}`, `POST /api/sos/events/{event_id}/cancel`. Fixture: +3 lines |
| Frontend | `mobility` folder (an SOS panel beside "Your phone is the sensor"); motion from the browser's own motion sensor. No new folder. The Expo app has no sensors today and is not part of the 12 hours |
| Data, results, evidence | Events in the existing app database, position kept 24 hours; `evidence/sos/` for the demo recording |
| Third party | None |
| Runs on | Laptop and one phone browser |
| Tests | Nothing is dialled; no message leaves unless the contact is a marked test contact; every event is stamped TEST; a cancel window stops the event; numbers come only from the config and a `null` number shows "no number recorded for this city" |
| Depends on | City layer; mesh (for the offline illustration); integration shows it in the feed |

### Live forecasting for any city (10 h)

Section 7 holds the full design. Summary: opt-in phone sensing is the main source; Amazon Location is a secondary
30-day source only where it returns traffic, and is paused; TomTom and Google are excluded. No new route, no new
folder. Depends on the city layer only.

### Integration — alerts feed and network results page (10 h)

| | |
|---|---|
| Backend | `alerts/`: one feed that lists congestion-onset alerts (exist), ambulance approaches and SOS events, each with its origin and a TEST or SIMULATED stamp. A read-only collector of the ambulance and mesh result files |
| API routes | New: `GET /api/alerts/feed`, `GET /api/network/results/{city_id}`. Fixture: +2 lines |
| Frontend | Feed in `today`; the network results page in `results`. No new folder |
| Data, results, evidence | Reads `results/emergency/`, `results/networking/`; no new store |
| Third party | None |
| Runs on | Laptop |
| Tests | Feed order and stamps; a city with no results says so; nothing from one city appears under another |
| Depends on | Phases 1, 3 and 2 |

### Translation (6 h)

| | |
|---|---|
| Backend | Sentences the backend writes for people (for example in `alerts/service.py`, `plan/monitor.py`, `plan/outcomes.py`, `routing/trip/analysis.py`) return a message key with its values instead of English text |
| API routes | None new; response fields gain a key beside the text |
| Frontend | The i18n system exists. 7 files use it; about 51 more contain text. The 6 hours cover the everyday pages (Map, Today, Plan, Goals, Messages, Settings) and the panels inside the City page. The five Lab pages stay English unless hours remain |
| Data | `frontend/src/i18n/locales/`; `docs/BANGLA_REVIEW.md` regenerated for the owner's review |
| Tests | Every key in every language with the same placeholders (exists); no English literal left in a translated file |
| Depends on | Best done after the phases above, so their text is translated once |

Six hours for about 51 files is tight. If it runs out, the untranslated files are listed, not hidden.

### Story mode and hosting (12 h)

*My reading:* story mode is a guided walk through the app for a first-time viewer; hosting puts the app on AWS at a
public address.

| | |
|---|---|
| Backend | Story mode: none. Hosting: `infra/` (the Dockerfile and compose file exist); a hosted-mode setting that turns off anything that spends money or samples a provider (the Train page's AWS launches, the sampler); the live-history table from section 7 |
| API routes | None new |
| Frontend | Story mode in `app/` (the shell), its text in the i18n files. No new folder |
| Data, results, evidence | `infra/`; `evidence/hosting/` with the deployed version and its checks |
| Third party | None |
| Runs on | One small **on-demand** AWS host in ap-south-1 (decided: not spot). Its type and monthly cost are stated for approval before launch |
| Tests | Hosted mode refuses paid actions; the health check; story steps exist in both languages |
| Depends on | Everything shown in the story |

Hosted mode (decided): the public address serves read-only pages and disables everything that changes data or
spends money. The app has no login today, so "disabled" means the hosted app refuses those requests outright; a test
lists every route that changes something and asserts each is refused in hosted mode.

### User study (6 h)

*My reading:* a small study with real participants on whether the app is understood and useful.

| | |
|---|---|
| Backend | A consent record and questionnaire answers in the existing app database |
| API routes | New: `POST /api/study/responses`. Fixture: +1 line |
| Frontend | `you` folder (consent and questionnaire). No new folder |
| Data, results, evidence | `docs/user_study/` (protocol, tasks, questionnaire); anonymised answers in `evidence/user_study/` |
| Third party | A standard questionnaire if one is used, with its source and licence recorded |
| Runs on | The hosted app |
| Tests | No answer is stored without consent; no name or contact is stored |
| Depends on | Hosting; translation, if participants read Bangla |

Decided: 15 to 20 participants, in Bangla. The owner is checking ethics approval with the supervisor; no participant
is recruited before that answer.

## 5. Hours

### Final plan (owner, 2026-10-06 05:41 +06): the project finishes in 50 hours, by 2026-10-08 07:41 +06

No new features after this instruction; only these nine items, in this order. Work already done or in progress is
not counted. Each item reports its hours when it ends. What each item reuses, with licences: `docs/COPY_LIST.md`.
The phase budgets in the table after this one are superseded and kept as record.

| # | Item | Budget (h) | Done (h) | Reuses (section 4) |
|---|---|---|---|---|
| 1 | App structure: traffic app first; LIFE OS hidden from navigation, code kept; menu Home / 3D City / Add city / Emergency / Offline alerts / Research / Settings; go-anywhere search; "zoom in to see 3D buildings" note | 6 | done 2026-10-06, about 0.35 h elapsed | the shell in `frontend/src/app/`, the twin, Add your city |
| 2 | Mesh: the PONS results from `research/mesh_pons/` into the app | 6 | done 2026-10-06, about 0.1 h elapsed | Phase 3's results page; PONS unchanged, movement from SUMO's traceExporter |
| 3 | SOS demo: the prototype from `research/sos/` into the app (the folder does not exist yet on 2026-10-06 05:41) | 6 | — | Phase 2's design: emergency numbers from the city config, TEST mode, nothing dialled |
| 4 | 4G in the ambulance sweep, from Xu et al. 2017 | 2 | done 2026-10-06, about 0.12 h elapsed | Phase 1's network model, where plain 4G was refused for lack of a source |
| 5 | Translation of Home, 3D City, Emergency and Offline alerts | 2 | done 2026-10-06, about 0.1 h elapsed | the i18n system |
| 6 | Minimal hosting: one small on-demand instance in ap-south-1, HTTPS, cost stated and approved first | 6 | — | `infra/`, hosted mode as decided |
| 7 | Story mode for the defense | 4 | done 2026-10-06, about 0.2 h elapsed | the shell; text through i18n |
| 8a | Plain language on the everyday pages (owner, 2026-10-06) | 2 (from item 8) | done 2026-10-06, about 0.1 h elapsed | `components/PlainResult.tsx`, `plain` in both result builders |
| 8 | Results pack: every result as a table and a figure with its evidence | 3 | — | `results/`, `evidence/` |
| 9 | Buffer; PeMS only if the account arrives (2 h of it) | 3 | — | the matched stations in `evidence/home/los_angeles/` |
| | **Total** | **40** of 50 wall-clock hours | | |

Future work, not built now (`docs/proposals.md`): ns-3, Ask the city, Edit your street, Google 3D tiles, WorldTrace
replay, DRINF, the full user study.

### Earlier budgets (superseded 2026-10-06; record only)

| Phase | Budget (h) | Actual (h) |
|---|---|---|
| 0.6 Simulated 3D twin | 18 | core done 2026-10-05 in about 0.3 h of elapsed working time; worldwide base map done (4 h assigned); "Add your city" done 2026-10-05 (10 h assigned; about 0.8 h elapsed by the session's timestamps, plan included); stretch: orbit, street level and night lighting done 2026-10-05 in about 0.2 h (cap was 2 h); visual realism (OpenFreeMap base map, 2016 satellite composite, lane-width roads, colours, automatic start) done 2026-10-05: 3.4 h assigned, about 0.5 h elapsed (20:59 to 21:30 by the session clock); real 3D vehicle models and "Ask the city" not started; vehicle click not exercised in a browser. **By assigned hours 17.9 of 18 are used; by elapsed time about 4.** |
| Everyday user home (2026-10-05) | 14.5, taken from: integration 7, live forecasting 3, Phase 1 2, buffer 2.5 | 12.0 of the 14.5 built on 2026-10-05 in about 0.45 h elapsed (21:40 to 22:07); the PeMS provider (2.5) waits for the account and its terms |
| 1 Ambulance alert (includes the network model) | 28 → 26 (2 went to the home's router, which this phase reuses). Of the 26, 3 are the Dhaka calibration on DhaTraX's two count points, its first step (owner, 2026-10-06), leaving 23 | **In progress, 2026-10-06.** Built: calibration (a miss, reported), network model (4G refused), make-way, preemption, runner, app. Sweep done on the uncalibrated demand only; the calibrated-demand sweep is not run. Elapsed by the session clock: about 2 h of the 3 + 23 |
| 3 Offline mesh simulation | 24 → 22.5 (1.5 to the recorded traffic replay, 2026-10-06) | — |
| 2 Crash SOS demo | 12 | — |
| Live forecasting for any city | 10 → 7 (3 went to the home's slider and per-section forecast) → 1 (6 went to "real data without a crowd") | the last hour was used on 2026-10-06: the Chronos import repaired and one backtest of Chronos-2 against recorded METR-LA and DhaTraX readings (`evidence/live_forecast/`). **0 left**; corridor speeds from phone cells, scoring against later readings and the measured band are unfunded |
| Real data without a crowd, steps 1 to 5 (2026-10-05) | 6.0, from live forecasting | done on 2026-10-05 in about 0.4 h elapsed (22:13 to 22:37), except that the WorldTrace scan is written and **not run** (it runs on Colab). Steps 6 to 9: calibration (3.0 h) is now the first step of Phase 1, from its budget; the Kaggle check is dropped (owner, 2026-10-06); WorldTrace replay and DRINF (7.0 h) are not funded |
| Integration | 10 → 3 (7 went to the home: tag, alerts feed, PeMS). What stays: the network results page and the tag on older pages | — |
| Translation | 6 → 4 (2 to the recorded traffic replay, 2026-10-06; Home and the 3D page only) | — |
| Story mode and hosting | 12 | — |
| User study | 6 | — |
| City layer (phase 0.5) | 6 | done; elapsed working time about 1 |
| PatchSTG GLA training | 2 | in progress |
| Real recorded traffic replay (DhaTraX trajectories; 2026-10-06) | 5, from translation 2, buffer 1.5, mesh 1.5 | built 2026-10-06 |
| Buffer | 6 | fully used: 2 earlier, data audit and Amazon fix (1); Google remediation: guard, inventory, plans, lean disconnect, withdrawal and deletion (about 1 elapsed) |
| **Total** | **140** | |

- **Buffer remaining: 0** (2 used earlier; 2.5 went to the everyday user home; 1.5 to the recorded traffic replay on 2026-10-06).
- "Actual" is reported at the end of each phase. What I can measure is elapsed time of the working session; it is not
  the same as a person's hours of review and decision, which I cannot see.
- Order (owner, 2026-10-05, evening): 0.6 → **everyday user home** → 1 → 3 → 2 → live forecasting → integration →
  translation → story mode and hosting → user study. The everyday user home is planned in plan mode first; it takes over
  the alerts feed, the real/simulated tag and the PeMS source, so those are not built again in the later phases. Its
  plan was approved on 2026-10-05; its hours are in the table above and its design in section 4.
- Also decided then: `config/cities/sylhet.yaml` is kept as evidence for "Add your city". routeSampler calibration
  waits until Dhaka field counts exist, then Dhaka and Los Angeles are calibrated together; until then every twin stays
  "uncalibrated". **Changed 2026-10-06:** Dhaka is calibrated on DhaTraX's two count points as the first step of
  Phase 1; Los Angeles still waits for PeMS counts. Vehicle mix: Los Angeles from PeMS vehicle classification, Dhaka from the owner's Farmgate video
  counted with the RT-DETR perception lab; until each exists, one class. **Changed later that evening:** Dhaka's mix
  comes from DhaTraX's published class counts (no detector run by us); DRINF may check it later.

## 6. Decisions

Taken by the owner on 2026-10-05:

1. **Dhaka demand.** New phases (0.6, 1, 3) use uncalibrated generated demand, like every other city. The 0.584 scale
   stays only to reproduce old results, labelled "synthetic what-if, uncalibrated (earlier calibration used Google
   data and is withdrawn)".
2. **Technologies.** Ambulance: ITS-G5 (802.11p), C-V2X, plain cellular 4G. Mesh: Bluetooth Low Energy. Every
   parameter has a paper or standard as its source.
3. **Make-way behaviour.** SUMO's own emergency-vehicle support (the bluelight device), as SUMO documents it.
4. **Minimum phones per reading:** 3.
5. **App host.** A small on-demand instance; hosted mode is read-only and disables anything that changes data or
   spends money.
6. **User study.** 15 to 20 participants, in Bangla; ethics approval is being checked with the supervisor.
7. **Cities.** Berlin stays without an area; Los Angeles is the second city.
8. **Hours.** The 8 hours outside the phase budgets are the city layer (6) and GLA training (2).
9. **Google-derived data.** Withdrawn and deleted on 2026-10-05; no Google API is called; details in
   `docs/proposals.md` and `evidence/audit_2026-10-05/`.

Still open:

- The Phase 0.6 visual references and stretch goals (to be re-sent).
- Which papers and standards supply each network parameter (found during phase 1 and phase 3, each recorded before use).
- AWS's answer on Amazon Location storage and polling (question drafted, to be sent by the owner).
- Removing the Google data from git history, at the final commit (`docs/proposals.md`, section F).

---

## 7. Live forecasting for any city

### What changed the design

Three facts, each checked on 2026-10-04, decide where live speeds can come from.

1. **Amazon Location returns no traffic for Dhaka.** Thirteen direct requests and the 94 stored samples agree: one
   fixed free-flow time per route, with traffic on, off, at the evening peak and a week ahead; Los Angeles and Berlin
   varied (`evidence/audit_2026-10-05/amazon_location_dhaka_traffic.md`).
2. **Provider terms limit storing.** AWS Service Terms 82.4(a) allow route results to be kept "for up to 30 days when
   you use HERE or Esri as your Geolocation Provider" and otherwise forbid storing or systematically collecting them.
   TomTom's terms forbid storing results at all. Google's terms forbid storing and forbid using the content to train,
   test or validate models.
3. **Only data we observe ourselves is ours to keep and learn from.** The opt-in phone sensing already in the app
   (`backend/app/probes/`) is that data.

So: our own opt-in phone sensing is the main source for any city; Amazon Location is a secondary source, 30 days
rolling, only where it returns traffic; TomTom is excluded.

### 1. Data sources compared

All quotes are from the pages named under "Sources read", on the dates given there. "Not found" means the pages I read
do not state it; it does not mean the answer is no.

| | Our opt-in phone sensing | Amazon Location Routes | TomTom Traffic Flow (Flow Segment Data) |
|---|---|---|---|
| Role in this design | **Main source** | Secondary, 30 days rolling, only where it returns traffic | **Excluded** |
| Bangladesh | Wherever a consenting person moves. Today: 10 stored points and 3 cells in total, so effectively no data yet | Routes: "Good". Traffic table: **no row**. Measured: no traffic returned for Dhaka | **Not listed** on the Traffic API market coverage page |
| United States | Same: only where people opt in | Routes "Comprehensive"; traffic "Both" (flow and incidents), Southern California included. Measured: Los Angeles varied | Listed, Traffic Flow ✔ |
| Germany | Same | Routes "Comprehensive"; traffic "Both". Measured: Berlin varied | Listed, Traffic Flow ✔ |
| Cost, one corridor every 5 minutes (8,640 requests a month) | No provider charge if positions are matched to roads with our own OpenStreetMap network. If Amazon SnapToRoads is used instead: $1.50 per 1,000 requests (Advanced), per batch of positions, not per poll | $0.50 per 1,000 routes (Core) → **$4.32 per corridor per month**; 12 corridors $51.84. Free tier: 10,000 routes a month for 3 months | 8,640 is inside the "Free 20K monthly" allowance for Traffic Flow API Segment Data. Price above the allowance: not found in the page text |
| Rate limits | Ours to set (the endpoint accepts up to 500 positions per batch) | Account quota: 20 requests per second for CalculateRoutes, 5 for CalculateRouteMatrix (read from Service Quotas) | A 429 "Too Many Requests" response is documented; no number found |
| May we store it? | Yes, under our own privacy rules: opt-in, device id hashed, raw positions deleted after 24 hours | Only "route results for up to 30 days when you use HERE or Esri as your Geolocation Provider" (82.4(a)(i)). Which provider serves our requests is **not established** | No: "The caching or storing of any Results shall be prohibited" except client caching per cache headers (11.4) |
| May we forecast from it or do research on it? | Yes | **Not stated.** "Systematically collect" is prohibited separately from storing, and 82.4(b) bars products "similar to the services of the Geolocation Providers" without "substantial, independent value". A question for AWS is drafted, not sent | No: no "secondary or derived database" (11.6.1); machine-learning use restricted (11.6.3, 11.6.4) |

Google Routes is not a candidate: Google Maps Platform Terms 3.2.3(c)(vii) forbid using the content "to improve machine
learning and artificial intelligence models, including to train, test, validate or fine-tune the models".

**What this means in practice.** For Dhaka there is no usable third-party live source among these three. A Dhaka
forecast can only come from phones that opted in, and until enough of them have, the honest output is "no data for
this city".

### 2. Collector

**Road segments.** Each city config gains a `live.corridors` list in `config/cities/<city_id>.yaml`: a name, two end
points and a source line per corridor. Dhaka's twelve move there from `core/common/data/reference_corridors.py`; a city
without a list derives up to twelve from its OpenStreetMap network with the existing
`core/common/data/city_corridors.py` (motorway, trunk, primary, longest first). A corridor is stored as the ordered
70 m cells along its OpenStreetMap path, computed once from the city's own network, with no provider call.

**Main source: phone sensing (exists, extended).**
- Exists: `POST /api/probes` takes positions from an opted-in phone; device ids are hashed; positions are binned into
  70 m cells by heading every 5 minutes (`probe_cells`); raw positions are deleted after 24 hours.
- To build: (a) place positions on roads with our own network instead of Amazon SnapToRoads, so the cells are ours to
  keep beyond 30 days; (b) every 5 minutes, combine the cells along each corridor into one corridor speed and write it
  to the existing history store as a row with provider `probes`; (c) write nothing when a corridor has no reading: a gap
  stays a gap and is never filled in.
- Decided: a corridor reading is shown or forecast only when at least 3 distinct phones are behind it.

**Secondary source: Amazon Location (paused).** Polling is switched off in code until AWS answers the drafted
question. If AWS permits it, it runs only for a city whose readings actually move (the existing
`observatory.traffic_signal` check), every 5 minutes on the same corridors, with rows deleted after 30 days and never
used to train or to score a model. It is never run for Dhaka.

**Polling interval.** 5 minutes for both, matching the bins already used.

**Where history is stored, and the monthly cost.**

| Stage | Store | Monthly cost |
|---|---|---|
| Now, inside the 10 hours | The existing SQLite files on the app host (`results/live/observatory.sqlite`, `results/live/lifeos.sqlite`) | $0 beyond the host |
| With the AWS hosting phase | One DynamoDB table in ap-south-1 (key: city and corridor; sort key: 5-minute bin; provider recorded on each row; an expiry attribute set to 30 days on provider rows only) | 12 corridors × 288 bins × 30 days = 103,680 writes per city → about $0.07 at $0.71 per million write request units; storage inside the first 25 GB, which is not charged |
| Secondary source, only if AWS permits | Same table, 30-day expiry | 6 corridors: $25.92 per city; 12 corridors: $51.84 per city |

So the lean design costs nothing in provider fees. The secondary source is the only real cost, and it is off.

### 3. Forecasting

- **Chronos-2, zero-shot (exists as an adapter).** `core/ml/forecasting/adapters/chronos_adapter.py` already
  forecasts one series at a time with a minimum of 8 readings and returns the 10 %, 50 % and 90 % quantiles. It is
  pointed at each corridor's `probes` series, at 15, 30 and 60 minutes. A corridor with fewer than 8 recent readings
  gets no forecast and the reason is shown. Nothing is trained.
- **OpenCity-plus (not in the 10 hours).** Its adapter does not run on demand today; it only runs as a batch job that
  needs 1,176 readings (about four days without gaps) on at least 9 corridors. With sparse phone data that bar will
  rarely be met. Design: a daily batch for a city that meets the bar, its forecasts logged and scored exactly like
  Chronos-2's. Whether it runs on a CPU for a dozen corridors has not been measured.
- **Conformal bands.** For each city and horizon, take the last 7 days of (forecast, later observed) pairs from the
  forecast log and compute the half-width that covered 90 % of them, with the same split-conformal method
  `core/ml/forecasting/evaluation/conformal.py` uses for the benchmark. Fewer than 200 pairs: no calibrated band;
  the model's own 10–90 % range is shown and labelled "uncalibrated". The band's measured coverage over the last 7 days
  is shown beside it.
- **Defect this must fix.** `core/common/data/city_map.py` forecasts every city from the Dhaka Google recording
  (`routing/forecast_costs.recorded_forecast`). That is wrong for any other city and uses data the Google terms do not
  allow for this.

### 4. Self-evaluation

- **Log (exists).** `core/simulation/closed_loop/protocols/evidence/forecast_ledger.py` already stores every issued forecast with its
  target time, city, corridor, horizon and model.
- **To change.** Today it scores only Dhaka, only against the Google recording, and skips speed forecasts. It will
  score any city against the later `probes` reading for the same corridor and 5-minute bin, in the city's own speed
  unit from its config.
- **What the app shows, per city, over the last 7 days:** mean absolute error per horizon; skill against "the speed
  stays what it is now"; how often the truth fell inside the 90 % band; and how many pairs and phones that rests on.
- **The statement shown with it:** "Accuracy is measured against speeds from phones that opted in on these roads. It
  is not an independent ground truth." Where a secondary provider is ever used: "…against the data provider's speeds".
- **Too little data:** "No data for this city yet" with the count so far, never a number from another city.
- Served by the existing `GET /api/forecast/{city_id}/scoreboard`; shown on the City page.

### 5. Fit with the existing architecture

| Item | Plan |
|---|---|
| Backend modules changed | `probes/` (road matching on our network, corridor speeds), `data/live_providers/observatory.py` (rows with provider `probes`), `data/city_config.py` (`live.corridors`), `data/city_map.py` (forecast from the city's own series), `protocols/evidence/forecast_ledger.py` (scoring for any city), `forecasting/evaluation/conformal.py` (reused for the rolling band) |
| Reused unchanged | Chronos adapters, model registry, `city_corridors.py`, the probe endpoints and tables |
| API routes | No new route. Changed behaviour only: `/api/forecast/{city_id}`, `/api/forecast/{city_id}/scoreboard`, `/api/city/{id}/map`. The pinned route list stays as it is |
| Frontend | Existing `forecast` feature folder (a panel in the corridor view); new strings in `frontend/src/i18n/locales/en.json` and `bn.json`; no new folder, so the feature-folder test is unchanged |
| Data, results, evidence | Corridors in `config/cities/`; history in `results/live/` (not tracked); a weekly accuracy record per city in `evidence/live_forecast/<city_id>/` |
| Third party | Chronos-2 weights (already used); its licence and exact revision to be recorded in `third_party/SOURCES.md` before this ships. No provider SDK added |
| Where it runs | Laptop or the app host, CPU. No GPU, no AWS job |
| Tests | Corridor speed from cells (gaps stay gaps; fewer than the minimum phones gives no reading); no provider-derived row is ever scored or learned from; a forecast needs 8 readings; scoring joins on corridor and bin; the band appears only at 200 pairs; "no data for this city" when empty; strings exist in both languages |
| Depends on | The city layer (configs and corridors). Nothing depends on a provider's answer |

### 6. Hours

Ten hours, lean:

| Work | Hours |
|---|---|
| Corridors in the city config; each corridor's cell path from the city's own network | 1.5 |
| Road matching on our network; corridor speed every 5 minutes into the history store | 2.5 |
| Chronos-2 forecast per corridor for any city; forecasts logged in the city's speed unit | 1.5 |
| Scoring against later phone readings over 7 days; rolling 90 % band | 2.0 |
| City page panel and both languages | 1.5 |
| Tests, evidence record, README commands | 1.0 |
| **Total** | **10.0** |

Left out of the 10 hours, on purpose: the OpenCity-plus daily batch, the DynamoDB table (it belongs with AWS hosting),
any Amazon sampling (paused), and anything that would produce data by itself. **Ten hours build the pipeline; they do
not create observations.** With 10 stored phone positions today, every city will say "no data for this city yet" until
people use the sensing. Showing a working forecast in a demo needs either real opted-in trips on a corridor or a public
trajectory dataset replayed through the same endpoint and labelled as such; choosing one is a decision for the owner.

**Where it sits in the budget.** It is its own 10-hour line in section 5. It replaces the assumption, in the twin and
integration phases, that a provider feeds a "live" city: for Dhaka that feed does not exist.

### Sources read

| What | Where | Read |
|---|---|---|
| AWS Service Terms, section 82 (dated 1 October 2026) | https://aws.amazon.com/service-terms/ | 2026-10-04 |
| Amazon Location data quality and coverage (route and traffic tables) | https://docs.aws.amazon.com/location/latest/developerguide/data-quality.html | 2026-10-04 |
| Amazon Location Routes pricing buckets | https://docs.aws.amazon.com/location/latest/developerguide/routes-pricing.html | 2026-10-04 |
| Amazon Location, DynamoDB prices for ap-south-1 | AWS Price List API (publication date 2026-09-11 for Amazon Location) | 2026-10-04 |
| Amazon Location request rate quotas | AWS Service Quotas, this account | 2026-10-04 |
| Amazon Location free tier ("10,000 Routes … for 3 months") | https://aws.amazon.com/location/pricing/ | 2026-10-04 |
| TomTom pricing (free monthly allowances) | https://docs.tomtom.com/pricing | 2026-10-04 |
| TomTom Traffic API market coverage | https://docs.tomtom.com/traffic-api/documentation/tomtom-maps/v1/product-information/market-coverage | 2026-10-04 |
| TomTom Portal Terms and Conditions, clauses 11.4 and 11.6 | https://docs.tomtom.com/legal/terms-and-conditions | 2026-10-04 |
| Google Maps Platform Terms of Service (last modified 26 August 2026), 3.2.3 | https://cloud.google.com/maps-platform/terms | 2026-10-05 |
| Google Maps Platform Service Specific Terms (last modified 10 June 2026), section 19 | https://cloud.google.com/maps-platform/terms/maps-service-terms | 2026-10-05 |

Not verified: whether TomTom marks Flow Segment Data as "deprecating soon" (the pricing page has such a list, but its
entries did not load in the text I read); the TomTom price above the free allowance; the DynamoDB expiry feature's own
cost. This is a reading of published terms by a non-lawyer, not legal advice.
