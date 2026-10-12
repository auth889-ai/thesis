# Crash SOS, car to car: a crash is detected, then warned to the cars behind (feature 2; README 2026-10-11)

**Goal.** Re-run the thesis's crash rule (WreckWatch: 4 g and a GPS speed over 15 mph) on the three saved traces, then show the
car-to-car side in SUMO: one car crashes on the Dhaka corridor, the warning spreads over V2X to equipped cars, warned cars reroute the
way Veins's TraCIDemo11p does. Measured live: cars warned, cars rerouted, and the affected cars' arrivals with and without the warning.
**There is no thesis number for car-to-car SOS**: these figures are new, computed now, SIMULATION; the run says so.

## Pipeline

```
three saved traces (SYNTHETIC)                 research/sos/traces/*.json  (evidence/sos/traces.SHA256SUMS)
        │
        ▼  the rule, unchanged
core/safety/sos.py:detect (43-56; 4 g at :25)  → REPRODUCED against evidence/sos/results.json      scripts/live/run_sos_v2v.py:rule_check (45-57)
        │
        ▼  SUMO 1.27.1 + TraCI, Dhaka density, service.scenario
crash at --crash-at (600 s): one car stops, red, lane change off          run_sos_v2v.py:simulate (60-157), the crash 90-105
   or --collide: one car sets speedMode 0 and hits the car ahead;          --collision.action warn, --collision.stoptime; SUMO's own
   SUMO detects the contact (getCollidingVehiclesIDList)                   collisions.xml kept in last_run.json
        │
        ▼  every interval, every warned car rebroadcasts (a flood)         106-135
V2X delivery: out of range / lost / delivered     core/networking/v2x/model.py:75-86 (called at :119)
        │
        ▼  a delivered warning → setAdaptedTraveltime(crash edge, 9999) + rerouteTraveltime   126-135  (TraCIDemo11p style)
same seed without warnings (200) → comparison (201-209) → evidence/live_runs/sos_v2v/last_run.json
```

## Upstream

| What | Where | Commit / version | Licence | How it is used |
|---|---|---|---|---|
| WreckWatch (White et al., MONET 16(3), 2011) | paper only | 2011 | © Springer | the rule: 4 g, speed over 15 mph; nothing copied (SOURCES.md:58) |
| Eclipse SUMO + TraCI | pip | 1.27.1, `7717f237…` | EPL-2.0 | the simulation; collision options from `docs/web/docs/Simulation/Safety.md` (SOURCES.md:9, :224) |
| Veins `TraCIDemo11p` | `~/.dhakaflow/upstream/veins`, unchanged | 5.3.1 = `6571085f…` | GPL-2.0-or-later | the `--veins` second view runs it as is; its reroute logic is re-implemented in our script, not subclassed (SOURCES.md:195) |
| ours | `core/safety/sos.py`, `scripts/live/run_sos_v2v.py`, `core/networking/v2x/model.py`, `core/simulation/live_jobs/jobs.py:sos` | — | — | the rule, the flood, the comparison, the web job |

## Files

- `core/safety/sos.py`: `detect` (43-56), `build` (82-104, writes `evidence/sos/results.json`), `raise_test` (TEST alerts; the "phone-sensor" source is never stored).
- `scripts/live/run_sos_v2v.py`: `rule_check` (45-57), `COLLIDE_VS_VEINS` (61-68), `simulate` (60-157), the comparison (201-209), `--collide`, `--gui-colours`.
- `core/simulation/live_jobs/jobs.py:sos` (132-169) → `frontend/map/src/traffictwin/ttSim.ts:frameFeatures` (28-31): the web job.
- Outputs: `evidence/live_runs/sos_v2v/last_run.json`, `runs/<warn|nowarn>_…/collisions.xml`.

## Commands

    make run-sos-v2v                                        # seed 11, Dhaka density, ITS-G5, 50 % equipped; crashed red, warned blue, rerouted green
    make run-sos-v2v ARGS="--share 0.2 --tech c_v2x --seed 12 --crash-at 900"
    make run-sos-v2v ARGS="--veins"                         # Veins's own TraCIDemo11p (stopped car red, hearers green)
    make run-sos-collide ARGS="--share 0.5 --seed 12"       # a real contact detected by SUMO; prints the 5 differences from TraCIDemo11p first
                                                            # ... and (R1) writes the crash sensor's trace from SUMO's record: evidence/live_runs/sos_v2v/collision_trace.json
    make sweep-sos [ARGS="--quick"]                         # Q1: share 25/50/75/100 % x crash at 600/900 s x seeds 11-15, paired with no-warning twins -> evidence/sos/sweep/

## Results from saved evidence

**The rule** (`evidence/sos/results.json`, sha256 `28cb4636…`; 3 SYNTHETIC traces at 50 Hz, 30 s): normal ride peak 1.54 g, not detected;
hard brake peak 2.03 g, not detected; crash-like jolt peak 6.37 g, detected at 12.04 s with 5.87 g (the sample that fired the rule).
No trace carries a speed, so the speed floor (24.1 km/h) was not applied. The live run prints `REPRODUCED (evidence/sos/results.json)`.

**Car to car** (`evidence/live_runs/sos_v2v/last_run.json`, sha256 `2becb2ff…`; seed 11, Dhaka density, ITS-G5, 50 %, crash at 600 s,
300 s after, the stopped-car mode):

| | With the warning | Without |
|---|---|---|
| cars warned | 269 (half of them within 17 s) | 0 |
| cars rerouted / no alternative road | 1 / 47 | 0 / 0 |
| messages broadcast / sent / delivered / lost / out of range | 42 201 / 10 452 / 269 / 27 / 10 156 | 0 |
| affected cars (heading for the crash road) arrived, mean time to arrive | 35 of 51, 212.4 s | 35 of 51, 212.5 s |
| teleports | 0 | 0 |

A `--collide` run's record (collider, victim, lane, position, time from SUMO's `collisions.xml`) is written to the same file when that
mode is run (the current `last_run.json`, run 2026-10-11 evening, is a `--collide` run; the table above is the stopped-car mode's).

**The crash sensor on SUMO's own collision (R1, 2026-10-11 evening).** `core/safety/sos.py:from_collision` turns SUMO's record into the
trace the Emergency page replays: closing speed |collider − victim| as a 120 ms half-sine pulse (ASSUMED length, the synthetic trace's),
the same road noise, and the crashed car's speed on every sample so the 15 mph floor applies. Last run (seed 11, 50 %, headless):
collider CNG `veh284` at 12.26 m/s, victim motorcycle `cal300_174` at 20.00 m/s at t = 687 s; closing speed 7.74 m/s → 10.33 g pulse;
phone at 72.0 km/h; the rule fires at 12.02 s (5.18 g on that sample). File `evidence/live_runs/sos_v2v/collision_trace.json` (kind
`sumo_collision`, label SIMULATION); API `/api/emergency/sos/trace/sumo_collision`; Emergency chip "collision from the simulation";
Research RQ6 table, one labelled line; `make present` step 2 → step 7. The three SYNTHETIC traces are unchanged.

## The finding

The warning spreads fast (half the equipped cars within 17 s, 269 warned) but changes almost nothing: 1 car rerouted, 47 had no other
road, and the affected cars arrive in the same time (212.4 s against 212.5 s). On this corridor the crash road has no alternative for most
of the cars behind it, so a car-to-car warning can inform but not divert. This is one seed and one setting; it is a demonstration of the
path, not a measured benefit.

## The sweep (step Q1, 2026-10-11)

`make sweep-sos` (`scripts/live/sweep_sos.py`): 40 warning runs + 10 twins without any warning, 182 s, `evidence/sos/sweep/sweep.json`
(sha256 `52f20766…`). Per cell: cars warned 213-971, rerouted 1.4-8.4 (most warned cars have no other road); seconds saved by the cars
heading for the crash, over all of them with a car not arrived counted at 600 s: medians −4 to +6 s, slower in 1-4 of 5 seeds; extra
cars arrived within 600 s: up to 11.6 at 75-100 % when the crash is at 600 s, about 0 at 900 s. In-range delivery 0.90-0.91. The saved
live run's cell REPRODUCED. Reading: the message reaches the cars; the corridor gives them nowhere else to go, so the measurable gain is a
few more arrivals at high app shares, not a reliable time saving. Full table in `docs/LIVE_RUNS.md`.

## Honest limits

- No thesis number exists for car-to-car SOS; the sweep (Q1) covers 5 seeds, 4 shares and 2 crash times on one corridor and one technology (ITS-G5), 600 s after the crash.
- The crash rule was checked on three synthetic traces and, since R1, on a trace built from SUMO's collision record; the pulse shape and its 120 ms length are ours (SUMO has no impact physics: it records the two speeds at the contact), so this is still not a recorded crash. On recorded crashes (VZCrash, step M, 2026-10-11) the same rule finds 45.6 % of 4,221 test-split crashes at 88.6 % precision and 1.24 % false alarms: `features/crash-detection/README.md`, `evidence/sos/vzcrash/`.
- The stopped-car mode imposes the stop; `make run-sos-collide` differs from Veins's TraCIDemo11p in five ways (`run_sos_v2v.py:61-68`,
  read from the vendored source, not run): (1) their "accident" is a car told to stop, here SUMO detects a real contact (`speedMode 0`,
  `--collision.action warn`); (2) their trigger is "stood still for 10 s", so queues warn too, here it is SUMO's collision list; (3) their
  warning carries the road id and receivers call `changeRoute(road, 9999)`, here delivery goes through the thesis's V2X model and receivers
  reroute the same way; (4) they rebroadcast once with a random delay, here every warned car rebroadcasts every interval (a flood);
  (5) SUMO's own collision record is kept in `last_run.json`.
- The contact at 687 s in `runs/*/collisions.xml` (collider `veh284`, a CNG, victim `cal300_174`, a motorcycle, lane `24448661#0_0`) is the
  `--collide` mode's own crash: `cal300_174` is the car commanded at 600 s, and SUMO names the CNG the collider by its own rule (the rear car at the contact). The two `runs/` folders are shared by both modes, so the file there is from the last `--collide` run; the stopped-car mode logs no contact.
- The flood sends 10 452 messages for 269 deliveries: the protocol is not tuned, and the web map draws the colours only.
- Naming: the browser's alert request carries the value that fired the rule under the field `peak_g` (`docs/CODE_MAP.md`, gap 1).

## Live demo (2026-10-12)

    make run-sos-collide                             # a real collision inside SUMO (one car ignores the safe-speed rules), the SOS rule, the car-to-car warning, reroutes
    make present ARGS="--only sos"                   # the same as step 2 of the talk

What to watch: the crash (SUMO's own collision record), the warned cars (range ring, warned cars coloured) and the reroutes; the terminal prints
the rule check on the thesis traces first ("REPRODUCED"). Real: the OpenStreetMap corridor, the WreckWatch rule's published thresholds.
Simulated: the vehicles, the crash, the radio. Fallback: `ARGS="--no-gui"`.
