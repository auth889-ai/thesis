# Forecast Routing over a Packet-Level Vehicular Network

A Graph WaveNet traffic forecast, trained on real road-sensor data, is turned into route advice and delivered to
connected vehicles over a simulated IEEE 802.11p radio. A vehicle changes route only when its radio really decodes
the advice. The question: **when a good forecast exists, how much of it actually reaches the cars, and does the city's
total travel time improve?**

Design project (SWE 4606), BSc in Software Engineering, Department of Computer Science and Engineering, Islamic
University of Technology. Author: Jana Junnatul Ferdous Eva (220042145). Supervisor: Faisal Hussain, Assistant
Professor.

## How it works

One simulation, shared by three programs that advance together one simulated second at a time:

| Program | Role |
|---|---|
| **SUMO** | the road world: the real OpenStreetMap network of central Los Angeles, about 12 500 vehicles, 30 % of them connected |
| **OMNeT++ 6.2 + Veins 5.3.1** (TraCI client 1) | the radio world: IEEE 802.11p PHY and MAC for every connected vehicle and 20 roadside units (RSUs); decides, per frame, who decodes it |
| **Python server** (TraCI client 2) | the brain: Graph WaveNet forecast, correction, routing decisions, advice to RSUs |

The two clients never talk directly: an RSU writes what it decoded into a SUMO point-of-interest parameter (the
"cable" to the server), and the server writes advice the same way.

Each round (every 300 s after a 1 200 s warm-up):

1. **Real history.** The last hour of real METR-LA speeds (207 sensors, 5-minute steps).
2. **Forecast.** Graph WaveNet predicts every mapped road's speed 15, 30 and 60 minutes ahead (`core/ml/forecasting/routing_forecast.py`).
3. **Car status.** Every connected vehicle sends road, position and speed every 10 s over 802.11p; the server only knows statuses an RSU decoded.
4. **Correction.** Where a vehicle's speed is at least 15 % off the forecast, the forecast is pulled towards it (`core/networking/v2x/state_correction.py`).
5. **Alternatives.** SUMO's `duarouter` finds 5 routes per vehicle on the forecast travel times.
6. **Decision.** Reroute only if the best route saves at least 60 s and 5 %; cooldown, share, capacity and budget gates (`core/simulation/routing/controller.py`).
7. **Advice by radio.** The nearest RSU within 600 m broadcasts it; the vehicle changes route only if it decodes the frame (`research/veins_loops/src/RoutingCar11p.cc`).

## Results

All numbers come from saved runs; the file is named next to each.

**Forecaster** (held-out METR-LA test data, MAE in mph; `results/forecasting/verify_GWNet_METR-LA_207.json`):

| Horizon | Graph WaveNet (ours) | "No change" | Published (Wu et al., IJCAI 2019) |
|---|---|---|---|
| 15 min | 2.71 | 4.02 | 2.69 |
| 30 min | 3.10 | 5.10 | 3.07 |
| 60 min | 3.56 | 6.80 | 3.53 |

**Loop over packet-level 802.11p** (seed 201, 15 minutes after warm-up, SUMO 1.21.0;
`evidence/veins_forecast_routing/20261012T142239Z/` and `20261012T143208Z/`):

| | 20 RSUs | 60 RSUs |
|---|---|---|
| Total travel time, baseline / forecast routing (veh-h) | 1055.5 / 1055.7 | 1055.5 / 1055.9 |
| Status messages reaching the server | 30.7 % | 52.3 % |
| Advice decided / handed to an RSU / received / route changed | 123 / 14 / 7 / 6 | 183 / 23 / 19 / 15 |

**Channel models** (SUMO 1.27.1): ITS-G5, seeds 201–203: −14.6, +42.5, +9.3 veh-h (`evidence/routing_profiles/its-g5/`);
share of connected vehicles 10–100 % with 4G: between −12.7 and +18.5 veh-h, no trend (`evidence/routing_penetration/4g_s201/`).

**Finding:** the forecast is accurate, but the total travel time does not change: at peak few vehicles have a route
that saves 60 s, and radio coverage limits who is heard and reached.

## Run it

Requirements: Python 3.13 with `requirements.txt`, SUMO 1.27.1 (`pip install eclipse-sumo==1.27.1`), OMNeT++ 6.2 and
Veins 5.3.1. Veins accepts SUMO only up to 1.21 (TraCI API 21); one line was added to its version table so that
SUMO 1.27.1 (API 22) is accepted with the settings of API 21. Build the vehicle and RSU apps once:

```
cd research/veins_loops/src && opp_makemake -f --make-so -o veinsloops -I$VEINS/src -L$VEINS/src -lveins -DVEINS_OMNETPP=1 && gmake MODE=release
```

```
make veins-forecast-routing ARGS="--no-gui --minutes 15 --rsus 20"     # baseline and forecast routing over 802.11p, no windows
make veins-forecast-routing SEED=clock ARGS="--minutes 8 --arms predictive_corrected_v2x --demo-early --veins-cmdenv --live-map"
                                                                        # dynamic demo: new seed every run, whole network, live map
make veins-forecast-routing SEED=6593 ARGS="--minutes 8 --arms predictive_corrected_v2x --demo-early --explain veh0_444 --step-through"
                                                                        # follow one car step by step (windows; press RUN in OMNeT++)
make prove-forecast-routing SEED=<any number>                           # run with that seed, then 14 PASS/FAIL checks from the run's own files
make run-forecast ARGS="--sensor 5 --at 2012-06-05T08:30"               # one forecast against the recording
python figures/make_figures.py                                          # regenerate the figures from the result files
```

`--demo-early` is a demonstration setting (decisions every 120 s from 120 s on); results above use the 300 s protocol.
Every run writes its log and outputs to `evidence/veins_forecast_routing/<time stamp>/`.

## Where the code is

| Path | What |
|---|---|
| `core/ml/forecasting/routing_forecast.py` | loads the checkpoint, fresh forecast per round, road travel-time costs |
| `core/networking/v2x/state_correction.py` | correction of the forecast from received vehicle reports |
| `core/simulation/routing/controller.py`, `route_optimizer.py` | alternatives from `duarouter`, decision rules |
| `core/simulation/routing/veins_routing_loop.py` | starts SUMO and Veins, second TraCI client, moves statuses and advice through RSUs, logs every outcome |
| `research/veins_loops/src/RoutingCar11p.cc`, `RoutingRSU11p.cc` | vehicle and RSU applications in Veins (C++) |
| `results/forecasting/checkpoints/GraphWaveNet/METR-LA_50_12_12/` | the trained model and its exact training config |
| `evidence/` | logs and outputs of every reported run |
| `figures/` | talk and report figures, built only from result files |
| `tests/platform/test_veins_routing_loop.py` | tests of the loop's files and parsers |

## Limitations

- The vehicles and their trips are simulated; the road map, the sensor speeds, the trained model and the radio models are real or published.
- Only 83 of the 207 sensors fall on roads of the simulated network.
- The 802.11p results use SUMO 1.21.0 and the channel-model results SUMO 1.27.1; numbers are compared only within one release.
- Dhaka has no long sensor history yet, so the method is tested on Los Angeles.

## Sources and licence

Reused work, used unchanged unless stated: Graph WaveNet (Wu et al., IJCAI 2019) through BasicTS (commit `4c3e2d37`,
Apache-2.0); METR-LA (Li et al., ICLR 2018); SUMO 1.27.1 (EPL-2.0); OMNeT++ 6.2; Veins 5.3.1 (GPL-2.0-or-later, one
version-table line added); design lineage from PRE-VE (Santamaria et al., IEEE TVT 2019). Versions, licences and the
files used are listed in `third_party/SOURCES.md`.

This project: MIT (see `LICENSE`).
