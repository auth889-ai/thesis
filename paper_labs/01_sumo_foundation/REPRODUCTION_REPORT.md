# REPRODUCTION_REPORT — Lab 01: SUMO Foundation

Completed 2026-08-11 from real Google Colab execution. No SUMO software was
installed or executed on the local machine.

**References:** Alvarez Lopez et al. 2018 (SUMO, ITSC); Bieker et al. 2014/15
(Bologna scenario); Varaiya 2013 (max-pressure). Classification: the unit
experiments are **our own code** (Category C, DhakaFlow module) built on the
official SUMO runtime; the Bologna run is an **official scenario executed
unmodified** from the pinned upstream.

## 1. Environment (real, from the run)

- Google Colab (account anastasiasaat81@gmail.com, Colab Pro badge visible), Python 3 runtime
- **SUMO: Eclipse SUMO 1.27.1** via `eclipse-sumo==1.27.1` (pinned; verified latest on PyPI 2026-08-11)
- `SUMO_HOME=/usr/local/lib/python3.12/dist-packages/sumo`; sumo + netconvert binaries verified
- TraCI: working (all 16 unit-scenario runs were TraCI-controlled; "Reason: TraCI requested termination")
- Upstream pins: DLR-TS/sumo-scenarios @ `00f6eb479a9dc0fbaeb731495c11d48d7a9661d3`;
  SUMO source tag `v1_27_1` = `7717f2379d9e314a0c81c5cec748444de06a2a91`
- Notebook: https://colab.research.google.com/drive/1FBywHwVADHiKuXU6uG-Ffh3bivGYXjpU

## 2. What was executed (all in Colab)

1. Pinned install + environment verification (traci/sumolib importable via SUMO_HOME/tools).
2. `pytest` unit+integration tests and deterministic unit-network build (netconvert).
3. Smoke matrix (1 seed × 3 controllers × 900 s; 232 vehicles; 616× real-time).
4. **Full matrix: 5 seeds × 3 controllers × 2100 s, identical seeded demand per controller**
   (~570× real-time; ~57 s total simulation wall time).
5. Pinned upstream fetch; **Bologna/Acosta executed unmodified** (exit 0; no
   tracked upstream file modified; the scenario's own generated outputs recorded
   as untracked files — see `outputs/evidence/bologna_unmodified/RERUN_NOTE.md`).
6. Independent metric recomputation + safety verification + evidence bundling
   (Drive: `DhakaFlow-Nexus-Data/Lab01_SUMO/`, incl. `evidence_lab01.zip`).

## 3. Results — full 5-seed matrix (means over seeds; `outputs/evidence/unit_full/`)

| Controller | Throughput | Avg TT (s) | ±std | p95 TT (s) | Avg wait (s) | Mean queue | p95 queue | Stops proxy | Spillback proxy |
|---|---|---|---|---|---|---|---|---|---|
| fixed_time | 757.8 | 140.6 | 6.4 | 241.6 | 63.3 | 23.7 | 38.0 | 3.0 | **0.41** |
| actuated | 739.2 | 147.0 | 3.9 | 242.6 | **57.9** | **21.4** | **32.2** | 5.3 | **0.00** |
| max_pressure | 732.2 | 149.7 | 4.9 | 246.9 | 59.2 | 21.7 | **32.2** | 5.5 | **0.00** |

**Fair-comparison reading (identical demand, 5 seeds):** the adaptive
controllers (queue-actuated, max-pressure) reduce average waiting time (−8.5%
and −6.5%), mean queues (−10%), p95 queues (−15%), and completely eliminate the
spillback-proxy episodes that the fixed plan suffers in 41% of steps under the
asymmetric demand peaks. The fixed plan achieves slightly higher raw throughput
and lower mean travel time in this small symmetric network — a well-known
trade-off, honestly reported; no controller is declared "winner" beyond what
the numbers support. Max-pressure behaves close to queue-actuated at this
single intersection (expected: its advantage is network-level pressure
coordination, which one junction cannot exhibit).

## 4. Verification

- **Independent recomputation** (fresh parser, not `metrics.py`): avg/p95 travel
  time, waiting time, mean queue, throughput recomputed from raw `tripinfo.xml`
  + `step_metrics.csv` for all 3 controllers (seed 11) — **exact match** with
  the pipeline (`outputs/evidence/verification_record.json`).
- **Safety:** 15/15 runs, **0 collision mentions, 0 teleports** in SUMO logs;
  yellow transitions preserved by construction (green terminated via
  `setPhaseDuration(0)` against a static program containing `yyrr`/`rryy`,
  asserted by `tests/unit/test_scenario_xml.py`); min/max-green enforced as
  pre-decision guards in both adaptive controllers. Two isolated
  emergency-braking warnings (severity 1.0) across all runs, recorded.
- Local SUMO-free tests: 4 passed. Colab pytest cell completed within the run.

## 5. Modifications & limitations (all logged in `resources/HANDOFF_MERGE_LOG.md`)

1. Colab bootstrap via Drive zip (repo is local-only) — notebook cell 3.
2. `/usr/bin/time` absent in Colab → Bologna wrapper fixed (first attempt exit 127).
3. Upstream-integrity check corrected to "no tracked file modified" (the
   unmodified acosta config writes untracked outputs into its own directory).
4. `install_colab.sh`'s `import traci` check is wrong for the wheel layout —
   documented; environment provided by `colab_env.configure_sumo_env()`.
5. Bologna re-run's refreshed manifest/tails live in Drive; Chrome blocked the
   automated re-download to this machine (values transcribed in RERUN_NOTE.md).
6. Stops = `waitingCount` proxy; spillback = queue-ratio proxy (as labelled).
7. Max-pressure here is a single-intersection movement-pressure controller —
   NOT a full Varaiya network reproduction (per handoff scientific note).
8. Free Colab runtime disconnected once mid-gate; the affected cell was re-run;
   Bologna statistics beyond the manifest were not extracted from tripinfo
   (upstream config controls its own outputs) — out of the unit-gate scope.
