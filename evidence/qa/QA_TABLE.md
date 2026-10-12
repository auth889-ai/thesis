# Reality check of the hosted app — failures ranked

- **Target:** https://43-205-213-250.sslip.io, run on 2026-10-07 (about 13:40–14:45 UTC).
- **Method:** headless Chrome (Playwright 1.63), with a phone at 390×844 and a desktop at 1400×900. Each feature ran three times on Dhaka (in Bangla) and once on Los Angeles (in English): 13 features × 8 runs = 104 runs.
- **Script:** `frontend/tests/qa/reality.cjs`.
- **Raw files:**
  - one JSON and one PNG per run in `evidence/qa/runs/`;
  - the log in `evidence/qa/run.log`;
  - the same table as data in `QA_TABLE.json`.
- **Nothing was changed in the app during the check.** No fix has been made yet.

**Severity:**
- **S1:** the feature gives no result.
- **S2:** the result is wrong or misleading.
- **S3:** the feature works but is confusing.
- **S4:** cosmetic.

"Runs failed" counts are per group: phone Dhaka · desktop Dhaka · phone LA · desktop LA. These are reviewed verdicts. Where the script's own pass/fail was wrong, the row says so.

| Rank | Feature | Sev. | What a person sees | Cause | Runs failed | Median time | Screenshot |
|---|---|---|---|---|---|---|---|
| 1 | Crash SOS (F9) | S1 | Tapping "crash-like jolt" (or any replay) does nothing: no countdown, no alert path, no message | Confirmed: the server answers 404 "no synthetic trace 'crash_jolt'" because `research/sos/traces/` is not in the hosted package (`infra/app/package.sh` / `data_files.txt`) | 3/3 · 3/3 · 1/1 · 1/1 | 34 s (timeout) | [F9-phone-dhaka-1](runs/F9-phone-dhaka-1.png) |
| 2 | Voice (F11) | S1 | Voice switches on in Settings, but no alert is ever spoken | Same as rank 1: every run shows the same 404 on the trace the voice check replays. Voice on its own is not yet proven either way | 3/3 · 3/3 · 1/1 · 1/1 | 50 s (timeout) | [F11-phone-dhaka-1](runs/F11-phone-dhaka-1.png) |
| 3 | Go-anywhere search (F1) | S1 | Typing "Motijheel" (or "Hollywood") shows only "Add 'Motijheel' as a city". Picking it opens Add city, which then fails (rank 5). No place can be chosen as a destination | Likely: `searchRows.ts` keeps only places inside the selected city's *built simulation area* (`insideBox(places, city.bounding_box)`), which is a small box, so ordinary places are dropped. To confirm during the fix | 3/3 · 3/3 · 1/1 · 1/1 | suggestions in 0.45 s; then nothing | [F1-phone-dhaka-1](runs/F1-phone-dhaka-1.png) |
| 4 | Switching the city to Los Angeles (Home: F3, F4, F5, F10, and F1/F6 on LA) | S1 | Home turns into "This page hit a problem: Cannot read properties of undefined (reading 'getSource')". No route, drive, Leave when or trip pack in LA | Likely: the old map is removed on the city switch while a pending style poll or Home map effect still calls `getSource` on it (`MapView` / `HomeMap`). To confirm during the fix | LA only: 1/1 · 1/1 for each of F3, F4, F5, F10 | 35 s (timeout) | [F3-desktop-los_angeles-1](runs/F3-desktop-los_angeles-1.png) |
| 5 | Add your city (F2) | S1 | After Search, a red box says "the search could not be made: ModuleNotFoundError: No module named 'duckdb'". This is raw English developer text, shown on the Bangla page too | Confirmed: `duckdb` is in `backend/requirements.txt` but missing from the hosted `infra/app/requirements.txt`. The raw exception is shown untranslated | 3/3 · 3/3 · 1/1 · 1/1 | 34 s (timeout) | [F2-phone-dhaka-1](runs/F2-phone-dhaka-1.png) |
| 6 | Trip pack and offline (F10) | S1 | "Saved: 10.1 MB, 33 map tiles" works (in 11 s). With no network, reopening the app gives only "Could not load the list of cities (Failed to fetch)", with no map and no route, so the saved trip is unusable | Confirmed from the run's requests: Home needs `/api/operate/cities` and `/api/profile` before anything shows, and the service worker keeps neither | 3/3 · 3/3 (LA blocked by rank 4) | 84 s | [F10-phone-dhaka-1](runs/F10-phone-dhaka-1.png) |
| 7 | Recorded traffic (F6) | S1 | Ticking "Real recorded traffic" gives "No recorded vehicles for Dhaka are ready on this computer". Nothing replays, and "on this computer" is wrong wording on a website | Likely: the DhaTraX recorded trajectories are not in the hosted package (only small summaries are). **The script passed these runs** because a reason was shown; on review that is a failure | 3/3 · 3/3 (LA correctly says it has none) | 16 s | [F6-phone-dhaka-1](runs/F6-phone-dhaka-1.png) |
| 8 | Nearest hospitals (F7) | S2 | The third "nearest hospital" from Mohakhali is **"Vet-RX"**, a veterinary clinic. The list also contains "National Veterinary Hospital". Times and distances are sensible (0.4–0.7 km, 3–4 min; road distance ≥ straight line) | Confirmed: `data/cities/dhaka/hospitals.json` (477 OSM `amenity=hospital` entries) includes animal hospitals; there is no filter for veterinary places | 3/3 · 3/3 (LA correctly says "no data") | 8.4 s | [F7-phone-dhaka-1](runs/F7-phone-dhaka-1.png) |
| 9 | Turn-by-turn, Bangla (F4) | S2 | One instruction reads "৫০ মিটার পরে হালকা বাঁয়ে হালকা বাঁয়ে যান-এ যান" ("in 50 m bear left onto *bear left*"). It is spoken like that too. The banner starts in English road names, as expected | Likely: `navText.ts` uses the maneuver text as the road name when the step has no name | 3/3 · 3/3 | 33 s (the 40 s watch) | [F4-phone-dhaka-1](runs/F4-phone-dhaka-1.png) |
| 10 | Leave when (F5) | S3 | Says plainly "no traffic data for Dhaka yet" (acceptable). But the everyday panel also shows developer English: "REAL — OpenStreetMap geometry converted by SUMO netconvert", "every section driven at its map speed limit; no traffic, signals or queues" | Plain-language rule: these lines belong on Research | 3/3 · 3/3 | 6.3 s | [F5-phone-dhaka-1](runs/F5-phone-dhaka-1.png) |
| 11 | 3D City in LA (F13) | S3 | The LA map shows, but Dhaka's simulation (left by an earlier visitor) is the one running. The LA numbers stay "—" until the person presses "Stop it and start Los Angeles". The page says why in small text. **The script passed these runs** | The one-simulation-per-site rule works as designed. The message is small and the empty numbers look broken | 0/0 · 0/0 · 1/1 · 1/1 | 5.4 s | [F13-desktop-los_angeles-1](runs/F13-desktop-los_angeles-1.png) |
| 12 | Bangla text (Home, nav, Leave when) | S4 | Units and digits are mixed: "১২.১ km যেতে প্রায় 54 মিনিট", "46টি", "২.৯ min", "০৮:৩৬ PM". Also "গাড়ি-এ" (should read "গাড়িতে") | Numbers are not all formatted through the Bangla locale, and the units are not translated | all Dhaka runs of F3, F4, F5 | — | [F3-phone-dhaka-1](runs/F3-phone-dhaka-1.png) |
| 13 | Search row icon | S4 | The row reads "add Add 'Hollywood' as a city" (Bangla: "যোগ … যোগ করুন"): the icon's name is printed as text | The icon ligature text is read as text | 8/8 | — | [F1-desktop-los_angeles-1](runs/F1-desktop-los_angeles-1.png) |
| 14 | Research page in Bangla (seen in the Tour) | S4 | The Research cards stay in English ("Does smart routing help? …") when the app is in Bangla | Research strings are not in the i18n files. This is a reviewer page, so the impact is low | all Bangla Tour runs | — | [F12-phone-dhaka-1](runs/F12-phone-dhaka-1.png) |

## What passed (with the number checks)
- **Whole-city route (F3), Dhaka 6/6:**
  - **Speed:** the route appears in 2.2 s.
  - **Server match:** 12.1 km, 54 min, against the server's own 12.08 km, 54.35 min, within 1 %.
  - **Distance:** the straight line is 9.47 km, so the route is 1.28× it.
  - **Average speed:** 13 km/h, within the plausible Dhaka range.
  - **Alternatives:** three (54, 58 and 65 min), and choosing one changes the sentence.
- **Motorbike (F3):** it shows the same 12.1 km and 54 min as the car. **The server's own motorcycle answer is identical** (12.08 km, 54.35 min), so the app reports the server faithfully, which is not an app bug. A person may still wonder why the two choices are the same.
- **Simulated drive (F4), Dhaka 6/6:** the first banner appears in 1.2–1.8 s, the distance counts down, and End removes the drive. The only problem is the Bangla wording, in rank 9.
- **Ambulance reach (F8), Dhaka 6/6:** the sentence says 10 %, 28 % and 46 %. The Research table says 9.7 %, 27.7 % and 45.9 %, so they match after rounding. 37 hospitals are listed. LA says "no data for Los Angeles" as the rules require; the script counted this as a failure, and it is not one.
- **Tour (F12), 8/8:** it goes through every step without getting stuck. The opening step highlights nothing on every run (it is an introduction), and on LA one more step (the third) has nothing highlighted.
- **3D City (F13), Dhaka 6/6:** the simulation is running, vehicles are shown and it is labelled SIMULATED, in 5–12 s.
- **Emergency numbers:** shown from the city config (Dhaka 999, LA 911) and never dialled.

## Order of fixes proposed (after approval, one at a time, with the same check re-run after each)
1. **Ranks 1 and 2:** package the SOS traces.
2. **Rank 5:** add duckdb to the hosted requirements, and show a plain translated error.
3. **Rank 4:** the LA crash on city switch.
4. **Rank 3:** place suggestions in the search.
5. **Rank 6:** offline Home.
6. **Rank 7:** deploy the recorded traffic, or say plainly that it is not on the website.
7. **Ranks 8 to 14** in order.

Ranks 1, 2 and 5 are deployment omissions. Ranks 1 and 2 share one cause.
