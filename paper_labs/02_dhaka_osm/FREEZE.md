# Lab 02 — FREEZE RECORD

**LAB02 = PASS · LAB02_FROZEN = TRUE** · user approval **2026-08-14**.

## Freeze baseline (two commits)

| Role | Commit | Contents |
|---|---|---|
| `SCIENTIFIC_EXECUTION_COMMIT` | `6936ea9` | Measured region selection (C1–C8 over R1–R5), dual-construction validation (Branch A OSMnx / Branch B netconvert), X1–X12 cross-validation, seeded demand run, live-reference foundation, figures |
| `RESOURCE_TRACEABILITY_COMMIT` | `c852e64` | `RESOURCE_MANIFEST.md` / `.yaml`, `docs/MASTER_RESOURCE_INDEX.md` |

## Frozen evidence baseline

- OSM snapshot `outputs/lab02_candidates/R1/R1.osm` — sha256
  `d854b26a8bb014ba123e870f560cfca3562307a0a74eca3b2188d57c48916654`,
  1 626 102 bytes, Overpass, ODbL 1.0, downloaded 2026-08-13T12:09:32Z.
- SUMO network `dhaka_r1.net.xml` — sha256
  `06194df039740fa2ceb0bcb2c438444efd755f26e0f863327f0e1d6524775dcb`,
  17 176 962 bytes.
- All machine-readable evidence under `results/lab02_v2/` and
  `results/candidates/`.
- `LIVE_REFERENCE = READY_NOT_EXECUTED` (user DECISION 1: no Google Maps Content
  persisted anywhere).

## Freeze rule

Do **not** rerun, redesign, extend, or cosmetically modify Lab 02. The only
admissible reason to touch it is a **genuine defect revealed by a future
integration test**; such a change must be recorded here with the failing test
and a new commit pair.

Capability graduation (what moves into `dhakaflow/` and what explicitly does
not) is recorded in `docs/GRADUATION_MAP.md` § "Lab 02".
