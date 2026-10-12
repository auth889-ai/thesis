# Reality check of the hosted app — after the fixes

- **Target:** https://43-205-213-250.sslip.io, final matrix run 2026-10-08 (+06) after the last deploy.
- **Coverage:** the same script (`frontend/tests/qa/reality.cjs`) and the same 13 features as the first table, plus F14, the owner's item on typed points being cleared.
- **Sizes and cities:** phone 390×844 and desktop 1400×900; Dhaka three times in Bangla, Los Angeles once in English.
- **Re-runs:** F7 and F12 were re-run after the last two small fixes (duplicate hospitals, the Research lab header). F8 Los Angeles was re-run after the check was corrected to accept the plain "no data" statement, the same rule the hospital check uses.
- **Files:** raw runs in `after_runs/`; the log in `after_run.log`; one record per fix in `fixes/`.

**112 of 112 runs pass.** (First table: 47 of 104 by the script; fewer on review.)

| Feature | What it checks | Passed | Phone Dhaka | Desktop Dhaka | Phone LA | Desktop LA | Median time | Before | Screenshot |
|---|---|---|---|---|---|---|---|---|---|
| F1 | Go-anywhere search | **8/8** | 3/3 | 3/3 | 1/1 | 1/1 | 7.8 s | 0/8 | [png](after_runs/F1-phone-dhaka-1.png) |
| F2 | Add your city | **8/8** | 3/3 | 3/3 | 1/1 | 1/1 | 14.3 s | 0/8 | [png](after_runs/F2-phone-dhaka-1.png) |
| F3 | Whole-city route and alternatives | **8/8** | 3/3 | 3/3 | 1/1 | 1/1 | 13.1 s | 6/8 | [png](after_runs/F3-phone-dhaka-1.png) |
| F4 | Turn-by-turn, simulated drive | **8/8** | 3/3 | 3/3 | 1/1 | 1/1 | 33.1 s | 6/8 | [png](after_runs/F4-phone-dhaka-1.png) |
| F5 | Leave when | **8/8** | 3/3 | 3/3 | 1/1 | 1/1 | 6.9 s | 6/8 | [png](after_runs/F5-phone-dhaka-1.png) |
| F6 | Recorded traffic | **8/8** | 3/3 | 3/3 | 1/1 | 1/1 | 16.3 s | 0/8 reviewed (script 8/8) | [png](after_runs/F6-phone-dhaka-1.png) |
| F7 | Nearest hospitals | **8/8** | 3/3 | 3/3 | 1/1 | 1/1 | 8.1 s | 0/8 reviewed (Vet-RX listed; LA check) | [png](after_runs/F7-phone-dhaka-1.png) |
| F8 | Ambulance reach | **8/8** | 3/3 | 3/3 | 1/1 | 1/1 | 11.9 s | 6/8 | [png](after_runs/F8-phone-dhaka-1.png) |
| F9 | Crash SOS | **8/8** | 3/3 | 3/3 | 1/1 | 1/1 | 35.5 s | 0/8 | [png](after_runs/F9-phone-dhaka-1.png) |
| F10 | Trip pack and offline | **8/8** | 3/3 | 3/3 | 1/1 | 1/1 | 38.4 s | 0/8 | [png](after_runs/F10-phone-dhaka-1.png) |
| F11 | Voice | **8/8** | 3/3 | 3/3 | 1/1 | 1/1 | 46.6 s | 0/8 | [png](after_runs/F11-phone-dhaka-1.png) |
| F12 | Tour | **8/8** | 3/3 | 3/3 | 1/1 | 1/1 | 34.4 s | 8/8 | [png](after_runs/F12-phone-dhaka-1.png) |
| F13 | 3D City | **8/8** | 3/3 | 3/3 | 1/1 | 1/1 | 5.2 s | 6/8 reviewed (LA: no note) | [png](after_runs/F13-phone-dhaka-1.png) |
| F14 | A place sent to Home survives the city loading (new) | **8/8** | 3/3 | 3/3 | 1/1 | 1/1 | 13.2 s | 0/4 (new check) | [png](after_runs/F14-phone-dhaka-1.png) |

## Number checks in the final runs
- **Route (F3):**
  - Dhaka shows 12.1 km and 54 min, against the server's own 12.08 km and 54.35 min (within 1 %). The straight line is 9.47 km, so the route is 1.28× it; average 13 km/h.
  - Los Angeles shows 20.1 mi (32.35 km) and 31 min, against 32.29 km and 30.9 min; average 63 km/h.
- **Nearest hospitals (F7, from Mohakhali):** Module General Hospital, 3 min, 0.4 km; General Medical Hospital, 4 min, 0.7 km; PG Outdoor, 5 min, 0.7 km. Each road distance is at least the straight-line distance. There is no animal hospital and no duplicate.
- **Ambulance reach (F8):** the sentence says 10 %, 28 % and 46 %; the Research table says 9.7 %, 27.7 % and 45.9 % (they match after rounding).
- **Bangla text:**
  - The route, progress, hospital and Leave when sentences contain no Latin digits, "km", "min" or AM/PM. Example: "গাড়ি নিয়ে ১২.১ কিমি যেতে প্রায় ৫৪ মিনিট".
  - The turn log no longer repeats a phrase.
  - Crash SOS and voice spoke 5 TEST lines in Bangla and in English, never dialled: 999 for Dhaka, 911 for Los Angeles.

## What is still open (not hidden)
- **English on the Bangla Research page:** the experiment's own labels and scenario texts are read from its run files and shown as recorded, for example "reactive routing (current travel times)" and "SIMULATED V2X EMULATOR". The page's own text and the lab header are translated.
- **Add city in Bangla:** a search result still shows Overture's place type in English ("locality") and its region code ("BD-G").
- **Motorbike:** the server gives it the car's exact route on 6 of 8 Dhaka trips. The choice is kept because it differs on 2 trips, and the page now says when the two are the same (`fixes/16_motorbike/RESULT.md`).
- **Ambulance reach in Los Angeles (F8):** the check's time, about 36 s, is the check waiting for a sentence that Los Angeles does not have. The page shows "no data" at once.
- **Incident during the fixes:** the first recorded-traffic deploy packaged the DhaTraX manifest without its two summary files. Every whole-city route then answered 500 for about 16 minutes (2026-10-07, 23:33–23:49 +06, from the two deploy logs' finish times), until the next deploy. A test now runs every recorded-data reader against the package (`fixes/7_recorded/RESULT.md`).
- **Backend suite:** 591 passed and 2 failed. Both failures predate this work and are untouched:
  - `tests/rebuild/test_phase1_prediction.py::test_real_record_carries_full_provenance`: `results/forecasting/trained_results.json`, committed 2026-10-04, has an empty `config` for D2STGNN and MegaCRN.
  - `tests/test_agent.py::test_read_tools_run_without_asking_and_everything_is_audited`: it plans a commute arriving 2026-10-01 09:00, which is now in the past.
- **Frontend suite:** all tests pass.
