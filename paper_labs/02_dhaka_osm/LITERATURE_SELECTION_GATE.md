# LITERATURE_SELECTION_GATE — Lab 02 (upgraded)

Verified 2026-08-13 against primary sources (PyPI JSON API, GitHub API, publisher
pages, official API docs). Nothing below is quoted from memory.

## A. Canonical / foundational

### A1. Boeing (2025) — OSMnx reference paper — **CORE**
- **Title:** Modeling and Analyzing Urban Networks and Amenities with OSMnx
- **Author:** Geoff Boeing · **Year:** 2025 · **Venue:** *Geographical Analysis* 57(4):567–577
- **DOI:** `10.1111/gean.70009` · **arXiv:** `2505.00736` · open access
- **Problem:** reproducible acquisition, modelling, simplification and analysis of
  urban street networks from OSM; the theory behind graph simplification,
  consolidation and network measures.
- **Why influential:** the current citable reference for OSMnx (supersedes Boeing
  2017 CEUS as the package's reference publication).
- **Official repo:** `github.com/gboeing/osmnx` · MIT · **pin `v2.1.1` = `2fc39cb2792ff869881b99f724a2d97f0e958667`** (PyPI `osmnx==2.1.1`, requires Python ≥3.11)
- **Dataset:** OpenStreetMap (ODbL) — same source as the SUMO branch.
- **Compute:** CPU-only, seconds–minutes for our bbox.
- **Dhaka relevance:** gives an *independent* topological model of the same Dhaka
  region, which is the whole basis of the dual-construction cross-check.

### A2. Alvarez Lopez et al. (2018) — SUMO reference paper — **CORE** (already archived, Lab 01)
- DOI `10.1109/ITSC.2018.8569938`; §IV NETCONVERT/OSM import governs our build;
  §IX-C sublane model reserved for Dhaka heterogeneity (Lab 13).
- **Official software:** `eclipse-sumo/sumo`, **pinned `v1_27_1` = `7717f2379d9e314a0c81c5cec748444de06a2a91`**, EPL-2.0. Local toolchain verified as SUMO **1.27.1**, identical to the Lab 01 pin.

### A3. Boeing (2017) — original OSMnx paper — **BASELINE (context only)**
- *Computers, Environment and Urban Systems* 65:126–139, DOI `10.1016/j.compenvurbsys.2017.05.004`.
- Cited for the original simplification/consolidation method; **not** the current
  reference publication → cite A1 for the software.

## B. Data / infrastructure sources

| Resource | Role | Pin / provenance | License |
|---|---|---|---|
| OpenStreetMap via **Overpass API** | the single OSM snapshot both branches consume | query + timestamp + sha256 recorded per run; mirrors rotate on 429/504 | ODbL 1.0 |
| **netconvert** (SUMO 1.27.1) | OSM → simulation network | option set incl. `--lefthand` | EPL-2.0 |
| **OSMnx 2.1.1** | OSM → analysis graph | `v2.1.1` / `2fc39cb…` | MIT |

**Single-snapshot rule:** OSMnx must consume the *same* archived `.osm` file that
netconvert consumed (`ox.graph_from_xml`), not a fresh download. Two downloads
minutes apart are two different snapshots and would make every discrepancy
uninterpretable.

## C. External live reference (optional track)

### C1. Google **Routes API** (`computeRoutes`) — **EXTERNAL_LIVE_REFERENCE**
- **Verified enum semantics** (official docs):
  - `TRAFFIC_UNAWARE` — ignores live traffic, lowest latency.
  - `TRAFFIC_AWARE` — live traffic with latency optimisations (default working mode for our sweeps).
  - `TRAFFIC_AWARE_OPTIMAL` — live traffic, most optimisations disabled, highest accuracy **and highest latency** → reserved for a small validation subset.
- **Fields to record:** `duration`, `staticDuration`, `distanceMeters` (+ our own request metadata).
- **Policy constraint (verified):** Routes API content caching is **restricted**;
  only **place IDs** are exempt and storable indefinitely. Attribution is required
  when content is displayed. ⇒ **Design decision:** raw Routes responses are
  treated as ephemeral, are written **outside git** (Drive), and only
  non-content run metadata (timestamps, OD identifiers, mode, HTTP status,
  counts) plus derived plots are retained in the repo. This is deliberately
  conservative; see OPEN QUESTION 1.
- **Classification:** `EXTERNAL_LIVE_REFERENCE` — *not* ground truth, *not*
  calibration input for Lab 02.

### C2. Google **Roads API** (snap-to-road) — **DESIGN ONLY, NOT EXECUTED**
- Prepared as an adapter shape for a future GPS track source. Not invoked in
  Lab 02 (no GPS observations exist yet). Its speed-limit endpoint is **rejected**
  as a real-time truth source (it returns posted limits, not observed speeds).

## D. Rejected for Lab 02

| Candidate | Why rejected *here* |
|---|---|
| `osmWebWizard` (SUMO) | convenience GUI wrapper; hides the netconvert options we must pin and audit |
| OSM `.pbf` extracts (Geofabrik) + osmium clipping | valid alternative, but Overpass gives an exact reproducible bbox query string; revisit only if Overpass rate limits block the full region |
| Any Google map *tiles/geometry* as network source | licence-incompatible with an OSM-derived, redistributable network |
| Live traffic as Lab 02 calibration target | out of scope — calibration is Lab 13 and needs camera-derived measurement, not a commercial ETA |

## E. Compute requirements

CPU-only throughout; the measured full-region build + 1 h simulation took **18 s**
locally on SUMO 1.27.1 (identical version to the Colab pin). Live-reference calls
are network-bound, a few hundred requests at most. No GPU.

## OPEN QUESTIONS (need your decision before execution)

1. **Routes API retention.** My default is *not* to commit any Google-derived
   duration/distance values, keeping them in Drive only. If you prefer them in
   git as evidence, confirm you accept the Maps Service Terms caching
   restrictions for that content.
2. **Region.** The design proposes measuring five candidate regions and selecting
   by pre-registered criteria (see `REGION_SELECTION.md`) rather than asserting a
   winner now.
