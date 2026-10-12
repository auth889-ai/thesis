# Demo cheat sheet (talk 2026-10-12 18:00; written 06:05)

Start once: `make present` runs the seven thesis steps in order (seed 11 everywhere, every THESIS CHECK must say REPRODUCED).
Everything below is SIMULATION on real road networks; nothing is a real ambulance, radio, phone or crash. Numbers on screen are
computed in the run or read from a results file. If a window does not open, add `ARGS="--no-gui"` to get the same lines in the terminal.

| Feature | Command | Expected on screen | Fallback |
|---|---|---|---|
| The seven thesis steps | `make present` | 7 steps, each "exit 0"; step 1 prints "REPRODUCED exactly" (292 s → 284 s) | `make present ARGS="--only v2x"` for one step; logs in `evidence/live_runs/present_*` |
| Ambulance V2X, thesis run | `make run-v2x` | sumo-gui: blue ring = radio range, orange cars making way, label with packets; THESIS CHECK REPRODUCED | `--no-gui` |
| Ambulance V2X, the viewer's own run | `make run-v2x-live` or `make run-v2x-live SEED=4242 FROM=<edge> TO=<edge>` | prints SEED (from the clock), ROUTE (edges, metres, signals), DEMAND (the DhaTraX counts and scale), then the two travel times; "new (not a thesis number)" | if "SUMO itself crashed … try another seed": run again (bluelight bug, about 1 seed in 5) |
| Full recorded counts | `make run-v2x-live DEMAND=dhatrax-peak` | the same, at scale 1.0 of the counts: gridlock, teleports, swings either way | expect crashes; the honest finding is "no stable effect" (`evidence/ambulance_rq2/dhatrax_peak/`) |
| ML + V2X in one loop | `make gui-ambulance-loop` | red ambulance from 900 s, yellow cars making way, junction labels "Q-learning" → "V2X override (msg delivered t=…)" → "Q-learning (released)"; terminal: V2X events per junction, final ambulance time and vehicle-hours | `ARGS="--seed 15"`; headless `ARGS="--no-gui"`; the 5-seed table is in `evidence/ambulance_loop/` |
| Forecast routing loop | `make gui-routing` | LA twin: yellow = connected, green flash = uplink delivered, blue = rerouted, red flash = downlink lost, red edges = forecast below half the limit; one line per 300 s round; final "CHECK … SAME" | `ARGS="--minutes 5"` (one round, ~30 s), `--profile its-g5` for the lossy link; `--no-gui` |
| Smart signals | `make run-signals` | two sumo-gui windows, fixed time left, Q-learning right; THESIS CHECKs | `make compare-signals ARGS="--quick"` |
| Crash SOS car to car | `make run-sos-collide` | a collision SUMO itself detects; the SOS rule fires; warned cars reroute | `make present ARGS="--only sos"` |
| Crash detection graph | `make present ARGS="--only sos"` (step 7) | phone-size screen, the collision trace through the 4 g rule, countdown starts | `/app/emergency` → trace chips |
| Phone mesh | `make run-mesh` / `make gui-mesh` | PONS delivery against phone count; The ONE's GUI | `make sweep-mesh ARGS="--quick"` |
| Weak signal | step 6 of `make present` | offline trip, prefetch with the OSM masts profile | Research page `/app/lab/evidence` |
| Crash on recorded data | `features/crash-detection/README.md` table | VZCrash: the app's rule 45.6 % recall / 88.6 % precision; the paper's baseline reproduced (AP 0.896) | numbers only; the data stays on the instance |

| ML + REAL network: ambulance (Phase 1) | `make veins-ambulance-loop` | OMNeT++ Qtenv window (press RUN/F5): cars as nodes, lines = 802.11p frames, red ambulance "DENM sent n", green cars "making way", RSU labels "DENM rx n"; sumo-gui follows; terminal: per-junction INFORMED / TAKEOVER / RELEASED with the DENMs the RSU really received; final table per RSU (sent, received, lost, below sensitivity) and the channel-model loop's medians next to it | **live:** `make veins-ambulance-loop SEED=clock` (a new traffic draw every time; let the supervisor name a seed with `SEED=<n>`); `ARGS="--no-gui --seeds 11 --arms fixed rl rl_v2i"` (~12 min); `evidence/veins_ambulance_loop/summary.json` |
| ML + REAL network: forecast routing (Phase 2) | `make veins-forecast-routing` | two runs (baseline, then predictive), each a Qtenv + sumo-gui pair (press RUN in each): 20 red RSU towers at the busiest LA junctions, status frames from yellow connected cars, advice frames back, rerouted cars blue; terminal: statuses the RSUs really decoded vs sent, the server's rounds (decisions), advice handed / received / applied, COMPARISON of vehicle-hours | **live:** `make veins-forecast-routing SEED=clock RSUS=40` (new demand draw, new real METR-LA moment, the units you name; the seed and the demand hash are printed first); `ARGS="--no-gui --minutes 10"` (~8 min); `docs/VEINS_LOOPS.md` |

What to say when asked "is it real?": the road networks are OpenStreetMap; the counts, the METR-LA speeds and the VZCrash recordings are
real and dated; the radio parameters are published measurements; every moving vehicle, every message and every crash is simulated.
