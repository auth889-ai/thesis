# LEARNING_GATE — Lab 02: Real Dhaka OSM → Validated SUMO Network

Work through these in order; each builds on the previous. Self-checks at the
end of every item — if you can answer them without looking, move on.

---

## 1. OpenStreetMap (OSM)

**Concept:** A free, editable world map built by volunteers — the "Wikipedia of
maps". Everything (roads, buildings, traffic lights) is stored as structured,
downloadable data, not as pictures.
**Tiny example:** Open https://www.openstreetmap.org, search "Farmgate, Dhaka",
right-click → "Show address" — everything you see is data anyone can download.
**Role in DhakaFlow:** the *only* free, legal source of Dhaka's real road
geometry; the geographic skeleton of the entire digital twin.
**Must understand now:** OSM is crowd-sourced → quality varies by area; central
Dhaka is well-mapped, but attributes (lanes, signals) may be missing where the
geometry is fine.
**Self-check:** Why can we not use Google Maps as the twin's base map? *(Licensing
and no raw-data export; OSM gives us the actual geometry with a free license.)*

## 2. Node

**Concept:** The atom of OSM: a single point with an id, latitude, longitude,
and optional tags (e.g. `highway=traffic_signals`).
**Tiny example:** `<node id="42" lat="23.7509" lon="90.3890"/>` — one point near
Farmgate.
**Role in DhakaFlow:** nodes become SUMO junction candidates; nodes tagged
`traffic_signals` tell us where Dhaka's signalized crossings are.
**Must understand now:** a node is not "an intersection" by itself — road shape
points are also nodes; only *shared* nodes between ways create topology.
**Self-check:** What two numbers does every node carry? *(lat, lon.)*

## 3. Way

**Concept:** An ordered list of nodes + tags. A road is a way with a `highway=*`
tag (e.g. `highway=primary`, `name=Kazi Nazrul Islam Avenue`, `lanes=3`,
`oneway=yes`).
**Tiny example:** `<way id="7"><nd ref="41/><nd ref="42"/><tag k="highway" v="primary"/></way>`
**Role in DhakaFlow:** ways become SUMO edges; their tags decide speed, lanes,
one-way direction, and road class for the Dhaka network.
**Must understand now:** one physical street is often many OSM ways (split at
every junction or tag change).
**Self-check:** How does OSM say a street is one-way? *(`oneway=yes` tag on the way.)*

## 4. Road topology

**Concept:** Which roads connect to which, at which points — the graph structure
(who touches whom), independent of the drawing.
**Tiny example:** Two ways crossing on the map but NOT sharing a node = an
overpass — no turning between them. Sharing a node = an intersection.
**Role in DhakaFlow:** wrong topology (a missing shared node) silently makes a
Dhaka junction untraversable — vehicles will vanish or detour absurdly.
**Must understand now:** visual crossing ≠ connection. Topology lives in shared
node ids.
**Self-check:** Two roads cross on screen; when is that NOT an intersection?
*(When they don't share a node — flyover/underpass.)*

## 5. SUMO edge

**Concept:** SUMO's directed road segment between two junctions. One two-way
OSM way becomes TWO edges (one per direction).
**Tiny example:** `<edge id="e1" from="J1" to="J2" numLanes="2" speed="13.9"/>`
**Role in DhakaFlow:** edges are where vehicles drive, queues form, and where
later detectors/measurements attach.
**Must understand now:** edge = one direction only; edge ids appear in routes,
results, everything downstream.
**Self-check:** A two-way Mirpur Road segment becomes how many edges? *(Two.)*

## 6. Lane

**Concept:** Each edge contains one or more lanes (`_0` is rightmost in SUMO).
Lanes have their own speed/width/permissions.
**Tiny example:** Edge `e1` with `numLanes="3"` has lanes `e1_0, e1_1, e1_2`.
**Role in DhakaFlow:** queue lengths, capacities, and later per-lane control all
live at lane level; Dhaka's OSM `lanes=` tags are often missing → defaults get
used, which we must sanity-check.
**Must understand now:** lane count drives capacity — a wrongly-defaulted
1-lane arterial will fake congestion.
**Self-check:** What does SUMO do if OSM has no `lanes` tag? *(Uses the type
default for that highway class — must be audited.)*

## 7. Junction

**Concept:** SUMO's intersection object: where edges meet, with internal
geometry and right-of-way rules.
**Tiny example:** `<junction id="J2" type="traffic_light" x="..." y="..."/>`
**Role in DhakaFlow:** junctions are where Dhaka's delay happens and where
signal control (later RL) acts.
**Must understand now:** junction `type` matters: `priority`, `traffic_light`,
`right_before_left`, `dead_end`.
**Self-check:** Name two junction types. *(priority, traffic_light — also
dead_end.)*

## 8. Connection

**Concept:** The permitted lane-to-lane movement across a junction ("from edge
A lane 1 you may turn left into edge B lane 0").
**Tiny example:** `<connection from="e1" to="e9" fromLane="1" toLane="0"/>`
**Role in DhakaFlow:** connections define which turns exist at Farmgate etc.;
missing connections = impossible turns = broken routing.
**Must understand now:** netconvert *guesses* connections from geometry; guesses
can be wrong and must be spot-checked.
**Self-check:** What breaks if a left-turn connection is missing? *(No route can
use that turn; traffic reroutes or trips become invalid.)*

## 9. Traffic-light logic

**Concept:** A TLS program: an ordered list of phases, each a duration + a state
string with one character per controlled connection (G/g/y/r).
**Tiny example (from Lab 01):** `GGrr → yyrr → rrGG → rryy` — two greens with
yellows between.
**Role in DhakaFlow:** the object every later controller (fixed/actuated/
max-pressure/RL) manipulates; Dhaka signal locations come from OSM
`highway=traffic_signals` where mapped.
**Must understand now:** the state string index ↔ connection mapping (Lab 01's
`getControlledLinks`); safety = yellows preserved, conflicting greens absent.
**Self-check:** In `GGrr`, how many controlled connections are there and how
many currently have green? *(4 controlled; 2 green.)*

## 10. OSM → SUMO import

**Concept:** The translation pipeline: OSM nodes/ways/tags → SUMO junctions/
edges/lanes/connections/TLS, using a type map that supplies defaults per
highway class.
**Tiny example:** `highway=primary` + no lanes tag → typemap says 2 lanes,
~50 km/h (before city adjustments).
**Role in DhakaFlow:** this IS Lab 02 — turning the real Dhaka map into a
runnable simulation substrate.
**Must understand now:** the import makes *many* silent decisions (defaults,
guessed connections, pruned fragments) — each must be surfaced and audited, not
trusted.
**Self-check:** Where do lane/speed defaults come from when OSM tags are
missing? *(The netconvert OSM typemap.)*

## 11. netconvert

**Concept:** SUMO's official network compiler: reads OSM (and other formats),
writes `.net.xml`, printing warnings about everything it fixed or discarded.
**Tiny example:** `netconvert --osm-files dhaka.osm -o dhaka.net.xml
--geometry.remove --junctions.join --tls.guess-signals`
**Role in DhakaFlow:** the single most important tool of this lab; its warning
log is a validation artifact, not noise.
**Must understand now:** key options: `--junctions.join` (merge messy OSM
junction clusters), `--tls.guess-signals` (attach mapped signal nodes to
junctions), `--keep-edges.components 1` (keep the biggest connected part),
`--remove-edges.isolated`.
**Self-check:** Why must we read netconvert warnings instead of ignoring them?
*(Each warning is a silent network edit — dropped edges, guessed signals — that
changes the science.)*

## 12. Route / trip

**Concept:** A *trip* = origin edge + destination edge + depart time. A *route*
= the explicit edge list connecting them. `duarouter` turns trips into routes
via shortest/fastest path.
**Tiny example:** trip `from=e12 to=e88 depart=30` → route `e12 e15 e40 e88`.
**Role in DhakaFlow:** every simulated Dhaka vehicle follows a route; route
computability doubles as a connectivity test.
**Must understand now:** if duarouter cannot route a trip, either the trip is
bad or the network is broken — the error census tells us which.
**Self-check:** What's the difference between a trip and a route? *(Trip = O/D
intent; route = actual edge path.)*

## 13. OD demand

**Concept:** Origin–Destination demand: how many vehicles want to go from each
zone/edge to each other per time slice — the demand matrix behind the trips.
**Tiny example:** "Farmgate→Shahbagh: 300 veh/h between 8:00–9:00".
**Role in DhakaFlow:** Lab 02 uses simple seeded random OD only as a *network
stress test*; realistic Dhaka OD comes later (calibration labs).
**Must understand now:** demand realism and network validity are separate
questions — this lab validates the network, not Dhaka's true demand.
**Self-check:** Why is random demand acceptable in Lab 02 but not later?
*(Here it only exercises the graph; the twin's fidelity later depends on real
calibrated demand.)*

## 14. Turning movement / turning ratio

**Concept:** At a junction, the split of arriving traffic among left/through/
right (e.g. 20/70/10%).
**Tiny example:** 100 vehicles reach Bangla Motor from the south: 20 turn left,
70 go straight, 10 turn right.
**Role in DhakaFlow:** later calibration data (video counts) arrives as turning
movements; signal timing quality depends on them.
**Must understand now:** in Lab 02 turning ratios emerge implicitly from routed
OD; we only check that all *physically real* turns are possible.
**Self-check:** What network object must exist for a turning movement to be
simulable? *(The lane-to-lane connection.)*

## 15. Connectivity validation

**Concept:** Proving vehicles can actually reach places: the network's directed
graph should have one large strongly-connected component (SCC) covering almost
all edges, and representative O-D pairs must be routable.
**Tiny example:** If `Farmgate→Shahbagh` routes but `Shahbagh→Farmgate` fails,
a one-way tag or missing connection broke the return direction.
**Role in DhakaFlow:** the twin is useless if parts of Dhaka are unreachable;
RL later exploits any connectivity bug it finds.
**Must understand now:** SCC fraction, dead-end census, and duarouter error rate
are the three connectivity numbers of this lab.
**Self-check:** What does "strongly connected" add over "connected"?
*(Reachability in BOTH directions for every pair.)*

## 16. Coordinate / projection basics

**Concept:** OSM uses lat/lon (WGS84 degrees); SUMO simulates in flat meters —
netconvert projects (UTM) and stores the offset. Dhaka is UTM zone 46N.
**Tiny example:** (23.7509 N, 90.3890 E) → about (233㎞ easting, 2628㎞
northing) in UTM 46N, shifted so the network's corner is near (0,0).
**Role in DhakaFlow:** every later georeferencing step (camera positions,
detector placement, plotting over map tiles) must round-trip this projection.
**Must understand now:** distances/speeds in SUMO are meters/seconds — correct
only if projection happened; check `<location>` in the net file.
**Self-check:** Why can't SUMO simulate directly in lat/lon? *(Degrees aren't a
uniform distance unit; dynamics need meters.)*

## 17. Demand sanity checks

**Concept:** Before trusting any simulation: did all vehicles depart, arrive,
and behave? Census of inserted vs loaded, running-at-end, teleports,
collisions, absurd travel times.
**Tiny example:** 1000 trips loaded, 940 inserted, 60 never entered → insertion
starvation (jam at sources) — must be explained, not ignored.
**Role in DhakaFlow:** the acceptance test of Lab 02's deterministic run and the
template for every later experiment's health check.
**Must understand now:** teleports usually mean broken junctions/connections;
zero-collision is the baseline expectation in default SUMO.
**Self-check:** A run reports 15 teleports — is that a demand problem or a
network problem? *(Usually network: blocked/deadlocked junctions or bad
connections; investigate before touching demand.)*
