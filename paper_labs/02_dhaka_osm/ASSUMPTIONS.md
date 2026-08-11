# ASSUMPTIONS — Lab 02 (Dhaka OSM → SUMO)

## PUBLISHED (official docs/tools)

- OSM data model (nodes/ways/tags), Overpass API semantics.
- netconvert OSM import + official typemap defaults; sumolib; randomTrips.py;
  duarouter (SUMO 1.27.1 documentation).
- Dhaka lies in UTM zone 46N; netconvert projects WGS84→UTM automatically.

## INFERRED

- Central Dhaka OSM geometry is substantially complete; attribute tags
  (`lanes`, `traffic_signals`) are partially mapped → defaults will fill gaps
  and are audited, not trusted.
- `--junctions.join` merges Dhaka's multi-node junction clusters into single
  controllable junctions (required for later signal control).

## ASSUMED (our choices, stated before running)

- Region bbox (METHOD_SPEC) — selection criteria pre-registered.
- Overpass highway-only query scope (non-road features irrelevant here).
- netconvert option set (each flag justified inline in ASSUMPTIONS below):
  `--geometry.remove` (shape-point cleanup, no topology change),
  `--junctions.join` (see above), `--tls.guess-signals --tls.join`
  (attach *mapped* signal nodes to joined junctions; static default programs),
  `--remove-edges.isolated --keep-edges.components 1` (drop unreachable
  fragments; the drop count is REPORTED), `--no-turnarounds.tls` (suppress
  U-turns at signals — Dhaka signalized junctions generally prohibit them).
- Pass thresholds: SCC ≥ 90% edges, unroutable ≤ 2%, 8/8 representative
  routes, 0 collisions.
- Demand for Lab 02 is a seeded uniform random stress test — NOT Dhaka's real
  demand (explicitly out of scope until calibration labs).
- Default typemap speeds/lane-counts stand in where OSM tags are missing; the
  per-class distributions are published in the validation tables so later labs
  know exactly what was defaulted.

## MODIFIED_BY_US

- SUMO's default TLS programs (static, netconvert-generated) are placeholders
  for real Dhaka timings — acceptable in Lab 02 (network validation), flagged
  for replacement during calibration.
- Any post-netconvert correction, if ever needed, must be an explicit
  transformation script under `src/network/patches/` with the original file
  preserved — no silent hand-edits (none exist at the time of writing).

## UNKNOWN FROM AVAILABLE MATERIAL

- True lane counts / signal timings for unmapped junctions (future field/video
  data).
- OSM completeness quantification for the bbox (we report what we import; we
  cannot audit what mappers omitted).
