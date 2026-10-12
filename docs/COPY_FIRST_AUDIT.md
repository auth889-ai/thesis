# Copy-first audit

Date: 2026-10-05. Written by a read-only session; no other file in the repository was touched and the test suite
was not run. Clones are in `~/.dhakaflow/upstream/`, nothing was cloned into the repository.

For each source: the licence and where it was found, a class, whether its example runs, and what it would save.

Classes:
- **(a)** reuse code with credit (an entry in `third_party/SOURCES.md`, the original result reproduced first)
- **(b)** separate tool only (installed and called as released, no code copied)
- **(c)** ideas only (nothing copied)

## What was and was not checked

- Licences were read from the files in each clone, and compared with what GitHub and PyPI report.
- **Only one example was actually run: the SUMO bluelight device**, with the SUMO 1.27.1 already installed here.
- **The examples of the cloned repositories were not run.** The session's permission system refused to execute
  code from freshly cloned repositories, and installing `pons-dtn` to run it falls under the same refusal. For
  those, "does the example run" below is answered from reading the code only, and says so. The exact commands to
  run are listed in the last section.
- None of the numbers printed in the READMEs of these repositories has been reproduced. They must not be quoted
  as ours.

## Summary

| Source | Licence (where found) | Class | Example runs? | What it would save |
|---|---|---|---|---|
| SUMO bluelight device | EPL-2.0 (`LICENSE`, `NOTICE.md` of eclipse-sumo; SPDX `EPL-2.0 OR GPL-2.0-or-later`) | (b) | **Yes, run here** on a small generated grid | Writing our own emergency-vehicle behaviour (running red lights, rescue lane) |
| Piyush04492/Traffic_Signal_Preemption_for_Emergency_Vehicles | **None.** No licence file, no licence line in the README or code; GitHub reports no licence | (c) | Not run. Looks runnable headless | Little: one pattern of about 200 lines |
| Adityakumar1805/adaptive-traffic-signal-rl | MIT (`LICENSE`, © 2026 Aditya Kumar; README; GitHub) | (a) allowed, small part worth it | Not run. Needs its own Python 3.10–3.12 environment | A 65-line preemption override and a signal safety state machine |
| gh0st42/PONS (`pons-dtn`) | MIT (`LICENSE`, © 2024 Lars Baumgärtner; `pyproject.toml` and PyPI classifier; GitHub) | (b) | Not run. `simpy` is not installed here | Writing a delay-tolerant network simulator and six routing protocols |
| MeixinZhu/vehicle-crash-identification | MIT (`LICENSE`, © 2021 Meixin; GitHub). The data has its own terms, not checked | (c) in practice | **Cannot run as cloned**: the data is not in the repository | Almost nothing for us: its inputs are signals we do not have |
| Google Photorealistic 3D Tiles with deck.gl | Not a licence: Google Maps Platform Terms of Service and Map Tiles API Policies | (b), display only, **and it conflicts with our current map** | Not run (needs a Google key and billing account) | Building and texturing a realistic 3D city; but see the conflicts below |
| a-b-street/abstreet | Apache-2.0 (`LICENSE`; GitHub) | (b) or (c) | Not built: Rust is not installed here | Nothing directly; ideas for lane and intersection editing |
| ChrisLi1221/ChatSUMO-Agent | MIT (`LICENSE`, © 2026 ChrisLi1221; README; `pyproject.toml`; GitHub) | (a) allowed | Not run. Needs a paid OpenAI key | A prompt-to-scenario loop, most of which our pipeline already does without a language model |

## 1. SUMO bluelight device

- **Source:** SUMO documentation, `docs/web/docs/Simulation/Emergency.md`, in the clone at commit
  `7717f2379d9e314a0c81c5cec748444de06a2a91` (tag `v1_27_1`, the version already in `third_party/SOURCES.md`).
- **Licence:** EPL-2.0. Found in `LICENSE` and `NOTICE.md` ("SPDX-License-Identifier: EPL-2.0 OR GPL-2.0-or-later").
- **Class (b).** It is part of the simulator we already use. We would only set documented options; no SUMO code
  is copied.
- **What it does** (from the documentation): a vehicle type with `vClass="emergency"` may use emergency lanes,
  overtake on the right and through the opposite direction. Adding the device makes it ignore red lights and
  change lanes freely when jammed. With the sublane model on (`--lateral-resolution` above 0), traffic ahead
  moves aside to form a rescue lane; those vehicles carry the parameter `rescueLane`. Reaction distance is 25 m
  by default (`--device.bluelight.reactiondist`).
- **Does the example run? Yes.** The documentation's example is this vehicle type:

  ```xml
  <vType id="rescue" vClass="emergency" speedFactor="1.5">
     <param key="has.bluelight.device" value="true"/>
  </vType>
  ```

  It was run with SUMO 1.27.1 on a 3×3 grid made by `netgenerate` (three lanes, one signal in the centre,
  `--lateral-resolution 0.8`, seed 42), once with the device and once without. With the device, SUMO reported
  `has.bluelight.device` as true and 18 surrounding vehicles carried `rescueLane` at some point; without it,
  none did. The emergency vehicle's arrival time was about the same in both runs, so this check shows that the
  device works, not that it saves time. **This was a smoke check in a temporary folder, with no entry under
  `evidence/`; these figures are not results.**
- **What it would save:** writing and validating our own red-light and rescue-lane behaviour.
- **What to know before using it:**
  - The rescue lane needs the sublane model. Nothing in `backend/app` or `config/` sets `--lateral-resolution`
    today, and turning it on changes how every vehicle moves and slows the simulation. Earlier results would
    not be comparable with runs that use it.
  - It is not signal preemption. The vehicle runs the red light; the signal does not change. Preemption would
    still be our own code.
  - To stay city-agnostic, the emergency vehicle type and the switch belong in `config/cities/<city_id>.yaml`.
  - The documentation cites Bieker (2011, 2015, Young Researchers Seminar) for the model.

## 2. Piyush04492/Traffic_Signal_Preemption_for_Emergency_Vehicles

- **Clone:** commit `17399b2c9b76ece619f2314fb51cb66ffb00e94e` (2026-09-19). One author, one day of commits, 0 stars.
- **Licence: none.** There is no `LICENSE` file, the README and the Python files carry no licence or copyright
  line, and GitHub reports no licence. Under fidelity rule 4, **none of its code or network files may be copied.**
- **Class (c), ideas only.**
- **What it is:** one signalised junction (and a two-junction corridor) in SUMO, with an ambulance approaching.
  Preemption is a TraCI `trafficlight.setPhase` call made after a delay that stands for 4G or 5G latency. A
  Streamlit page compares baseline, 4G and 5G. About 1,170 lines of Python.
- **Does the example run?** Not run. From the code: `python v2x_emergency_sim.py 5G headless` avoids the window
  and the prompt; `python simulation_engine.py` runs the three modes headless but exits unless `SUMO_HOME` is
  set (it is not set in this shell). It rewrites its own network files on each run.
- **Points against relying on it:**
  - The README table gives 4G a 50 ms latency, while the standalone script hard-codes a 3,500 ms delay for 4G
    and 5 ms for 5G. The README's delays and ranges are the author's assumptions, with no source given.
  - The ambulance in `intersection.rou.xml` has only `guiShape="emergency"`, not `vClass="emergency"`, and no
    bluelight device.
  - README "Option C" has an empty command.
- **What it would save:** little. The usable idea is "request sent when the vehicle is within range, phase set
  after the network delay, normal plan restored afterwards", which is short to write on top of our own
  `core/networking/v2x/` channel model, where the delay would come from our simulation instead of a constant.

## 3. Adityakumar1805/adaptive-traffic-signal-rl

- **Clone:** commit `b62436b5d5fb1e5d07008d6f486f1a06a09ff64a` (2026-10-02). One author, 1 star, no paper.
- **Licence:** MIT. Found in `LICENSE` (© 2026 Aditya Kumar), the README's "Licence" section, and GitHub.
- **Class (a) is allowed.** Only a small part is worth taking.
- **What it is:** four DQN agents on a 2×2 grid, fixed-time and max-pressure baselines, a safety state machine
  for amber and all-red, an emergency override, and a dashboard. It runs on its own point-queue simulator by
  default, and on SUMO optionally.
- **Does the example run?** Not run. From the code: `python run.py doctor` checks the environment and
  `python run.py eval` repeats its 36-run benchmark from the shipped checkpoint. It pins Python 3.10–3.12,
  `numpy==1.26.4` and `torch==2.2.2`; this machine has Python 3.13.9, NumPy 2.5.2 and torch 2.13.0, so it needs
  its own environment. Its README says retraining is not reproducible across NumPy versions.
- **Limits its own README states:** the published numbers come from the point-queue simulator (no spill-back,
  no car-following); the fixed-time baseline is near saturation at rush hour, so the headline 61 % says as much
  about the baseline as about the method; the state machine can cancel a change during amber, and greens are
  one second longer than configured; preemption reacts only when the vehicle reaches the stop line. Its SUMO
  backend notes that the emergency reward bonus never fires on SUMO.
- **What it would save:**
  - `src/atsc/control/emergency.py` (65 lines): an override that wraps any controller and asks for the phase
    serving the emergency vehicle's approach. This is the piece that fits our signal code.
  - `src/atsc/envs/phases.py` (141 lines): the safety state machine, but with the two flaws above.
  - Not needed: max-pressure and the SUMO multi-agent environment already exist in `core/simulation/signals/`.
- **If used:** rule 3 applies. Run `python run.py eval` unchanged first and record our numbers next to
  `outputs/benchmark_summary.md`, then credit the file in `third_party/SOURCES.md`.

## 4. gh0st42/PONS (`pip install pons-dtn`)

- **Clone:** commit `90a6a3558a6107f68b5ee3245e37f2ef9206fda8` (2025-07-25). PyPI: `pons-dtn` 0.2.1.
- **Licence:** MIT. `LICENSE` holds the MIT text without the title line (© 2024 Lars Baumgärtner);
  `pyproject.toml` and PyPI carry the classifier "License :: OSI Approved :: MIT License"; GitHub reports MIT.
- **Class (b):** install the released package and call it. Nothing needs copying.
- **What it is:** a discrete-event simulator for delay-tolerant networks in pure Python, in the style of the
  ONE simulator. Routing: epidemic, spray and wait, first contact, direct delivery, PRoPHET, static. Movement:
  random waypoint, ONE traces, ns-2 traces. Contact plans and a scenario runner that needs no code.
- **Does the example run?** Not run: installing and executing it was not permitted in this session, and
  `simpy` is not installed here. The repository has its own check, `examples/run_tests`, which runs each
  example and compares message counts with `examples/tests.json`. Dependencies are light (simpy, networkx,
  pandas, matplotlib, pillow); Python 3.9 or later.
- **What it would save:** writing and validating a store-and-forward simulator and six routing protocols.
  Vehicle movement could come from SUMO, whose `tools/traceExporter.py` writes ns-2 mobility traces. **Whether
  PONS reads SUMO's ns-2 output as written has not been tested.**
- **Before using it:** nothing in `backend/app` does delay-tolerant networking today, so this is a new feature.
  Under fidelity rule 5 it belongs in `docs/proposals.md` first. It is also a second network simulator beside
  Eclipse MOSAIC; the two should not be mixed in one result.

## 5. MeixinZhu/vehicle-crash-identification

- **Clone:** commit `85b88f370b6fd4cdec249068bea07eeaea7d3475` (2023-01-03).
- **Paper:** Zhu, Yang, Liu, Pu, Wang, "Real-time crash identification using connected electric vehicle
  operation data", Accident Analysis & Prevention 173 (2022) 106708. The README calls this the official code.
- **Licence:** MIT for the code (`LICENSE`, © 2021 Meixin; GitHub). The data is not in the repository; it comes
  from a DataFountain competition (`datafountain.cn/competitions/500`), behind an account. **Its terms were not
  read.**
- **Class:** the licence allows (a). In practice **(c), ideas only**.
- **Does the example run? Not as cloned.** Only `raw_data/train_labels.csv` (120 vehicles) is shipped; the
  per-vehicle files the code reads (`raw_data/train/<n>.csv`) are missing. The README's command is
  `python mian.py`, but the file is `main.py`. The pinned packages date from 2021 (`pandas==1.1.5`,
  `numpy==1.20.1`, `scikit_learn==0.24.1`, `tsfresh==0.18.0`) and will not install on Python 3.13.
- **What it would save:** almost nothing. The method classifies crashes from an electric vehicle's own
  operating signals, with hand-made features and AdaBoost, about 950 lines. We have no such signals for any
  evaluation city, and without the data the published result cannot be reproduced first, which rule 3 requires.
  The idea of features around the moment of impact can be cited from the paper.

## 6. Google Map Tiles API: Photorealistic 3D Tiles with deck.gl

Read on 2026-10-05: Map Tiles API Policies and the 3D Tiles overview (both "last updated 2026-09-28"), Google
Maps Platform Terms of Service ("last modified August 26, 2026"), Maps Service Specific Terms ("last modified
June 10, 2026"), the pricing page, and deck.gl's `Tile3DLayer` page. This is a reading of the terms, not legal
advice.

- **Class (b):** a paid service used for display only. Nothing from it may be stored or reused.
- **Does it run?** Not run. It needs a Google Maps key and a billing account. deck.gl documents the call:
  `Tile3DLayer` with `data: 'https://tile.googleapis.com/v1/3dtiles/root.json'` and the key in the
  `X-GOOG-API-KEY` header. Google's own page names only CesiumJS and Cesium for Unreal as renderers and does not
  mention deck.gl; the policies do allow third-party renderers. deck.gl's own licence was not checked here.
- **What the terms require:**
  - **Display only.** "You may not use Map Tiles API for any non-visualization use cases, such as: Image
    analysis, Machine interpretation, Object detection or identification, Geodata extraction or resale, Offline
    uses". So the tiles cannot feed perception, calibration or any model.
  - **No storing.** "you must not pre-fetch, index, store, or cache any Content except under the limited
    conditions stated". Screenshots of the tiles as thesis evidence need care for the same reason.
  - **Our own objects on top are allowed**, "as long as the 3D objects aren't extracted, traced, or otherwise
    derived by hand or machine from Photorealistic 3D Tiles". Simulated vehicles from SUMO qualify.
  - **Attribution.** The Google Maps logo must be shown and not covered by the renderer's logo, and "You must
    aggregate, sort, and display in a line, all attributions for displayed tiles". deck.gl's page says nothing
    about doing this, so we would write it.
  - **Sessions.** A root tileset request is valid for at least three hours, then must be made again.
- **Conflict with our current map.** The Terms of Service say: "Customer will not use the Google Maps Core
  Services with or near a non-Google Map in a Customer Application." The Service Specific Terms have no section
  for Map Tiles that lifts this. Our maps are MapLibre with OpenFreeMap streets, Overture buildings and the EOX
  satellite picture, all non-Google. As I read it, Google's 3D tiles could only appear in a view of their own,
  with none of those layers on the same screen.
- **Cost.** Per the pricing page: 1,000 root tileset requests free each month, then $6.00 per 1,000 (up to
  100,000). A card on file is required. This is a paid launch and needs approval first.
- **City-agnostic rule.** Coverage is described only as "many of the world's populated areas". **Whether Dhaka
  is covered was not checked.** Where there is no coverage the app must say "no data for this city".
- **Developers billed in the European Economic Area** have different terms from 2025-07-08 and some content is
  not returned to them. This matters if the Berlin work is ever billed from there.
- **What it would save:** modelling a realistic 3D city. Against that: the app already shows 3D buildings
  worldwide from Overture with an open licence, the tiles add a second renderer (deck.gl is not a dependency
  today), and they cannot be mixed with the existing map.
- **A related point to check, outside this audit's list:** the same Service Specific Terms say of the Routes
  API, "Customer must not use Google Maps Content from the Routes API in conjunction with a non-Google map."
  `core/common/data/live_providers/google_routes.py` reads the Routes API. I did not check how its output is
  shown; if it is drawn on the MapLibre map, that clause applies.

## 7. a-b-street/abstreet and ChrisLi1221/ChatSUMO-Agent

### a-b-street/abstreet

- **Clone:** commit `0964f29315820c91b171b585eb51e300164e9197` (2025-09-10), fetched without file contents;
  only `LICENSE`, `README.md` and `Cargo.toml` were read.
- **Licence:** Apache-2.0 (`LICENSE`; GitHub). Its maps come from OpenStreetMap (ODbL).
- **Class (b) or (c).** It is a Rust application with its own traffic simulator, not a library for a Python
  and SUMO project. Copying code is permitted by the licence but would mean porting Rust.
- **Does the example run?** Not built: `cargo` is not installed here. The README links ready-made builds
  (v0.3.49 for Mac, Windows, Linux) and a browser version; none was tried. The README's 2025 note says the
  project has moved on to several successor tools.
- **What it would save:** nothing directly. It is a reference for importing any city from OpenStreetMap and for
  editing lanes and signals by hand, and its simulator is documented. A second simulator's output must not be
  mixed with SUMO results.

### ChrisLi1221/ChatSUMO-Agent

- **Clone:** commit `2ec0cb6c148cc41e7c97668ed423470c8cbbda9b` (2026-04-06), the commit already listed in
  `third_party/SOURCES.md` as "Nothing yet (a stretch goal)".
- **Licence:** MIT (`LICENSE`, © 2026 ChrisLi1221; README; `pyproject.toml`; GitHub).
- **Class (a) is allowed.**
- **What it is:** a Streamlit chat page where a language model plans calls to tools that build a network from
  OpenStreetMap, generate traffic, run SUMO and report measures. About 3,000 lines. The README names no paper.
- **Does the example run?** Not run. It needs `OPENAI_API_KEY` (a paid service), and it pins `sumolib` and
  `traci` 1.24.0 against our 1.27.1. No sample output is shipped to compare with.
- **What it would save:** the planning loop from a sentence to a scenario. The steps it calls (network from
  OpenStreetMap, random trips, run, read outputs) already exist in `core/simulation/twin/`. If used, the model
  provider would have to be swapped for ours, and every reported measure must still come from a saved SUMO run,
  never from the model's text.

## Decisions for you

1. **Piyush04492 repository has no licence.** Rule 4 says to stop and tell you: nothing of it should be copied.
   Ideas only, unless the author adds a licence.
2. **Google 3D tiles** conflict with the current non-Google map and cost money beyond 1,000 loads a month.
   Recommended: do not adopt; keep Overture buildings.
3. **PONS** and any **ChatSUMO-Agent** use are new features; they need an entry in `docs/proposals.md`.
4. **Bluelight** is the cheapest gain, but the rescue lane needs the sublane model, which changes all runs.
5. **Google Routes API on a non-Google map**: please check how its output is displayed.

## Commands still to run (not run in this session)

Each from a copy outside the repository, with the log and output hash saved under `evidence/` before any number
is quoted:

```bash
# Piyush04492 (SUMO_HOME must be set for the second)
python v2x_emergency_sim.py 5G headless
python simulation_engine.py

# adaptive-traffic-signal-rl, in a Python 3.10–3.12 environment with its requirements.txt
python run.py doctor
python run.py eval            # compare with outputs/benchmark_summary.md

# PONS, in its own environment
pip install pons-dtn==0.2.1
cd examples && ./run_tests    # compares with examples/tests.json
```
