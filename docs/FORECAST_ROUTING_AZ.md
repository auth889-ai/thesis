# Forecast routing from A to Z: the study guide for the talk (2026-10-13)

Every number here is read from a results file named next to it. Read the file before the talk, so you can open it when asked.

## A. The question the feature answers

Can a traffic forecast, sent to connected cars over a network, make them take better routes than they would on their own?
Three parts must exist for that: real data to forecast from, a forecaster that works, and a network that carries the advice.

## B. The real data

- METR-LA: 207 loop detectors on Los Angeles freeways and arterials, speed every 5 minutes, 1 March to 27 June 2012.
  File `data/forecasting/cities/metr_la.npz`, 34 272 time steps × 207 sensors, unit mph; dataset hash `857a98d0ec47b353`
  (`results/forecasting/verify_GWNet_METR-LA_207.json`). Released with the DCRNN paper; recorded in `third_party/SOURCES.md`.
- The road map: OpenStreetMap, the box 34.08–34.16 N, 118.342–118.222 W, converted with SUMO's netconvert into
  `data/cities/la_c4_central_wide/sumo/la_c4_central_wide.net.xml` (hash `0d81df27ab2d`).
- The sensor positions: `graph_sensor_locations.csv` from the DCRNN repository, used to place each sensor on an edge of the map.
  83 of the 207 sensors land on an edge the twin has with good confidence (`results/routing/coverage_rescue/la_c4_central_wide/sensor_to_edge_207.json`).

Say: "The speeds the cars will meet are the speeds those sensors recorded that day. Nothing about the traffic state is invented."

## C. The forecaster

- Model: Graph WaveNet (Wu et al., IJCAI 2019), run through BasicTS (Apache-2.0, commit `4c3e2d37…`): 12 past bins (one hour) in, 12 future bins out.
- Training: on the first 70 % of the time steps (0–23 990), validation 23 990–27 417, test 27 417–34 272, never touched during training.
- Held-out error on the test part, in mph: 15 min ahead 2.71 (persistence, "same as now", 4.02); 30 min 3.10 (5.10); 60 min 3.56 (6.80).
  The paper's published numbers: 2.69 / 3.07 / 3.53, so the reproduction matches. File: `results/forecasting/verify_GWNet_METR-LA_207.json`.
- Checkpoint: `GraphWaveNet_best_val_MAE.pt`, sha256 `548e399bd53c…`, 3.7 MB. The same sha256 is written into every routing run's `PROTOCOL.json`.

Say: "The forecaster is the one we validated in the forecasting chapter; it beats 'no change' by a third at 15 minutes."

## D. The simulated part, said openly

- The cars: 12 480 vehicles drawn by SUMO's randomTrips on the real map, the thesis's 8× "peak" profile with arterial origins and
  destinations. Each seed is a different draw; the file's hash is printed and stored (`summary.json`, `demand.demand_hash`).
- 30 % of the cars are "connected" (have a radio). The others drive and never hear anything.
- Every arm of every run is a simulation. No real car, phone or server exists.

## E. How the real future enters the simulation

The sensors' recorded speeds after the chosen moment are replayed as lane speed caps on the 83 mapped edges, every 300 s, in every arm
(`core/ml/forecasting/routing_forecast.py`, `caps()`; applied in `veins_routing_loop.py`, `apply_caps`). So the baseline and the
predictive arm both drive into the same real traffic, and the forecast has a real answer to be scored against.

## F. The loop, second by second (the Veins version, `make veins-forecast-routing`)

One SUMO 1.21 simulation with two clients that step in lockstep:

1. A connected car sends a status frame every 10 s over IEEE 802.11p: id, road, position, speed (`research/veins_loops/src/RoutingCar11p.cc`).
2. Veins decides, frame by frame, who decodes it: path loss, noise floor, interference (Veins 5.3.1, 20 mW, 6 Mbit/s).
3. A roadside unit that decodes it writes the status into its SUMO point of interest, the "cable" to the server (`RoutingRSU11p.cc`).
4. The Python server reads only those statuses (`core/simulation/routing/veins_routing_loop.py`), drops duplicates, feeds
   `RoutingController.receive()` (`core/simulation/routing/controller.py`).
5. Every 300 s, from 1 500 s on, the server runs the forecaster on the real history up to the round's moment (`as_of` moves one bin per
   round), builds edge costs for horizons 0/15/30/60 min, and corrects them where cars reported speeds at least 15 % off the forecast
   (`core/networking/v2x/state_correction.py`: 30-min decay, 2 upstream hops, half weight per hop).
6. For every connected car it knows about, it asks SUMO's duarouter for 5 alternative routes on those costs and keeps a reroute only
   if it saves 60 s and 5 %, the car is past its 300 s cooldown, the road's capacity (BPR α 0.15, β 4) and the 40 % share rule allow
   it, and the round's budget (10 % of cars, at least 2) is not spent (`controller_config.json`, `route_optimizer.py`).
7. Each advice goes to the unit nearest the car, only if within 600 m; otherwise it waits and expires after 60 s.
8. The unit broadcasts it; only the addressed car, and only if it decodes the frame, changes route inside Veins, with the same checks as
   `route_application.py` (still on the route, not inside a junction).
9. The car reports the outcome through a point of interest; the server logs it (`reroute_log.jsonl`).
10. At the end: vehicle-hours from SUMO's tripinfo, packet counts from Veins's own scalar file.

## G. The three versions of the network, and why there are three

| version | link model | what it answers | result |
|---|---|---|---|
| ideal / ITS-G5 / C-V2X / 4G profiles (`make gui-routing PROFILE=…`) | latency, jitter, loss, lifetime per message, parameters from 5GAA field tests, tinyLTE and a DSRC-vs-LTE study | does the link's delay or loss change the outcome | no benefit on 3 seeds under any profile (`evidence/routing_profiles/`) |
| penetration sweep (`scripts/routing/penetration_sweep.py`) | 4G profile, 10 to 100 % connected | does the share of connected cars matter | no monotone trend, ±20 veh-h (`evidence/routing_penetration/4g_s201/`) |
| Veins 802.11p (`make veins-forecast-routing`) | packet level, roadside units | what a real deployment would hear and reach | 20 units: 31 % of statuses heard, 6 reroutes, +0.2 veh-h; 60 units: 52 %, 15 reroutes, +0.4 (`evidence/veins_forecast_routing/`) |

Say: "Under every kind of link, from perfect to packet-level, the forecast changes almost nothing on this demand. That is the finding."

## H. Why "no benefit" is an honest result and not a failure

- Most cars have no alternative worth 60 s on an 11 × 9 km grid at peak; the decision counts say so (`NO_ALTERNATIVE` is the largest class every round).
- Rerouting the 10 % budget moves load onto roads others use; the penetration sweep shows gains and losses of the same size.
- With roadside units, coverage bounds everything: the server hears a third to a half of the cars and reaches a handful within 60 s.
- The method is not the weak part: the forecast is validated (C), and the decisions are traceable per car and per round.

## I. How to prove it is real and dynamic at the table

`make prove-forecast-routing` (or `SEED=<their number> RSUS=<their number>`): a run with a seed chosen now, then 14 PASS/FAIL checks
read from that run's files: the real dataset, checkpoint and map on disk with their hashes; one forecast per round with its own hash
and a moving real moment; a different demand hash, moment and decisions than the saved run; the loop's packet counters equal to the
Veins scalar file; applied reroutes equal to the cars' own reports. Run on 2026-10-13 04:13 with seed 7220: all 14 PASS
(`evidence/live_runs/prove_forecast_routing/20261012T221340Z/proof.json`).

Then `make veins-forecast-routing SEED=clock` for the picture (press RUN in the OMNeT++ window).

## J. Questions a teacher may ask, with the answer

- **Is the data real?** Yes: 207 Los Angeles detectors, 2012, released with the DCRNN paper; the file and its hash are on disk.
- **Is the model trained by you?** Yes, with BasicTS's official config; the held-out error matches the paper's (2.71 vs 2.69 mph at 15 min).
- **Does the forecast run during the simulation?** Yes, every 300 s; each round records its input-window hash, forecast hash and inference time.
- **Why Los Angeles and not Dhaka?** Dhaka has no detector history; the forecasting chapter shows only zero-shot models can run there and none beats "no change" an hour ahead. The loop needs a validated forecaster, so it runs on the city that has one.
- **Is the network real?** It is a packet-level simulation (Veins): every frame is decided by physics models, not by a loss percentage. The earlier versions used a channel model with measured parameters; both are reported.
- **Is it a fixed demo?** No: the seed can be chosen at the table; a new seed gives a new demand draw, a new real moment, new forecasts and new decisions, and the proof command checks it.
- **What is synthetic?** The cars and their trips; the radio events; the roadside-unit deployment (busiest junctions of a saved run). The map and buildings, the speeds, the model and the link parameters are real or published.
- **Why no improvement?** Section H. Say it before they ask.
- **What would change the result?** More units or a longer validity (coverage), a demand with real alternatives (an incident), or a city with denser sensing. Those are proposals, not claims.
- **Where is the code?** `core/simulation/closed_loop/` (the loop), `core/simulation/routing/` (controller, optimizer, edge costs, the Veins client), `core/networking/v2x/` (channel, correction), `research/veins_loops/src/` (the Veins apps), `scripts/live/` (demos and the proof).

## K. The files to have open

`results/forecasting/verify_GWNet_METR-LA_207.json`, `evidence/veins_forecast_routing/20261012T142239Z/summary.json`,
`evidence/live_runs/prove_forecast_routing/<stamp>/proof.json`, `docs/VEINS_LOOPS.md`, `features/forecast-routing/README.md`,
`docs/FORECAST_ROUTING_SOURCES.md` (every borrowed piece with its licence).
