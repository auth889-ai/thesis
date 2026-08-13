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

## Decision table (to be completed by the measurement run)

| ID | C1 | C2 | C3 | C4 | C5 | C6 | C7 | C8 | Total | KEEP/REJECT | Reason |
|---|---|---|---|---|---|---|---|---|---|---|---|
| R1 | | | | | | | | | | *pending* | |
| R2 | | | | | | | | | | *pending* | |
| R3 | | | | | | | | | | *pending* | |
| R4 | | | | | | | | | | *pending* | |
| R5 | | | | | | | | | | *pending* | |

Exactly one region is KEPT as the Lab 02 product; the others are recorded as
REJECT with reasons and remain available for later scale-up (Lab 26).
