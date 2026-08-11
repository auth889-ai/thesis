# EXPERIMENT_SPEC — Lab 02

Status: `[RUN]` fields completed from Colab gate records after execution.

- Execution: Google Colab (anastasiasaat81@gmail.com); storage: Drive
  `DhakaFlow-Nexus-Data/Lab02_DhakaOSM/`; local = code/tests/lightweight evidence.
- Runtime pins: `eclipse-sumo==1.27.1`, PyYAML≥6, pytest≥8, matplotlib 3.8.4.
  SUMO/netconvert versions printed in-notebook `[RUN]`.
- Experiments (config-driven, seed 42 everywhere):
  - `configs/smoke.yaml` — inner box (Karwan Bazar/Bangla Motor core), 600 s
    demand stress test.
  - `configs/full.yaml` — pre-registered central-Dhaka region, 3600 s run.
- Exact commands: `python scripts/run_lab02.py --config configs/<x>.yaml
  --output-root <Drive>/lab02_<x>` (full command lines + netconvert/duarouter/
  sumo argv recorded inside each run's JSON records).
- OSM acquisition date/query/sha256: `outputs/manifests/*/osm_manifest.json` `[RUN]`.
- Network checksum: `netconvert_record.json` `[RUN]`.
- Pass thresholds: METHOD_SPEC (SCC ≥ 0.90 full / 0.85 smoke; unroutable ≤ 2%;
  8/8 representative routes; 0 collisions; ≥5 TLS full / ≥1 smoke).
- Local validation performed before Colab: 5 SUMO-free unit tests + tiny-OSM
  end-to-end integration test (6/6 pass; used the machine's pre-existing conda
  SUMO for seconds — nothing was installed locally).
