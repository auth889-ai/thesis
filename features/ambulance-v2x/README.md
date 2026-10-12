# Ambulance V2X alert (RQ3): does a car-to-car alert get the ambulance through sooner? (feature 1; README 2026-10-11)

**Goal.** An ambulance on a 3.4 km Dhaka corridor sends an alert over V2X (ITS-G5, C-V2X or 4G); equipped cars within 100 m ahead
make way (rule v2) and the route's signals turn green for it (copied safety state machine). Measured: the ambulance's travel time with
and without the alert, over seeds, equipped shares and densities. Everything here is SIMULATION on generated traffic scaled to two
counted sections ("Dhaka density" = scale 0.78); nothing is a statement about Dhaka at its recorded density.

## Pipeline

```
corridor net + demand (scale 0.78 = "Dhaka density")        core/simulation/ambulance/service.py:57-103  (service.scenario)
        │
        ▼  SUMO 1.27.1 + TraCI, one run per (arm, technology, share, seed, demand)
siren-only run (no alert) ──────────────────────────────────  the baseline every saving is measured against
alert run: AmbulanceRun.step each step                      service.py:133-152
        │  _alert: cars ahead within 100 m with a radio      service.py:169-207
        ▼
V2X delivery: out of range / lost / expired / delivered     core/networking/v2x/model.py:75-86   (configs/network_model.yaml: 425 m ITS-G5, 625 m C-V2X, 4G unlimited)
        │
        ├─ delivered → MakeWay.alert / release               core/simulation/ambulance/makeway.py:34-43, 52-59
        └─ junction on the route → SumoPreemption            core/simulation/signals/preemption/sumo_adapter.py:95-143 → emergency.py:46-66 → phases.py:62-101
        │
        ▼  per run: metrics.json (travel_time_s, messages, vehicles_alerted …)
results/emergency/dhaka/rq2/runs*/…/metrics.json  →  results/emergency/dhaka/rq2/summary.json (saved, findings, why_dhaka, plain)
```

## Upstream

| What | Where | Commit / version | Licence | How it is used |
|---|---|---|---|---|
| Eclipse SUMO + TraCI | pip `eclipse-sumo` | 1.27.1, commit `7717f237…` | EPL-2.0 | the simulation; bluelight device on in the thesis runs (SOURCES.md:9) |
| adaptive-traffic-signal-rl (2 files) | copied into `core/simulation/signals/preemption/{emergency,phases}.py` (+ `upstream_types.py`) | `b62436b5…` | MIT | the emergency override and the signal safety state machine, unchanged apart from a header and one import line; its own 36-run benchmark reproduced byte-identical first (`evidence/third_party/atsc_rl/`, SOURCES.md:163) |
| Veins | `~/.dhakaflow/upstream/veins` | 5.3.1 = `6571085f…` | GPL-2.0-or-later | second view only (`--veins`, `make gui-veins`): 802.11p frames under OMNeT++ 6.2.0 Qtenv; its numbers are Veins's, not the thesis's (SOURCES.md:194-195) |
| ours | `core/simulation/ambulance/{service,makeway,measures}.py`, `core/networking/v2x/model.py`, `sumo_adapter.py`, `scripts/live/run_v2x.py`, `run_veins.py`, `research/veins_dhaka/src/AmbulanceAlert11p.*` (subclass of `DemoBaseApplLayer`) | — | — | the scenario, the alert, make-way, delivery model, the live runs |

## Files

- `core/simulation/ambulance/service.py`: scenario (57-103), `AmbulanceRun` (133-213), `run_one` (297-350), `trip_metrics` (274-294).
- `core/simulation/ambulance/makeway.py`: rule v2 (100 m, keep the strategic lane change); `configs/ambulance.yaml:13-20`.
- `core/networking/v2x/model.py:deliver` (75-86); `core/networking/v2x/configs/network_model.yaml:19-70` (range, delivery ratio, delay per technology).
- `core/simulation/signals/preemption/`: `sumo_adapter.py` (ours), `emergency.py`, `phases.py` (copied), checked by `backend/tests/signals/test_preemption_adapter.py:75-76`.
- `scripts/live/run_v2x.py`: the live run; `gui_hook` (80-121) draws the ring, colours and label; `saved()` (59-62) and the check (193-202) compare with the saved metrics; `--gui-colours` (ambulance green, alerted yellow).
- `scripts/live/sweep_v2x.py`: the share sweep (`make sweep-v2x`).
- Web: `backend/app/live_jobs/router.py` → `core/simulation/live_jobs/{runner,jobs}.py:v2x` → `frontend/map/src/traffictwin/TtSimulation.vue`, `ttSim.ts`.

## Commands

    make run-v2x                                                   # seed 11, Dhaka density, ITS-G5, every car equipped; sumo-gui + THESIS CHECK
    make run-v2x ARGS="--tech c_v2x --share 0.5 --seed 12 --level x2"
    make run-v2x ARGS="--arm alert"                                # alert only, no green signals
    make run-v2x ARGS="--gui-colours --speed 8"                    # the talk's colours (display only)
    make run-v2x ARGS="--veins"   /   make gui-veins               # second view in OMNeT++ Qtenv (Veins's numbers)
    make sweep-v2x ARGS="--quick"                                  # share 0/25/50/75/100 % x 2 seeds → evidence/sweeps/ (5 seeds without --quick)
    make run-v2x-live                                              # 2026-10-12: seed from the clock (SEED= to choose), a random start and end, the thesis level; prints seed, route, demand, result
    make run-v2x-live SEED=4242 FROM=13848342#1 TO=1478491311#0    # a viewer's own seed and edges (the thesis trip's ends are these two)
    make run-v2x-live DEMAND=dhatrax-peak                          # the corridor at the FULL recorded DhaTraX counts (scale 1.0), heavier than the thesis level
    PYTHONPATH=.:backend python scripts/ambulance/peak_check.py    # the Step 2 check at the full counts → evidence/ambulance_rq2/dhatrax_peak/

### Live demo input (added 2026-10-12; defaults unchanged, so every saved number stays the same)

`scripts/live/run_v2x.py` now takes `--seed N|clock` (default 11 as before, so `make present` and the THESIS CHECK are unchanged; `clock` draws the seed from the clock and prints "SEED n (from the clock)", which `make run-v2x-live` does when SEED is not given), `--from`/`--to` (edge ids on
the corridor network, or `random`, drawn by the seed with at least 1.5 km of emergency-drivable route between them;
`service.random_route`, `service.scenario(..., route=)`), and `--demand current|dhatrax-peak`. The "Dhaka density" scale is read
from `evidence/ambulance_rq2/dhaka_density/match.json` (`chosen_scale`, computed by `corridor.match`), the recorded counts are
summed from `calibration.json` (BM 2361 veh/h on 2026-04-20, INT 1230 veh/h on 2026-04-19) and printed, the SUMO version and the
make-way distance are read, not typed, and the GUI label no longer shows a literal "rerouted 0". A chosen route is written under a
`r<hash>` folder, never into a study folder, and the THESIS CHECK says "new" for it. The web job (`core/simulation/live_jobs/jobs.py`
`validate("v2x")`) accepts the same `demand`, `from`, `to` (the page does not expose them yet). Tests:
`tests/platform/test_live_runs.py::test_run_v2x_live_inputs_…`, `::test_web_v2x_job_accepts_…`.

### Step 2 (2026-10-12): the same three arms at the FULL recorded DhaTraX counts (`--demand dhatrax-peak`, scale 1.0)

`scripts/ambulance/peak_check.py` → `evidence/ambulance_rq2/dhatrax_peak/` (`summary.json` sha256 `7a7a7bd1…`, `run.log`, one folder per run).
The counts are summed from `calibration.json` (BM 2361 veh/h, INT 1230 veh/h, 07:00-08:00);
the thesis level is x0.78 of them, this check is x1.0. ITS-G5, every car equipped, seeds from 11 upward until five completed.

| | no alert | alert | alert + pre-emption |
|---|---|---|---|
| ambulance arrived (of 5 seeds) | 4 | 5 | 5 |
| median travel time, arrivals only | 583.5 s | 417.0 s | 390.0 s |
| saving vs no alert, per seed (s) | — | -35, +94, +211, -311 (median +30) | -8, +132, +215, -97 (median +62) |
| teleports per run (SUMO's jam resolution) | 664-994 | 645-870 | 399-1020 |

Honest reading. Completed seeds: [12, 17, 19, 28, 31]; **16 of the 21 seeds tried died in SUMO's bluelight segfault** (the known
1.27.1 bug, `evidence/emergency/dhaka/sumo_bluelight_crash.json`; it strikes far more often at these counts than at the thesis level, 2 of 10).
At the full counts the corridor is gridlocked: hundreds of teleports per run, and in seed 17 the siren-only ambulance never arrived within
the hour. The alert's effect swings from -311 s to +211 s from seed to seed, so the medians above are not a reliable gain:
with only four paired seeds and that spread, the honest statement is "no stable effect measured at the recorded counts". The saved
thesis results (x0.78) are untouched by this check; its numbers appear only here and in `evidence/ambulance_rq2/dhatrax_peak/`.

## Results from saved evidence

**Live run** (`evidence/live_runs/v2x/last_run.json`, sha256 `d8b8025e…`; seed 11, Dhaka density, ITS-G5, 100 %, alert + pre-emption):
no alert 292 s → with alert 284 s (2.7 %); messages sent 190, delivered 101, lost 13, out of range 76; 30 cars alerted; 2 junctions
pre-empted; `thesis_check: true` (equal to the saved run).

**Study** (`results/emergency/dhaka/rq2/summary.json`, sha256 `00b67409…`, key `saved.<arm>.<share>.dhaka`; 10 seeds each, scale 0.78):

| Arm, equipped share | Mean saving, s | Median saving, s | 25th / 75th pct, s | Slower runs |
|---|---|---|---|---|
| alert, 25 % | 15.8 | 6.0 | −18.8 / 40.0 | 4 of 10 |
| alert, 50 % | 47.8 | 7.5 | −23.8 / 124.0 | 4 of 10 |
| alert, 75 % | 70.3 | 24.0 | 1.0 / 72.5 | 2 of 10 |
| alert, 100 % | 60.4 | 26.0 | −17.0 / 39.8 | 4 of 10 |
| alert + pre-emption, 25 % | −31.0 | 4.0 | −110.2 / 63.0 | 5 of 10 |
| alert + pre-emption, 50 % | 32.5 | 62.5 | −27.5 / 130.5 | 3 of 10 |
| alert + pre-emption, 75 % | −62.1 | 15.5 | −81.2 / 36.5 | 4 of 10 |
| alert + pre-emption, 100 % | 18.3 | 3.0 | −21.0 / 32.5 | 4 of 10 |

Across generated densities (`findings.density`, every car equipped): median saving −0.5 s at x0.5, 0.5 s at x1, 2.5 s at x2, 3.5 s at x3,
−2.0 s at x4; `findings.stops`: no equipped share reaches a median saving of 10 % at any density. The everyday sentence uses `plain`:
median 26 s, `alert_reliable: false`, `not_every_time: true`, 4 slower runs of 10.

**Share sweep, computed 2026-10-11** (`make sweep-v2x`, `evidence/sweeps/v2x_share.json`, alert + pre-emption over ITS-G5, seeds 11-15,
25 runs, 25 of 25 REPRODUCED exactly against the saved study runs): median saving 71 s at 25 %, 76.5 s at 50 %, 32 s at 75 %, 8 s at
100 %; 6 of 25 runs have no arrival (SUMO's bluelight device stopped the run, as in the saved runs); no monotone gain with the share.

## The finding

At the counted Dhaka density the alert does not give a reliable saving: a median 26 s with the alert alone and 3 s with pre-emption,
but a quarter of the runs are slower and the arms swap places from seed to seed (`docs/QA_PREP.md` §1, per seed). The 26 s vs 3 s gap
is inside the spread and **is not a reliable effect; its cause is not established**. What the 400 paired runs at generated densities
do say (`findings.why`): the saving falls with the free width ahead of the siren-only ambulance (Spearman rho −0.16, 95 % CI −0.25 to
−0.06) and rises with the queue at the route's signals (rho 0.18, CI 0.08 to 0.27), and is unrelated to how many alerted cars actually
moved aside (rho −0.003). The free width hardly changes with density (7.7-8.4 m), so room to move aside is not what limits the alert;
the ambulance's delay on this route sits at the junctions more than behind cars that could move.

## Honest limits

- All traffic is simulated; the demand is generated and scaled to two counted sections, not calibrated city-wide; the "Dhaka density"
  row is a 300 m corridor cut (1 198 of 6 527 roads) with no traffic from the rest of the city (`summary.json` `caveats`).
- The simulation does not reach Dhaka's recorded density on the INT section (`density_gap`): every ambulance number is from lighter traffic
  than Dhaka's recorded morning.
- The route crosses 2 signals; ITS-G5 only in the sweep; SUMO 1.27.1's bluelight device crashes on some seeds, and a crashed seed is
  replaced by the next one (`evidence/emergency/dhaka/sumo_bluelight_crash.json`).
- The make-way distance (100 m) is our own choice, fixed before the pilot; no published value exists (`summary.json` `makeway`).
- The web job always uses `alert_preemption` (`jobs.py:113`); `--veins` ignores `--tech` (802.11p only).
