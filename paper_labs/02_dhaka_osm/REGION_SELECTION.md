# REGION_SELECTION — candidate Dhaka regions (design, pre-registered)

Rule: candidates are **measured, then selected**. The criteria and their weights
are fixed here *before* the measurement run, so the choice cannot be
rationalised after seeing which region flatters the pipeline.

## Pre-registered criteria (each scored 0–3 from measured evidence)

| # | Criterion | Measured by |
|---|---|---|
| C1 | **Network-control usefulness** — enough signalised junctions to coordinate | TLS count after `--tls.guess-signals`; count of TLS with ≥2 conflicting phase groups |
| C2 | **Road hierarchy** — a real arterial spine, not only residential | share of trunk/primary/secondary lane-km |
| C3 | **Routing alternatives** — genuine path choice for Lab 22 | mean number of distinct k=3 shortest paths per O-D; edge-disjointness |
| C4 | **Connectivity health** | largest-SCC edge fraction; dead-end share |
| C5 | **Camera-data feasibility (Lab 04–06)** | count of high-hierarchy signalised junctions with clear approach geometry; presence of known CCTV-bearing intersections |
| C6 | **Public-transport relevance** | OSM bus routes/stops intersecting the box; BRT/major bus corridor presence |
| C7 | **Emergency / pedestrian relevance (Lab 23)** | hospitals, crossings, footway density in the box |
| C8 | **Auditability** — small enough to inspect junction-by-junction | edge count, junction count |

Tie-break order: C1 → C3 → C5 → C2.

## Candidates

| ID | Region | Approx. bbox (S,W,N,E) | Rationale | Known risk |
|---|---|---|---|---|
| **R1** | Farmgate – Karwan Bazar – Bangla Motor – Shahbagh (Kazi Nazrul Islam Ave spine) | 23.723, 90.372, 23.762, 90.408 | CBD arterial spine; several canonical signalised junctions; Shahbagh serves Dhaka Medical + Dhaka University; dense bus corridor | large-ish (measured: 6 495 edges) |
| **R2** | Gulshan 1 – Gulshan 2 – Banani (Gulshan Ave) | 23.780, 90.405, 23.800, 90.425 | well-mapped, grid-like, signalised, high routing alternative count | diplomatic zone access restrictions; atypical of general Dhaka traffic |
| **R3** | Dhanmondi – Science Lab – New Market (Mirpur Rd) | 23.730, 90.375, 23.752, 90.392 | very dense intersection spacing; strong retail/institutional demand | heavy overlap with R1's western edge |
| **R4** | Mohakhali – Airport Rd (Banani → Kuril) | 23.775, 90.395, 23.830, 90.425 | high-speed arterial, BRT/expressway interaction | few at-grade signalised junctions → weak for network signal control |
| **R5** | Motijheel – Gulistan (old CBD) | 23.715, 90.405, 23.735, 90.425 | highest bus-terminal density; extreme heterogeneity | OSM attribute quality lowest; rickshaw-dominated flows hardest to model early |

## Preliminary evidence already in hand (not yet a selection)

R1 was built during pre-audit execution (see `PRELIMINARY_EXECUTION_NOTE.md`):
6 495 edges, 7 805 lanes, 2 936 junctions, **16 TLS**, largest-SCC edge fraction
**0.920**, 211 dead ends; left-hand verified; 1 h synthetic run with 0 teleports
and 0 collisions. Its inner sub-box gave 1 064 edges / 3 TLS / SCC 0.934.

This satisfies C1/C4/C8 on its own, but **R2–R5 have not been measured**, so no
KEEP/REJECT is recorded yet. The execution phase runs the same measurement
script over all five and fills the table below.

## Decision table — COMPLETED 2026-08-13 from the measurement run

All five candidates were measured by `scripts/measure_candidates.py` with the
identical pipeline (one Overpass snapshot each, network + context features;
OSMnx 2.1.1 Branch A; netconvert `--lefthand` Branch B). Raw numbers:
`outputs/lab02_candidates/decision_table.{json,csv}`; per-candidate snapshots
and manifests with sha256 in `outputs/lab02_candidates/R*/`.

Scoring bands (fixed before scoring, applied uniformly):
- **C1** TLS after guess/join: 0–2→0, 3–6→1, 7–12→2, ≥13→3
- **C2** major-road (motorway/trunk/primary/secondary±links) length share: <0.10→0, <0.175→1, <0.24→2, ≥0.24→3
- **C3** fraction of fixed O-D pairs with ≥2 distinct k=3 paths: <0.5→0, <0.8→1, <1.0→2, =1.0→3
- **C4** SUMO SCC edge fraction f and dead-end junction share d: f≥0.90∧d<0.10→3, f≥0.90→2, 0.85≤f<0.90→1, f<0.85→0
- **C5** surveillance nodes s + TLS-on-major proxy p: s≥5∧p≥7→3, s≥3→2, s≥1→1, else 0
- **C6** bus stops b (+route relations): b≥60→3, b≥30→2, b≥10→1, else 0
- **C7** hospitals h + crossings c: h≥50∨(h≥20∧c≥20)→3, h≥20∨c≥20→2, h≥5→1, else 0
- **C8** edge count E (junction-by-junction auditability): E<3000→3, E<5000→2, else→1

| ID | C1 | C2 | C3 | C4 | C5 | C6 | C7 | C8 | Total | KEEP/REJECT | Reason |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **R1** | **3** (17 TLS, 28 signal nodes) | **3** (0.244) | **3** (6/6) | **3** (0.919, 7.1% dead) | **3** (5 cams, 17 TLS proxy) | **3** (76 stops) | **3** (104 hosp, 37 cross) | 1 (6 527 edges) | **22** | **KEEP** | Highest control usefulness (C1) by a wide margin; passes every connectivity bar; best camera/bus/emergency context. Size cost (C8) already proven tractable: full build+validate in ~13 s, 1 h sim clean. |
| R2 | 1 (6 TLS) | 1 (0.151) | 3 (6/6) | 0 (SCC 0.816) | 2 (3 cams) | 1 (13 stops) | 1 | 3 (2 401) | 12 | REJECT | Fails the C4 connectivity bar (SCC 0.816 < 0.90 — gated diplomatic-zone streets fragment the drivable graph); weakest signal density of the viable boxes. |
| R3 | 1 (3 TLS) | 2 (0.178) | 3 (6/6) | 3 (0.913, 9.9%) | 0 (0 cams, 3 TLS) | 1 (22 stops) | 2 (31 hosp) | 3 (1 878) | 15 | REJECT | Healthy and auditable but only 3 TLS — too few signalised junctions for *network-wide* signal coordination (the thesis objective); also overlaps R1's western edge. |
| R4 | 2 (9 TLS) | 2 (0.193) | 3 (6/6) | 1 (SCC 0.875) | 3 (6 cams) | 3 (71 stops) | 2 | 1 (6 482) | 17 | REJECT | Best surveillance count, but fails the C4 bar (SCC 0.875 < 0.90 — expressway/BRT grade separation breaks at-grade continuity) and its corridor shape gives signal control few at-grade junctions per km². |
| R5 | 1 (3 TLS) | 3 (0.273) | 3 (6/6) | 3 (0.954, 4.5%) | 0 (0 cams) | 2 (41 stops) | 1 | 3 (2 447) | 16 | REJECT | Cleanest connectivity, but only 3 TLS and 3 tagged signal nodes (weakest C1) and zero mapped surveillance (weakest C5 — the pre-registered tie-breaker: future real camera/data availability). |

**Selected region: R1 (Farmgate–Karwan Bazar–Bangla Motor–Shahbagh).**
No tie-break was needed — R1 leads outright on C1 (17 TLS vs runner-up 9) and
ties or leads on C2–C7; its only non-maximal score is C8 (size), where the
measured build/validation cost (~13 s local) shows the audit remains feasible.
The C5 tie-breaker ("future real camera/data availability") independently
favours R1 (5 mapped surveillance nodes on a signal-dense CBD spine) over the
higher-connectivity but camera-free R5.

Frozen product snapshot: `outputs/lab02_candidates/R1/R1.osm`,
sha256 `d854b26a…` (full value in `R1_manifest.json`). R2–R5 remain archived
for Lab 26 scale-up.
