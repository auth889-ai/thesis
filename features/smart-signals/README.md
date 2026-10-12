# Smart signals: sumo-rl Q-learning against fixed time on the Dhaka corridor (feature 3; README 2026-10-11)

**Goal.** Let the 3 traffic lights within 500 m of the ambulance route be controlled by sumo-rl's Q-learning agents (trained
beforehand, frozen during evaluation) instead of SUMO's fixed-time programmes, and measure the ambulance's travel time and the cost to
everyone else (vehicle-hours). SIMULATION on generated traffic scaled to two counted sections.

## Pipeline

```
corridor net + demand (scale 0.78 = "Dhaka density")       core/simulation/ambulance/service.py:57-103
        │
        ├─ FIXED-TIME side: service.run_one(observe=True)    service.py:297-350, hook = display (run_signals.py:48-90)
        │
        └─ Q-LEARNING side: rl_signals.run                    core/simulation/ambulance/rl_signals.py:127-180
              _sumo_rl checks the pinned commit (31-40)       ~/.dhakaflow/upstream/sumo-rl @ 86f0fc41…, venv ~/.dhakaflow/venvs/sumo-rl-np1
              corridor_signals: lights within 500 m (43-53)
              _env subclasses sumo_rl.SumoEnvironment (64-80), _sumo_step at 69-74
              frozen Q-tables, alpha 0, epsilon 0 (155-166)   results/emergency/dhaka/rq2/rl/q_*.pkl  (trained: train --scale 2 --episodes 30)
        │
        ▼  both sides: RouteObserver (measures.py:38-106), trip_metrics (service.py:274-294)
ambulance travel time, queue at signals, time blocked, total vehicle-hours → THESIS CHECK against results/emergency/dhaka/rq2/runs/…
aggregate: results/emergency/dhaka/rq2/summary.json  (findings.rl, saved.rl_signals, qlearning_dhaka)
```

## Upstream

| What | Where | Commit / version | Licence | How it is used |
|---|---|---|---|---|
| SUMO-RL (Alegre, 2019; RESCO nets from Ault & Sharon, NeurIPS 2021 D&B) | `~/.dhakaflow/upstream/sumo-rl`, unchanged | `86f0fc41…` (2026-03-08), checked at run time | MIT | `SumoEnvironment`, `agents.QLAgent`, `exploration.EpsilonGreedy`, its default observation, reward ("diff-waiting-time") and timing; extended by a subclass only. **Reproduced first:** `experiments/ql_single-intersection.py` unchanged, `evidence/ambulance_rq2/reproduce/SUMMARY.json` (SOURCES.md:156) |
| Eclipse SUMO + TraCI | pip | 1.27.1, `7717f237…` | EPL-2.0 | the simulation and its fixed-time programmes (SOURCES.md:9) |
| ours | `rl_signals.py` (subclass, training loop, evaluation), `scripts/live/run_signals.py`, `measures.py`, `core/simulation/live_jobs/jobs.py:signals` (210-258) | — | — | the two-window live run, the measures, the web job |

## Files

- `core/simulation/ambulance/rl_signals.py`: pin check (31-40), `corridor_signals` (43-53), `_env` (64-80), settings (90-124: alpha 0.1, gamma 0.99, epsilon 0.05→0.005), `run` (127-180), training seeds separate from evaluation seeds (:27).
- `scripts/live/run_signals.py`: `main` (114-157) starts two `side_main` processes (93-111); `display` (48-90); `saved` (42-45) and the check (148-155).
- `core/simulation/ambulance/measures.py:RouteObserver` (38-106).
- Outputs: `evidence/live_runs/signals/{last_run,last_fixed,last_rl}.json`, `runs/`.

## Commands

    make run-signals                                   # seed 11, Dhaka density: two sumo-gui windows, FIXED-TIME left, Q-LEARNING right; table + 2 THESIS CHECKs
    make run-signals ARGS="--level x2 --seed 12"
    python -m core.simulation.ambulance.rl_signals train --scale 2 --episodes 30     # training (already done; writes results/emergency/dhaka/rq2/rl/q_*.pkl)

## Results from saved evidence

**Live run** (`evidence/live_runs/signals/last_run.json`, sha256 `08658694…`; seed 11, Dhaka density; `checks: [true, true]`):

| Side | Ambulance travel time, s | Queue at signals | Time blocked, s | Total vehicle-hours |
|---|---|---|---|---|
| fixed time (SUMO programmes) | 292 | 4.0 | 49 | 532.3 |
| Q-learning (sumo-rl, frozen) | 188 | 0.0 | 2 | 793.9 |

**Study** (`results/emergency/dhaka/rq2/summary.json`, sha256 `00b67409…`):
- `findings.rl` (generated densities, 3 signals controlled): median saving against SUMO's programmes 11.0 s at x0.5, 32.5 s at x1,
  36.0 s at x2, 39.0 s at x3, 92.5 s at x4; the Q-learning signals' median saving beats the alert to every vehicle at 5 of 5 densities (`findings.why`).
- `saved.rl_signals.0.dhaka` (10 seeds, Dhaka density): mean saving −54.8 s, median −49.5 s, 25th/75th pct −243.8 / 140.0 s, 5 of 10 runs slower;
  with the alert as well (`rl_signals_alert.1.dhaka`): mean 0.9 s, median 33.5 s, 4 slower.
- `qlearning_dhaka` (the 5 Dhaka-density seeds where Q-learning made the ambulance slower: 14, 18, 19, 21, 23): the ambulance stood
  2 065 s in all against 699 s siren-only; 0 of those seconds within 100 m of a light; the next light was green for it in 1 962 s, red in 0 s.
- sumo-rl's own example, reproduced first (`evidence/ambulance_rq2/reproduce/SUMMARY.json`): Q-learning's mean total waiting over the last
  20 % of steps 31.2 against fixed timing's 3 418 365.7, the direction of the README figure (no published number to match).

## The finding

At generated densities the learned signals help the ambulance more than the car-to-car alert does (median 11-92 s saved against the
fixed programmes, growing with density), which says the ambulance's delay on this route sits at the junctions. At Dhaka density the
picture reverses: a median loss of 49.5 s over 10 seeds, with 5 runs slower, and on seed 11 the ambulance's gain (292 → 188 s) costs
everyone else 794 against 532 vehicle-hours. The logs of the slow seeds show the lights did not hold the ambulance directly (never
within 100 m of a light); it stood in short queues whose heads were cars waiting to change lane. **The cause of the slowdown and of the
vehicle-hours cost is not established** (`summary.json` `qlearning_dhaka.reading`, :884); it is stated, not explained.

## Max-Pressure and EV priority (step S, added 2026-10-11; `evidence/signals/controllers/compare.json`, sha256 `6dd664df…`)

`make compare-signals`: fixed time, Q-learning, Max-Pressure (Varaiya 2013, our `signal_baselines.MaxPressureController`; RESCO is GPL-3.0
and LibSignal unlicensed, so neither was copied: `third_party/SOURCES.md`) and Max-Pressure + EV priority (`core/simulation/ambulance/
mp_signals.py`: the junction ahead of the driving ambulance prefers its approach's green, program-safe, no V2X message), seeds 11-15,
Dhaka density. Mean ambulance time 411.6 / 380.3 / 493.6 / 475.0 s; others' mean time loss 483.1 / 417.4 / 490.8 / 493.0 s; queue at the
signals 7.4 / 0.4 / 3.7 / 1.8 vehicles. Paired against fixed time, Max-Pressure is +82 ± 629 s for the ambulance (2 of 5 better) and
+63 ± 495 s with EV priority (2 of 5): **not reliably better**. Fixed time and Q-learning reproduced the study's runs 10 of 10.
Per-seed table and plot: `docs/LIVE_RUNS.md` "Max-Pressure signals", `evidence/signals/controllers/compare.png`.

## Honest limits

- The reward and state are sumo-rl's defaults (diff-waiting-time), not tuned for an ambulance; the agents never see the ambulance.
- 3 lights controlled, trained at scale 2 for 30 episodes and evaluated frozen; no training at Dhaka density itself.
- Vehicle-hours are for the corridor cut (1 198 of 6 527 roads), with no traffic from the rest of the city; the demand is generated.
- The Q-learning side runs in a separate venv (`~/.dhakaflow/venvs/sumo-rl-np1`) and does not run on the hosted server.
- The web map draws no signal state (counts only); the mean saving at Dhaka density has sd 264 s over 10 seeds, so no arm is reliably different.
- Max-Pressure (step S): our implementation, not RESCO's or LibSignal's (licences); queue-based pressure with halting counts, min/max
  green 10/60 s; EV priority sees the ambulance's position directly (as a transponder would), which the V2X arms do not assume; 5 seeds,
  one level; the Q-learning arm lost 2 seeds to SUMO's bluelight stop, so its paired numbers rest on 3 seeds.

## Live demo (2026-10-12)

    make run-signals                                 # two sumo-gui windows: fixed time (left) vs sumo-rl Q-learning (right), seed 11; THESIS CHECKs
    make gui-ambulance-loop                          # Part E: the Q-learning signals WITH the V2X alert and V2I pre-emption in one run (features/ambulance-loop/README.md)

What to watch: the three controlled lights near the route; the ambulance's time and the vehicle-hours of everyone else in the terminal. Real:
the road network and sumo-rl's code (MIT, pinned). Simulated: the traffic, the agents' decisions (frozen Q-tables, no learning during the demo).
Fallback: `make compare-signals ARGS="--quick"` (headless table).
