# Handoff merge log — 2026-08-11

Source: `paper_labs/DhakaFlow_Lab01_SUMO_Foundation_Handoff/` (audited, merged,
then removed). This is the ONLY active Lab 01; the older scaffold copy stays
archived read-only in `reference_scaffold/DhakaFlow-Nexus-Labs-00-01/` and was
verified to contain nothing unique (its RESOURCES.md links are a subset of
`resources/RESOURCE_MANIFEST.md`).

## Audit results

- All 26 handoff files reviewed. Local SUMO-free unit tests: **4 passed** (also
  re-run after merge in the active location).
- `eclipse-sumo==1.27.1` pin verified against PyPI on 2026-08-11: it exists and
  is the **latest** release. Upstream lock (`resources/UPSTREAM_LOCK.json`)
  kept unchanged: SUMO tag `v1_27_1`; DLR-TS/sumo-scenarios pinned SHA
  `00f6eb47…` with the Bologna/Acosta clean-tree guard in
  `scripts/run_bologna_unmodified.sh`.
- Controller design reviewed: yellow transitions are preserved by terminating
  green via `setPhaseDuration(0)` against a static program whose phase list
  explicitly contains `yyrr`/`rryy` (asserted by `tests/unit/test_scenario_xml.py`);
  min/max-green enforced in both actuated and max-pressure controllers;
  `waitingCount` reported as `avg_stops_proxy`; spillback reported as a proxy.

## Modifications (MODIFIED_BY_US)

1. `notebooks/Lab01_SUMO_Foundation_Colab.ipynb` cell 3: original assumed a repo
   checkout at `/content/DhakaFlow-Nexus/...`. The thesis repo is local-only, so
   the cell now bootstraps the lab from
   `MyDrive/DhakaFlow-Nexus-Data/Lab01_SUMO/lab01_source.zip` when the checkout
   is absent.
2. Added `scripts/make_colab_zip.sh` — builds that source zip (44 KB, excludes
   outputs/logs/caches/generated networks).
3. Handoff wrapper docs preserved in `resources/handoff_meta/`.

## Rejected

- Nothing. No handoff file was scientifically wrong; the only defect found was
  the missing repo-into-Colab mechanism (fixed above).
