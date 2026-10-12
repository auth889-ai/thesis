# Hospital reach: how much of the city an ambulance reaches in 10, 20 and 30 minutes (isochrones; live reach on the map app)

**Goal.** For every point of a 500 m grid over Dhaka, the drive time from the nearest hospital with an emergency department at map
speeds (Valhalla), and the share of the grid within 10 / 20 / 30 minutes; the same with two recorded speeds (DhaTraX) corrected in.
Since step K (2026-10-11) the map app can draw, for any tapped point, the three nearest hospitals' 10/20/30-minute areas computed now
by the city's Valhalla server. Label: MAP SPEEDS, not live traffic.

## Pipeline

```
OpenStreetMap hospitals (emergency=yes; 37 of 477)     core/safety/reach.py:chosen_hospitals (60-70)
        │
        ▼  500 m grid, 2 610 points                     reach.py:grid (45-57), STEP_M :30
Valhalla /sources_to_targets (car, map speeds)         core/simulation/routing/valhalla.py:matrix (156-178)   ← infra/valhalla (valhalla-scripted 3.9.0)
        │
        ├─ recorded variant: two DhaTraX sites at 08:30 → per-site delta (139-146) → reach.py:decompose (92)
        ▼
reach.py:_best, plain_numbers (119)  →  results/reach/dhaka/summary.json   (make the shares; per-hospital cells and km²)
        │
        ▼  the API                                       backend/app/emergency/router.py
GET /api/emergency/reach/{city}            saved build (get_reach 48)
GET /api/emergency/reach/{city}/isochrone  one hospital's polygons (get_isochrone 64 → valhalla.isochrone 141-153)
GET /api/emergency/reach/{city}/nearest    (reach.nearest 193)
GET /api/emergency/reach/{city}/live       step K: 3 nearest by drive time, each one's 10/20/30-min polygons in parallel, timed (reach.live 210, _iso_cached 76)
        │
        ▼
Emergency page: ReachCard.tsx, ReachMap.tsx · map app: TtHospitals.vue (toggle "Live reach: tap the map"), ttReach.ts
```

## Upstream

| What | Where | Commit / version | Licence | How it is used |
|---|---|---|---|---|
| Valhalla (`valhalla-scripted` image) | https://github.com/valhalla/valhalla | 3.9.0 (image tag; master `f49f3b9d…` at reading) | MIT | Unchanged, on AWS (`infra/valhalla/launch.sh`, `user-data.sh:16-34`): `/sources_to_targets`, `/isochrone`; pinned by tag, not digest (SOURCES.md:184) |
| Valhalla isochrone API | `docs/docs/api/isochrone/api-reference.md` | server 3.9.0 | MIT | Step K: one request per nearest hospital, contours 10/20/30 min, `polygons: true`, `denoise 0.5`, `generalize 50`; the GeoJSON drawn as it comes (SOURCES.md:223) |
| gis-ops valhalla-app | https://github.com/gis-ops/valhalla-app | `439ea98f…` | MIT | The request shape and the colours only; no code copied (SOURCES.md:50) |
| DhaTraX | Roy, Arnob, Zenodo 2026, doi 10.5281/zenodo.22157752 | version 1.0 | CC BY 4.0 | Two sites' median speeds at 08:30 for the recorded variant (`summary.json` `recorded.sites`) |
| OpenStreetMap | Geofabrik `asia/bangladesh` | extract 2026-10-04 | ODbL | Hospitals and the road network |

## Files

- `core/safety/reach.py`: `grid` (45-57), `chosen_hospitals` (60-70), `recorded_sites` (73-88), `decompose` (92), `plain_numbers` (119), `build` (126), `nearest` (193), `live` (210).
- `core/simulation/routing/valhalla.py`: `TIME_SOURCE` (:27), `isochrone` (141-153), `matrix` (156-178).
- `backend/app/emergency/router.py`: `get_reach` (48), `get_isochrone` (64), `_iso_cached` (76), `get_live_reach` (88).
- `frontend/src/features/emergency/ReachCard.tsx` (18-69), `ReachMap.tsx` (16-65), `reach.ts`.
- `frontend/map/src/traffictwin/TtHospitals.vue` (toggle `data-tt="reach-live-toggle"`, card `reach-live`, failure line `reach-live-failed`), `ttReach.ts` (`reachFeatures` 12, `reachSummary` 19, `reachBounds`); `frontend/map/public/sw.js` bypasses the computed-live endpoints.
- `infra/valhalla/launch.sh`, `user-data.sh`. Tests: `backend/tests/emergency/test_live_reach.py`; check `frontend/tests/qa/live_reach.cjs`.

## Commands

    PYTHONPATH=.:backend python -m core.safety.reach build --city dhaka --at 08:30     # rebuild the table (needs TRAFFICTWIN_VALHALLA_URL_DHAKA; no make target)
    make app → / → Hospitals chip → "Live reach: tap the map" → tap a point              # LIVE: computed now by Valhalla, timed
    LOCAL_URL=http://127.0.0.1:8011/ node frontend/tests/qa/live_reach.cjs               # desktop + phone check → evidence/reach/live/

Web: `/app/emergency` (the reach table; pick a hospital for its isochrones; click for the nearest hospitals).

## Results (`results/reach/dhaka/summary.json`, sha256 `89d7a17f…`, built 2026-10-06; 37 hospitals, 2 610 grid points, 0.25 km² cells)

| Within the nearest emergency hospital's reach | Map speeds (`plain.map_pct`) | With the two recorded sites (`plain.recorded_pct`) |
|---|---|---|
| 10 minutes | **9.7 %** | 9.7 % |
| 20 minutes | **27.7 %** | 27.7 % |
| 30 minutes | **45.9 %** | 45.9 % |

Recorded sites (`recorded.sites`): BM, 8.3 km/h recorded against 11.7 km/h on the map over 62.5 m, delta 8.0 s; INT, 9.1 against
14.5 km/h over 89.2 m, delta 13.1 s. Points whose route passes a site: 7 132 and 6 640 (`points_changed_per_site`).

Live reach check (`evidence/reach/live/live_reach_check.json`, sha256 `cbaf254a…`, 2026-10-11, local app): 11 of 11 on 1440×900 and
390×844: off by default; a tap draws the three nearest hospitals' 10/20/30-minute polygons (server 12.9 s and 10 s); the thesis
numbers above are shown unchanged beside the live card; toggling off removes it; no page errors.

## The finding

At map speeds, less than half of Dhaka's grid (45.9 %) is within 30 minutes of a hospital with an emergency department, and under a
tenth (9.7 %) within 10 minutes. The study measures reach; it does not test causes (`README.md:134`). The live reach shows the same
engine answering for any tapped point, computed now, in about 8-13 s because the routing server is in Mumbai.

## Honest limits

- Map speeds, not live traffic (`valhalla.py:27`); the morning peak in Dhaka is far slower, so these shares are optimistic.
- **The recorded variant equals the map variant** (CODE_MAP known gap 6): the two sites' corrections are 8.0 s and 13.1 s on
  62.5 m and 89.2 m stretches, so no grid point crosses a 10, 20 or 30-minute line although about 7 000 points pass each site. This
  is explained here and in CODE_MAP, not yet in the results file ("Not analysed", `README.md:134`).
- Hospitals are those OpenStreetMap tags `emergency=yes` (37 of 477); the tag's completeness in Dhaka is not checked.
- The reach table is a saved build; only "nearest hospitals", one hospital's isochrone and the step-K live reach are computed live.
- Valhalla is pinned by image tag, not digest; the recorded variant depends on two DhaTraX sites only.
- No make target for the build (STRENGTH_AUDIT f); the live reach is checked on the local app, and on the hosted app only after the
  next deploy.
