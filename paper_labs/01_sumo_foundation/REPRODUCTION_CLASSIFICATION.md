# REPRODUCTION_CLASSIFICATION — Lab 01

Every component of Lab 01 carries exactly one label. No component is described
with a stronger claim than its evidence supports.

| Component | Classification | What that means here | Evidence |
|---|---|---|---|
| **SUMO paper** (Alvarez Lopez et al. 2018) | `FOUNDATION_VALIDATION` | The paper is a tool reference, not an algorithm to reproduce. We validate that we can operate the tool as the paper describes (scenario triple, repeated stochastic runs, documented outputs, TraCI coupling). **No paper metric is reproduced because the paper reports none for us to match.** | `PAPER_SUMMARY.md` §1; `PAPER_TO_CODE_MAP.md` rows 1–5, 9, 11 |
| **SUMO software** (v1.27.1) | `OFFICIAL_IMPLEMENTATION_USED` | Official binary/wheel, pinned tag + SHA, never vendored or patched. All simulation physics is upstream code. | `upstream/UPSTREAM_LOCK.yaml`; `EV/verification_record.json` (`Eclipse SUMO sumo 1.27.1`) |
| **Bologna/Acosta scenario** | `OFFICIAL_SCENARIO_EXECUTION` | The official municipal-derived scenario was executed **unmodified** from the pinned upstream SHA; exit 0; no tracked upstream file changed. We do **not** claim to reproduce the Bologna paper's validation study (their sim-vs-detector comparison), only that the official artefact runs correctly under our pinned stack. | `EV/bologna_unmodified/manifest.txt`, `RERUN_NOTE.md`, `FIG/11_bologna_scenario.png` |
| **Fixed-Time controller** | `CLASSICAL_BASELINE` | Standard practice, no paper claim. Implemented as pure observation: SUMO executes the declared static plan. | `src/.../controllers/fixed_time.py`; `EV/unit_full/aggregate_metrics.csv` |
| **Queue-Actuated controller** | `CLASSICAL_BASELINE` | Textbook demand-responsive actuation (extend on served queue, min/max green). No specific paper reproduction claimed. | `controllers/actuated.py` |
| **Max-Pressure controller** | `BASELINE_IMPLEMENTATION` — **NOT a full paper reproduction** | Single-intersection movement pressure (q_in − q_out over green movements). Varaiya (2013) is a **network-level** formulation with a stability theorem, known turning ratios, and network experiments. We implement none of that, claim none of that, and report none of Varaiya's metrics. Its advantage is structurally invisible at one junction. The dedicated classical-control lab performs the network-scale benchmark. | `controllers/max_pressure.py`; caveat repeated in `REPRODUCTION_REPORT.md` §3, `LAB_DASHBOARD.md`, `FIG/02` |
| **Our 5-seed controller matrix** | `DHAKAFLOW_FOUNDATION_EXPERIMENT` | Our own fair-comparison experiment on our own unit scenario: identical demand/seeds/scenario/duration across three controllers. It is evidence that the *harness* is trustworthy — not a claim about which controller is best in general, and not comparable to any published number. | `EV/unit_full/{per_seed,aggregate}_metrics.csv`; `FIG/04–09` |
| **Independent metric recomputation** | verification procedure (not a result) | Fresh parser recomputed avg/p95 travel time, waiting, mean queue, throughput from raw `tripinfo.xml` for all three controllers at seed 11; exact match with the pipeline. | `EV/verification_record.json::indep_metrics` |

## Claims we explicitly do NOT make

1. We do **not** claim reproduction of any published numerical result — none of
   the three papers provides a metric that this lab's scenario could match.
2. We do **not** claim Varaiya-style max-pressure performance or stability.
3. We do **not** claim Bologna calibration/validation quality (the paper's
   85 %/15 % criterion is *not* evaluated here).
4. We do **not** claim the fixed-time/adaptive ranking generalises beyond this
   single symmetric junction under this synthetic demand.
5. We do **not** claim heterogeneous-traffic realism — the sublane model is
   identified for later use (Lab 13) but is unused here.

## Result-type separation (per the traceability rule)

- `PUBLISHED_RESULT` — **none applicable** in this lab (see above).
- `REPRODUCED_RESULT` — **none claimed**; the only upstream artefact reproduced
  is *successful unmodified execution* of Acosta (binary outcome: exit 0).
- `DHAKA_RESULT` — **none**; Lab 01 contains no Dhaka data. Dhaka enters at
  Lab 02 (network) and Lab 13 (calibration).
- `DHAKAFLOW_FOUNDATION_EXPERIMENT` results — the 5-seed matrix table, frozen at
  commit `ca2ac81`.
