# Lab 02 — REPRODUCTION_REPORT

**Lab:** 02 — Real Dhaka Network + Geospatial Validation + Live External Reference Foundation
**Status:** PASS (see gate table) · **Date executed:** 2026-08-13 · **Machine:** local Mac (lightweight only, per resource policy)
**Classification:** FOUNDATION_VALIDATION (network construction with official tools) + DHAKAFLOW_ADAPTATION (platform wiring). No paper metric is reproduced in this lab; the "reproduction" object is the *official toolchain behaviour* itself.

## 1. What was executed

1. **Five pre-registered candidate regions** (R1–R5, frozen in `src/regions.py` before measurement) each measured with the identical pipeline by `scripts/measure_candidates.py`: one Overpass snapshot per candidate (network **and** context features in the same snapshot — single-snapshot rule), OSMnx 2.1.1 analysis graph (Branch A), `netconvert --lefthand` SUMO network (Branch B), and the eight pre-registered criteria C1–C8. No candidate was pre-selected (user DECISION 2).
2. **Selection:** R1 (Farmgate–Karwan Bazar–Bangla Motor–Shahbagh) — total score 22/24, leads C1 outright (17 TLS vs runner-up 9), so the tie-break chain was never reached; the C5 tie-breaker (future camera availability) independently favours R1. Full table with scoring bands: `REGION_SELECTION.md`; raw numbers: `results/candidates/decision_table.{json,csv}`.
3. **Full v2 pipeline on R1** (`scripts/run_lab02_v2.py`): checksum-verified frozen snapshot → dual construction → all v1 gates (validation, left-hand, lane/TLS/turn audits, representative routes) → Branch A metrics/routes/centrality → X1–X12 cross-validation → seeded synthetic demand → deterministic 3600 s SUMO run → platform scenario + live-reference status.
4. **Figures** (`scripts/make_lab02_figures.py`, `scripts/capture_sumo_gui.py`): 15 planned figures + 2 junction zooms rendered from the machine-readable audit artifacts; `sumo_gui_dhaka.png` is a real sumo-gui frame (XQuartz) of the running scenario at t=900 s. `live_external_reference.png` intentionally absent (not executed).

## 2. Provenance (exact)

| Item | Value |
|---|---|
| OSM snapshot (R1, product) | `outputs/lab02_candidates/R1/R1.osm`, sha256 `d854b26a8bb014ba123e870f560cfca3562307a0a74eca3b2188d57c48916654`, 1 626 102 bytes, downloaded 2026-08-13T12:09:32Z from `https://overpass-api.de/api/interpreter`, ODbL 1.0 |
| Candidate snapshots R2–R5 | sha256 in `results/candidates/R*_manifest.json` |
| SUMO network | `dhaka_r1.net.xml`, sha256 `06194df039740fa2ceb0bcb2c438444efd755f26e0f863327f0e1d6524775dcb`, 17 176 962 bytes; full netconvert command in `results/lab02_v2/netconvert_record.json` |
| Toolchain | Eclipse SUMO 1.27.1 (pip, byte-identical version to Lab 01 Colab pin) · OSMnx 2.1.1 (pinned; Boeing 2025, DOI 10.1111/gean.70009) · networkx 3.6.1 · Python 3.13.9 |
| Demand | `randomTrips` + `duarouter` (official tools), seed 42, 3 600 s, period 1.2 — labelled `SYNTHETIC_VALIDATION_DEMAND`, **not** calibrated Dhaka demand |
| Signal timings | netconvert-synthesised static programs — `IMPORTED_HEURISTIC`, **not** observed Dhaka plans |

## 3. Results (R1 product network)

- 6 527 edges · 7 865 lanes · 2 956 junctions · **17 TLS** · largest-SCC edge fraction **0.9193** · 211 dead-end junctions · 325 boundary stubs (4.98%, censused with explanation).
- **Left-hand traffic verified two ways:** declared `lefthand=true` in the net AND geometric test (sign of direction×offset over 5 250 opposite-carriageway pairs): 98.9% left-hand ⇒ verdict `left_hand`. The 59 contrary votes are short curved medians/service pairs.
- **Signal safety:** 0 conflicting **G/G** (priority-priority) green violations across all 17 programs; 38 permissive G/g conflicts censused separately (SUMO yield-inside-junction semantics — legitimate design, documented in the audit). All conflicted programs have yellow phases.
- **Turn connections:** 0 vehicular approaches without movements (2 093 non-vehicular footway/pedestrian approaches excluded with a documented reason).
- **Representative routes:** 8/8 role pairs routable in both directions on the SCC core.
- **Demand run:** 3 001/3 001 trips routed (0.0% unroutable); deterministic run: return code 0, **0 collisions**, **1 teleport** (jam, vehicle 410, junction 10031329991, t=1167 s — a priority 3-arm junction under uncalibrated synthetic load; 0.03% of vehicles, explained, not a network defect), 1 emergency braking; 2 773 arrivals, mean travel time 266.7 s, mean speed 13.1 m/s.
- **Cross-validation X1–X12:** 8 PASS, 4 REVIEW → `PASS_WITH_EXPLANATIONS`. Every REVIEW was **investigated with measurements** (`results/lab02_v2/cross_validation_explanations.json`): X1 (14.0% length gap) is a uniform per-class deficit caused by `--junctions.join` moving junction-interior geometry into internal lanes (≈26 m/junction × ~2 900 junctions); X5 (5.3pp vs 5pp band, both branches ≥0.90) follows netconvert's connection-level semantics; X7 is a definitional census difference after junction joining (quantified); X9's two marginal deltas (15.0%, 16.2%) carry the same X1 geometric bias. Per DESIGN_V2 §3, explained tolerance failures do not fail the lab; unexplained ones would.

## 4. Defects found and fixed during execution (honest log)

1. **TLS audit over-flagged permissive greens** — treated `g` (yield) like `G` (priority) on foe pairs, producing 38 false "violations". Fixed: only G/G foe pairs are violations; G/g censused as permissive. (SUMO state semantics.)
2. **Turn audit counted footways** — 112 "approaches without movements" were all non-vehicular (footway/pedestrian). Fixed: audit restricted to approaches allowing passenger cars; exclusions counted and reported.
3. **Teleport counter counted words, not events** — `count("teleport")` matched the warning, the "ends teleporting" line and the statistics line (3 for 1 event). Fixed: regex on `Teleporting vehicle …; waited too long (reason)` with per-reason census; collisions parsed from SUMO's own statistics.
4. **Branch A/B universe mismatch** — OSMnx retained all components while netconvert pruned to the largest. Fixed: Branch A now mirrors `--keep-edges.components 1` (0.41% of edges dropped, recorded in `component_prune`).

## 5. Live external reference (user DECISION 1 — conservative)

`dhakaflow.common.live_reference.LiveTrafficReference` protocol + `GoogleRoutesReference` provider implemented and unit-tested with a mock transport (field mask deliberately excludes polylines). No `GOOGLE_MAPS_API_KEY` in the environment ⇒ **LIVE_REFERENCE = READY_NOT_EXECUTED**. By construction the module never writes durations, distances, polylines or any Google Maps Content to disk — only request metadata and derived boolean verdicts are persistable. No Google content appears in git, Drive, or any figure.

## 6. Platform integration (Sprint A)

`build_scenario` produced `TrafficScenario dhaka_R1_lab02_v2` (metadata: `demand=SYNTHETIC_VALIDATION_DEMAND`, `traffic_side=left_hand`); `SumoDhakaBackend` conforms structurally to `dhakaflow.simulation.SimulationBackend`; `GoogleRoutesReference` conforms to `LiveTrafficReference` (runtime-checked in tests). No Lab-01 frozen result was touched.

## 7. Tests

- Lab: `python -m pytest paper_labs/02_dhaka_osm/tests -q` → **12 passed** (unit: query/warning/SCC/percentile + v2: frozen candidates, context query, cluster-id expansion, live-reference disabled path, mock transport + metadata-only persistence, preference validation; integration: tiny-OSM pipeline).
- Platform: `python -m pytest tests/platform -q` → **23 passed**.

## 8. Limitations (carried forward)

- Signal timings are heuristic (`IMPORTED_HEURISTIC`) — Lab 13 must source real DMP/field timings.
- Demand is synthetic validation demand — no realism claim; Lab 13 calibrates.
- OSM attribute completeness on R1: lanes 22.1%, maxspeed 12.8%, name 45.2% of edges (X12) — quantifies the field-survey burden for calibration.
- Live reference designed and tested but not executed (no key) — any future execution stays ephemeral per DECISION 1.
- Betweenness centrality used a seeded 500-node sample (deterministic; documented) rather than exact O(nm) computation.
