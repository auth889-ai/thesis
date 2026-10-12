# Supervisor demo kit

Four commands that run on this laptop with no internet, no AWS and no login. Each one first prints what it does, the software it
uses and the paper behind it. Every number it shows comes from a run or a saved results file named below. Run them from the
repository root in a normal terminal on the laptop's own screen.

| Command | Time | What you see | Implemented in |
|---|---|---|---|
| `make check` | 1 s | OK or FAIL per item, with the exact fix command for each failure | `scripts/demo/check.py` |
| `make demo-ambulance` | about 75 s | SUMO window: an ambulance crosses the Dhaka corridor; cars it alerts turn orange and move aside; junctions ahead turn green; then both travel times | `scripts/demo/ambulance.py` → `core/simulation/ambulance/service.py` (`run_one`, unchanged study code) |
| `make demo-forecast` | 1 s | one figure: forecast error against "no change" in Los Angeles and Dhaka, and Dhaka's stop-and-go share | `scripts/demo/forecast.py`, reading `results/forecasting/rq1/summary.json` |
| `make demo-mesh` | 2 s | one figure: alerts delivered phone to phone against the number of phones, for three protocols | `scripts/demo/mesh.py` (PONS set-up from `research/mesh_pons/scripts/03_run_pons.py`) |

## What to say

**make check.**
"This checks that the simulator, the saved results and the mesh environment are on the laptop, and prints the fix for anything missing.
Nothing in the demos needs the internet."

**make demo-ambulance.**
"An ambulance drives the same stretch of Dhaka twice, in the same traffic. The first time nobody is told; the second time cars within
100 m get a V2X message and move aside (orange), and the signals ahead turn green.
On this seed it arrives 2.7 % sooner (292 s against 284 s), exactly as in our saved study run. One seed is not the result: over 10
paired seeds at Dhaka's density the alert saves a median 26 s on a 346 s trip but 4 of 10 runs are slower than the siren alone, and the
script prints this line from the study's summary (RQ3)."
- **Software:** Eclipse SUMO 1.27.1 with TraCI; our V2X delivery model (ITS-G5).
- **Make-way rule v2:** settings from SUMO's bluelight device (MSDevice_Bluelight) and the SUMO "Emergency" documentation. The 100 m
  distance is our own choice; no paper gives it (`evidence/ambulance_rq2/makeway_v2/choice.json`).
- **Signal pre-emption:** adapted from the atsc-rl repository, reproduced first.
- **Traffic:** generated at Dhaka's measured density (×0.78), seed 11.

**make demo-forecast.**
"Below the dashed line a model beats simply assuming speeds stay as they are. In Los Angeles the trained model is far below it at every
horizon; in Dhaka the best model is only slightly below at 15 and 30 minutes and above it at 60 minutes.
The right panel shows why: Dhaka's speed jumps in 6.5 to 13.1 % of 5-minute steps, against 0.7 % in Los Angeles."
- **Data:** METR-LA (DCRNN release, Li et al., ICLR 2018); DhaTraX v1.0 (three sites, one recorded day each, CC BY 4.0).
- **Models:** D2STGNN via BasicTS; Chronos-Bolt and Chronos-2 zero-shot.

**make demo-mesh.**
"With no mobile network, can an alert hop from phone to phone over 10 m Bluetooth between cars in Dhaka traffic? With 4 to 17 phones,
only about 2 to 3 % of alerts arrive within 5 minutes, for all three protocols. That is why the app sends by mobile network first
and uses the mesh only as a fallback."
- **Simulator:** PONS (pons-dtn 0.2.1).
- **Protocols:** Epidemic (Vahdat & Becker 2000), Spray and Wait (Spyropoulos et al. 2005), PRoPHET (Lindgren et al. 2003).
- **Radio range:** from The ONE simulator.
- **Phones:** "k phones" are k of the 17 simulated vehicles present for the whole window. With all 17, the result equals the saved
  mesh study.

## Outputs and evidence

| Demo | Files | Check that it ran correctly |
|---|---|---|
| ambulance | `evidence/demo/ambulance/last_run.json`, the run's SUMO output under `evidence/demo/ambulance/runs/` | exit code 0 only when both travel times equal the saved study runs for seed 11 (`results/emergency/dhaka/rq2/runs*/`) |
| forecast | `evidence/demo/forecast.png` | `tests/platform/test_demo_kit.py` checks the plotted ratios against `summary.json` |
| mesh | `evidence/demo/mesh/{results.json,run.log,mesh.png,SHA256SUMS}` | exit code 0 only when the 17-phone row equals `results/networking/mesh/dhaka/summary.json` |

Three runs of each from a fresh terminal (`env -i … zsh -lic 'make <target>'`), 12 of 12 passed on 2026-10-09:
`evidence/demo/fresh_runs/`.

## If something fails

- Run `make check` and do the FIX line it prints.
- The SUMO window needs the laptop's own screen; it does not open over ssh.
- If `results/…` files are missing, `make fetch-data` restores them; that is the only step that needs the internet.

## Full walkthrough video

`evidence/demo/full_walkthrough.mp4` (8.8 min, 11 chapters, 1920×1080), with `full_walkthrough.en.srt`, `full_walkthrough.bn.srt`,
`chapters.txt` and one file per chapter in `evidence/demo/segments/`. It is made against a local server on this laptop:

```bash
cd frontend && npx vite build && cd map && npx quasar build && cd ../..                 # current build
TRAFFICTWIN_TRAVELMUX_URL_DHAKA=http://127.0.0.1:9101 python -m uvicorn app.main:app --app-dir backend --port 8011 &   # with .env loaded
python scripts/demo/ambulance.py --record evidence/demo/raw/sumo_frames                  # the SUMO chapter (no screen-recording permission needed)
LOCAL_URL=http://127.0.0.1:8011/ node frontend/tests/qa/walkthrough.cjs                  # records phone and desktop, renders captions
python scripts/demo/video.py                                                             # composes the video, subtitles, chapters, frames
```

- **Needs the internet:** place search (Photon) and the Dhaka routing server (Valhalla on the routing instance, reached through a local
  travelmux container, `tm-dhaka` on port 9101). Steps that fail are listed in `evidence/demo/walkthrough_record.json`; the 2026-10-09
  run has none.
- **Captions:** rendered by Chrome as images beside the phone or under the desktop page, then placed by ffmpeg (this ffmpeg has no text
  filters). The browser's spoken Bangla lines are recorded instead of played and shown in yellow.
- **Frame check:** `evidence/demo/frame_check.md`.
