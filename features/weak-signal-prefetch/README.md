# Weak-signal prefetch: a usable route when the signal is poor (RQ5; Bartendr, BreadCrumbs)

**Goal.** When a trip is planned on a good signal, save the route, the map tiles along it and the app shell on the phone, so that on a
2G-like link or offline the route still shows at once; estimate the radio energy of three download plans (now, as needed, Bartendr's
schedule). Everything below is SIMULATED: the network is emulated in headless Chromium, the energy is estimated from a paper's
measurements, not measured on our phones.

## Pipeline

```
a planned trip (Dhaka route)                       frontend/src/features/today/TripPackPanel.tsx  "Works with weak signal"
        │
        ▼  signal along the route (predicted per step)
backend/app/routing/router.py:city_route_signal    → signal_predict.py:predict → core/simulation/routing/signal.py (steps, combine)
        │
        ▼  "Save this trip" (MB shown)
frontend/src/lib/pack.ts:savePack                  route answers + tiles (saveTile) + app assets (packAssets.ts) → Cache Storage trip-pack-<city>
        │
        ├─ along the drive: useAlongTheDrive.ts; personal forecast useBreadcrumbs.ts → lib/breadcrumbs.ts (learn / forecast / readiness)
        │
        ▼  offline / weak link
frontend/src/sw.ts (app /app/), pack.ts:registerPackProtocol (our tiles), frontend/map/public/sw.js (map app: fromPack, networkFirst)
        │
        ▼  experiment: 4 network presets × 2 arms × 3 runs, service worker throttled too
frontend/tests/weak_signal.experiment.cjs → core/networking/prefetch/results.py:build (energy via core/networking/v2x/energy.py:bartendr)
        │
        ▼
results/networking/prefetch/summary.json   (copied to evidence/prefetch/summary.json)
```

## Upstream

| What | Where | Commit / version | Licence | How it is used |
|---|---|---|---|---|
| Bartendr | Schulman, Navda, Ramjee, Spring, ACM MobiCom 2010 (`papers/bartendr_mobicom2010.pdf`, sha256 `1ddd1d93…`) | the paper, read 2026-10-06 | © ACM, paper only | The schedule (download in strong-signal stretches) reimplemented in `frontend/src/lib/schedule.ts:24-50`; its Palm Pre power and throughput figures for the energy estimate (`core/networking/v2x/energy.py`) |
| BreadCrumbs | Nicholson, Noble, ACM MobiCom 2008 (`papers/breadcrumbs_mobicom2008.pdf`, sha256 `de8aa556…`) | the paper, read 2026-10-06 | © ACM, paper only | The personal connectivity forecast reimplemented in `frontend/src/lib/breadcrumbs.ts` (`learn`, `forecast`, `readiness`) |
| Workbox + vite-plugin-pwa | https://github.com/GoogleChrome/workbox | 7.4.1; 2.0.0 | MIT; MIT | Unchanged: precache of the built app, network-first for this app's API GETs (`frontend/src/sw.ts`) |
| OpenFreeMap "liberty" style | https://github.com/hyperknot/openfreemap-styles | `cf9e8e72…` | repo MIT; style JSON BSD-3 | Copied to `frontend/public/liberty/`; source, sprite and glyph URLs changed (SOURCES.md:71) |
| Noto Sans glyphs | https://github.com/maplibre/demotiles `font/` | gh-pages, `601ae607…` for the two ranges added 2026-10-10 | BSD-3 (repo); OFL (font) | Copied to `frontend/public/fonts/` (SOURCES.md:72) |
| Planetiler; PMTiles | https://github.com/onthegomap/planetiler ; npm `pmtiles` | v0.10.2; 4.5.0 | Apache-2.0; BSD-3 | Unchanged: our own tiles and the reader (SOURCES.md:70, :20) |

## Files

- `frontend/src/lib/pack.ts` (`savePack` 73-87, `saveTile` 48-53, `registerPackProtocol` 30-45), `packAssets.ts`, `schedule.ts` (`bartendr` 24-50, `nowJ` 53, `asNeededJ` 56-66), `breadcrumbs.ts`, `basemap.ts`, `sw.ts` (13-23).
- `frontend/src/features/today/TripPackPanel.tsx` (27-93), `useAlongTheDrive.ts` (11-34), `useBreadcrumbs.ts` (25-51).
- `frontend/map/public/sw.js` (`fromPack` 49-56, `networkFirst` 58-72): the map app's service worker.
- `backend/app/routing/router.py:city_route_signal` (242-253), `signal_predict.py:predict` (10-41), `core/simulation/routing/signal.py`.
- `frontend/tests/weak_signal.experiment.cjs` (`oneRun` 85-149; throttling the service worker 40-78); `core/networking/prefetch/results.py` (`build` 111-137, `energy_rows` 52-74); `core/networking/v2x/energy.py:bartendr` (25-50).
- Checks: `frontend/tests/qa/offline_home.cjs`, `scripts/live/run_offline.py` (`make run-offline`).

## Commands

    make run-offline                        # LIVE: visible Chrome, plan + start a trip, go offline, reopen; lists what the service worker served
    make run-offline ARGS="--rq5"           # the same, then the thesis experiment once more with the time-to-route check
    make run-offline ARGS="--profile=2g"    # throttled instead of offline (also --profile=3g)
    node frontend/tests/weak_signal.experiment.cjs 3 && PYTHONPATH=.:backend python -m core.networking.prefetch.results   # rebuild the results (no make target)
    make prefetch-masts [ARGS="--fetch"]        # Q3: the signal profile from real OSM mast positions + 3GPP path loss, energy on it -> evidence/prefetch/masts/
    node frontend/tests/qa/offline_home.cjs --with-route                                                                  # offline Home check

## Results (`results/networking/prefetch/summary.json`, sha256 `990136245da9…`, built 2026-10-06; 24 runs, 3 per cell; route pack median 10 201 674 bytes)

| Network (emulated) | Time to the route, without the saved trip | With the saved trip |
|---|---|---|
| fast 4G (4/3 Mbit/s, 20 ms) | 0.8 s | 0.8 s |
| slow 3G (400/400 kbit/s, 400 ms) | 1.8 s | 0.8 s |
| 2G-like (50/20 kbit/s, 1 000 ms) | **7.4 s** (range 6.8-7.4) | **0.8 s** |
| offline 10 s after the route | continues 3 of 3 | continues 3 of 3 |

Energy (`energy.rows`, 9 rows: weak stretches over 10, 30 and 50 % of the real Dhaka route, 3 seeds each; ESTIMATED from Bartendr's
Palm Pre figures: 1.5 / 1.8 / 2.25 W, tail 4.5 J): download now 35.1 J in every row; as needed 62.0-72.1 J (10 %), 97.6-106.9 J (30 %),
122.1-131.6 J (50 %); Bartendr's schedule 35.1 J, one burst, in all 9 rows. Saving against "as needed": 43.4-73.3 %.

Offline check (`evidence/offline_home/offline_home_check.json`, sha256 `d2c87c56…`, 2026-10-10): 6 of 6. Live offline run
(`evidence/live_runs/offline/last_run.json`): 8 of 8 steps, 37 of 47 answers from the service worker after the cut.

## Signal from real mast positions (step Q3, 2026-10-11; `evidence/prefetch/masts/summary.json`, sha256 `33aa91c8…`)

`make prefetch-masts` (`core/networking/prefetch/masts.py`): the real Dhaka route's 85 steps judged from the nearest OpenStreetMap
radio site (`data/cities/dhaka/masts.json`: Overpass query recorded, OSM base 2026-10-11; a radio site = mast/tower tagged
`tower:type=communication` or `communication:mobile_phone=yes`, **8 of 40 elements** in the 15 x 10 km box) and the 3GPP TR 38.901
urban-macro path loss (1.8 GHz, user 1.5 m, base 25 m) with an ASSUMED EIRP of 56 dBm; bins at Bartendr's anchors (strong >= -70 dBm,
medium >= -90, weak below). Result: nearest site median 2 040 m (max 5 630 m); steps strong 4 / medium 32 / weak 49
(508 / 4493 / 7307 m); the route starts with 6 km below -90 dBm and its only strong stretch is at km 10. Energy on this profile: now 35.1 J,
as needed 140.3 J, Bartendr 35.1 J in 1 burst (saving 75.0 % against as needed), against the synthetic rows' as-needed 62-132 J.
**Reading:** this is the route "that starts on a weak signal" the finding above said we lacked, and Bartendr's energy-only schedule puts
its one burst in the strong stretch at km 10, after 80 % of the drive: the model has no deadline, so the map would arrive too late; that
limit is the paper's model as implemented, not fixed here. The level is MODELLED from real positions, not measured, and OSM lists a tiny
fraction of Dhaka's cell sites (8 in the box against thousands in the city), so the "weak" stretches say where OSM has no mast, not
where the network is weak. In the app the mast-based bin replaces the road's density guess only with `TRAFFICTWIN_SIGNAL_MASTS=1`
(`backend/app/routing/signal_predict.py`, off by default; history still wins, a tunnel still wins; the answer names the source).

**R2 / R3 (2026-10-11 evening).** The hosted app runs with `TRAFFICTWIN_SIGNAL_MASTS=1` (set in `infra/app/setup.sh`'s `.env`; the
code default is off) and ships `data/cities/dhaka/masts.json`, so the trip's signal strip there uses the real OSM mast positions too. The
Research RQ5 table shows the mast profile's energy line (`prefetchRes.masts`), read from `evidence/prefetch/masts/summary.json` when the
page is served (`results.py:masts_row`); the synthetic rows above it are the saved ones.

## The finding

Saving the trip while the signal is good makes the route appear at once on a weak link (0.8 s against 7.4 s on 2G-like) and keeps
the app and the saved answers working offline. **The energy saving (43-73 %) comes from prefetching, not from Bartendr's
scheduling:** on our route the schedule equals "download now" in 9 of 9 rows (one burst, 35.1 J), because the whole pack fits in the
first strong stretch. Bartendr's contribution is a plan that would matter on a route that starts on a weak signal; we did not have one.

## Honest limits

- The network is emulated in headless Chromium (CDP presets), not a real cellular link; the service worker is throttled too, which
  the first attempt did not do (`evidence/prefetch/run1_discarded_service_worker_not_throttled.log`).
- Energy is an estimate from a 2010 phone's measurements (Palm Pre), not measured on any phone; the thesis's signal profiles are SYNTHETIC
  (weak stretches placed by seed, one 200 m tunnel); the Q3 profile is MODELLED from 8 OSM radio sites with assumed transmitter constants,
  and OSM's mast coverage of Dhaka is a tiny fraction of the real network.
- One route (Dhaka), 3 runs per cell; the time-to-route range is 0.8-0.8 s in most cells because the app shell answers from cache.
- Not measured offline: whether our own tiles were drawn after the cut (the route answers stayed on screen in both arms,
  `summary.json` `not_measured`).
- Bartendr and BreadCrumbs are papers only; no reference code exists to reproduce first (STRENGTH_AUDIT criterion a: WEAK).
- No Makefile target for the experiment itself or for `core.networking.prefetch.results` (STRENGTH_AUDIT f).
