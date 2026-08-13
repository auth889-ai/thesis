# LAB 02 v2 DESIGN — Real Dhaka Network + Geospatial Validation + Live External Reference Foundation

Supersedes the thin v1 design in `METHOD_SPEC.md` (kept for history). Same lab,
same directory, no parallel lab. **Design only — not executed.**

Classification: `DHAKAFLOW_ADAPTATION` (network construction) +
`FOUNDATION_VALIDATION` (geospatial cross-validation). No CV/forecasting/RL.

---

## 1. Why v1 was too thin

v1 built one network with one tool and checked it against itself. Every audit
shared netconvert's assumptions, so a systematic import error would have been
invisible. v2 adds an **independent second construction** (OSMnx) of the *same
OSM snapshot*, and cross-checks topological invariants — which is what makes the
network trustworthy enough to carry Labs 13–26.

---

## 2. Dual construction

Both branches consume **one archived `.osm` snapshot** (sha256 recorded).
OSMnx must read that file (`ox.graph_from_xml`), never re-download — two
downloads are two snapshots and would make discrepancies uninterpretable.

| | Branch A — OSMnx 2.1.1 | Branch B — netconvert 1.27.1 |
|---|---|---|
| Product | `MultiDiGraph` (analysis graph) | `.net.xml` (simulation network) |
| Purpose | topology, centrality, reachability, k-shortest, attribute completeness | executable microsimulation with lanes, connections, right-of-way, TLS |
| Key settings | `network_type="drive"`, `simplify=True`, `retain_all=False`, then `consolidate_intersections` for a junction-level view | `--lefthand`, `--junctions.join`, `--tls.guess-signals`, `--keep-edges.components 1`, `--no-turnarounds.tls`, `--output.street-names` |
| Left-hand | attribute-level only (OSM `oneway`, geometry) | **explicit `--lefthand`**, verified two ways |

---

## 3. Cross-validation plan (invariants, not raw counts)

Raw node/edge counts **must not** be expected to match: OSMnx simplifies
degree-2 chains, netconvert joins junction clusters, prunes to the largest
component and adds internal lanes. Comparing them directly would manufacture a
false discrepancy. We therefore compare quantities that *should* survive both
pipelines, each with a pre-registered tolerance.

| # | Invariant | A (OSMnx) | B (SUMO) | Tolerance | Rationale |
|---|---|---|---|---|---|
| X1 | Total drive length (km) | Σ edge `length` | Σ edge length | ±10 % | pruning/joining shifts it slightly |
| X2 | Lane-km | Σ length×`lanes` (tagged only) | Σ length×`numLanes` | ±20 % | B defaults untagged lanes; gap **quantifies** default reliance |
| X3 | Road-hierarchy mix (trunk/primary/secondary/tertiary/residential shares) | `highway` tag | edge `type` | ±5 pp per class | direct tag→type mapping |
| X4 | One-way share | `oneway` | absence of reverse edge | ±5 pp | |
| X5 | Largest **SCC** edge fraction | `nx.strongly_connected_components` | our Kosaraju | both ≥0.90; Δ ≤5 pp | reachability is the point of the network |
| X6 | **WCC** count | `nx.weakly_connected_components` | pre-prune components from netconvert log | report + explain | B keeps 1 by design |
| X7 | Dead-end count | degree-1 nodes | `dead_end` junctions + zero-outgoing edges | ±20 % | clipping artifacts on both sides |
| X8 | Signalised junctions | nodes with `highway=traffic_signals` | TLS count | B ≤ A (join merges) — must explain any B > A | |
| X9 | O-D shortest-path length, 12 fixed pairs | `ox.shortest_path` (length + travel time) | `sumolib` `getShortestPath` | length ±15 % | different cost models; large gaps = topology defect |
| X10 | k-shortest (k=3) alternatives | `ox.k_shortest_paths` | duarouter alternatives | ≥2 distinct routes for ≥80 % of pairs | Lab 22 needs real choice |
| X11 | Top-10 central junctions | betweenness on consolidated graph | same OSM ids after cluster expansion | ≥6/10 overlap | the junctions later control cares about |
| X12 | Attribute completeness | % edges with `lanes`, `maxspeed`, `name` | — | report only | tells Lab 13 what must be surveyed |

**ID mapping problem (must be solved, not hand-waved):** `--junctions.join`
produces `cluster_<osmid>_<osmid>…` junction ids. The mapper expands cluster ids
into their member OSM node ids and compares sets; OSMnx
`consolidate_intersections` similarly groups nodes. X8/X11 compare *sets of OSM
node ids*, never string ids.

Failure of any tolerance ⇒ investigate and document; it does not auto-fail the
lab, but an unexplained failure does.

---

## 4. Left-hand traffic (already implemented, kept)

1. **Declared** — `lefthand` attribute in `<net>`.
2. **Geometric, flag-independent** — for opposite carriageway pairs, the sign of
   `direction × offset`; in left-hand traffic the opposing carriageway lies to
   the *right*. Both must agree with `expected="left_hand"`.

---

## 5. Live external reference (optional track)

**Interface** `LiveTrafficReference` (new, platform-level):

```python
@runtime_checkable
class LiveTrafficReference(Protocol):
    def travel_time(self, req: LiveRouteRequest) -> LiveRouteObservation: ...
    @property
    def provider(self) -> str: ...
    @property
    def enabled(self) -> bool: ...
```

- `LiveRouteObservation` records origin/destination, `duration_s`,
  `static_duration_s`, `distance_m`, `routing_preference`, `requested_at_utc`,
  `provider`, `status`, and `classification="EXTERNAL_LIVE_REFERENCE"`.
- **Implementation:** `GoogleRoutesReference` calling `computeRoutes` with
  `routingPreference=TRAFFIC_AWARE` for the standard sweep and
  `TRAFFIC_AWARE_OPTIMAL` for a small validation subset (higher accuracy, higher
  latency — verified semantics in the literature gate).
- **Disabled path:** no `GOOGLE_MAPS_API_KEY` ⇒ provider constructs disabled,
  returns `status="DISABLED_NO_KEY"`, lab records
  `LIVE_REFERENCE = READY_NOT_EXECUTED`. Tested with a mock transport so the
  interface is proven without any key.
- **Scientific boundary (enforced in text and in the type):** this data is
  `EXTERNAL_LIVE_REFERENCE`. Lab 02 will **not** compare it against uncalibrated
  SUMO travel times to claim realism. Its only Lab-02 use is a *plausibility
  band* on route geometry/length and an order-of-magnitude sanity note.
- **Retention:** raw responses stay outside git (Drive); repo keeps request
  metadata + figures only (caching policy, literature gate §C1).

**Roads API (snap-to-road):** adapter *shape* only, not called; no GPS data
exists yet. Its speed-limit endpoint is rejected as real-time truth.

---

## 6. System track — what Lab 02 graduates

| Lab 02 object | Platform expression | Where |
|---|---|---|
| `DhakaRoadNetwork` | validated `.net.xml` + manifest (checksums, bbox, snapshot, build command) | lab product; referenced by scenarios |
| `DhakaTrafficScenario` | `dhakaflow.common.TrafficScenario` (already wired in `src/platform_adapter.py`) | Sprint A type reused, not re-invented |
| `RoadGraph` | thin read-only accessor over the OSMnx graph for topology queries | `dhakaflow/simulation/` (new small module) |
| `RouteValidator` | reachability / k-shortest / O-D matrix checker | `dhakaflow/evaluation/` |
| `LiveTrafficReference` | new Protocol + dataclasses (§5) | `dhakaflow/common/` + provider in lab `src/live_reference/` |
| `SumoDhakaBackend` | conforms to `dhakaflow.simulation.SimulationBackend` (already implemented) | lab `src/platform_adapter.py` |

No future models are implemented.

---

## 7. Artifact plan (all rendered from real audit outputs)

`selected_dhaka_region.png` · `raw_osm_graph.png` · `sumo_network.png` ·
`osmnx_vs_sumo_topology.png` · `connected_components.png` · `road_hierarchy.png` ·
`lane_completeness.png` · `tls_audit.png` · `turn_connection_audit.png` ·
`representative_routes.png` · `k_shortest_routes.png` ·
`route_reachability_matrix.png` · `live_external_reference.png` *(only if
executed)* · `sumo_gui_dhaka.png` *(sumo-gui screenshot via local XQuartz —
allowed lightweight visual inspection)* · `validation_dashboard.png` ·
`dhakaflow_connection.png`

Every figure is generated by a version-controlled script from a CSV/JSON audit
artifact; each audit writes its own machine-readable evidence file.

---

## 8. PASS gate (all must hold)

`REAL_OSM_SNAPSHOT` (sha256 + query + timestamp) · `OSMNX_GRAPH` ·
`SUMO_CONVERSION` · `LEFT_HAND` (both checks agree) · `TOPOLOGY_CROSS_CHECK`
(X1–X12 within tolerance or explained) · `CONNECTIVITY` (largest SCC ≥0.90) ·
`LANE_AUDIT` · `TLS_AUDIT` (0 conflicting-green violations) · `TURN_AUDIT` ·
`REPRESENTATIVE_OD_ROUTES` (all pairs, both directions) · `SUMO_TRAVERSAL`
(runs to completion) · `TELEPORTS = 0 unexplained` · `COLLISIONS = 0 unexplained`
· `REPRODUCIBLE_CHECKSUMS` · `TESTS`.

`LIVE_REFERENCE` is **additional evidence**: `EXECUTED` or
`READY_NOT_EXECUTED`; it can never substitute for the core gates and its absence
cannot fail them.

---

## 9. Execution plan (on approval)

1. Measure all five candidate regions → complete `REGION_SELECTION.md` KEEP/REJECT.
2. Freeze the chosen snapshot; build both branches from it.
3. Run X1–X12 cross-validation → `outputs/tables/cross_validation.csv`.
4. Run the existing SUMO audits (left-hand, lanes, TLS, turns, connectivity, O-D).
5. Synthetic validation demand only, deterministic seed, full 1 h run.
6. Live reference: enabled if a key exists, else `READY_NOT_EXECUTED`.
7. Figures, dashboard, tests, `REPRODUCTION_REPORT.md`, commit, STOP.

Heavy/large steps (all five regions, GUI capture) run locally only while they
stay lightweight (measured: 18 s for the full region); anything larger moves to
Colab per the compute policy.
