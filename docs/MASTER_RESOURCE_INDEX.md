# MASTER_RESOURCE_INDEX — DhakaFlow Nexus

Project-wide map from every lab to its papers, repositories, datasets, tools,
checkpoints, services and documentation. Per-lab detail lives in each lab's
`RESOURCE_MANIFEST.md` / `.yaml` (mandatory from Lab 02 onward; Labs 00–01
predate the rule — their provenance is recorded in the per-lab docs cited
below and consolidated here).

Classification: USED · VERIFIED_NOT_USED · OPTIONAL · FUTURE · REJECTED.
Rule: a lab may not PASS if a CORE resource was only mentioned but never
fetched/pinned/audited/used.

---

## Lab 00 — UTD19 / MFD foundation (PASS, frozen)

| Resource | Type | Pin / provenance | Class |
|---|---|---|---|
| Loder et al. 2019, *Understanding traffic capacity of urban networks* (MFD/critical point) | primary paper | archived in `paper_labs/00_utd19/` docs | USED |
| **UTD19 dataset** | dataset | ETH Research Collection **DOI `10.3929/ethz-b-000437802`** (DSpace REST); landing https://utd19.ethz.ch/ (free registration, e-mailed link); `utd19_u.csv` 6,978.6 MB + `detectors_public.csv` 2.6 MB + `links.csv`; 39 distinct city labels observed vs 40 listed (documented); stored on Drive `DhakaFlow-Nexus-Data/Lab00_UTD19/raw/` | USED |
| DuckDB (out-of-core aggregation) | tool | pip pin in lab notebook | USED |
| Frozen result | artifact | torino k\*=31.9–33.0 veh/km/lane, q\*=1104–1266 veh/h/lane, `UNCALIBRATED_ANALYSIS`; regression fixture only — **not** a Dhaka threshold | USED |
| Amazon Location / OSRM speed calibration | service | deferred backlog variant | FUTURE |

Docs: `paper_labs/00_utd19/{DATA_SPEC,METHOD_SPEC,REPRODUCTION_*}.md`

## Lab 01 — SUMO control foundation (PASS, frozen @ `ca2ac81`)

| Resource | Type | Pin / provenance | Class |
|---|---|---|---|
| Alvarez Lopez et al. 2018, SUMO | primary paper | DOI `10.1109/ITSC.2018.8569938`; PDF + sha256 in `paper_labs/01_sumo_foundation/paper/CITATION.bib` | USED |
| Bieker et al. 2014, Bologna scenario | scenario paper | DOI `10.1007/978-3-319-15024-6_4`; PDF archived | USED |
| Varaiya 2013, Max-pressure control | theory paper | DOI `10.1016/j.trc.2013.08.014` | USED |
| **Eclipse SUMO** | official software | `github.com/eclipse-sumo/sumo` tag `v1_27_1` = `7717f2379d9e314a0c81c5cec748444de06a2a91`, pip `eclipse-sumo==1.27.1`, EPL-2.0; `OFFICIAL_IMPLEMENTATION_USED`, never patched | USED |
| **Eclipse SUMO source (tools + docs)** | official software | `github.com/eclipse-sumo/sumo` tag `v1_27_1` = `7717f2379d9e314a0c81c5cec748444de06a2a91`, sparse checkout at `~/.dhakaflow/upstream/sumo` (tools/, docs/web/docs/); EPL-2.0. Reused process: `tools/osmWebWizard.py`, `tools/osmBuild.py`, `tools/randomTrips.py`, `tools/assign/duaIterate.py`, docs Demand/Automatic_Routing, Demand/Dynamic_User_Assignment, Simulation/Routing, Simulation/Rerouter, TraCI. Manifest: `pipeline/city/RESOURCE_MANIFEST.md` | USED |
| **DigitalTwin_GenevaMotorway** (Kušić et al. 2023, AEI 55:101858) | digital-twin reference | `github.com/SiLab-group/DigitalTwin_GenevaMotorway` @ `5d2f6c2`, local `~/.dhakaflow/upstream/GenevaMotorway`; GPL-3.0. Reused process: SCENARIO-II minute-resolution flow inputs → SUMO calibrators → runtime demand (`DT_GM_workday_dynamic_flow.py`, `functions_DT_GE_live24h.py`); their network/data not redistributed | USED (process) |
| **Bologna/Acosta official scenario** | benchmark | `github.com/DLR-TS/sumo-scenarios` @ `00f6eb479a9dc0fbaeb731495c11d48d7a9661d3`, run **unmodified** (`OFFICIAL_SCENARIO_EXECUTION`, exit 0) | USED |
| Locks | provenance | `upstream/UPSTREAM_LOCK.yaml`, `EV/verification_record.json` | USED |

Docs: `paper_labs/01_sumo_foundation/{PAPER_TO_CODE_MAP,REPRODUCTION_CLASSIFICATION,CITATION.bib}`

## Sprint A — dhakaflow platform (frozen @ `563b10f`)

Shared interfaces only (no external algorithms): `dhakaflow/` 13 modules,
`docs/PLATFORM_ARCHITECTURE.md`, `docs/GRADUATION_MAP.md`, platform tests.

## Lab 02 — Real Dhaka network + geospatial validation + live reference (PASS @ `6936ea9`)

Full detail: `paper_labs/02_dhaka_osm/RESOURCE_MANIFEST.{md,yaml}` · literature audit: `LITERATURE_SELECTION_GATE.md`

| Resource | Type | Pin / provenance | Class |
|---|---|---|---|
| Boeing 2025, OSMnx reference paper | primary paper | DOI `10.1111/gean.70009`, arXiv `2505.00736` | USED |
| **OSMnx** | official software | `github.com/gboeing/osmnx` `v2.1.1` = `2fc39cb2792ff869881b99f724a2d97f0e958667`, MIT | USED |
| **Eclipse SUMO 1.27.1** | official software | same pin as Lab 01 (version-identity verified locally) | USED |
| **OSM snapshots R1–R5 (Overpass)** | dataset | ODbL 1.0; five checksummed snapshots 2026-08-13 (R1 product: sha256 `d854b26a…`); manifests in `results/candidates/` | USED |
| Boeing 2017 (original OSMnx paper) | context paper | DOI `10.1016/j.compenvurbsys.2017.05.004` | OPTIONAL |
| **Google Routes API** | external API | docs + semantics verified; adapter `GoogleRoutesReference` mock-tested; ENV `GOOGLE_MAPS_API_KEY` (name only); DECISION 1: no content persisted | VERIFIED_NOT_USED |
| Google Roads API | external API | adapter shape reserved; speed-limit-as-truth rejected | FUTURE |
| osmWebWizard · Geofabrik `.pbf` · Google tiles · live-traffic-as-calibration | alternatives | reasons in manifest §R-07 | REJECTED |

## Labs 03–27 — pending

Each lab's `RESOURCE_MANIFEST.md/.yaml` is created from **fresh web research
before execution** (permanent rule, 2026-08-13). Planned CORE resources whose
official repositories must be fetched/pinned/reproduced when their lab starts:
RT-DETR (Lab 04), ByteTrack (Lab 05), DCRNN / Graph WaveNet / STID /
STAEformer / Chronos-2 (Labs 07–12), SUMO-RL / PressLight / FRAP / CoLight /
MAPPO (Labs 15–19), URB/RouteRL challengers (Lab 27). Links are deliberately
NOT listed here yet — they will be verified at lab start, not quoted from
memory (no invented links).

## Assistant (LIFE OS) — approvals, audit, planning

| Resource | Type | Pin / provenance | Class |
|---|---|---|---|
| **OpenMuse (tahodev)** — exact-action approvals, hash-chained audit with signed checkpoints | official software | `github.com/tahodev/openmuse` @ `e39abd62fc61` (docs/life_os_pins.json); design adapted in `backend/app/agent/approvals.py`, `audit.py` | USED (design) |
| **OpenAI Agents SDK** — `needs_approval` predicate, always-approve/reject, rejection message | official software | `github.com/openai/openai-agents-python` @ `7b27134b2da9`; adapted in `approvals.py`, `tools.py`, `orchestrator.py` | USED (design) |
| **OpenMuse (CopilotKit)** — reviewable plan before it runs, action review, receipts | official software | `github.com/CopilotKit/openmuse` @ `6151b4e47543`; followed by the proposed-goal flow | USED (design) |

## Pinned for later gates (2026-09-29)

| Resource | Type | Pin / provenance | Class |
|---|---|---|---|
| UniST (KDD 2024), RAST | cross-city / retrieval forecasting | `upstream/UPSTREAM_PINS.yaml` | FUTURE |
| LargeST (NeurIPS 2023 D&B) | large-scale benchmark | `upstream/UPSTREAM_PINS.yaml` | FUTURE |
| MAPIE | conformal prediction intervals | `upstream/UPSTREAM_PINS.yaml` | FUTURE |
| OpenTripPlanner, Valhalla (+ docker-valhalla) | multimodal / self-hosted routing, map matching | `upstream/UPSTREAM_PINS.yaml` | FUTURE |
| Map-Matching (HMM reference) | phone probe traces → corridor speeds | `upstream/UPSTREAM_PINS.yaml` | FUTURE |
| RL_signals_CityFlow, smart-traffic-rl | RL signal control references | `upstream/UPSTREAM_PINS.yaml` | FUTURE |
| SUMO-V2X platooning & CIM | V2X worked example | `upstream/UPSTREAM_PINS.yaml` | FUTURE |
| DCRNN, Graph WaveNet, STID, STAEformer, Eclipse SUMO, sumo-rl, LibSignal, Eclipse MOSAIC, OpenCity | already pinned in earlier labs | see the lab sections above and `UPSTREAM_PINS.yaml` | USED / PINNED |

