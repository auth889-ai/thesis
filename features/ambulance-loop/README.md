# Ambulance V2X + Q-learning signals in one loop (Part A, 2026-10-12; new flag/target only, nothing existing changes)

**Goal.** One SUMO run in which the machine-learning signal control and the networking alert act together: the three corridor
signals are driven by the thesis's frozen sumo-rl Q-learning agents, the ambulance broadcasts over the thesis's V2X delivery model,
each junction is a receiver (V2I), and a junction pre-empts only when a message is actually delivered to it, through the copied
emergency override unchanged, then hands itself back to the agent after the ambulance has passed. SIMULATION on generated traffic
scaled to two counted sections (the thesis's "Dhaka density" level, scale read from `evidence/ambulance_rq2/dhaka_density/match.json`).

## Pipeline (ML → network → action)

```
frozen Q-tables (RQ3, results/emergency/dhaka/rq2/rl/q_dhaka_density_x0.78.pkl)      sumo-rl SumoEnvironment, greedy agents, 3 signals within 500 m
        │  every 5 simulated seconds: observation → action (next green)                 rl_v2x_loop.py: HeldEnv (sumo-rl subclass), run()
        ▼
SUMO 1.27.1 corridor, the ambulance departs at 900 s                                    service.AmbulanceRun (unchanged) → LoopRun (subclass)
        │  each second: cars ahead within 100 m are alerted (make-way rule v2, unchanged)
        │  the PRIMARY and SECONDARY junctions on the route are addressed (EMVLight, AAAI 2022, design idea only)
        ▼
V2X delivery model (core/networking/v2x/model.py): out of range / lost / expired / delivered per message   ITS-G5 425 m, C-V2X 625 m, 4G
        │  delivered to a junction →
        ▼
restore the junction's own programme, pause its agent, emergency override takes it at its next green     adaptive-traffic-signal-rl (MIT, unchanged)
        │  the ambulance passes → override releases, the agent acts again from the next step
        ▼
metrics.json per run: messages per junction, informed / takeover / released times, ambulance time, everyone else's vehicle-hours
```

## Built on

| What | Where | Licence | Use |
|---|---|---|---|
| SUMO-RL `SumoEnvironment`, `QLAgent`, `EpsilonGreedy` | `~/.dhakaflow/upstream/sumo-rl` @ `86f0fc41…` (checked at run time) | MIT | subclassed (`HeldEnv`): a held junction gets no action and no yellow bookkeeping; `fixed_ts=True` for the fixed-time arms |
| adaptive-traffic-signal-rl emergency override + safety state machine | `core/simulation/signals/preemption/{emergency,phases}.py` @ `b62436b5…` | MIT | unchanged, driven through our `sumo_adapter.SumoPreemption` on a delivered V2I message |
| EMVLight (Su et al., AAAI 2022, arXiv:2109.05429) | the paper; no code released | — | the primary/secondary junction idea only |
| our V2X delivery model, alert, make-way v2 | `core/networking/v2x/model.py`, `core/simulation/ambulance/service.py` | — | unchanged; `LoopRun` subclasses `AmbulanceRun` |

Recorded in `third_party/SOURCES.md` ("Ambulance V2X + Q-learning in one loop").

## Results (`evidence/ambulance_loop/summary.json`, SHA256SUMS `4b4c4592…`, 2026-10-12; ITS-G5, every car equipped, scale 0.78)

Seeds completed: [11, 15, 18, 20, 21] out of 11 tried; **6 runs died in SUMO** (`Connection closed by SUMO`, its bluelight
segfault; seed 12 rl, seed 13 rl, seed 14 fixed_v2i, seed 16 fixed_v2i, seed 17 rl, seed 19 rl_v2i), each such seed dropped and the next tried, as in the study.

| | fixed | Q-learning | Q-learning + V2X/V2I | fixed + V2X/V2I |
|---|---|---|---|---|
| median ambulance time | 292 s | 196 s | 194 s | 345 s |
| median saving vs fixed, same seed | — | +31 s | +32 s | -2 s |
| median vehicle-hours, everyone else | 670 | 867 | 873 | 695 |

Per seed (ambulance time / everyone else's vehicle-hours):

| seed | fixed | Q-learning | Q-learning + V2X/V2I | fixed + V2X/V2I |
|---|---|---|---|---|
| 11 | 292 s / 532 veh-h | 188 s / 794 veh-h | 186 s / 715 veh-h | 284 s / 488 veh-h |
| 15 | 226 s / 670 veh-h | 195 s / 867 veh-h | 194 s / 938 veh-h | 244 s / 699 veh-h |
| 18 | 608 s / 1092 veh-h | 972 s / 1153 veh-h | 1019 s / 1198 veh-h | 571 s / 1125 veh-h |
| 20 | 348 s / 538 veh-h | 196 s / 720 veh-h | 182 s / 810 veh-h | 350 s / 695 veh-h |
| 21 | 288 s / 707 veh-h | 426 s / 1006 veh-h | 403 s / 873 veh-h | 345 s / 633 veh-h |

What the loop recorded for seed 11, Q-learning + V2X/V2I: each of the two route junctions was addressed every second from
1000 m ahead; ITS-G5 reaches 425 m, so the first 34 messages to the first junction were out of range and the 35th was delivered
(no resend once informed); the override took the junction the same second (949 s) and released it 17 s later when
the ambulance had passed; the second junction likewise (968 s to 987 s). Every run's `metrics.json` holds the same record.

**Honest reading.** Seed 11's fixed arms reproduce the saved study exactly (292 s and 284 s, 532.33 and 488.167 vehicle-hours), so the
loop runs the study's traffic. Over the five seeds, Q-learning cuts the ambulance's median time by 31 s but costs everyone else about
196 vehicle-hours more (as RQ3 found); adding the V2X alert with V2I pre-emption ON TOP of Q-learning changes the median by
+1 s, inside the seed-to-seed spread; fixed time + V2X/V2I is -2 s against fixed on these seeds (the study's own
finding: not a reliable effect at this density). Seeds 18 and 21 show Q-learning making the ambulance slower than fixed time.
**Q-learning + V2X is not better than Q-learning alone here, and the combined loop is not better than the study's fixed + V2X.**

## Limits

- Pre-emption holds a junction for about 17-19 s per passage (informed → released); the override's takeover is immediate only because
  the restored programme happened to be in a green; if it is in amber the override waits for the next green (its own rule).
- When the agent takes a junction back, SUMO-RL's bookkeeping (yellow state, time since the last change) is reset by us, so its first
  action after a release may switch without SUMO-RL's own yellow; recorded here, not hidden.
- The sumo-rl Q-tables were trained with the agents owning all three signals; they were not retrained with pre-emption in the loop
  (EMVLight trains its agents with the emergency vehicle; we only borrow its two-junction idea).
- SUMO 1.27.1's bluelight segfault removed 6 of 11 seeds; every number above is from the five that completed.
- Simulation only: generated traffic scaled to two counted sections, the thesis's radio parameters, no real ambulance or radio.

## Live demo (Part E, 2026-10-12): `make gui-ambulance-loop`

    make gui-ambulance-loop                                   # seed 11, arm rl_v2i, ITS-G5: sumo-gui, the loop unchanged (scripts/live/gui_ambulance_loop.py)
    make gui-ambulance-loop ARGS="--arm fixed_v2i --tech c_v2x --delay 40"

Colours and labels (display only, painted from outside the loop): the **ambulance red**; a car that **received the alert turns yellow and stays
yellow while it is making way**; cars out of range or whose message was lost **stay white** (nothing reached them). At each route junction a
label with the controller in charge: **"Q-learning"** → **"V2X override (msg delivered t=…)"** while the copied emergency override holds it
after a delivered message → **"Q-learning (released)"** when the ambulance has passed. The terminal prints one line per V2X message to a
junction (sent → DELIVERED / LOST / OUT OF RANGE, with that junction's running counts) and, at the end, the ambulance's travel time and
everyone else's vehicle-hours read from the run's `metrics.json`. The window runs at full speed until the ambulance departs (900 s), then
slows to `--delay` ms per step. What is real: the road network (OpenStreetMap), the counts the demand is scaled to, the radio parameters'
sources, sumo-rl's code and the copied override. What is simulated: every vehicle, the radio (a delivery model, no signal propagation),
the Q-learning agents' decisions, the ambulance itself. Fallback if the window does not open or SUMO crashes on the seed (its bluelight
bug): `make gui-ambulance-loop ARGS="--seed 15"`; headless: add `--no-gui`.

## How to run

    make run-ambulance-loop                                    # 5 seeds x {fixed, rl, rl_v2i, fixed_v2i}, ITS-G5 -> evidence/ambulance_loop/ (summary.json, SHA256SUMS, run.log)
    make run-ambulance-loop ARGS="--seeds 11 --arms rl_v2i --tech c_v2x"
    python -m pytest tests/platform/test_ambulance_loop.py -q # the primary/secondary rule, the per-junction counting, the evidence hashes

Arms on the same seed: `fixed` (SUMO's programmes, no alert), `rl` (Q-learning, no alert), `rl_v2i` (Q-learning + alert + V2I pre-emption),
`fixed_v2i` (fixed time + the same alert; the study's `alert_preemption` arm through this loop). A seed on which SUMO dies (its bluelight
segfault) is recorded and the next seed tried, as in the study.

## Packet-level network: the loop in Veins (Phase 1, 2026-10-12): `make veins-ambulance-loop`

The supervisor's point was that a latency/loss channel is not networking. `core/simulation/ambulance/veins_loop.py` runs the SAME
Q-learning agents (frozen RQ3 Q-tables) and the SAME copied override, but the alert is an **IEEE 802.11p frame in Veins 5.3.1 / OMNeT++
6.2.0** (20 mW, 6 Mbit/s, path loss, the corridor's OpenStreetMap buildings as obstacles, interference, collisions): one SUMO 1.21 with two
TraCI clients, Veins (order 1) and this loop (order 2). The ambulance's app broadcasts a DENM-like frame every second; a car that really
decodes it within 100 m ahead makes way (rule v2, inside the app); a road-side unit at each of the 3 junctions that really decodes it
writes the reception into its traffic light's SUMO parameters, and the Python client hands that junction to the override (EMVLight's
primary/secondary addressing) until the ambulance has passed, then back to Q-learning. Architecture, quirks, what to see: `docs/VEINS_LOOPS.md`.

Results (`evidence/veins_ambulance_loop/summary.json`, SHA256SUMS `85c191cf84eb…`; SUMO 1.21.0, scale 0.78, 100 % equipped, seeds 11-15,
every number read from the metrics files; Veins's own scalars for the frames):

| seed | fixed: ambulance s / others veh-h | Q-learning | Q-learning + 802.11p V2I | DENMs sent | decoded by the route's 2 RSUs | below sensitivity | lost to interference | cars that made way | first pre-emption (s) |
|---|---|---|---|---|---|---|---|---|---|
| 11 | 280 / 712.3 | 385 / 923.4 | 274 / 864.1 | 272 | 22 / 28 | 250 / 244 | 0 | 67 | 977 |
| 12 | 210 / 683.7 | 191 / 902.8 | 216 / 730.8 | 216 | 25 / 32 | 191 / 184 | 0 | 43 | 989 |
| 13 | 429 / 685.3 | 212 / 898.6 | 205 / 829.7 | 205 | 27 / 32 | 178 / 173 | 0 | 42 | 960 |
| 14 | 558 / 852.7 | 343 / 873.1 | 942 / 731.6 | 942 | 23 / 31 | 919 / 911 | 0 | 108 | 967 |
| 15 | 375 / 596.6 | 281 / 1010.3 | 276 / 1010.3 | 276 | 25 / 30 | 251 / 246 | 0 | 59 | 1034 |
| **median** | **375 / 685.3** | **281 / 902.8** | **274 / 829.7** | | | | | | |

Median saving against fixed time (per seed, then median): Q-learning 94 s, Q-learning + 802.11p 6 s. The channel-model loop
of Part A (`evidence/ambulance_loop/summary.json`, SUMO 1.27, ITS-G5 delivery model) gave medians fixed 292 / 670.4,
Q-learning 196 / 866.6, Q-learning + V2I 194 / 872.6.

Honest reading. (1) The two tables are on different SUMO releases: a control run of the Q-learning arm on SUMO 1.21 without Veins gives
seed 11's 385 s / 923.41 veh-h exactly, so Veins changes nothing in the traffic and the gap to Part A is the SUMO version, not the
network. (2) The real radio shortens the effective range: an RSU decodes the frame only in the last ~20-30 s of approach (about
250 m through buildings), so the junction is taken over just before the ambulance reaches it (first pre-emption 960-1034 s for a
900 s departure), where the channel model's ITS-G5 range informed it earlier. (3) The 802.11p arm beats Q-learning alone on 3 of 5
seeds (11, 13, 15), is slower on seed 12 and loses badly on seed 14 (942 s: a gridlock in which the released junction and the
make-way cars block the corridor); medians 274 vs 281 s, so no measurable gain, as with the channel model in Part A. (4) Only the ambulance transmits, so Veins records no frame lost to interference; `--beacons` adds a 1 Hz
beacon per car (CAM-like load) and showed 411 088 beacons with 0 collisions on a 1 200 s check, at 30x the wall time, so the evidence
runs leave it off. (5) Q-learning's cost to everyone else (teleports in the hundreds) is the same finding as Part A.

Commands: `make veins-ambulance-loop` (windows: press RUN in the OMNeT++ window), `make veins-ambulance-loop ARGS="--no-gui --seeds 11 12 13 14 15 --arms fixed rl rl_v2i"`
(the evidence run, ~65 min), `python -m pytest tests/platform/test_veins_loop.py` (5 unit tests; `-m slow` adds the 1 200 s two-client run).
