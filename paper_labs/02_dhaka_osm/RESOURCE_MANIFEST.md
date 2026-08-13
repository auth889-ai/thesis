# RESOURCE_MANIFEST — Lab 02 (Real Dhaka Network + Geospatial Validation + Live External Reference Foundation)

Machine-readable twin: `RESOURCE_MANIFEST.yaml`.
Verification date: **2026-08-13** — all pins below were checked against primary
sources (PyPI JSON API, GitHub API, publisher pages, official API docs) during
the Lab 02 literature gate; nothing is quoted from memory. Fields that do not
exist for a resource are marked N/A; genuinely unavailable resources would be
marked NOT PUBLICLY AVAILABLE (none in this lab).

Classification legend: USED · VERIFIED_NOT_USED · OPTIONAL · FUTURE · REJECTED.

---

## R-01 · Eclipse SUMO 1.27.1 (netconvert, sumo, sumo-gui, duarouter, randomTrips, sumolib, TraCI) — **CORE, USED**

| Field | Value |
|---|---|
| Primary paper | Alvarez Lopez et al., *Microscopic Traffic Simulation using SUMO*, IEEE ITSC 2018, DOI `10.1109/ITSC.2018.8569938` (PDF archived: `../01_sumo_foundation/paper/AlvarezLopez2018_SUMO_ITSC.pdf`, sha256 in `../01_sumo_foundation/paper/CITATION.bib`) |
| Supplementary material | N/A (tool paper; docs serve this role) |
| Author/project page | https://eclipse.dev/sumo/ (DLR project) |
| Official repository | `github.com/eclipse-sumo/sumo` — **fetched, pinned, used** (binary wheel; never vendored/patched) |
| Exact commit/tag | tag `v1_27_1` = SHA `7717f2379d9e314a0c81c5cec748444de06a2a91`; installed via pip `eclipse-sumo==1.27.1`; local `sumo --version` verified = 1.27.1, identical to the Lab 01 Colab pin |
| Official documentation | https://sumo.dlr.de/docs/ (netconvert options incl. `--lefthand`, TraCI, duarouter, randomTrips) |
| Official dataset | N/A (consumes OSM; see R-03) |
| Pretrained weights | N/A |
| Official configs | netconvert typemap `data/typemap/osmNetconvert.typ.xml` from the installed wheel — USED (path recorded in `results/lab02_v2/netconvert_record.json`) |
| Preprocessing scripts | official `netconvert` — USED (full command + warnings recorded) |
| Training scripts | N/A |
| Evaluation scripts | official `sumo --tripinfo-output/--summary-output` + `sumolib` — USED |
| Visualization scripts | `sumo-gui` (XQuartz) — USED for `sumo_gui_dhaka.png` via TraCI `gui.screenshot` |
| Environment/requirements | pip `eclipse-sumo==1.27.1`, Python 3.13.9 |
| Docker/container | official `docker.io` images exist — VERIFIED_NOT_USED (local wheel is version-identical to the Lab 01 pin) |
| Official benchmark | Bologna/Acosta scenario (`DLR-TS/sumo-scenarios` @ `00f6eb479a9dc0fbaeb731495c11d48d7a9661d3`) — USED in Lab 01, not needed here |
| Errata/issues | netconvert OSM-import warning classes handled explicitly in `src/network/build.py::WARNING_PATTERNS` |
| Tutorials | https://sumo.dlr.de/docs/Tutorials/ — consulted, OPTIONAL |
| License/terms | EPL-2.0 (with GPL exceptions) |
| DhakaFlow adapter path | `src/network/build.py`, `src/demand/generate.py`, `src/platform_adapter.py` (`SumoDhakaBackend` → `dhakaflow.simulation.SimulationBackend`) |
| Experiment artifacts | `outputs/lab02_v2/network/dhaka_r1.net.xml` (sha256 `06194df0…`), `results/lab02_v2/netconvert_record.json`, `results/lab02_v2/gate_record.json` |

## R-02 · OSMnx 2.1.1 — **CORE, USED**

| Field | Value |
|---|---|
| Primary paper | Boeing (2025), *Modeling and Analyzing Urban Networks and Amenities with OSMnx*, Geographical Analysis 57(4):567–577, DOI `10.1111/gean.70009`, open access |
| Supplementary material | arXiv `2505.00736` (preprint mirror) |
| Author/project page | https://osmnx.readthedocs.io/ · https://geoffboeing.com/ |
| Official repository | `github.com/gboeing/osmnx` — **fetched (pip), pinned, used** |
| Exact commit/tag | tag `v2.1.1` = SHA `2fc39cb2792ff869881b99f724a2d97f0e958667`; installed `osmnx==2.1.1` (requires Python ≥3.11; running 3.13.9) |
| Official documentation | https://osmnx.readthedocs.io/en/stable/ (`graph_from_xml`, `k_shortest_paths`, `project_graph`, `nearest_nodes`) |
| Official dataset | N/A (consumes OSM; see R-03) |
| Pretrained weights / configs / training | N/A (analysis library) |
| Preprocessing | `ox.graph_from_xml(..., simplify=True)` on the SAME archived snapshot (single-snapshot rule) — USED |
| Evaluation scripts | library functions via `src/analysis/osmnx_graph.py` — USED |
| Visualization | `ox.plot_graph` — USED (`raw_osm_graph.png`) |
| Environment | `osmnx==2.1.1`, `networkx==3.6.1` (BSD-3) |
| Docker | N/A |
| Benchmark/baselines | Boeing (2017) CEUS 65:126–139, DOI `10.1016/j.compenvurbsys.2017.05.004` — context-only BASELINE, cite A1 for the software |
| Errata/issues | none material for `graph_from_xml` at this pin |
| License | MIT |
| DhakaFlow adapter path | `src/analysis/osmnx_graph.py`, `src/analysis/cross_validate.py` |
| Experiment artifacts | `results/lab02_v2/osmnx_metrics.json`, `osmnx_routes.json`, `cross_validation.json` (+ `_explanations.json`) |

## R-03 · OpenStreetMap via Overpass API — **CORE DATASET, USED**

| Field | Value |
|---|---|
| Source | OpenStreetMap contributors, queried through the Overpass API |
| Download page / endpoints | `overpass-api.de/api/interpreter` (used for all 5 snapshots) + verified mirrors `overpass.kumi.systems`, `overpass.private.coffee`, `overpass.osm.jp` (rotation on 429/504; endpoint recorded per manifest) |
| Dataset paper | N/A (community dataset; OSM wiki documents the model) |
| Official documentation | https://wiki.openstreetmap.org/wiki/Overpass_API (+ Overpass QL reference) |
| Version | live database snapshots, versioned by download timestamp + bbox + exact query string (all recorded in each manifest) |
| Checksums / sizes / dates | R1 `d854b26a8bb014ba123e870f560cfca3562307a0a74eca3b2188d57c48916654` (1,626,102 B) · R2 `6115382d…` · R3 `59080949…` · R4 `a9f12bf5…` · R5 `8c97f5f2…` — all 2026-08-13, full values in `results/candidates/R*_manifest.json` |
| Split | N/A (one snapshot per candidate region; R1 is the product, R2–R5 archived for Lab 26) |
| License | **ODbL 1.0** (© OpenStreetMap contributors; attribution carried in every manifest) |
| Preprocessing | Branch B: netconvert options in `src/network/build.py::NETCONVERT_OPTIONS`; Branch A: OSMnx `graph_from_xml` + vehicular-class filter; context census (bus stops/routes, hospitals, surveillance, crossings) from the SAME snapshot |
| Rate limits | public instances throttle (429/504 observed in earlier runs) — handled by mirror rotation, `attempts_per_mirror=2` |
| Classification | USED |
| Artifacts | `outputs/lab02_candidates/R*/R*.osm` (gitignored, checksummed), `results/candidates/decision_table.{json,csv}` |

## R-04 · Google Routes API (`computeRoutes`) — **EXTERNAL_LIVE_REFERENCE, VERIFIED_NOT_USED**

| Field | Value |
|---|---|
| Provider / purpose | Google Maps Platform — independent live travel-time reference (`EXTERNAL_LIVE_REFERENCE`; never ground truth, never a calibration target in Lab 02) |
| Official docs | https://developers.google.com/maps/documentation/routes (endpoint `https://routes.googleapis.com/directions/v2:computeRoutes`) |
| Verified semantics | `TRAFFIC_UNAWARE` / `TRAFFIC_AWARE` / `TRAFFIC_AWARE_OPTIMAL` (highest accuracy + highest latency); response fields `duration`, `staticDuration`, `distanceMeters`; **field mask required** — ours deliberately excludes polylines |
| Pricing/billing | requires a Google Cloud project with billing enabled; per-request pricing (Routes API tier) |
| Rate limits | per-project QPS quotas (Cloud console); irrelevant while unexecuted |
| Terms/storage restrictions | caching of Maps Content restricted; only place IDs exempt; attribution required when displayed. **User DECISION 1 (stricter, enforced in code):** no raw responses, polylines, durations or distances persisted in git or as permanent Drive evidence; in-memory only; metadata + derived booleans persistable |
| API credential/signup | https://console.cloud.google.com/ → enable "Routes API" → API key. Secret ENV VAR NAME: `GOOGLE_MAPS_API_KEY` (name only — see `SECRETS_MANIFEST.md`; never store values) |
| DhakaFlow adapter path | `dhakaflow/common/live_reference.py` (protocol) + `src/live_reference/google_routes.py` (provider; mock-transport tested) |
| Experiment artifacts | `results/lab02_v2/gate_record.json::live_reference` = `READY_NOT_EXECUTED` |
| Classification | VERIFIED_NOT_USED (interface proven with mock; no key in env; PASS does not depend on it) |

## R-05 · Google Roads API (snap-to-road / speed limits) — **FUTURE (design only)**

Docs: https://developers.google.com/maps/documentation/roads. Adapter *shape*
reserved for future GPS sources; **not invoked** (no GPS data exists yet); its
speed-limit endpoint is REJECTED as a real-time truth source (posted limits ≠
observed speeds). Classification: FUTURE (adapter shape) / REJECTED (speed-limit-as-truth).

## R-06 · Supporting environment — USED

`networkx 3.6.1` (BSD-3; SCC/WCC, betweenness, shortest paths) · `matplotlib`
(figures) · `PyYAML` (configs) · Python 3.13.9 · XQuartz (sumo-gui capture).
All orchestration code is ours and only *translates*; no algorithm was
re-implemented (official-implementation policy).

## R-07 · Rejected alternatives (recorded with reasons)

| Resource | Classification | Reason |
|---|---|---|
| `osmWebWizard` (SUMO) | REJECTED | GUI convenience wrapper hides the netconvert options we must pin and audit |
| Geofabrik `.pbf` + osmium clipping | REJECTED (revisit if Overpass blocks) | Overpass gives an exact reproducible bbox query string |
| Google map tiles/geometry as network source | REJECTED | licence-incompatible with an OSM-derived redistributable network |
| Live traffic as Lab 02 calibration target | REJECTED | calibration is Lab 13, from camera-derived measurement |

---

**CORE-resource PASS check:** SUMO 1.27.1 (fetched+pinned+used), OSMnx 2.1.1
(fetched+pinned+used), OSM snapshots (downloaded+checksummed+used) — no CORE
resource is merely linked. Lab 02 PASS stands under the resource-traceability rule.
