# Map app navigation: Headway's map app with our turn-by-turn, trips and safety on top (Headway, travelmux, Valhalla, Ferrostar)

**Goal.** A production map app at `/` for any city with a config: search, place card, directions with alternatives, Ferrostar
turn-by-turn in Bangla or English, the trip saved for weak signal, the SOS button and the phone's crash sensor, hospitals and live
reach, and the Simulation chip that runs the thesis's own simulations. Headway's web app is copied and edited in place; the routing
is Valhalla through travelmux, unchanged.

## Pipeline

```
search box (Headway SearchBox) → /pelias/v1/*  → backend/app/routing/headway_adapter.py:_search (209-225; Photon, Nominatim)
map style                                        → headway_adapter.py:map_style (136-145): Headway basic-v3 pointed at our tiles and glyphs
        │
        ▼  Directions
frontend/map/src/models/Trip.ts:fetchBestTrips (457-494) → services/TravelmuxClient.ts:fetchPlans (326-377)
        → headway_adapter.py:travelmux_proxy (268-288; city_at 70-82) → travelmux container → that city's Valhalla (infra/app/setup.sh:45-52)
        │
        ▼  Start (or "Try simulated" ×8)
AlternatesPage.vue:27-33 / StepsPage.vue:24 → traffictwin/TtStart.vue:go (52-64) → traffictwin/tt.ts:startTrip (52-112) → /tt/maplink.js
        │
        ▼  navigation
frontend/src/maplink/index.ts:startNavigation (42-95): FerrostarCore, endpoint /api/navigate/{city}/route, Bangla banners, voice off, trip saved
backend/app/routing/router.py:navigate_route (217-239): Ferrostar's body forwarded unchanged (car or motorbike) → Valhalla /route
        │
        ▼  the trip screen
index.ts:62-75 → tt.ts:onState (90-103) → TtTrip.vue: banner, km and minutes, "Trip saved for weak signal (N MB)", SOS, phone sensor; armSos, pollAlerts (tt.ts:127-174)
```

## Upstream

| What | Where | Commit / version | Licence | How it is used |
|---|---|---|---|---|
| Headway web frontend (`services/frontend/www-app`) | https://github.com/headwaymaps/headway | `d0b994e513c5abe3ce25039f35c077e4865e643b` (2026-10-08) | Apache-2.0 (`frontend/map/LICENSE`, `frontend/map/NOTICE`) | **Copied to `frontend/map/` and edited in place.** The upstream files that carry "TrafficTwin change" are listed in `frontend/map/UPSTREAM.md` (`index.html`, `quasar.config.ts`, `src/boot/i18n.ts`, `src/css/quasar.variables.scss`, `src/i18n/index.ts`, `src/utils/Config.ts`, `BaseMap.vue`, `PlaceCard.vue`, `MainLayout.vue`, `BaseMapPage.vue`, `AlternatesPage.vue`, `StepsPage.vue`, `ShieldQa.test.ts`); diff `evidence/design/headway_reproduce/traffictwin_changes.patch` (SOURCES.md:99) |
| travelmux (Headway) | `ghcr.io/headwaymaps/travelmux` | image `sha256:7b57fa04…` | Apache-2.0 OR MIT | Unchanged: one container per city in front of that city's Valhalla, no transit server (`infra/app/setup.sh:47`) |
| Headway style `basic-v3` + icon SVGs | same commit, `services/tileserver/assets/` | `d0b994e5…` | style Apache-2.0; icons Maki CC0 | The style re-pointed at serve time by the adapter; icons rendered once into a sprite with martin 1.16.1 (SOURCES.md:101-102) |
| Valhalla | https://github.com/valhalla/valhalla | 3.9.0 | MIT | Unchanged: `/route` for navigation (car `auto`, motorbike `motorcycle`), no Bangla narration available (SOURCES.md:84) |
| Ferrostar (Stadia Maps) | https://github.com/stadiamaps/ferrostar ; npm `@stadiamaps/ferrostar-webcomponents`, `@stadiamaps/ferrostar` | `4e2d7f64…`; 0.57.0 | BSD-3 | Unchanged: `FerrostarCore` and the web components, built into `public/tt/maplink.js` with vite-plugin-wasm 3.6.0 (SOURCES.md:80, :106-109) |
| MapLibre GL JS | https://github.com/maplibre/maplibre-gl-js | 6.10 (map app), 5.24.0 (React app) | BSD-3 | Unchanged |

## Files

- Ours in the map app ("TrafficTwin addition"): `frontend/map/src/traffictwin/*` (`tt.ts`, `ttPure.ts`, `ttSim.ts`, `ttReach.ts`, `TtStart.vue`, `TtTrip.vue`, `TtHospitals.vue`, `TtSimulation.vue`, `TtForecast.vue`, `TtMenu.vue`, `TtPlaceActions.vue`), `src/boot/tt.ts`, `src/css/traffictwin.scss`, `src/i18n/{bn/*, en-US/tt.ts}`, `public/sw.js`.
- Shared navigation code: `frontend/src/maplink/index.ts` (Ferrostar config 26-33, `startNavigation` 42-95, `armCrashDetector` 112-141) → `frontend/map/public/tt/maplink.js` (`vite build --config vite.maplink.config.ts`).
- Backend: `backend/app/routing/headway_adapter.py` (Pelias, travelmux, tileserver, config), `backend/app/routing/router.py:213-239`.
- Checks: `frontend/tests/qa/mapflow.cjs` (the QA matrix), `offline_home.cjs`, `live_reach.cjs`, `phone_sensor.cjs`.

## Commands

    make app                                           # the API + web app on http://127.0.0.1:8000; the map app at /
    cd frontend/map && quasar build                    # the map app bundle (frontend/map/package.json:15)
    cd frontend && npx vite build --config vite.maplink.config.ts   # our shared navigation bundle → frontend/map/public/tt/maplink.js
    HOSTED_URL=https://<host>/ HOSTED_USER=… HOSTED_PASSWORD=… node frontend/tests/qa/mapflow.cjs    # QA matrix → evidence/qa/mapflow/ (no make target)
    make run-offline                                   # LIVE: a trip saved for weak signal, then offline (features/weak-signal-prefetch)

## Results from saved evidence

- Hosted QA matrix (`evidence/qa/mapflow/2026-10-11T00-36-55-953Z.{json,md}`, sha256 `325ae270…`, hosted app): **48 PASS, 0 FAIL**
  of 54 rows (6 rows without a verdict), phone and desktop, Dhaka and Los Angeles: search suggestions, place card with 3 actions,
  3 routes listed, hospitals chip, 8 menu entries, Start and the trip screen.
- Offline Home check (`evidence/offline_home/offline_home_check.json`, 2026-10-10): 6 of 6; `make run-offline` last run
  (`evidence/live_runs/offline/last_run.json`): 8 of 8 steps, 37 of 47 answers from the service worker.
- Live reach and phone sensor checks: see `features/hospital-reach/README.md` (11 of 11) and `features/crash-detection/README.md` (7 of 7).
- Navigation itself has no thesis number: the route is Valhalla's, forwarded unchanged (`router.py:217-239`); nothing here is a
  research result, and the app says SIMULATION / Real recorded / Forecast on every result it shows (CLAUDE.md plain-language rule).

## The finding

A mature open-source map app (Headway) carries the thesis's features to a phone without us writing a map app: search, directions
and turn-by-turn are upstream's, used unchanged or through adapters, and our additions sit in a separate `traffictwin/` folder plus
the marked edits. The hosted QA matrix passes for both evaluation cities with the same code, which is the city-agnostic rule in
practice. What the map app does not do is decide routes with the thesis's models: forecast-aware routing was found inconclusive in
RQ2 and is deliberately not in the app (STRENGTH_AUDIT "Not proposed").

## Honest limits

- Headway is edited in place (a fork, no reference checkout); the saved patch is older than the latest edits, and the marked-file
  count in `SOURCES.md:99` was corrected on 2026-10-11 (CODE_MAP known gap 2). Fetching the reference checkout and regenerating the
  patch is STRENGTH_AUDIT fix 12, not done.
- Valhalla has no Bangla narration (`bn-IN`, `bn` asked on 2026-10-07); banners are translated by us, voice is off.
- Ferrostar 0.57.0's turn icon throws for a maneuver pair it has no icon for; we do not edit it (SOURCES.md:108).
- The route is never altered by the thesis (by design); the map app's forecast and simulation panels show results, they do not steer.
- Mesh and signals do not run on the hosted server (no PONS / sumo-rl there); the web V2X job always uses `alert_preemption` (CODE_MAP gap 5).
- No make target for the map app build or `mapflow.cjs`; `frontend/map/README.md` is Headway's own (STRENGTH_AUDIT f).
- 6 of the 54 QA rows carry no verdict (informational rows); the matrix is a browser check, not a user study.
