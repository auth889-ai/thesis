# research/mesh_pons — PONS (DTN simulator) on Dhaka SUMO movement

Prototype for the mesh phase: store-carry-forward message delivery between vehicles, simulated with
PONS (MIT) on vehicle movement exported from the project's frozen Dhaka SUMO network. Not wired into
the app. Results: [RESULTS.md](RESULTS.md) — every number there is **simulated**.

Everything lives in this folder: its own venv (`.venv/`), the PONS clone (`upstream/`, never edited),
large intermediates (`work/`). Those three are git-ignored by the local `.gitignore`. Nothing outside
this folder was changed; the Dhaka network was read, not rebuilt. `SOURCES_ENTRY.md` is the
`third_party/SOURCES.md` entry to paste.

## Our code, and why it exists

- **ns2 -> PONS movement adapter is our code** (`scripts/03_run_pons.py`, `read_ns2`). PONS's own
  ns2 reader (`pons.Ns2Movement.from_file`) divides by the setdest speed and so divides by zero on any
  stopped vehicle (`evidence/ns2_reader_failure.log`). The adapter turns each line SUMO's
  traceExporter wrote into PONS's native move tuple `(t, node, x, y, 0)`; positions and times are
  untouched and `scripts/selfcheck.py` verifies they equal SUMO's FCD positions.
- **Message generator with `metadata={}`** (`generator_with_metadata`), used for Spray and Wait only,
  because PONS 0.2.1's Spray and Wait crashes with PONS's own generator. Equivalence with PONS's
  generator is checked on Epidemic and PRoPHET (`evidence/generator_equivalence.json`).
- **The upstream examples were run on Python 3.11** because, unchanged, they crash on Python 3.13
  (`evidence/upstream_sim_python313_failure.log`); the venv is therefore built on Python 3.11.

## Reproduce (from the repository root)

```sh
cd research/mesh_pons
PY311=/Users/jannatulferdouseva/miniconda3/envs/traffic-sumo/bin/python      # any Python 3.9-3.11
SUMO_TOOLS=/Users/jannatulferdouseva/miniconda3/lib/python3.13/site-packages/sumo/tools   # SUMO 1.27.1; `sumo` on PATH

$PY311 -m venv .venv && .venv/bin/pip install pons-dtn==0.2.1 pyyaml
git clone https://github.com/gh0st42/PONS upstream/PONS && git -C upstream/PONS checkout 0.2.1

./scripts/01_run_upstream_example.sh                      # step 2: PONS's own examples, unchanged
.venv/bin/python scripts/02_export_movement.py --sumo-python python3 --sumo-tools "$SUMO_TOOLS"   # step 3
.venv/bin/python -W ignore scripts/03_run_pons.py         # step 4: 3 routers x 5 seeds (+10 equivalence runs)
.venv/bin/python scripts/04_report.py                     # step 5: RESULTS.md + evidence/SHA256SUMS
.venv/bin/python -W ignore scripts/selfcheck.py           # checks; prints ALL CHECKS PASSED
```

`configs/dhaka.yaml` holds the experiment parameters (window, radio range with its source, message
settings, seeds, routers). City values come from `config/cities/<city_id>.yaml` at run time; a city
without `sumo.prebuilt`/`sumo.build` there stops with "no data for this city".

## Layout

| path | what |
|---|---|
| `configs/dhaka.yaml` | experiment parameters |
| `scripts/01_run_upstream_example.sh` | runs `sim.py` and `examples/ext_ns2.py` from the clone, unchanged |
| `scripts/02_export_movement.py` | randomTrips -> sumo (fcd) -> window/vehicle selection -> `traceExporter.py --ns2mobility-output` |
| `scripts/03_run_pons.py` | PONS runs; contains the two adapters above |
| `scripts/04_report.py` | RESULTS.md from `evidence/runs/*.json` only |
| `scripts/selfcheck.py` | standalone checks (not the project test suite) |
| `evidence/` | logs, `movement.json`, `runs/*.json` (PONS statistics verbatim), `generator_equivalence.json`, `SHA256SUMS`, failure logs that justify the adapters |
| `work/` | ignored: routes, FCD, ns2 trace |

## Known limits / follow-ups (not done here)

- Only vehicles present for the whole 300 s window are simulated (17 of 277), because PONS parks
  absent ns2 nodes as phantom relays. Modelling vehicles that enter and leave needs an on/off
  mechanism PONS's ns2 path does not have.
- One movement trace for all runs; the seed spread covers message draws only.
- Demand is synthetic randomTrips, uncalibrated; the radio is an ideal 10 m disc.
