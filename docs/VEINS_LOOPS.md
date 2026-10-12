# The Veins loops: machine learning and a packet-level network in ONE run (2026-10-12/13)

The supervisor's point: a latency/loss channel model on top of SUMO is not networking, and the ML and the network did not look
combined. These loops answer it: the network is **Veins 5.3.1 on OMNeT++ 6.2.0, IEEE 802.11p at packet level** (PHY, MAC with
CSMA/CA, path loss, building shadowing from the OpenStreetMap outlines, interference and collisions), and the machine learning runs
**in the same simulation**, on the same SUMO, step by step. Nothing in `core/simulation/closed_loop`, `rl_v2x_loop.py` or any
earlier result changes; everything here is new files and new make targets.

## Architecture: one SUMO, two TraCI clients

```
                    SUMO 1.21.0   --num-clients 2   (the SUMO Veins 5.3.1 speaks: TraCI API 21)
                    ┌───────────────────────────────────────────────────────────┐
                    │  road network (OSM), demand, vehicles, traffic lights     │
                    │  parameters on vehicles / traffic lights = the only link │
                    └───────────▲───────────────────────────────▲──────────────┘
        TraCI, order 1          │                               │        TraCI, order 2
   ┌────────────────────────────┴──────────┐        ┌───────────┴─────────────────────────────┐
   │ client 1: Veins / OMNeT++ (C++)        │        │ client 2: Python (SUMO-RL environment)   │
   │  every vehicle = an 802.11p node       │        │  frozen Q-learning agents on the 3       │
   │  RSU at each signalised junction       │        │  corridor signals (rl_signals.py)        │
   │  ambulance app: DENM-like WSM every 1 s│        │  each second: reads the RSU flags;      │
   │  car app: real reception → make-way v2 │        │  a flagged junction → the copied         │
   │  RSU app: real reception → writes      │        │  adaptive-traffic-signal-rl override,    │
   │    veins.rx / veins.rx_t on the TLS    │        │  unchanged; release → Q-learning again   │
   │  Qtenv: frames drawn, cars recoloured  │        │  prints every event, writes metrics      │
   └────────────────────────────────────────┘        └──────────────────────────────────────────┘
```

* The two clients never talk to each other. Veins writes what its radio really received into SUMO parameters
  (`trafficlight.setParameter`); the Python client reads them (`getParameter`) and acts. Both step the same SUMO in lockstep
  (`setOrder` 1 and 2; SUMO advances only when both have stepped).
* Veins launches SUMO itself (`TraCIScenarioManagerForker`, command line with `--num-clients 2`); the Python client connects to that
  port as client 2 (`traci.init` + `setOrder(2)` instead of SUMO-RL's `traci.start`), everything else in SUMO-RL unchanged.
* Feasibility spike (`research/veins_loops/spike/`, 2026-10-12 19:00): both clients drove one SUMO 1.21 to the end, 44 parameter
  writes read back, Veins simulated 99 frames sent and 1 473 receptions in 3 s of wall time. No fallback (no Q-table port to C++) was needed.
* A SUMO 1.21 quirk, recorded honestly: the two-client connect fails now and then before the first step
  (`Storage::readChar(): invalid position` on SUMO's side; Veins's `setOrder` is encoded as a compound, which SUMO 1.21 handles with a
  hard-coded length, #5037). The loop detects a failure before any step and restarts the whole run on a fresh port (up to 3 attempts,
  logged as "handshake failed"). A run that stepped is never restarted.

## Phase 1: ambulance loop, `make veins-ambulance-loop` (`core/simulation/ambulance/veins_loop.py`)

Dhaka corridor at the thesis's Dhaka-density level (scale from `evidence/ambulance_rq2/dhaka_density/match.json`), seed 11 first,
then seeds 11-15; the ambulance departs at 900 s on the thesis trip; horizon 3 600 s; three arms on the same seed and traffic:

| arm | signals | radio |
|---|---|---|
| `fixed` | SUMO's own fixed-time programmes | nodes exist, apps silent |
| `rl` | frozen SUMO-RL Q-learning agents (RQ3's Q-tables, greedy) | nodes exist, apps silent |
| `rl_v2i` | the same agents, paused on a junction while the override holds it | ambulance DENM every 1 s over 802.11p (20 mW, 6 Mbit/s, Veins's example PHY settings, OSM buildings as obstacles); cars that really receive it within 100 m ahead make way (rule v2); an RSU that really receives it flags its light; the Python client applies the override (EMVLight's primary/secondary addressing) |

Veins apps (new, `research/veins_loops/src/`, GPL-2.0-or-later as Veins; derived from `TraCIDemo11p` / `TraCIDemoRSU11p` and our
`AmbulanceAlert11p`): `AmbulanceLoop11p` (ambulance + cars), `AmbulanceLoopRSU11p` (road-side unit). Scenario: `research/veins_loops/SharedSumoScenario.ned`.
Build once: `cd research/veins_loops/src && opp_makemake -f --make-so -o veinsloops -I$VEINS/src -L$VEINS/src -lveins -DVEINS_OMNETPP=1 && gmake MODE=release`
(GNU make 4 is needed for OMNeT++'s makefiles; macOS's `make` 3.81 is not enough).

Packet numbers are Veins's own scalars (`results/*.sca` of each run): `alertsSent` on the ambulance node, `denmReceived` per RSU,
`SNIRLostPackets` (interference/collision) and `RXTXLostPackets` (arrived while transmitting) per RSU NIC; "below sensitivity" =
sent − received − lost, since Veins does not count per node the frames that never reached the receiver's minimum power.
`--beacons` adds Veins's 1 Hz beacon on every car (a CAM-like channel load), so collisions can happen; it is slower.

What to see on screen (`make veins-ambulance-loop`, the default is seed 11, arm `rl_v2i`, Qtenv + sumo-gui):
* the terminal: the header (SUMO 1.21 with two clients, 3 RSUs, radios ACTIVE), "press RUN in the OMNeT++ window"; then every 300 s a
  line with vehicles, DENMs sent, DENMs each RSU really received; and one line per event: `RSU1 junction … INFORMED / TAKEOVER /
  RELEASED (DENMs this RSU really received so far: n)`;
* the OMNeT++ (Qtenv) window after RUN (F5) or FAST (F6): cars as nodes; a line between two nodes is an 802.11p frame in the air;
  the ambulance node is red with "DENM sent n"; a car that made way turns green with "making way"; each RSU shows "RSU …: DENM rx n"
  and turns green on its first reception; cars without a radio are grey (100 % equipped by default, so none);
* the sumo-gui window: the same traffic, driven by both clients; the ambulance red, cars making way green;
* at the end: the ambulance's travel time, the other drivers' vehicle-hours, the packet table per RSU, and the channel-model loop's
  medians (`evidence/ambulance_loop/summary.json`) next to them for comparison.

Evidence: `evidence/veins_ambulance_loop/` (`summary.json`, `run.log`, `runs/<arm>_s<seed>_x<scale>/{metrics.json,run.log,veins.log,
sumo.sumocfg,veins/omnetpp.ini,veins/results/*.sca}`, `SHA256SUMS` `85c191cf84eb…`).

### Phase 1 results (seeds 11-15, SUMO 1.21.0, scale 0.78, 100 % equipped; medians from `summary.json`, details in `features/ambulance-loop/README.md`)

| arm | ambulance travel time (median, s) | everyone else (median, vehicle-hours) | saving vs fixed (median of per-seed differences) |
|---|---|---|---|
| fixed-time signals | 375 | 685.3 | — |
| Q-learning | 281 | 902.8 | 94 s |
| Q-learning + 802.11p DENM + RSU pre-emption + make-way | 274 | 829.7 | 6 s |

Per seed the 802.11p arm sent 205-942 DENMs; the two RSUs on the route decoded 28-32 of them each (the rest arrived below the receiver's
sensitivity through the buildings: a real range of about 250 m), 0 were lost to interference (only the ambulance transmits); 42-108
cars made way; the first junction was taken over at 960-1034 s for a 900 s departure. Against the channel-model loop of Part A (SUMO
1.27, ITS-G5 delivery model: fixed 292 / 670.4, Q-learning 196 / 866.6, Q-learning + V2I 194 / 872.6): the SUMO release, not the
network, explains the level shift (the Q-learning arm on SUMO 1.21 without Veins reproduces the Veins run exactly, 385 s / 923.41
veh-h on seed 11); within SUMO 1.21 the packet-level radio informs a junction later than the channel model did, and the V2I arm still
adds no measurable time over Q-learning alone (3 seeds better, 2 worse, one of them a 942 s gridlock).

## Showing it live, not canned (2026-10-13)

Both targets take their inputs at the table: `make veins-ambulance-loop SEED=clock` and `make veins-forecast-routing SEED=clock RSUS=40`
draw a new seed from the clock (printed first, with the demand hash), so a new traffic draw, a new real moment of the METR-LA history
(the routing loop's `as_of` index), new frames and new decisions come out every time; `SEED=<n>` lets the supervisor name the seed and
`RSUS=<n>` the deployment. Checked headless 2026-10-13 04:00: ambulance seed 6576 → 196 s, 58 RSU receptions, pre-emption at 965 s;
routing seed 6532 → as_of 33896, demand hash `d47d76e5…`, 10 reroute decisions in the first round. A live run writes under
`evidence/live_runs/`, never over the evidence folders.

## What is real, what is simulated

| real (recorded, published, or computed at run time) | simulated |
|---|---|
| the corridor's roads and buildings (OpenStreetMap), the DhaTraX counts behind the density level | every vehicle, the ambulance, every frame |
| the radio physics as modelled by Veins (published models: free-space/two-ray path loss, simple obstacle shadowing, 802.11p MAC); its parameters are Veins's example values (20 mW, 6 Mbit/s, −110 dBm sensitivity), not Dhaka measurements | reception, loss, collisions: decided by those models frame by frame |
| the Q-tables (trained earlier by SUMO-RL on this corridor), the override's logic (copied repo, unchanged) | the signal states they produce in the run |
| every number printed: computed in the run or read from its result files | — |

## Phase 2: forecast routing in Veins, `make veins-forecast-routing` (`core/simulation/routing/veins_routing_loop.py`)

The design of PRE-VE (Santamaria, Fazio, Raimondo, Tropea, De Rango, IEEE TVT 2019: road-side units, 802.11p, predictive rerouting;
no code released) with the thesis's own forecaster and decision rules, on the LA twin:

```
 connected car (30 %, Veins's draw)        RSU at a busy junction            Python client = the EXISTING server
 RoutingCar11p                              RoutingRSU11p                      closed_loop.Server (RoutingController, unchanged)
  status frame every 10 s  ──802.11p──▶  really decoded? → POI "obs" ──SUMO param──▶  server.receive()  (only what the RSUs heard)
                                                                                      every 300 s: Graph WaveNet forecast on the real
                                                                                      METR-LA history + residual correction + rules
  route changed only here  ◀──802.11p──  frame "ADVICE …"  ◀──POI "adv"──SUMO param──  advice handed to the RSU nearest the car (≤ 600 m)
  outcome → POI "v2x_log" ───────────────────────────────────SUMO param──────────────▶  reroute log, counters
```

* The uplink and the downlink are real frames: a status that no RSU decodes never reaches the server; an advice that the car does not
  decode never changes its route. The wired backhaul between an RSU and the server is a SUMO point-of-interest parameter.
* The route change itself happens inside Veins (`changeVehicleRoute`), with the same checks as `route_application.py` (car still on
  an edge of the advised route; on a junction the change waits a second, five times at most; past the fork it is inapplicable).
* No fork state (SUMO 1.21 cannot load a 1.27 state): both arms run from 0 s; nothing is sent before the 1 200 s warm-up; the first
  decision round is at 1 500 s. The demand is drawn with the thesis's own SUMO 1.27 tools before the Veins environment is set, so its
  hash can be compared with the channel-model runs (`demand_hash` in `summary.json`).
* RSUs: the N busiest junctions (vehicles entered on their incoming edges, summed over a saved baseline run's `edgedata.xml`), at least
  500 m apart; N = 20 by default. The LA twin has no building polygons, so the radio runs without obstacle shadowing
  (`research/veins_loops/config_no_obstacles.xml`: Veins's example config minus that model).
* Phase 2 lets the Python client own the SUMO process (`SharedSumoScenarioExt.ned`, plain `TraCIScenarioManager`): Veins leaves at its
  time limit, the client closes last, and SUMO writes its outputs in full (with the Forker, Veins's SIGTERM at its finish truncated
  the 12 000-vehicle tripinfo). The two-client handshake restart of Phase 1 applies here too.

Apps (new, GPL-2.0-or-later, derived from Veins's `TraCIDemo11p` / `TraCIDemoRSU11p`): `RoutingCar11p`, `RoutingRSU11p`, `PoiParams.h`
in `research/veins_loops/src/`. Built into the same `libveinsloops.dylib` as Phase 1.

What to see on screen (`make veins-forecast-routing`, default seed 201, 15 min after the warm-up, baseline then predictive, Qtenv + sumo-gui;
press RUN in each Qtenv window):
* the terminal: the demand hash and vehicle count, the 20 RSU junctions and their entered counts; per minute: vehicles, connected cars,
  statuses the RSUs really received (and how many distinct ones reached the server), advice handed / applied; per round: priced
  edges, cars considered, the decision counts (REROUTE, KEEP_CURRENT_BELOW_THRESHOLD, NO_ALTERNATIVE, …), advice sent; at the end the
  COMPARISON line (baseline vs predictive vehicle-hours, same seed and demand) and the packet table;
* Qtenv: red RSU towers at the busy junctions, lines for frames; a car whose route changed is blue with "rerouted"; an RSU's label counts
  "status rx n, advice tx m";
* sumo-gui: the RSUs as red squares (points of interest), connected cars yellow, rerouted cars blue.

Evidence: `evidence/veins_forecast_routing/<stamp>/` (`summary.json`, `run.log`, `rsus.json`, `PROTOCOL.json`, per arm `arm_result.json`,
`network_metrics.json`, `reroute_log.jsonl`, `veins/results/*.sca`, `SHA256SUMS`).

### Phase 2 results (seed 201, 15 min after the warm-up, 12 480 vehicles, 30 % connected; read from the two `summary.json` files)

| RSUs | run | baseline veh-h | predictive veh-h | statuses sent → decoded by an RSU → distinct to the server | advice decided → handed (in reach) → broadcast → received → applied | frames lost to interference |
|---|---|---|---|---|---|---|
| 20 | `20261012T142239Z` (SHA256SUMS `1016a154f6ae…`) | 1055.5 | 1055.7 (+0.2) | 101 184 → 59 115 → 31 114 (30.7 %) | 123 → 14 → 13 → 7 → 6 | 0 |
| 60 | `20261012T143208Z` (SHA256SUMS `b22bfc9005e6…`) | 1055.5 | 1055.9 (+0.4) | 101 385 → 115 474 → 52 981 (52.3 %) | 183 → 23 → 22 → 19 → 15 | 0 |

What it says: the packet-level network changes the picture in the way a real deployment would. The server only knows what the RSUs
hear (a third to a half of the statuses), and an advice reaches a car only when it passes a unit within its 60 s validity, so a few
dozen of the server's ~180 decisions become route changes and the vehicle-hours do not move. Tripling the RSUs raises the uplink
coverage from 31 % to 52 % and the applied advice from 6 to 15. No frame was lost to interference at this load (about 50 status
frames per second over the whole twin); collisions would need denser traffic or shorter status periods. The forecast loop itself is
the thesis's, unchanged; the comparison with the channel-model runs (`features/forecast-routing/README.md`) shows the same
"no travel-time benefit" result under both kinds of network.
