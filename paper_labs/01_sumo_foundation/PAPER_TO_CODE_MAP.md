# PAPER_TO_CODE_MAP — Lab 01

Traceability: paper concept → official SUMO implementation/docs → official
scenario resource → our wrapper → config → test → **actual artifact from the
validated Colab run** (commit `ca2ac81`). Nothing in the last column is
hypothetical.

Legend for artifacts: `EV/` = `outputs/evidence/`, `DRIVE/` =
`MyDrive/DhakaFlow-Nexus-Data/Lab01_SUMO/`, `FIG/` = `outputs/figures/`.

| # | Paper concept (source) | Official implementation / docs | Official scenario resource | Our code (adapter) | Config | Test | Real artifact |
|---|---|---|---|---|---|---|---|
| 1 | **Microscopic simulation**, per-vehicle dynamics (ITSC §I) | `sumo` binary, Krauss car-following | — | `src/dhakaflow_lab01/runner.py::run_one` (builds argv, owns process) | `sumo_binary`, `sim_end`, step-length 1 s | `tests/integration/test_sumo_available.py` | `EV/verification_record.json` → `sumo_version: "Eclipse SUMO sumo 1.27.1"` |
| 2 | **Scenario = network + infrastructure + demand** (ITSC §II) | `netconvert`; `.sumocfg` | Acosta `run.sumocfg` | `scenarios/unit_validation/*.xml` + `scripts/build_unit_network.sh` | `unit.sumocfg` | `tests/unit/test_scenario_xml.py` | `network.net.xml` built in-run; `FIG/04_experiment_design.png` |
| 3 | **Network model: nodes + unidirectional edges, lanes** (ITSC §IV) | `netconvert` node/edge/connection files | Acosta `.net.xml` | `nodes.nod.xml`, `edges.edg.xml`, `connections.con.xml` | `--no-turnarounds` | `test_scenario_xml.py` (4 connections asserted) | netconvert output + `EV/unit_full/*` (runs traverse it) |
| 4 | **Traffic-light program** (phases/states) (ITSC §II output list; TLS docs) | `<tlLogic>` static program; `Simulation/Traffic_Lights.html` | Acosta signal plans (municipal telemetry, §1.4.5 Bologna) | `scenarios/unit_validation/tls.tll.xml` (`GGrr→yyrr→rrGG→rryy`) | `tls_id: C` | `test_scenario_xml.py` asserts exact state list | `FIG/10_signal_phase_timeline.png` (rendered from that XML) |
| 5 | **TraCI external control** (ITSC §X; TraCI docs; TraCI4Traffic_Lights tutorial) | `traci.start/simulationStep/close`, `trafficlight.*` | — | `runner.py::_import_traci`, step loop; `controllers/base.py` | `decision_interval` | integration gate (all runs TraCI-driven) | `EV/unit_full/**` logs: "Reason: TraCI requested termination" |
| 6 | **Fixed-time control** (classical baseline; SUMO static program) | SUMO executes the declared program | Acosta uses municipal plans | `controllers/fixed_time.py` (observation only — never writes) | `controllers: [fixed_time]` | matrix run | `EV/unit_full/aggregate_metrics.csv` row `fixed_time` |
| 7 | **Actuation / demand-responsive green** (classical baseline) | `trafficlight.setPhaseDuration`, `lane.getLastStepHaltingNumber` | UTOPIA "variable phases" motivate it (Bologna §1.4.5) | `controllers/actuated.py` + `helpers.phase_queue_score` | `min_green`, `max_green`, `extension`, `switch_margin` | matrix run | row `actuated` (waiting 57.9 s vs 63.3 s fixed) |
| 8 | **Max-pressure** (Varaiya 2013) — *BASELINE_IMPLEMENTATION* | `trafficlight.getControlledLinks` (in/out lane pairs) | — | `controllers/max_pressure.py` + `helpers.phase_pressure_score` (q_in − q_out) | same controller block | matrix run | row `max_pressure`; scope caveat in `REPRODUCTION_CLASSIFICATION.md` |
| 9 | **Repeated stochastic execution** (ITSC §II: "simulate a number of times and draw statistical conclusions") | `--seed` | — | `scripts/run_matrix.py` (seed loop; same route file across controllers) | `seeds: [11,22,33,44,55]` | `tests/unit/test_demand.py` (byte-identical for equal seed) | `EV/unit_full/per_seed_metrics.csv` (15 rows) |
| 10 | **Demand generation** (ITSC §V) | `randomTrips.py`/`DUAROUTER` described; we use explicit routes to avoid discarded trips | Acosta demand from loop counts (Bologna §1.4.6) | `src/dhakaflow_lab01/demand.py` (seeded Poisson, `expovariate`) | `demand.periods` (asymmetric NS/EW peaks) | `test_demand.py` | `DRIVE/unit_full/demand/routes_seed_*.rou.xml` |
| 11 | **Simulation outputs** (ITSC §II) | `--tripinfo-output`, `--summary-output`, `--log` | — | `runner.py` (writes tripinfo/summary/log/step CSV/action JSONL), `metrics.py` | output paths | `tests/unit/test_metrics.py` | `EV/unit_full/*.csv`, `EV/verification_record.json` |
| 12 | **Validation practice / RMSE, honest error bounds** (ITSC §VII) | SUMO validation guidance | Bologna sim-vs-measured scatter (§1.5) | independent recomputation cell in the notebook (fresh parser) | — | assertions in that cell | `EV/verification_record.json::indep_metrics` (exact match) |
| 13 | **Real-world scenario execution** (Bologna paper) | `sumo -c run.sumocfg` | **DLR-TS/sumo-scenarios @ `00f6eb47…`, `bologna/acosta/run.sumocfg`** | `scripts/fetch_upstreams.sh`, `scripts/run_bologna_unmodified.sh` (integrity guard) | pinned SHAs in `upstream/UPSTREAM_LOCK.yaml` | manifest assertion in notebook | `EV/bologna_unmodified/manifest.txt` (`exit_code=0`), `RERUN_NOTE.md`, `FIG/11_bologna_scenario.png` |
| 14 | **Safety of signal switching** (TLS docs: yellow between conflicting greens) | phase list semantics; `setPhaseDuration(0)` terminates current green, SUMO then runs the declared yellow | Acosta plans include yellows | `controllers/base.py::phase_is_green` + min/max-green guards | `min_green: 10`, `max_green: 45` | `test_scenario_xml.py` (yellow states present) | `EV/verification_record.json::safety` → 0 collisions / 0 teleports in 15 runs |
| 15 | **Heterogeneous traffic / reduced lane discipline** (ITSC §IX-C Sublane model) | `--lateral-resolution`, sublane model | — | **not used in Lab 01** (deliberate) | — | — | Recorded as the official mechanism for Dhaka vTypes in Lab 13 (`DHAKAFLOW_CONNECTION.md`) |
| 16 | **Visualization** (SUMO `Tools/Visualization.html`) | `plot_trajectories.py`, sumo-gui | — | `scripts/make_figures.py` (matplotlib from real CSV/JSON/XML) | — | figure regeneration is deterministic | `FIG/01…12*.png` |

## Notes on faithfulness

- Rows 6–8 are **classical baselines / baseline implementation**, not paper
  reproductions; row 8's scope limit is stated wherever the result appears.
- Row 10 deliberately **deviates** from `randomTrips.py`: the ITSC paper warns
  that unroutable random trips are silently discarded, which would make seeds
  incomparable across controllers. Explicit seeded routes remove that
  confound. Documented in `ASSUMPTIONS.md`.
- Row 15 is a *forward* mapping: the paper feature exists and is chosen for
  later use; nothing in Lab 01 claims to have exercised it.
