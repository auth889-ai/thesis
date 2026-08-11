# DATA_SPEC — Lab 02 (Dhaka OSM)

Status: PRE-ACQUISITION for the real extract; `[RUN]` fields are filled from the
Colab manifests after execution. The pipeline itself is fully validated on a
synthetic tiny-OSM fixture (tests/integration).

## Source

- **OpenStreetMap** via the official **Overpass API**
  (`https://overpass-api.de/api/interpreter`), license ODbL 1.0.
- Query: all `way["highway"]` + referenced nodes within the pre-registered bbox
  (METHOD_SPEC); exact query string stored in `osm_manifest.json`.
- Recorded per acquisition: UTC timestamp, endpoint, query, bytes, sha256
  `[RUN]`. No API key required.

## Region

Full: S 23.723, W 90.372, N 23.762, E 90.408 (central Dhaka; Farmgate, Karwan
Bazar, Bangla Motor, Shahbagh, Sonargaon area). Smoke: inner box
S 23.738, W 90.385, N 23.752, E 90.400. Selection criteria: METHOD_SPEC.

## Files & storage

| Artifact | Location | Notes |
|---|---|---|
| Raw `.osm` extract | Drive `DhakaFlow-Nexus-Data/Lab02_DhakaOSM/<exp>/osm/` | size `[RUN]`; sha256 in manifest |
| `osm_manifest.json` | git `outputs/manifests/` (copied from run) | provenance record |
| `dhaka.net.xml` | Drive + git if reasonably small (`[RUN]` decision by size) | sha256 recorded |
| `netconvert.log` + classified warnings | Drive; counts in git gate record | validation artifact |
| Validation JSONs, route/demand records, metrics, figures | git `outputs/` (lightweight) | |
| Full sim outputs (tripinfo/summary) | Drive | |

## Known data-quality expectations (to verify, not assume)

- `lanes=` tag coverage in central Dhaka is partial → defaulted lane counts are
  itemized per road class `[RUN]`.
- `highway=traffic_signals` mapping is incomplete relative to reality → TLS
  census reports *mapped* signals only; missing real-world signals are a
  documented limitation for the calibration labs.
- Expect netconvert to prune isolated fragments (count reported `[RUN]`).
