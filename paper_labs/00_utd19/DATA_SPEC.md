# DATA_SPEC — UTD19 dataset (Lab 00)

**Status: PRE-AUDIT.** Schema facts below come from (a) the ETH Research
Collection record and (b) column handling verified against the *real* files by
the earlier `utd19_berlin_sumo_e2e_v3` Colab run (July 2026), whose code bound
all columns BY NAME from real headers. Everything marked `[AUDIT]` must be
confirmed/filled by the Lab 00 Colab audit before this document is final.
No numbers in this file may be invented; `[AUDIT]` means "not yet measured by us".

## 1. Source of record

- Landing page: https://utd19.ethz.ch/ (free registration form; download link sent by e-mail)
- ETH Research Collection item: DOI `10.3929/ethz-b-000437802`,
  UUID `bfb14ee7-82c8-4357-a293-3bf18d8f93f9`
  (files discoverable via DSpace REST API `https://www.research-collection.ethz.ch/server/api`)
- Documentation PDF: bitstream in the same record ("manual")
- **No API key is required.** The ETH REST endpoint served the files to the
  July 2026 Colab run without authentication. Note: on 2026-08-09 the endpoint
  returned "Access Restricted" HTML to a plain curl from the user's local
  network — the Colab notebook must verify access and, if blocked, fall back to
  the utd19.ethz.ch registration route (user action: sign up with
  studyemail953@gmail.com and paste the e-mailed link into the notebook config).

## 2. Files

Real bitstream listing returned by the ETH DSpace API (observed live in the
Lab 00 Colab run, 2026-08-09/10):

| Bitstream name | Canonical name | Size | Format |
|---|---|---|---|
| `utd19_u.csv` | `utd19_u.csv` | 6,978.6 MB | CSV |
| `detectors_public.csv` | `detectors.csv` | 2.6 MB | CSV |
| `links.csv` | `links.csv` | 7.5 MB | CSV |
| `Manual.pdf` | `manual.pdf` | 0.1 MB | PDF |
| `utd19_u.csv.txt`, `detectors_public.csv.txt`, `links.csv.txt` | – | ~0.1 MB each | column descriptions |
| `license.txt`, `mets.xml`, `Manual.pdf.jpg` | – | <0.1 MB | record metadata |

Canonical mapping + sha256 per file recorded in the Drive manifest
(`outputs/manifest/drive_manifest.csv`). `[AUDIT: sha256 values]`

## 3. Verified schemas (bound by name from real headers in the July 2026 run)

### 3.1 `utd19_u.csv`

| Column | Meaning | Units / format | Notes |
|---|---|---|---|
| `day` | observation date | `YYYY-MM-DD` (some cities `DD.MM.YYYY`) | both formats observed in real data |
| `interval` | seconds from midnight, start of interval | s (0–86399) | aggregation interval typically 300 s `[AUDIT: per-city interval table]` |
| `detid` | detector ID | string | joins to `detectors.csv` |
| `flow` | vehicle flow | veh/h **per lane** `[AUDIT: confirm against manual.pdf]` | |
| `occ` | occupancy | fraction 0–1 `[AUDIT: confirm range per city]` | |
| `error` | error flag | blank / flag values `[AUDIT: enumerate values + frequency]` | |
| `city` | city name | lowercase string | |
| `speed` | speed where available | km/h `[AUDIT: which cities report speed]` | missing for many cities |

### 3.2 `detectors.csv`

Columns verified present: `detid`, `length`, `pos`, `fclass`, `road`, `limit`,
`lanes`, `linkid`, `long`, `lat`, `citycode`.
~23,577 rows in the release used by the July 2026 run `[AUDIT: re-verify]`.
Quoting quirk (verified): 3 Toulouse rows contain quoted road names with commas —
CSV readers must pin `quote='"'`.

| Column | Meaning | Units |
|---|---|---|
| `length` | detector segment length | km `[AUDIT: confirm via manual]` |
| `pos` | detector position on link | km |
| `fclass` | OSM functional class | trunk/primary/secondary/tertiary/... |
| `limit` | speed limit | km/h |
| `lanes` | monitored lanes | count |
| `long`, `lat` | WGS84 coordinates | deg |

### 3.3 `links.csv` — `[AUDIT: enumerate columns from real header]`

## 4. Scientific Correction 1 — 41 cities (paper) vs 40 cities (released UTD19)

- The **2019 paper analyzed 41 cities / 107 regional networks** (Introduction ¶5).
- The **public UTD19 release lists 40 cities** (utd19.ethz.ch city list).
- The Data Availability statement explains why: data is available "after
  consultation with those cities where a non-disclosure agreement applies" —
  i.e., at least one analyzed city's data could not be released, and released
  cities may also have reduced date ranges or detector subsets.
- **Consequence for reproducibility:** exact reproduction of the 107-network
  sample statistics (P̄\*, n̄\*, Table 1) from public UTD19 alone is NOT
  guaranteed even in principle. Per-city MFD reconstruction remains feasible for
  released cities. `[AUDIT: which city in the paper's Table-1/acknowledgements
  list is absent from the release — e.g., compare acknowledgements city list
  (includes Duisburg, Melbourne, Tokyo, Toronto, ...) with the released city
  column values.]`
- Mirrored in ASSUMPTIONS.md → PUBLISHED/INFERRED.

## 5. Metadata relationships to verify in audit

- `utd19_u.detid` ⋈ `detectors.detid` (+ city/citycode consistency) — orphan rates both directions `[AUDIT]`
- `detectors.linkid` ⋈ `links` `[AUDIT]`
- Does any released field encode the paper's **regional network membership**?
  `[AUDIT — expected answer: no; if absent, regional partitions are
  UNKNOWN FROM AVAILABLE MATERIAL and our region definitions become MODIFIED_BY_US]`

## 6. Validation rules (implemented in the Colab notebook, §V cells)

Nothing is dropped silently; every rule reports its removal count into
`outputs/audit/validation_report.csv` (small, committed to git).

| Rule | Check |
|---|---|
| V1 timestamp | `day` parses (both formats); `interval` integer in [0, 86399] |
| V2 duplicates | duplicate (city, detid, day, interval) rows |
| V3 missing | NULL/blank in flow, occ; speed missingness reported separately |
| V4 negative flow | flow < 0 impossible |
| V5 occupancy range | occ outside [0, 1] (if data proves scale is 0–100, rule adapts and the finding is documented) |
| V6 speed validity | speed < 0 or > 200 km/h where speed exists |
| V7 flow w/o occupancy | flow > 0 while occ = 0 (paper's "obvious error" example) |
| V8 metadata consistency | measurement detids missing from detectors.csv |
| V9 temporal ordering | per (detid, day): intervals strictly increasing, gap census |
| V10 error flag | census of `error` values; non-blank error rate per city |

## 7. Candidate-city audit table (Scientific Correction 3)

Produced in Colab as `outputs/audit/city_audit.csv` with, per city:
detector count, observation count, date coverage (min/max/day count),
flow/occ/speed availability %, non-blank error rate, missing-value rate,
duplicate rate, median interval length. Selection criteria for the smoke city
(documented before looking at results):

1. speed column present (>50% non-null) — enables later uncalibrated speed checks;
2. moderate size: 10⁶–10⁸ measurement rows — big enough to be meaningful,
   small enough for a smoke run;
3. ≥100 detectors with coordinates and fclass in {trunk, primary, secondary, tertiary};
4. ≥14 days of coverage;
5. low error-flag rate (<10%);
6. tie-break: city that also appears in the paper's Supplementary figures
   (all released cities should) and has a compact spatial extent.

## 8. Storage policy

Raw UTD19 lives ONLY in Google Drive
(`MyDrive/DhakaFlow-Nexus-Data/Lab00_UTD19/raw/`), never in this git repo.
The local repo stores: this spec, the notebook, small audit CSVs, small PNGs,
and `outputs/manifest/drive_manifest.csv` (Drive-relative path, size, sha256,
download timestamp, source URL per file).
