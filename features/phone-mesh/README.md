# Phone mesh: phone-to-phone alerts without the network (RQ4: PONS; The ONE as a second view)

**Goal.** When the mobile network is down, can a crash alert hop from phone to phone between vehicles? Three delay-tolerant routers
(Epidemic, Spray and Wait, PRoPHET) run inside PONS on the movement of a Dhaka SUMO run, with the radio range of The ONE's default
Bluetooth interface; The ONE itself shows the same setting in its own window as a second, independent view. Everything is
SIMULATED on generated, uncalibrated traffic.

## Pipeline

```
Dhaka SUMO network (data/cities/dhaka_r1, randomTrips demand, seed 11)      research/mesh_pons/scripts/01…
        │
        ▼  SUMO tools/traceExporter --ns2mobility-output, seconds 900-1200
ns-2 movement trace (sha256 2ca59a89…)                                      scripts/02_export_movement.py  → evidence/movement.json
        │
        ▼  read_ns2 + generator_with_metadata (our two adapters, each justified by a saved failure log)
PONS 0.2.1 NetSim: 17 phones present for the whole window, 10 m radio,       scripts/03_run_pons.py  → research/mesh_pons/evidence/runs/*.json
one 100-byte message per second, TTL 300 s, seeds 1-5, three routers
        │
        ▼
results/networking/mesh/dhaka/summary.json  (delivery, delay, copies, overhead)   core/networking/mesh/results.py
        │                                   │
        ▼ Offline alerts page / map chip    ▼ live: make run-mesh (matplotlib, REPRODUCED seed by seed) · make gui-mesh (The ONE's GUI)
```

## Upstream (`third_party/SOURCES.md`, "Phone mesh" rows)

| What | Where | Commit / version | Licence | How it is used |
|---|---|---|---|---|
| PONS, Python Opportunistic Network Simulator | pip `pons-dtn==0.2.1` (`research/mesh_pons/.venv`) | identical to tag `0.2.1` = `2fd70381b1b02e3e2227b5e596dc7fd92f458893` | MIT | `NetSim`, `EpidemicRouter`, `SprayAndWaitRouter`, `PRoPHETRouter`, unchanged; its own `sim.py` and `examples/ext_ns2.py` run first (`evidence/upstream_sim.log`, `upstream_ext_ns2.log`; PONS publishes no reference numbers) |
| The ONE simulator | `~/.dhakaflow/upstream/the-one` | tag `v1.6.0` = `42b6e20f45799f2533866df215768fa9aedd0f4f` | GPL-3.0 | `core.DTNSim` GUI and batch, `ExternalMovement`, the three routers, `MessageStatsReport`; no code copied. The 10 m range cited from `default_settings.txt` lines 19-23 (commit `43eaab1e…`) |
| SUMO `tools/traceExporter.py`, `randomTrips.py` | pip `eclipse-sumo` 1.27.1 | tag `v1_27_1` | EPL-2.0 | The movement trace and the demand, unchanged |

## Files

- `research/mesh_pons/scripts/02_export_movement.py` (`main` 36-104): the ns-2 trace and its hash.
- `research/mesh_pons/scripts/03_run_pons.py`: `read_ns2` (28-38), `generator_with_metadata` (41-54), `make_router` (57-64), `run_one` (85-113).
- `core/networking/mesh/results.py:build` (36-92) → `results/networking/mesh/dhaka/summary.json`; served by `backend/app/mesh/router.py:get_results` (11-14); shown by `frontend/src/features/emergency/OfflineAlertsPage.tsx` (14-29).
- `scripts/live/run_mesh.py` (`simulate` 41-63, `View` 88-109, the seed check 166-175); `scripts/live/mesh_frames.py` (web frames).
- `scripts/live/run_mesh_one.py` (`movement` 28-39, `settings` 42-82, `main` 86-115; `--legend`): The ONE's GUI.
- `research/mesh_pons/configs/dhaka.yaml` (the 10 m range, lines 7-10); `research/mesh_pons/RESULTS.md`.

## Commands

    make run-mesh                                             # LIVE: PONS drawn as it runs, 17 phones, 10 m, epidemic, study seeds; THESIS CHECK seed by seed
    make run-mesh ARGS="--protocol epidemic --phones 8 --range 30"   # other settings: the result is new, not the thesis's
    make gui-mesh                                             # The ONE's own window (17 phones, 10 m, PRoPHET, seed 1); press Play; the legend is printed
    make gui-mesh ARGS="--protocol epidemic --seed 3"
    python -m core.networking.mesh.results --city dhaka       # rebuild the summary from research/mesh_pons/evidence/runs/

## Results (`results/networking/mesh/dhaka/summary.json`, sha256 `084fb854…`; seeds 1-5, mean ± sd)

| Router | Delivery ratio | Delay of delivered, s | Copies per message | Seeds without a delivery |
|---|---|---|---|---|
| Epidemic | 0.028 ± 0.009 (min 0.013, max 0.033) | 65.2 ± 21.4 | 0.62 ± 0.09 | 0 |
| Spray and Wait (7 copies) | 0.027 ± 0.014 (min 0.010, max 0.043) | 60.0 ± 20.7 | 0.44 ± 0.04 | 0 |
| PRoPHET (PONS defaults) | 0.029 ± 0.013 (min 0.010, max 0.047) | 77.6 ± 22.1 | 0.03 ± 0.01 | 0 |

Scope (`summary.json` `scope`): window 900-1200 s, 277 vehicles seen, 17 simulated (present for the whole window), 300 messages
per seed. Live check (`evidence/live_runs/present_20261011_095038/mesh.log`): epidemic, seeds 1-5, delivered 4/10/8/10/10 of 300 →
delivery 0.028, REPRODUCED seed by seed. Sweeps over phones (4/8/12/17) and range (10 against 30 m) are in `research/mesh_pons/RESULTS.md`.
The ONE's own run records no statistics yet (`evidence/live_runs/mesh_one/last_run.json` `stats: {}`); it is a view, not a result.

## The finding

**With 17 phones over a 5.8 × 5.5 km network and a 10 m radio, contacts are rare: about 3 % of alerts reach their destination within
5 minutes, whichever router is used.** The routers differ in cost, not in reach: Epidemic spends 0.62 copies per message, Spray and
Wait 0.44, and PRoPHET 0.03 because in this sparse window its delivery predictability never favours a relay, so every PRoPHET delivery
is a direct source-to-destination contact (`RESULTS.md:59-65`). The low delivery is the sparse setup, not a property of Dhaka traffic.

## Routers over the phone count in The ONE (step P, added 2026-10-11; `evidence/mesh/routers/sweep.json`, sha256 `2c777c3e…`)

`make sweep-mesh`: The ONE's EpidemicRouter, SprayAndWaitRouter (7 copies), ProphetRouter and MaxPropRouter on the study window with
17 / 50 / 100 / 200 phones (ranked by presence; absent phones parked out of range; the 17 full-window phones are the only senders and
receivers, the rest relay), seeds 1-3, radio 10 m. Delivery ratio 0.036-0.040 for every router at every count (sd over seeds <= 0.01),
latency 71-79 s. **Finding: the router and the relays make no difference here**: at a 10 m radio over a 5.8 x 5.5 km network in 300 s,
contacts are the bottleneck. Checked (`make sweep-mesh ARGS="--range-sweep"`, `evidence/mesh/range/range.json`, sha256 `0010567a…`): with
Epidemic the delivery ratio rises with the radio range, 0.036 -> 0.110 (17 phones) and 0.040 -> 0.184 (100 phones) from 10 to 100 m,
and relays begin to matter only at the longer ranges. The ONE's numbers (second view), consistent with the thesis's PONS 0.028; the thesis result is untouched.

## Honest limits

- Generated, uncalibrated traffic (randomTrips), one network, one 300 s window, 17 of 277 vehicles; nothing is a measurement of the city.
- The movement is the same in every seed; the spread is only over which vehicles send to which and when.
- The alerts never feed back into the traffic: the routers decide inside PONS and The ONE, the cars do not react.
- The radio is an ideal 10 m disc with PONS's own model, no loss beyond it; 10 m is The ONE's default Bluetooth value, not a measurement.
- PONS publishes no reference numbers, so its own examples are recorded, not compared; The ONE's numbers are its own and are not the thesis's.
- Mesh does not run on the hosted server (no PONS or Java there); `make run-mesh` and `make gui-mesh` are local.
- Phone-count sweep (step P): The ONE, not PONS; added phones are vehicles present for only part of the window, parked out of range when
  absent (a modelling choice, stated in `scripts/live/sweep_mesh.py`); 300 messages per run, 3 message sets; one radio range (10 m).

## Live demo (2026-10-12)

    make run-mesh                                    # PONS mesh drawn as it runs (phones, range circles, deliveries); THESIS CHECK seed by seed
    make gui-mesh                                    # second view: The ONE's own GUI on the thesis setting (17 phones, 10 m, PRoPHET)

Colours (The ONE): blue squares phones, green circles range, black lines connections, red lines transfers. Real: the simulators' code (MIT /
GPL run only) and the mobility model's parameters. Simulated: every phone, every hop. Fallback: `make sweep-mesh ARGS="--quick"`.
