# DhakaFlow — what was built, what is proven, what is not

**Traffic prediction first, route optimisation second.** Every number below is read from a file
in this package, and every file names the one command that regenerates it. Nothing is typed by hand.

Verified at commit `33659af`. Tests: **232 passed, 5 skipped**. CI: **green**.

## The research question

> **How do realistic V2X communication constraints affect distributed traffic forecasting
> accuracy, and how does that prediction degradation affect prediction-aware routing
> performance?**

Everything below is either (a) the reproduction baseline that question is built on, or (b) an
experiment answering part of it. The single causal chain under test is:

`communication impairment → federated forecasting accuracy → predicted edge costs → routing
decision → SUMO travel time and waiting time`

Sections 1-5 are the verified foundation. Section 8 lists the experiments still running.

---

## 1. Phase 1 — traffic prediction (the priority)

Official architectures, official configs, trained on GPU (never on a laptop), evaluated under the
standard protocol and checked against the numbers their authors published.

### METR-LA (207 sensors, 34,272 five-minute bins)

| model | MAE@15 min | MAE@30 | MAE@60 | published MAE@15 | gap |
|---|---|---|---|---|---|
| **STAEformer** (CIKM 2023) | **2.674** | 2.985 | 3.350 | — | — |
| **Graph WaveNet** (IJCAI 2019) | **2.719** | 3.111 | 3.595 | 2.69 | **+1.1 %** |
| **STID** (CIKM 2022) | 2.825 | 3.214 | 3.593 | — | — |
| persistence *(floor)* | 3.460 | 4.147 | 5.308 | — | — |
| historical average *(floor)* | 4.189 | 4.189 | 4.189 | — | — |

### PEMS-BAY (325 sensors, 52,116 bins)

| model | MAE@15 min | MAE@30 | MAE@60 | published MAE@15 | gap |
|---|---|---|---|---|---|
| **Graph WaveNet** | **1.308** | 1.638 | 1.945 | 1.30 | **+0.6 %** |
| **STID** | 1.318 | 1.644 | 1.920 | — | — |
| persistence *(floor)* | 1.590 | 2.170 | 3.040 | — | — |

50 epochs each, Tesla T4 (`g4dn.xlarge` / `g5.xlarge`), BasicTS harness pinned at
`4c3e2d373c647667c2123e1591f2d79c229dfcc6`, configs unmodified except epochs and horizons.
→ `results/forecasting/phase1_comparison.md`, `trained_results.csv`, `aws_logs/`

### Why these numbers can be trusted

**The evaluation protocol was validated before any model was trained.** Our historical-average
floor on METR-LA is 4.189 MAE / 7.86 RMSE; DCRNN (ICLR 2018, Table 1) publishes 4.16 / 7.80 for
the same baseline — a **0.7 % match**. A wrong split, a wrong mask, or a wrong scaler would have
shown up here, before the results could flatter us. The same check on PEMS-BAY is looser
(3.02 vs 2.88 MAE, **4.9 %**), which is stated in the file rather than only the flattering half.

**A machine-checked gate, not a claim.** Six conditions, all PASS:

| gate | what it checks |
|---|---|
| G1 | results exist on two independent cities |
| G2 | all four arithmetic floors computed on both |
| G3 | all trained models present |
| G4 | **every trained model beats every floor** |
| G5 | GWNet reproduces its published MAE at all horizons (worst gap +1.8 %) |
| G6 | saved checkpoints reload and reproduce their error (≤3.6 %) |

G6 matters: it proves the weights on disk actually produce the reported numbers. It also caught a
real bug — the checkpoint finder matched on architecture alone, so a GWNet/PEMS-BAY run silently
loaded METR-LA weights. Only the differing sensor counts (325 vs 207) exposed it.

### The metric the field reports hides where models actually differ

Average MAE over a whole test set is dominated by free-flow bins, where forecasting is easy and
nobody needs it. Scoring the full test region of both cities on the bins that are *actually*
congested (per-sensor threshold at 60 % of that sensor's own free-flow speed, taken from the
training split only) gives a different picture:

| METR-LA, 15 min | overall MAE | **congestion MAE** | free-flow MAE | congestion F1 | onset detection |
|---|---|---|---|---|---|
| Graph WaveNet | 2.71 | **6.92** | 2.18 | 0.851 | 70.7 % |
| STID | 2.83 | **7.97** | 2.18 | 0.830 | 60.9 % |

Three findings:

1. **Error during congestion is 2–4.5× the reported average.** GWNet is 2.71 MAE overall on
   METR-LA but 6.92 where it matters; on PEMS-BAY, 1.31 vs 4.43.
2. **It degrades far faster with horizon than the headline suggests.** GWNet's congestion MAE runs
   4.60 → 11.50 from 5 to 60 min (2.5×) while its free-flow MAE moves only 1.94 → 2.56 (1.3×).
   Recall falls 0.90 → 0.70 while precision holds — these models grow conservative at long range
   and *miss* jams rather than raising false alarms.
3. **Ranking by average MAE understates the operational gap.** GWNet beats STID by 4 % on average
   MAE at 15 min, but by 15 % on congestion MAE and 16 % on onset detection rate.

Congestion warning lead time is also reported, two ways: the earliest horizon that flags an onset,
and a stricter *sustained* lead requiring every horizon from 5 min up to it to agree, so one lucky
long-range flag cannot be sold as an hour of notice. Sustained lead is 36 min on METR-LA but only
15 min on PEMS-BAY — lead time is a property of the site, not just of the model.

→ `results/forecasting/congestion_metrics.md`

### Honest position in the field

The field is **saturated**. Four years moved best-known METR-LA MAE from 2.69 to 2.65 — 1.5 %.
Ten architectures published 2018–2023 sit inside 2.67–2.85, a spread plausibly within seed noise.
Our STAEformer at 2.674 sits **0.9 % off** the best published number and ahead of ten published
models; our PEMS-BAY GWNet at 1.308 is state-of-the-art-tier. This is a faithful reproduction at
published strength — it is *not* a claim of a new architecture, and the report does not make one.

### Portability across cities — what is and is not shown

`pipeline/forecasting/city_datasets.py` is one interface over METR-LA, PEMS-BAY, PEMS04, PEMS08,
a Dhaka twin, and the Dhaka live feed. Adding a city is a registry entry, not a code change.
A subtle trap is handled explicitly: METR-LA encodes sensor outages as `0.0`, which is also a legal
speed. The mask carries missingness end-to-end and values are never imputed.

**This demonstrates software portability, not cross-city prediction accuracy.** Multiple loaders
prove the pipeline runs on a new city's data; they say nothing about whether a model trained on one
city forecasts well on another. A cross-city generalization claim requires a zero-shot / fine-tuned
comparison against city-specific models, which is in progress and is **not claimed here**.
Dhaka prediction accuracy in particular is **not claimed** — there are not yet enough legitimate
Dhaka historical observations to support it.

---

## 2. Real live data — Dhaka, measured not simulated

A recorder has been sampling **six real Dhaka corridors every five minutes** through the Google
Routes API: **218 sweeps, 1,295 successful captures, 13 failures**, ~11 hours and growing.
Congestion classes on the real road network — at the time of writing, `karwanbazar→shahbagh`
SEVERE, `karwanbazar→banglamotor` CONGESTED, `farmgate→shahbagh` SLOW.

**Terms-of-service compliance is enforced in code, not promised in prose.** The recorder runs in
`RUNTIME_REFERENCE` mode: only the *derived* congestion verdict is stored. Durations, distances,
speed-reading intervals and polylines are in a `never_persisted` list and are dropped before
writing. → `artifacts/live_dhaka/RECORDER_MANIFEST.json`

---

## 3. Phase 2 — route optimisation, including the results that did not work

Route optimisation was evaluated on **paired seeds** with bootstrap confidence intervals and
paired Wilcoxon tests, on the real Dhaka R1 road network in SUMO.

| arm | mean travel time vs static | 95 % CI | p |
|---|---|---|---|
| **DUE (equilibrium)** | **−22.5 %** | [−30.0, −13.4] | 0.01 |
| reactive (greedy rerouting) | **+12.8 % — worse** | [5.8, 23.3] | 0.00 |
| predictive (oracle forecast) | +1.9 % | [−5.1, 8.4] | 0.56 — not significant |

**Two of these are negative results and both are reported.** Greedy reactive rerouting makes the
network measurably *worse* (teleports rise 5,274 %, arrivals fall 6.5 %) — the classic
overreaction/oscillation failure. Predictive rerouting shows no significant effect at this demand.
Only user-equilibrium assignment helps, and only on time loss and p95.

A **decision guard** enforces this honesty automatically: it will only report ACT if vehicle-hours
improve on *every* paired seed and arrivals do not fall and teleports do not rise. Run on the live
Dhaka congestion state, it returned **NO_ACTION** — 1 of 3 seeds improved. The system refuses to
claim a benefit its own data does not support. → `results/routing/live_chain.md`

---

## 4. The strongest result: real measured vehicles, causal control experiment

The strongest evidence in the project does not use simulated demand at all. It uses **pNEUMA**
drone-measured trajectories over Athens — 697 vehicles whose origins, destinations and departure
times are *observed*, not generated.

A digital twin of the same streets was calibrated against them: **speed MAE 3.0 m/s, 0 teleports**,
per-vehicle travel-time errors 1–9 s. Its validated regime is stated explicitly and enforced:
per-cycle, short-horizon experiments with real per-cycle initialisation.

Inside that regime, a signal-coordination experiment with paired same-seed branches:

| offset | time loss / veh | stopped time / veh | teleports |
|---|---|---|---|
| green wave (14 s, progression rule) | 60.0 s | **0.0 s** | 0 |
| mistimed (45 s) | 318.6 s | 221.0 s | 0 |

**73.1 % mean reduction in corridor delay, 6 of 6 paired seeds, stops eliminated entirely** — from
identical real vehicles. Two further findings make it credible rather than convenient:

1. **The observed Athens timing already *is* the green wave.** The progression rule
   (offset = distance / free-flow speed) independently reproduces the offset the city actually
   runs. The twin recovered real-world engineering it was never told about.
2. **At light demand the same intervention does nothing** — 0 of 6 seeds, 0.0 % change. That
   boundary is reported, not hidden. The effect is real but conditional on congestion.

→ `artifacts/urban_real_site/STEP3_SUPP_B_RECORD.json`, `STEP2_RECORD.json`, `results/routing/real_demand.md`

---

## 5. The four components the brief required

| required | where it lives | strength |
|---|---|---|
| **ML** | arithmetic floors, TF-IDF + logistic regression, user-equilibrium assignment | protocol-validated to 0.7 % of published |
| **DL** | Graph WaveNet, STID, STAEformer, DCRNN — official code, GPU-trained | reproduce published MAE to ≤1.8 % |
| **NLP** | incident-text classifier → routing action | **DistilBERT 0.978 acc / 0.972 macro-F1** on 10,226 held-out |
| **Networking** | Eclipse MOSAIC 25.2, ITS-G5 V2X, DENM broadcast, penetration sweep | measured, not assumed — see below |

### Networking is simulated end-to-end with an official stack, not assumed

Eclipse MOSAIC 25.2 with a registered Dhaka R1 scenario, its SNS ad-hoc ITS-G5 model, DENM hazard
broadcast, penetration swept 0 → 100 % over three seeds each. **These are simulated V2X
communication events produced by an official simulator — not packets captured off real radio
hardware.** Every latency, loss and delivery figure below inherits that nature:

| penetration | equipped | delivery ratio | latency mean / p95 | route switches |
|---|---|---|---|---|
| 0 % | 0 | — | — | 0 |
| 10 % | 204 | 0.965 | 30.0 / 57.4 ms | 65 |
| 50 % | 1,052 | 0.971 | 30.0 / 57.4 ms | 362 |
| 100 % | 2,120 | 0.975 | 30.0 / 57.5 ms | 713 |

Then the question that actually matters — **do advisories arrive in time to be useful?** The base
latency distribution is taken from the official MOSAIC Barnim example (n = 504 simulated
receptions, mean 2.6 ms, p95 7.0 ms), and time-to-hazard from 4,386 rerouting vehicles in the
sweep (median 50.8 s). Under Monte Carlo latency and loss injection: **85.7 % of advisories arrive
before the decision point**, and the 1 Hz DENM repeat holds delivery at **77.8 %** even with 5 s
added latency and 30 % packet loss.

An awkward fact is reported rather than dropped: **14 % of vehicles were already inside the hazard
zone at first reception** — for them no advisory can ever arrive in time. They are counted as
failures in the headline column.

### An NLP finding worth the supervisor's attention

DistilBERT wins on the benchmark test set (0.978) — but on a held-out **Dhaka-specific** set it
scores 0.647, while a much smaller TF-IDF model augmented with Dhaka text scores **0.873**. The
larger model loses badly to domain shift. This is a genuine, measured result about deploying
Western-trained NLP on Dhaka traffic text, not a benchmark number.

---

## 6. What is *not* claimed

Stated plainly so an examiner does not have to find them:

1. **No new architecture is proposed.** This is faithful reproduction at published strength.
2. **The Athens 900 s free-running routing gain (−18.5 %) is not a transport result.** At 10 %
   compliance only six routes change, yet vehicle-hours fall 38 % — that is release of a
   *simulation deadlock*, and it is labelled as such in the file, not quoted as a benefit.
3. **The twin is not validated for free-running long-horizon network forecasting.** Declared
   out of scope in `STEP2_RECORD.json` rather than quietly exceeded.
4. **Dhaka twin sensor data is simulated** on the real frozen R1 topology. It is never described
   as real sensor measurement; an automated evidence audit enforces the reality labels.
5. **Predictive rerouting did not beat static routing** at the demand tested.
6. **The federated V2X experiment has not landed.** A GPU job was launched; its results are not
   in this package and no number is quoted for it.

---

## 7. Verifying any of it

```bash
pip install -r requirements.txt
python main.py status                        # what exists, what is real, what is missing
python pipeline/forecasting/comparison_table.py   # rebuilds the Phase-1 table and re-runs the gate
python -m pytest tests/ -q                   # 232 tests
python results/build_results.py              # rebuilds results/RESULTS.md from evidence files
uvicorn dashboard.backend.main:app           # the live dashboard at 127.0.0.1:8000
```

`REPRODUCE.md` maps **every headline number → one command → the evidence file it writes.**

The dashboard is a real application, not a table dump: six panels over a FastAPI evidence API with
a Server-Sent-Events live stream, a MapLibre map of the real corridors coloured by observed
congestion, and a provenance line on every panel naming the file and the command behind it.

---

## 8. Open items — the research programme in progress

Every item follows an **upstream-first rule**: clone the official repository, pin its SHA, use the
authors' own preprocessing and config, reproduce their published benchmark, record
REPRODUCTION_PASS/FAIL, and only then attach a thin adapter. No algorithm is reimplemented from
the paper text, and no new architecture is invented.

| # | experiment | official source | status |
|---|---|---|---|
| 1 | STAEformer reproduced from the authors' own repo, not only via the shared harness | `XDZhelheim/STAEformer` (fetched, SHA pinned) | pending GPU |
| 2 | Congestion-aware metrics: congestion-period MAE, precision/recall/F1, warning lead time | — | **done** — `results/forecasting/congestion_metrics.md` |
| 3 | CNFGNN reproduced | `mengcz13/KDD2021_CNFGNN` @ `5056608` (fetched, verified) | blocked on the authors' Zenodo dataset + a py<3.8 environment |
| 4 | FedGTP reproduced | `LarryHawkingYoung/KDD2024_FedGTP` @ `ff128f5` (fetched, verified) | launcher done; blocked on GPU access |
| 5 | Centralized vs FedAvg vs CNFGNN vs FedGTP under **A** ideal, **B** MOSAIC V2X profile, **C** latency stress, **D** loss stress | thin adapter over 3 & 4 | **adapter built and tested**; runs pending GPU |
| 6 | Cross-city: city-specific vs OpenCity zero-shot vs fine-tuned, on METR-LA + PEMS-BAY + a held-out third city | `HKUDS/OpenCity` @ `eca64c9` (fetched, verified) | notebook ready; weights not yet fetched |
| 7 | End-to-end chain: link quality → advisory delivery → rerouting → SUMO delay | composition of 5 and the routing stack | **running** — first result below |
| — | Real user pilot (3 users, live advisories) | — | pending, marked PENDING in the evidence audit |
| — | Thesis chapters | — | not written |

### Experiment 7 — result: the chain cannot yet be tested, and that is the finding

Three runs, each overturning the last:

| run | seeds | delivery spread | result |
|---|---|---|---|
| first | 3 | 0.857 → 0.778 | +4.4 % vehicle-hours, +21 % waiting — looked like a clean causal effect |
| wider | 10 | 0.857 → 0.544 | effect **vanished**: 5/10 seeds either way, no trend |
| decisive | 10 | 0.857 → 0.544, plus an *unaware* reference arm | `INCONCLUSIVE_UNDERPOWERED` |

The first result was seed noise. Ten seeds and a delivery spread wide enough to remove **37 % of
all advisories** (2,268 → 1,444 delivered) produced no detectable change in network delay.

The reference arm explains why. Advising every equipped vehicle over a perfect link beats advising
nobody by **−1.96 % vehicle-hours on 8 of 10 seeds** — a real effect, but a small one. If degrading
the link removes a proportional share of a 2 % benefit, the quantity being measured is a *fraction
of one percent*, which is well inside the seed-to-seed spread. **The experiment is underpowered for
the hypothesis, not evidence against it.**

That is a useful negative result rather than a dead end: it says the causal chain must be tested in
a regime where routing gives a large, unanimous benefit — higher compliance, heavier congestion, or
a network where rerouting matters more — so that degrading delivery has something substantial to
erode. Without the reference arm this run would have been reported as "communication quality does
not affect routing", which would have been wrong.

The verdict is computed by the script from the seed data, so it cannot be talked up in prose.

→ `results/routing/impairment_chain_decisive.md`

### The reproduction ledger

`results/upstream/REPRODUCTIONS.md` records, per (model, dataset), the pinned SHA, the authors'
own config path, their published number, ours, and a **computed** verdict. Graph WaveNet passes on
both cities. STID and STAEformer are `REFERENCE_UNKNOWN` — we have our numbers but have not yet
read the authors' published figures out of the papers, and that is deliberately not counted as a
pass. Nothing is invented to fill a slot.

Until experiments 1-7 report, the claims in this document are limited to what sections 1-5
actually measured.

---

### Attribution

All code, models and datasets are open source and cited: BasicTS (TKDE 2024), Graph WaveNet
(IJCAI 2019), STID (CIKM 2022), STAEformer (CIKM 2023), DCRNN (ICLR 2018), Eclipse SUMO 1.27.1,
Eclipse MOSAIC 25.2, pNEUMA (Barmpounakis & Geroliminis, 2020), OpenStreetMap. Official
implementations are used unmodified as the algorithmic source of truth; adapters only translate.
Full list in `CITATION.cff` and `docs/`.
