# core/common — shared foundations: cities, data, labels, paths

What every research area and the web app share:
- a city as one config file;
- the datasets and recorded data;
- the reality labels and tags that travel with every number;
- provenance, units and typed records;
- the subsystem interfaces.

Nothing here names a city. Dhaka, Los Angeles and Berlin are config files in `config/cities/`.

## Papers and official repositories
`core/common` implements no paper's method. The data sources it reads, from `third_party/SOURCES.md`:

| Source | Version | Licence |
|---|---|---|
| DhaTraX: Roy, Arnob, Zenodo, doi:10.5281/zenodo.22157752 | v1.0. Files checked against Zenodo's checksums: `Traffic_Analysis.zip` sha256 `0440ebd9…`; `Homography.zip` `d254fda4…`; trajectories `BM_realXY.zip`, `INT_realXY.zip` | CC BY 4.0 |
| DCRNN sensor locations (Li et al., ICLR 2018) | commit `602afd9d767d3aa1c9b3eac51710d6aeee12c227` | MIT |
| OpenStreetMap through the Overpass API | `osm_base` date recorded per file | ODbL 1.0 |
| Overture Maps, divisions theme (city search, `data/city_search.py`) | release looked up at run time; `2026-09-23.1` used 2026-10-05 | ODbL ("© OpenStreetMap contributors, Overture Maps Foundation") |

## Which file implements which part
| File / folder | Part |
|---|---|
| `data/city_config.py`, `data/city_spec.py`, `city.py` | A city as one tracked file (`config/cities/<city_id>.yaml`), and what it is allowed to claim. |
| `data/city_search.py`, `data/city_builds.py`, `data/cities.py` | Adding a city: find it, write its config, build it one at a time. |
| `data/city_graph.py`, `data/city_corridors.py`, `data/city_datasets.py` | Any city's road graph, observation corridors derived from it, and one interface to its sensor data. |
| `data/recorded/dhatrax.py`, `data/recorded/replay.py` | DhaTraX as published: speeds, class mix, trajectories, and the replay of recorded vehicles (labelled "replay, not live"). |
| `data/real_speeds.py` | Real road speeds or nothing: probe cells (at least 3 phones), recorded datasets kept apart from the present, and no gap filled. |
| `data/station_matching.py` | Matches the published METR-LA stations in the Los Angeles box to road sections. |
| `data/researcher.py` | The researcher's own consented trips (one device, hashed id). |
| `data/live_providers/` | Live road providers. Amazon Location where it answers; no Google API is called. |
| `reality.py`, `tag.py`, `provenance.py` | Reality labels, the real / simulated / forecast tag on every value, and provenance records. |
| `units.py`, `types.py`, `schemas.py` | One unit per quantity, shared records, and the API's response contracts. |
| `interfaces/` | Contracts for forecasting, routing, control, safety, perception, NLP and simulation. |
| `paths.py`, `evidence_paths.py`, `settings.py`, `credentials.py` | Workspace and evidence locations; default city and time zone from the environment; keys read from `.env` on the server only. |

## Substitutions and why
- **A recorded reading is never mixed into the present.** `real_speeds.recorded()` is separate from `read()`, so a recorded speed cannot become a travel time or a departure.
- **Probe readings need 3 or more distinct phones** (owner's decision, 2026-10-05). The researcher's own device is exempt and shown only on the machine that lists it.

## Tests
| File | What it checks |
|---|---|
| `backend/tests/test_core_boundary.py` | `core/` never imports the web app (`app/`). |
| `backend/tests/city/test_city_layer.py`, `test_city_list.py`, `test_city_home.py` | Any city can exist as software without claiming data it lacks; one bad config cannot take the list down; real speeds or nothing. |
| `backend/tests/test_anti_hardcode.py` | Inputs change outputs; nothing answers with a canned number. |
| `backend/tests/rebuild/test_city_datasets.py`, `test_sensor_map.py` | The dataset interface; published detector ids only. |
| `tests/platform/test_interfaces.py` | Interface conformance. |

## Results
None of its own. It records where every result came from: `evidence/cities/<city_id>/build.json` and `evidence/recorded/`.
