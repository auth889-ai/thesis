# QA after the focused Home (2026-10-08)

Hosted app https://43-205-213-250.sslip.io, the same script (`frontend/tests/qa/reality.cjs`); phone 390×844 and desktop 1400×900, Dhaka ×3 (Bangla), Los Angeles ×1 (English). Raw runs: `matrix/`; log: `matrix_run.log`.

**136 of 136 runs pass.**

| Check | What | Phone Dhaka | Desktop Dhaka | Phone LA | Desktop LA | Median time |
|---|---|---|---|---|---|---|
| H1 | Home: Crash SOS (Arm, a real sensor jolt, Cancel, then the TEST path with the city's number) | 3/3 | 3/3 | 1/1 | 1/1 | 20.1 s |
| H2 | Home: Nearest hospital from my location | 3/3 | 3/3 | 1/1 | 1/1 | 8.9 s |
| H3 | Home: Navigate (destination, Start, spoken, saved for weak signal, keeps going offline) | 3/3 | 3/3 | 1/1 | 1/1 | 50.7 s |
| F1 | Search (in More) | 3/3 | 3/3 | 1/1 | 1/1 | 7.8 s |
| F2 | Add city | 3/3 | 3/3 | 1/1 | 1/1 | 13.5 s |
| F3 | Trip planner: route and alternatives | 3/3 | 3/3 | 1/1 | 1/1 | 12.8 s |
| F4 | Trip planner: simulated drive | 3/3 | 3/3 | 1/1 | 1/1 | 32.6 s |
| F5 | Trip planner: Leave when | 3/3 | 3/3 | 1/1 | 1/1 | 6.7 s |
| F6 | Recorded traffic | 3/3 | 3/3 | 1/1 | 1/1 | 16.3 s |
| F7 | Emergency: nearest hospitals | 3/3 | 3/3 | 1/1 | 1/1 | 8.4 s |
| F8 | Emergency: ambulance reach | 3/3 | 3/3 | 1/1 | 1/1 | 11.1 s |
| F9 | Emergency: crash SOS with replays | 3/3 | 3/3 | 1/1 | 1/1 | 34.7 s |
| F10 | Trip pack and offline (/trip) | 3/3 | 3/3 | 1/1 | 1/1 | 28.2 s |
| F11 | Voice | 3/3 | 3/3 | 1/1 | 1/1 | 45.5 s |
| F12 | Tour (in More) | 3/3 | 3/3 | 1/1 | 1/1 | 45.0 s |
| F13 | 3D City | 3/3 | 3/3 | 1/1 | 1/1 | 5.1 s |
| F14 | A place sent to the Trip planner survives the city loading | 3/3 | 3/3 | 1/1 | 1/1 | 12.5 s |

Found and fixed during this run (each re-run with the same check):
- F10 0/8: the Trip planner moved to `/trip` and, offline, its reload found no page (the service worker served only `/`). Fix: a navigation fallback to the precached shell (`frontend/src/sw.ts`); test `frontend/src/lib/swShell.test.ts`. After: 8/8.
- H1 7/8: the check read the SOS steps 4 s after the path appeared; it now waits for the four steps (up to 15 s). After: 8/8. No app change.
- H3 Los Angeles: the test trip (0.8 mi) ended while the network was off; the check now uses a farther destination. No app change.
- The map on our own tiles missed its icons ("Invalid sprite URL"): the style's sprite and glyphs are now made absolute (`lib/basemap.ts`, test in `basemap.test.ts`).
- **Incident:** a deploy on 2026-10-08 took the hosted app down for about 12 minutes (05:25–05:37 +06): the new RQ1 Research endpoint imported pandas at start-up and the hosted app does not install it. Fixed; a test now starts the app with every research-only library unimportable, and `infra/app/deploy.sh` refuses to deploy unless `tests/test_hosted_package.py` passes.
