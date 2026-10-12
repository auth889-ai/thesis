# RQ2 — the ambulance alert, made strong

How much time does the ambulance alert save? At which traffic densities and equipped shares? Against which baselines, and why?

**Where things are:**
- the plan and the results: `docs/PAPER_MAP.md` (RQ2);
- the code: `backend/app/emergency/` (`rq2.py`, `rq2_summary.py`, `measures.py`, `rl_signals.py`; `service.run_one` gained `scale` and `observe`, whose defaults keep the original runs);
- the results: `results/emergency/dhaka/rq2/`;
- the hashes: `evidence/ambulance_rq2/`.

**Licences:** sumo-rl (MIT, commit 86f0fc4) and PettingZoo (MIT), in `third_party/SOURCES.md`, "Ambulance alert, RQ2".

```bash
research/ambulance_rq2/scripts/00_reproduce_sumo_rl.sh     # sumo-rl's own Q-learning example vs fixed timing, unchanged -> evidence/ambulance_rq2/reproduce/SUMMARY.json
# from the repository root (core/ and backend/ on the path: PYTHONPATH=.:backend)
DHAKAFLOW_NO_OBSERVATORY=1 python -m core.simulation.ambulance.study ladder     # siren-only ambulance at demand x0.5, 1, 2, ... until gridlock
DHAKAFLOW_NO_OBSERVATORY=1 python -m core.simulation.ambulance.study sweep      # alert and alert+preemption x shares 25/50/75/100 % x paired seeds
DHAKAFLOW_NO_OBSERVATORY=1 python -m core.simulation.ambulance.study rl         # sumo-rl Q-learning: 30 training episodes per level, then frozen runs
DHAKAFLOW_NO_OBSERVATORY=1 python -m core.simulation.ambulance.corridor build    # RQ2b: corridor net (netconvert keep-edges) + routeSampler routes from DhaTraX INT/BM counts
DHAKAFLOW_NO_OBSERVATORY=1 python -m core.simulation.ambulance.corridor density  # INT density reached at the full counts, no ambulance
DHAKAFLOW_NO_OBSERVATORY=1 python -m core.simulation.ambulance.corridor match    # the count scale whose INT density lies in the recorded IQR -> match.json
DHAKAFLOW_NO_OBSERVATORY=1 python -m core.simulation.ambulance.study dhaka      # every arm at that "Dhaka density" level, 10 paired seeds, sumo-rl trained on the corridor
DHAKAFLOW_NO_OBSERVATORY=1 python ../research/ambulance_rq2/scripts/inspect_dhaka_slow.py --seeds 12 15 19 21      # logged re-runs of slow seeds (siren only and alert)
for v in near50 nojunction strategic; do DHAKAFLOW_NO_OBSERVATORY=1 python ../research/ambulance_rq2/scripts/inspect_dhaka_slow.py --seeds 11 12 13 15 17 18 19 20 21 22 --arms alert --variant $v; done
python ../research/ambulance_rq2/scripts/slowdown_summary.py      # why the alert slows the ambulance at Dhaka density -> evidence/ambulance_rq2/inspect/dhaka/SLOWDOWN.md
# RQ2c: make-way v2 (configs/ambulance.yaml alert.makeway); the v1 results stay in results/emergency/dhaka/rq2/record_v1_makeway_artefact/
for v in v2d100 v2d50; do DHAKAFLOW_NO_OBSERVATORY=1 python ../research/ambulance_rq2/scripts/inspect_dhaka_slow.py --seeds 11 12 13 15 17 18 19 20 21 22 --arms alert --variant $v; done
DHAKAFLOW_NO_OBSERVATORY=1 python ../research/ambulance_rq2/scripts/inspect_dhaka_slow.py --seeds 17 18 20 22 --arms no_alert   # siren-only logs of the flagged seeds
python ../research/ambulance_rq2/scripts/choose_makeway.py       # the distance, by the rule fixed before the pilot (and its owner-approved amendment) -> evidence/ambulance_rq2/makeway_v2/choice.json
DHAKAFLOW_NO_OBSERVATORY=1 python -m core.simulation.ambulance.study rerun_v2   # every alerting arm at every level again with v2, into runs_v2/ (4 at a time)
SUMO_HOME=... ~/.dhakaflow/venvs/sumo-rl-np1/bin/python ../research/ambulance_rq2/scripts/inspect_dhaka_slow.py --seeds 14 18 19 21 23 --arms no_alert rl_signals --tag rq2c
SUMO_HOME=... ~/.dhakaflow/venvs/sumo-rl-np1/bin/python ../research/ambulance_rq2/scripts/inspect_dhaka_slow.py --seeds 14 18 19 23 --arms rl_signals --tag rq2c_deep --deep
python ../research/ambulance_rq2/scripts/qlearning_inspect_summary.py   # where the ambulance stood under Q-learning at Dhaka density -> QLEARNING.md
DHAKAFLOW_NO_OBSERVATORY=1 python -m core.simulation.ambulance.study summary    # summary.json/.md, figures, hashes
python ../research/ambulance_rq2/scripts/paper_map_rq2.py         # the RQ2 section of docs/PAPER_MAP.md, from summary.json
DHAKAFLOW_NO_OBSERVATORY=1 python -m pytest tests/emergency/test_rq2.py -q
```

**Environment:** sumo-rl runs in `~/.dhakaflow/venvs/sumo-rl-np1`, which has NumPy below 2. The pinned sumo-rl's `encode()` calls `int()` on a one-element array, and NumPy 2 refuses that. The code is used unchanged, in an environment its dependency list allows. `rq2 rl` calls that environment itself.
