# DhakaFlow Nexus — Lab 01: SUMO Foundation

**Purpose:** establish a reproducible microscopic-traffic-simulation foundation before Dhaka OSM, perception, forecasting, or RL.

This handoff is intentionally **one lab only**. It is not a second DhakaFlow project. Claude should merge/adapt this folder into the active repository at `paper_labs/01_sumo_foundation/`, audit it, run it in Colab, and only then declare PASS/PARTIAL/FAIL.

## Scientific scope

1. Learn SUMO/TraCI/network/TLS fundamentals.
2. Build a deterministic four-arm, two-stage signalized intersection for unit validation.
3. Compare **Fixed-Time**, **queue-actuated**, and **movement Max-Pressure** control under identical seeded demand.
4. Measure travel time, p95 travel time, waiting time, time loss, queue, throughput, stops, and a documented spillback proxy.
5. Clone and pin the official `DLR-TS/sumo-scenarios` repository and run `bologna/acosta/run.sumocfg` **unmodified** before any wrappers.
6. Preserve official upstream code untouched.

## Important boundary

The unit intersection is a **validation environment**, not the final Dhaka network. General network-scale controllers are developed later. Lab 01 exists to prove simulation/control mechanics and measurement correctness.

## Start

```bash
bash scripts/install_sumo_ubuntu.sh
bash scripts/build_unit_network.sh
python scripts/run_matrix.py --config configs/full.yaml
bash scripts/fetch_upstreams.sh
bash scripts/run_bologna_unmodified.sh
```

For Colab, use `notebooks/Lab01_SUMO_Foundation_Colab.ipynb`.

## PASS gate

See `EXPERIMENT_SPEC.md` and `REPRODUCTION_REPORT.md`. **Code existence is not PASS. Actual SUMO execution and evidence are required.**


## Colab-only runtime

Do not install SUMO on the user's Mac. Real Lab 01 execution is Colab-only. See `COLAB_ONLY_RUNBOOK.md` and run `scripts/install_colab.sh` inside Colab. Heavy/full outputs belong in Google Drive; only lightweight evidence belongs in Git.
