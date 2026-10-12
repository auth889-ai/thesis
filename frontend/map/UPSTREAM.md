# The map app: Headway's web frontend, with what we changed

**Source.** https://github.com/headwaymaps/headway, `services/frontend/www-app`, commit `d0b994e513c5abe3ce25039f35c077e4865e643b` (2026-10-08). **Licence:** Apache-2.0 (`LICENSE`), read before copying; it allows use, change and redistribution with the licence, a notice of changes (`NOTICE`) and attribution. Recorded in `third_party/SOURCES.md`, "Map app (Headway)".

**Reproduced first, unchanged** (`evidence/design/headway_reproduce/`).
- **Our copy:** its own `yarn install --frozen-lockfile` and `yarn build` pass. 11 of 12 test files pass; the 12th (`ShieldQa.test.ts`) reads a style from elsewhere in Headway's repository, which is not part of the web app.
- **Headway's full checkout:** `yarn build` then `yarn test` pass **12 of 12 files, 85 of 85 tests**.
- **Node:** 24, which Headway's `engines` allows; this machine's Node 25 is outside that range.

## Upstream files changed (each marked `TrafficTwin change`)
| File | Why |
|---|---|
| `quasar.config.ts` | boot file `tt` (our service worker); our stylesheet `traffictwin.scss`; dark mode follows the device |
| `index.html` | our name, the fonts of our pages (Inter, Fraunces, Noto Sans Bengali), theme colour |
| `src/css/quasar.variables.scss` | our palette (espresso, caramel, cream) |
| `src/components/PlaceCard.vue` | our actions (category, Directions, Start, Share) in place of the mode bar; "Edit details" made small |
| `src/boot/i18n.ts` | the language comes from the setting both apps share (`tt.lang`), else the browser's |
| `src/i18n/index.ts` | Bangla (`bn`) and our strings (`tt`) added |
| `src/utils/Config.ts`, `src/components/BaseMap.vue` | a first visit opens on our default city, not 0,0 |
| `src/layouts/MainLayout.vue` | our trip overlay (`TtTrip`) |
| `src/pages/BaseMapPage.vue` | the nearest-hospitals chip; our menu drawer in place of Headway's dropdown (its About and Contact pointed at maps.earth) |
| `src/models/ShieldQa.test.ts` | reads Headway's style from `upstream/tileserver/styles/` in this copy |
| `src/pages/AlternatesPage.vue`, `src/pages/StepsPage.vue` | Start (our turn-by-turn) on the chosen route |

## Files added
- **`src/traffictwin/`:** `tt.ts`, `ttPure.ts`, `TtStart.vue`, `TtTrip.vue`, `TtHospitals.vue`, `TtMenu.vue`, `TtPlaceActions.vue`, `TtSimulation.vue`, `ttSim.ts`, `TtForecast.vue`, `ttReach.ts`, and `tt.test.ts`.
- **`src/css/traffictwin.scss`:** our look over Headway's styles.
- **Translations:** `src/i18n/bn/` (Bangla for Headway's strings and ours) and `src/i18n/en-US/tt.ts`.
- **`src/boot/tt.ts`.**
- **`public/sw.js`:** the service worker.
- **`public/tileserver/sprite/`:** Headway's icons, rendered by martin.
- **`public/tt/maplink.js`:** our shared code, built from `frontend/src/maplink`.

## Headway's services, replaced by adapters (backend/app/routing/headway_adapter.py)
| Headway expects | We serve |
|---|---|
| Pelias `/pelias/v1/*` | our Photon search and Nominatim lookups, translated to Pelias GeoJSON |
| travelmux `/travelmux/*` | Headway's travelmux image, **unchanged**, one per city in front of that city's Valhalla; the city is the one holding the trip's start |
| tileserver `/tileserver/style/basic-v3` | Headway's style with its tiles pointed at our map provider (OpenFreeMap, same OpenMapTiles schema), fonts at the provider's Noto Sans (which covers Bengali), icons at the sprite above. Left out: Headway's separate low-zoom landcover and terrain layers, which the provider has no source for |
| `/static/headway-config.json` | no transit server, no hard bounds, Research as the "About" link, the first routed city as the first view |
