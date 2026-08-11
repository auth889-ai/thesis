# METHOD_SPEC — Lab 02: Real Dhaka OSM → Validated SUMO Network

Items tagged PUBLISHED (official docs/tools), INFERRED, ASSUMED, or MODIFIED_BY_US.

## Research questions

**RQ1.** Can a connected, signal-bearing SUMO network of a real central-Dhaka
corridor be generated reproducibly from OSM with all import decisions surfaced?
**RQ2.** Does the generated network sustain deterministic demand end-to-end
(routable representative O-Ds, run to completion, no unexplained teleports)?

## Region selection (documented, pre-registered)

Bounding box (WGS84): **south 23.723, west 90.372, north 23.762, east 90.408**
(~4.3 km N-S × 3.7 km E-W, central Dhaka).
Why this box (criteria before download):
1. Contains several of Dhaka's canonical signalized junctions — Farmgate,
   Karwan Bazar, Bangla Motor, Shahbagh, Sonargaon crossing — multiple
   intersections requirement met.
2. Dense arterial grid (Kazi Nazrul Islam Ave, Panthapath, Green Rd, New
   Eskaton, Sonargaon Rd) — meaningful network control later, not a single
   corridor toy.
3. Among the best-mapped parts of Bangladesh in OSM (central business/
   institutional district) — best attribute quality available.
4. Small enough to audit junction-by-junction; large enough (>100 junctions
   expected) for later multi-agent control.
5. Future labs benefit: area is rich in CCTV/video vantage points and DMP
   signal locations for later calibration.

## Pipeline (each step = one src module, orchestrated by scripts/run_lab02.py)

1. **OSM acquisition** — Overpass API (official OSM infrastructure), query =
   all `highway=*` ways + their nodes in the bbox (`way[highway](bbox); (._;>;);
   out body;`). Records: UTC timestamp, endpoint, exact query, bytes, sha256.
   PUBLISHED tooling; query scope (highway-only) ASSUMED (buildings/landuse
   irrelevant to Lab 02).
2. **Import** — `netconvert` (SUMO 1.27.1, pinned as in Lab 01) with the
   official OSM typemap `$SUMO_HOME/data/typemap/osmNetconvert.typ.xml` and
   options: `--geometry.remove --junctions.join --tls.guess-signals --tls.join
   --tls.default-type static --remove-edges.isolated --keep-edges.components 1
   --no-turnarounds.tls`. Every option justified in ASSUMPTIONS.md; full
   warning log captured and classified (counts per warning class) — warnings
   are validation artifacts. PUBLISHED tool; option set MODIFIED_BY_US
   (documented).
3. **Network validation** — via `sumolib`: edge/lane/junction/TLS census;
   dead-end census; lane-count and speed distributions per highway type;
   one-way share; **strong connectivity**: Kosaraju SCC over the edge graph
   (built from net connections); largest-SCC edge fraction reported.
   Signal validation: TLS count, per-TLS program dump for a manual sample of
   ≥5 named junctions, checks: every program has ≥2 phases, contains yellow
   between conflicting greens, no all-green phase.
4. **Representative routes** — 8 deterministic O-D pairs (N↔S, E↔W boundary
   arterials + center cross pairs, both directions) routed with `duarouter`;
   all must succeed; path lengths recorded.
5. **Demand stress test** — `randomTrips.py` (official tool), fixed seed,
   uniform random O-Ds at configured rate → `duarouter` (error census: % 
   unroutable trips recorded, threshold in config) → SUMO run (deterministic:
   fixed seed, fixed step length) with tripinfo/summary outputs.
6. **Sanity metrics** — loaded vs inserted vs arrived; running at end;
   teleports (threshold: explained or zero); collisions (must be 0); travel
   time / speed / waiting distributions; throughput.
7. **Visualization** — matplotlib network plot from sumolib shapes (colored by
   road class, TLS junctions marked) + zoom panels of 2 sampled junctions.
8. **Reproducibility** — all artifacts derive from configs + scripts; network
   sha256 recorded; evidence bundle to Drive + lightweight copies to git.

## Pass thresholds (pre-registered; config-driven)

- Largest SCC ≥ 90% of edges (Dhaka OSM quality caveat; shortfall must be
  itemized by edge class). ASSUMED.
- duarouter unroutable ≤ 2% of generated random trips. ASSUMED.
- Representative routes: 8/8 both-direction successes REQUIRED.
- Collisions = 0 REQUIRED; teleports: 0 or individually explained.
- ≥ 5 TLS junctions present (else signal-validation gate re-scoped and
  documented — OSM signal mapping in Dhaka may be sparse; `--tls.guess-signals`
  only converts *mapped* signal nodes; we do NOT invent signals in Lab 02).
