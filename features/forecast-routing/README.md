# Forecast routing (RQ2): Graph WaveNet forecast → V2X → rerouting in the Los Angeles twin (README 2026-10-12)

**Goal.** Connected cars send their status to a server; every 300 s the server forecasts the next 15 minutes of speeds with Graph WaveNet
(trained on METR-LA), corrects the forecast with what the cars just reported, prices every road, asks duarouter for alternatives, and sends
a reroute only when it saves at least 60 s and 5 %; the message crosses a simulated V2X link and the car changes route when it arrives.
Measured: everyone's vehicle-hours against a baseline that never reroutes. SIMULATION on the real OpenStreetMap network of central
Los Angeles with the real METR-LA detector speeds replayed as lane speed caps; the vehicles themselves are synthetic.

Pipeline, code and results: `core/simulation/closed_loop/` (`control/closed_loop.py run_point`, `core/simulation/twin/runner.py run_sumo`,
`core/simulation/routing/controller.py plan_round`, `route_optimizer.py`, `network_assignment.py`, `core/networking/v2x/channel.py`,
`core/networking/v2x/state_correction.py`); saved study `results/v2x/closed_loop/`; live check `make run-routing-quick`; live GUI
`make gui-routing` (`features/forecasting/README.md`, "Live demo"); radio profiles `scripts/routing/run_profile.py` →
`evidence/routing_profiles/` (ITS-G5 over seeds 201-203: −14.6, +42.5, +9.3 vehicle-hours against baseline: no benefit under the lossy link).

## What is real, what is synthetic

- **Real:** the road network (OpenStreetMap, `data/cities/la_c4_central_wide/sumo/la_c4_central_wide.net.xml`); the METR-LA speeds
  (`data/forecasting/cities/metr_la.npz`, 207 detectors, 5-minute bins, 2012-03-01 to 2012-06-27, mph), replayed as lane speed caps on the
  83 mapped edges in every arm and used as the forecast's input and as the reference for its error; the trained Graph WaveNet checkpoint;
  the radio parameters' sources (5GAA, Xu et al. 2017, tinyLTE, ETSI).
- **Synthetic:** the demand (SUMO `randomTrips` on the real network, one draw per seed, 8x "peak" profile on the arterials); every vehicle's
  movement; the V2X link (a latency / loss / lifetime model, no radio propagation); the reroutes.
- **Fixed design choices:** 30 % connected (deterministic per vehicle and seed), status every 10 s, a round every 300 s, a 15-minute horizon,
  60 s and 5 % minimum saving, 300 s cooldown, at most 40 % of reroutes on one alternative, BPR load penalty α = 0.15, β = 4
  (`core/simulation/routing/routing_config.json`, `scripts/live/run_routing_quick.py SETTINGS`).

## Design lineage

The closed-loop predictive rerouting design is comparable to **PRE-VE**, i.e. Santamaria, Fazio, Raimondo, Tropea and De Rango, "A New Distributed Predictive Congestion Aware Re-Routing
Algorithm for CO2 Emissions Reduction", IEEE Transactions on Vehicular Technology 68(5), 2019, doi:10.1109/TVT.2019.2905753: predictive,
congestion-aware rerouting with messages over 802.11p, simulated in Veins/SUMO. **We did not copy their code: none is public.** Ours
differs in the forecaster (Graph WaveNet trained on METR-LA, with a residual correction from the cars' reports, instead of their
congestion prediction), in the decision rules (duarouter alternatives, a 60 s / 5 % saving threshold, cooldown, share and capacity
admission with a BPR penalty) and in the link (a latency / loss / lifetime channel on infrastructure, not an 802.11p vehicular network in
Veins). Recorded in `third_party/SOURCES.md` ("Design lineage of the forecast-routing loop").

## Live demo (2026-10-12): `make demo-routing`, two windows from the same fork

    make demo-routing                                   # LEFT baseline (no rerouting), RIGHT predictive + 4g; seed 201; 15 min after the fork; delay 120 ms per step
    make demo-routing ARGS="--profile its-g5 --minutes 10 --delay 60"
    make gui-routing PROFILE=4g                         # one window only, the simpler display
    make demo-routing ARGS="--no-gui"                   # headless, same printouts and result files

Both windows start from the ONE saved SUMO state at 1 200 s with the same seed, so the traffic is identical until the right window's
advice starts changing routes (`scripts/live/demo_routing.py` prepares the fork once; each window is `scripts/live/gui_routing.py --demo`
in its own process; the loop itself, `core/simulation/closed_loop`, is unchanged and drives everything through its hooks).

What you see, and what triggers it:

| On screen | Meaning | Where it comes from |
|---|---|---|
| yellow car / white car | connected (30 %) / not connected | the loop's own `connected(seed, id)` rule, painted at first sight |
| green flash (1 s) | this car's status report reached the server (uplink DELIVERED) | channel event `V2X_RX`, uplink |
| **blue, for the rest of the run** | an advised route was applied (`setRoute`) | `TRACI_ROUTE_RESULT` outcome APPLIED |
| red flash (2 s) + grey **X** (3 s) | the advice to this car was lost on the downlink | channel event `V2X_TX` status DROPPED, downlink |
| thin **red line** car → base station | a status being sent (one in every 25 drawn, or the map disappears) | `V2X_TX`, uplink |
| **green line** base station → car | an advice received | `V2X_RX`, downlink |
| grey base-station POI and ring, with the profile's latency / loss / lifetime | the cellular server ↔ car link (4g: 75 ms, 4 % loss, tinyLTE and Xu et al. 2017) | `scripts/routing/run_profile.py` registration from `network_model.yaml` |
| edges green / orange / red | corrected forecast speed ≥ 70 % / 40-70 % / < 40 % of the limit, this round | the round's own `edge_cost_table.json` (`bounded_speed_mps / speed_limit_mps`) |
| matplotlib window, three panels | Graph WaveNet forecast (blue), real METR-LA (green), corrected @15 min (red dot), now (dashed) for the three busiest mapped sensors, with each one's MAE | the loop's forecaster (`fc.service.predict`), its data (`fc.vals`) and the round's table; saved as `forecast_round_k.png` |
| terminal PHASE lines | 1 REPORTING (every 60 s: statuses, advice, rerouted, vehicles), 2 FORECAST (per round: corrected edges, bands, decisions, advice sent), 3 ADVICE APPLIED (the first three) | the hooks' counters and the round record |
| window label | the arm's name and the round line | same |

Colour convention: the red/green message lines, the grey lost marker and the blue "rerouted" car follow the way Eclipse MOSAIC's
and Veins' visualisers show V2X traffic (MOSAIC: Eclipse Public License 2.0; Veins: GPL-2.0-or-later; neither is run or copied here, only
the convention is borrowed; recorded in `third_party/SOURCES.md`). Real: the OpenStreetMap network, the METR-LA speeds (replayed as caps,
the forecast's input and the plot's green line), the trained checkpoint. Simulated: the vehicles (8x peak randomTrips), the link, the reroutes.
Fallback: `ARGS="--no-gui"`; a single window with `make gui-routing PROFILE=4g`; the headless comparison is in `evidence/live_runs/demo_routing/`.

## Penetration sweep (addition A, 2026-10-12) and SUMO's own plots (addition B)

    PYTHONPATH=.:backend python scripts/routing/penetration_sweep.py --seed 201 --profile 4g       # shares 0.1/0.3/0.5/0.7/1.0, predictive arm + baseline once, one run at a time (~35 min)
    PYTHONPATH=.:backend python scripts/routing/plot_run.py <run folder>                            # speed_map.png (plot_net_dump.py), running_vehicles.png, mean_speed.png (plotXMLAttributes.py)

The sweep follows Chan, Kuncheria and Macfarlane (arXiv:2207.12580, 2022), who swept the rerouting penetration rate 0-100 % in Mobiliti;
no code copied (ours is SUMO through the unchanged closed loop; `--connected-share` only sets the protocol's penetration, default 0.30).
Results, when run: `evidence/routing_penetration/<profile>_s<seed>/summary.json` and `penetration_sweep.png` (vehicle-hours saved vs share,
reroutes vs share), with SHA256SUMS. The plots use two scripts that ship with SUMO (EPL-2.0, `$SUMO_HOME/tools/visualization`, called unchanged)
on the run's own `edgedata.xml` (the loop's 300 s edgeData output) and `summary.xml`.

### Penetration sweep result (2026-10-12 09:36; seed 201, 4g, 60 min after the fork; `evidence/routing_penetration/4g_s201/summary.json` sha256 `743f7f12…`)

Baseline (no rerouting): 3750.9 vehicle-hours.

| connected share | connected / seen | vehicle-hours (vs baseline) | reroutes applied | uplink delivered / sent | downlink delivered / sent |
|---|---|---|---|---|---|
| 10 % | 1110 / 11508 | 3738.2 (-12.7) | 125 | 106,147 / 110,691 (lost 4,544) | 158 / 167 (lost 9) |
| 30 % | 3400 / 11505 | 3752.4 (+1.5) | 307 | 324,833 / 338,296 (lost 13,463) | 526 / 548 (lost 22) |
| 50 % | 5700 / 11501 | 3769.4 (+18.5) | 506 | 546,558 / 569,241 (lost 22,683) | 950 / 991 (lost 41) |
| 70 % | 8050 / 11507 | 3751.6 (+0.7) | 585 | 769,513 / 801,774 (lost 32,261) | 1279 / 1328 (lost 49) |
| 100 % | 11506 / 11506 | 3740.3 (-10.5) | 757 | 1,100,226 / 1,146,349 (lost 46,123) | 1663 / 1730 (lost 67) |

Honest reading: on this seed the system cost does not fall with the share of connected cars; it moves within ±20 vehicle-hours of the
baseline (about 0.5 %) with no monotone trend, while reroutes and messages grow with the share (lost messages stay at the 4g profile's 4 %).
One seed, synthetic demand: this is a demonstration of the sweep, not a finding; Chan et al. report system-level gains only at scale.
Plot: `penetration_sweep.png` (vehicle-hours saved vs share; reroutes vs share).

## Packet-level network: the loop in Veins (Phase 2, 2026-10-12): `make veins-forecast-routing`

The supervisor's point was that a latency/loss channel is not networking. `core/simulation/routing/veins_routing_loop.py` runs the SAME
server (Graph WaveNet + residual correction + the decision rules, `RoutingController` unchanged) as TraCI client 2 of one SUMO 1.21, with
**Veins 5.3.1 / OMNeT++ 6.2.0 as client 1**: every connected car (30 %, Veins's draw) is an IEEE 802.11p node that sends a status frame
every 10 s; road-side units at the 20 busiest junctions (vehicles entered, from a saved baseline's `edgedata.xml`, ≥ 500 m apart) write
the statuses they really decode to a SUMO point of interest (the wired backhaul); the server is fed only those; each advice is handed to
the RSU nearest the car (≤ 600 m) and broadcast as a frame; **only a car that really decodes it changes route** (inside Veins). Design:
PRE-VE (Santamaria et al., IEEE TVT 2019; no code). Architecture, quirks and what to see: `docs/VEINS_LOOPS.md`.

Result (`evidence/veins_forecast_routing/20261012T142239Z/summary.json`, SHA256SUMS `1016a154f6ae…`; seed 201, the thesis's 8x peak
demand of 12 480 vehicles, hash `50efca1c9ed7…`, both arms from 0 s with a 1 200 s warm-up, 15 min after it, 20 mW, 6 Mbit/s, no obstacle
shadowing because the LA twin has no building polygons):

| arm | vehicle-hours | arrived | teleports | statuses sent → decoded by an RSU → distinct ones reaching the server | advice decided → handed to an RSU in reach → broadcast → received by the car → applied |
|---|---|---|---|---|---|
| baseline (radios silent) | 1055.5 | 3180 | 5 | 0 | 0 |
| predictive_corrected_v2x over Veins | 1055.7 (+0.2) | 3185 | 5 | 101 184 → 59 115 → 31 114 (30.7 %) | 123 → 14 → 13 → 7 → 6 (109 expired before any RSU was within 600 m) |
| predictive over Veins  **60 RSUs** (`20261012T143208Z`  SHA256SUMS `b22bfc9005e6…`) | 1055.9 (+0.4) | 3162 | 6 | 101 385 → 115 474 → 52 981 (52.3 %) | 183 → 23 → 22 → 19 → 15 (89 expired out of reach  71 still pending at the end) |

Honest reading: with 20 RSUs on an 11 km × 9 km network most advised cars are never within reach of a unit before the advice's
60 s validity ends, so six routes changed and the vehicle-hours are the same. The uplink is the realistic part: 30.7 % of the statuses
reach the server, the rest were sent out of any RSU's range. Veins recorded no frame lost to interference or collisions at this load
(≈ 48 frames/s over the whole twin). With 60 RSUs the server hears 52.3 % of the statuses and 15 routes change; the vehicle-hours still do not move (+0.4). Coverage, not the forecast, bounds the loop on this twin.
Wall time: baseline 108 s, predictive 201 s for 2 100 simulated seconds.

Commands: `make veins-forecast-routing` (windows; press RUN in each OMNeT++ window), `make veins-forecast-routing ARGS="--no-gui --minutes 15 --rsus 20"`
(the evidence run), `python -m pytest tests/platform/test_veins_routing_loop.py` (4 unit tests; `-m slow` adds the 5-minute two-arm run).
