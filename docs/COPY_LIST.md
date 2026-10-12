# Copy list for the final 50 hours

Written 2026-10-06 for the final plan in `docs/HANDOFF.md`. For every remaining item: the code and data to start
from, so that no step starts from nothing.

**Rules for every entry (owner, 2026-10-06):**
- Read the licence and record it in `third_party/SOURCES.md` **before** use: URL, commit or version, licence, paper,
  files used or changed.
- MIT, Apache or BSD → reuse code with credit. GPL → separate tool only, nothing copied. No licence → ideas only.
- Reproduce the source's own example unchanged first; report our number next to the published one.
- Licence states below were checked on 2026-10-06 from the repository files or GitHub's licence field. "To read"
  means the text itself has not been read in this session.

## Already in use (credit kept in `third_party/SOURCES.md`)

| Source | Licence | Recorded? | Used by |
|---|---|---|---|
| Eclipse SUMO and its tools (`traceExporter`, `routeSampler`, `randomTrips`, the bluelight device) — https://github.com/eclipse-sumo/sumo | EPL-2.0 (`LICENSE`, `NOTICE.md`) | yes (tag `v1_27_1`, `7717f237…`; two entries) | the city pipeline, the Dhaka calibration, the ambulance phase; item 2's movement export; item 4's sweep |
| adaptive-traffic-signal-rl — https://github.com/Adityakumar1805/adaptive-traffic-signal-rl | MIT | yes (`b62436b5…`, "Ambulance alert phase") | preemption override in the ambulance sweep (item 4 reruns it) |
| Vehicle shapes — https://github.com/karthiksenv/real-time-digital-traffic-simulation | MIT | yes (`f8ef3592…`) | the 3D City page (items 1, 5, 7) |
| DhaTraX — https://zenodo.org/records/22157752 | CC BY 4.0 | yes ("Recorded real data") | the Dhaka calibration, vehicle mix, recorded replay; item 8 cites it under every Dhaka table |
| Overture Maps — https://docs.overturemaps.org | ODbL | yes (buildings and divisions) | 3D buildings and Add city (item 1's "zoom in to see 3D buildings" note describes this layer) |
| OpenFreeMap — https://openfreemap.org | MIT project; OpenStreetMap data, ODbL; credit line required | yes | every map page |
| Chronos-2 — https://github.com/amazon-science/chronos-forecasting | Apache-2.0 | yes ("Forecasting model"); **no published number reproduced yet** (rule 3 outstanding, noted there) | the home's forecast; item 8 must label its backtest as our own measurement |

## Item 1 — App structure (6 h)

Nothing new to copy. Start from: `frontend/src/app/AppShell.tsx`, `LabShell.tsx`, `routes.tsx`; the feature folders
`twin` (3D City), `today` (Home), `results` (Research), `mobility`. LIFE OS folders (`goals`, `plan`, `you`,
`activity`, `assistant`) stay in the tree, only their menu entries go. The 200-line limit per frontend file and the
pinned route list (`backend/tests/fixtures/api_routes_pre_structure.json`) apply. All menu labels and the note go
through `frontend/src/i18n/locales/`.

## Item 2 — Mesh (6 h)

| Source | Licence | Class | Record before use | Start from |
|---|---|---|---|---|
| PONS (`pons-dtn`) — https://github.com/gh0st42/PONS. Routers: Epidemic, Spray and Wait, PRoPHET | MIT (`LICENSE`, © 2024 Lars Baumgärtner; PyPI classifier) | separate tool, installed from pip, **unchanged** | **Not yet in `third_party/SOURCES.md`** — add: pip `pons-dtn==0.2.1` (`research/mesh_pons/evidence/pip_freeze.txt`), upstream commit `2fd70381b1b02e3e2227b5e596dc7fd92f458893` (`evidence/upstream_commit.txt`), MIT, no paper (the README names the ONE as its model) | `research/mesh_pons/`: `scripts/01_run_upstream_example.sh` (its own example, run unchanged: `evidence/upstream_sim.log`), `02_export_movement.py`, `03_run_pons.py`, `configs/dhaka.yaml`, 10 run files in `evidence/runs/` (epidemic seeds 1–5 and more) |
| Movement from SUMO, `tools/traceExporter.py --ns2mobility-output` | EPL-2.0 (SUMO) | tool | covered by the SUMO entry; add the tool's name to "What we use" | `research/mesh_pons/work/dhaka.ns2.tcl`, `evidence/export_movement.log` |
| The ONE simulator's default Bluetooth range (10 m), cited as the radio parameter | GPLv3 (`LICENSE.txt`: "released under the GPLv3"); its Helsinki map data is not GPL and is not used | ideas and a cited value only; no code | add as a cited value with the line reference already in `configs/dhaka.yaml` | `research/mesh_pons/configs/dhaka.yaml`, `radio.source` |

Known adapter fact to carry into the app text: PONS's own ns-2 reader divides by speed and fails on a stopped
vehicle (`evidence/ns2_reader_failure.log`); `03_run_pons.py` translates the trace lines one-to-one instead and
changes no PONS code. The app shows the results as SIMULATED, per city, with router, seed and window from the config.

## Item 3 — SOS demo (6 h)

`research/sos/` **does not exist** on 2026-10-06 05:41. When it does, its files are the start; until then, the
design in `docs/ARCHITECTURE_PLAN.md`, "Phase 2 — crash SOS demo" (emergency numbers only from the city config,
shown and never dialled; TEST mode; test contacts; cancel window; position kept 24 h).

| Source | Licence | Class | Record before use | Start from |
|---|---|---|---|---|
| Browser motion sensor, MDN — https://developer.mozilla.org/en-US/docs/Web/API/DeviceMotionEvent | MDN prose CC-BY-SA 2.5, code samples CC0 (MDN's "About" page; to read and cite) | reference; the API is the browser's | yes, as a documentation entry with the date read | `frontend/src/features/mobility/` ("Your phone is the sensor") |
| Browser location, MDN — https://developer.mozilla.org/en-US/docs/Web/API/Geolocation_API | same | same | same | `backend/app/probes/` already receives positions with hashed device ids |
| AccidentDetectionApp — https://github.com/omkarmagdumwork/AccidentDetectionApp (Android, Java; accelerometer and sound; one-tap calling) | **None** (no licence file; GitHub reports none; commit `b998235e…`) | **ideas only** — and its one-tap calling is the opposite of our rule (numbers shown, never dialled) | record as "ideas only, nothing copied" | — |
| Crash detection data | none chosen (`docs/proposals.md`, "From the copy-first audit", item 2) | — | — | the demo uses a jolt threshold on the phone's own sensor and says so; no model, no published result claimed |

## Item 4 — 4G in the ambulance sweep (2 h)

| Source | Licence | Class | Record before use | Start from |
|---|---|---|---|---|
| Xu, Li, Zhao, Zhang, Wang, "DSRC versus 4G-LTE for Connected Vehicle Applications", J. Advanced Transportation 2017, https://doi.org/10.1155/2017/2750452 | CC BY (Hindawi; to confirm from the PDF's own licence line) | cited values only | yes: the PDF's sha256, the page and table each value comes from, its licence line | `core/networking/v2x/configs/network_model.yaml` line 58 (`value: null  # NO SOURCE READ`) and the "Not read" row in `third_party/SOURCES.md`; `core/networking/v2x/model.py`; the sweep runner from Phase 1 |

The session cannot read the owner's Downloads folder (macOS refuses it). **The owner copies the PDF to a readable
path** (for example `research/networking/sources/`, untracked) before this item starts. The sweep reruns only the
4G rows with the same seeds and pairing rule as Phase 1; results go beside `evidence/emergency/dhaka/`.

## Item 5 — Translation of Home and 3D City (2 h)

Nothing to copy. Start from `frontend/src/i18n/`, the existing placeholder test, and `docs/BANGLA_REVIEW.md` (253
machine-written strings awaiting review; new ones are appended there).

## Item 6 — Minimal hosting (6 h)

Nothing to copy. Start from `infra/api.Dockerfile`, `infra/docker-compose.yml`, `infra/service.yaml`, and the hosted
mode decided in `docs/ARCHITECTURE_PLAN.md` ("Story mode and hosting"). Before launch: instance type, hours and cost
stated and approved; tags `project=dhakaflow`, `phase=hosting`; ap-south-1; shutdown at the end; the instance listed
at the end of every session.

## Item 7 — Story mode (4 h)

Nothing to copy. Start from the shell (`frontend/src/app/`) and `frontend/src/components/Steps.tsx`; text in both
languages through i18n.

## Item 8 — Results pack (5 h)

| Source | Licence | Class | Record before use | Start from |
|---|---|---|---|---|
| traffic-digital-twin — https://github.com/Uzumaki-Chethan/traffic-digital-twin (commit `027158d5…`, 0 stars, pushed 2026-10-05) | **None** (no licence file; GitHub reports none) | **ideas only**: the look of a results page, nothing copied | record as "ideas only" | — |

Start from `results/` (`forecasting/`, `networking/`, `emergency/`), `evidence/`, and the Evidence page in
`frontend/src/features/results/`. Every table and figure names its city, dataset, run log and output hash; a result
with no evidence entry is not shown.

## Item 9 — Buffer; PeMS if the account arrives (2 h of 3)

Caltrans PeMS: the terms shown after login must be read and recorded first (`docs/HANDOFF.md`, open decision 2).
Start from the 24 matched stations in `evidence/home/los_angeles/station_matching.json` and
`core/common/data/station_matching.py`.

## Future work only — not built now (`docs/proposals.md`)

| Source | Licence | If ever used |
|---|---|---|
| ChatSUMO-Agent — https://github.com/ChrisLi1221/ChatSUMO-Agent | MIT (already in `SOURCES.md` as "Nothing yet") | code with credit; its planner swapped for ours; every number still from a saved SUMO run |
| A/B Street — https://github.com/a-b-street/abstreet | Apache-2.0 | separate tool or ideas (Rust) |
| The ONE simulator — https://github.com/akeranen/the-one | GPLv3 | separate tool only; its Helsinki map data is not GPL and is excluded |
| DRINF — https://huggingface.co/datasets/hamimmahmud0/DRINF | CC BY 4.0 (stated by the owner; to read on the dataset card) | data with credit |
| WorldTrace — https://huggingface.co/datasets/OpenTrace/WorldTrace | ODbL (stated by the owner; to read on the dataset card) | data with credit and share-alike noted; the coverage notebook is written and not run |
| Google Photorealistic 3D Tiles, ns-3, Ask the city, Edit your street, full user study | see `docs/COPY_FIRST_AUDIT.md` and `docs/proposals.md` | — |
