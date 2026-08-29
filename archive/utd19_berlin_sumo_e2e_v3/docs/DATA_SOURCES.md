# Public sources encoded in the project

## UTD19

- Landing DOI: `10.3929/ethz-b-000437802`
- ETH item UUID: `bfb14ee7-82c8-4357-a293-3bf18d8f93f9`
- Files are discovered from the ETH Research Collection DSpace REST endpoint rather than hard-coding unstable bitstream UUIDs.

## Berlin traffic detection

- Catalog: `https://daten.berlin.de/datensaetze/verkehrsdetektion-berlin`
- Public archive browser: `https://api.viz.berlin.de/daten/verkehrsdetektion`
- Azure public container discovered from the Berlin archive's official open-source browser: `https://mdhopendata.blob.core.windows.net/verkehrsdetektion/`
- Locations: `https://api.viz.berlin.de/daten/verkehrsdetektion/teu_standorte.json`
- The historical archive was revised in 2025. V3 saves the exact downloaded blob names, ETags, sizes and timestamps.

## OpenStreetMap

- Default Berlin extract: `https://download.geofabrik.de/europe/germany/berlin-latest.osm.pbf`
- V3 records checksum and download timestamp because the paper's exact OSM snapshot is unavailable.

## SUMO

- Installed through `eclipse-sumo` and uses official `netconvert`, `duarouter`, `randomTrips.py`, and `routeSampler.py`.
