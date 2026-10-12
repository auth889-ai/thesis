# core/safety — crash detection, hospitals, ambulance reach

The phone-side safety research: crash detection with the WreckWatch rule (**RQ6**), the hospitals of a city, and how far
an ambulance reaches from them (**supporting measurement**). The web app's Emergency page and the map app's hospital
sheet import from here; nothing here imports the web app.

## Papers
- **WreckWatch**: White, Thompson, Turner, Dougherty, Schmidt, "WreckWatch: Automatic Traffic Accident Detection and
  Notification with Smartphones", *Mobile Networks and Applications* 16(3), 2011. We read it for its rule; no code exists.
- Ambulance reach has no paper. It uses the Valhalla engine's APIs; the request shape and colours come from GIS•OPS's valhalla-app.

## Official repositories, versions, licences
All from `third_party/SOURCES.md`, sections "Crash SOS" and "Ambulance reach, nearest hospitals, map matching".

| Source | Version | Licence |
|---|---|---|
| WreckWatch (paper, author copy) | journal version, 2011, read 2026-10-06 | a paper (Springer); nothing copied |
| Valhalla engine (`/isochrone`, `/sources_to_targets`, `/trace_attributes`) | 3.9.0 | MIT |
| Valhalla web app (GIS•OPS) | `439ea98f184f8821a7e9146a48af1f383a40ce05` | MIT; request shape and colours only, no code |
| OpenStreetMap hospitals through Overpass | `osm_base` date recorded in each file (Dhaka: 2026-10-06T14:33:00Z) | ODbL, © OpenStreetMap contributors |

## Which file implements which part
| File | Part |
|---|---|
| `sos.py` | WreckWatch's rule: an alarm when the acceleration magnitude exceeds 4 g and, when a speed is known, the phone moves faster than 15 mph (24.1 km/h). Also the labelled SYNTHETIC traces (seed 7, 50 Hz, 30 s), the countdown, and the alert path in TEST mode only. |
| `hospitals.py` | One Overpass query per city for `amenity=hospital`, kept in `data/cities/<city>/hospitals.json` with its query, date and sha256. Also drops places not for patients (e.g. animal hospitals) and merges duplicates by name. |
| `reach.py` | The 10/20/30-minute reach from every hospital: Valhalla's time matrix (sliced under the server's 2 500-pair limit), the nearest hospitals to a point, and our recorded-speed re-timing (a path from hospital H to point T that passes recorded site S is re-timed when t(H,S)+t(S,T) ≤ t(H,T)+30 s). |

## Substitutions and why
- **One WreckWatch signal, not two.** The paper's second signal, a loud acoustic event, is not implemented.
- **The speed floor applies only when a speed is known.** Each result row says whether it was applied.
- **Traces are SYNTHETIC.** We have no recorded crashes. The three traces (normal ride, hard brake, crash-like jolt) show what the rule does; they say nothing about how often real crashes or false alarms occur.
- **Valhalla in place of a hosted routing API.** Our own server, so reach uses the same graph as the app's routes. Its "map speeds" are OpenStreetMap defaults, not measured traffic.
- **Recorded-speed re-timing is our own method** on top of Valhalla's matrix (stated beside the result on the Research page).

## Tests
| File | What it checks |
|---|---|
| `backend/tests/emergency/test_sos.py` | The WreckWatch rule on the synthetic traces; deterministic traces; the plain sentence is built from the results table; the alert path stays in TEST mode. |
| `backend/tests/emergency/test_reach.py` | The grid; the matrix decomposition (a path through a recorded site is delayed by exactly the stretch's delta; one that does not pass it is unchanged); honest refusals. |
| `backend/tests/emergency/test_nearest_people_only.py` | Places not for patients (e.g. "Vet-RX", an animal hospital) are never offered as a nearest hospital. |

## Results
- **RQ6, crash detection:** `evidence/sos/results.json` (rule, generator, one row per trace, each with its sha256); traces in `research/sos/`. Every row is labelled SYNTHETIC.
- **Ambulance reach, Dhaka:** `results/reach/dhaka/summary.json` (label "MAP SPEEDS"). Its `plain.map_pct` gives the share of the 2 610 grid points within 10, 20 and 30 minutes: 9.7 %, 27.7 % and 45.9 %. Evidence: `evidence/reach/`.
- Hospitals list for Dhaka: `data/cities/dhaka/hospitals.json`, `evidence/reach/dhaka/hospitals.json`.
