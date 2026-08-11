# Bologna/Acosta re-run record (2026-08-11)

The sibling `manifest.txt` in this folder is from the FIRST attempt, which
failed with exit 127 before SUMO started because `/usr/bin/time` does not exist
in the Colab image (defect in OUR wrapper script; fixed in
`scripts/run_bologna_unmodified.sh` and logged in
`resources/HANDOFF_MERGE_LOG.md`).

The successful re-run was executed in the same Colab session and its outputs
were verified on screen and archived to Drive
(`DhakaFlow-Nexus-Data/Lab01_SUMO/evidence_lab01.zip`, 21:49 version, and
`.../bologna_unmodified/` with full stdout/stderr logs). Values observed from
the run's manifest:

    repo_sha=00f6eb479a9dc0fbaeb731495c11d48d7a9661d3   (pinned DLR-TS/sumo-scenarios)
    sumo_version=Eclipse SUMO sumo 1.27.1
    config=/content/dhakaflow_upstreams/lab01/sumo-scenarios/bologna/acosta/run.sumocfg
    exit_code=0

Upstream integrity: `git status --porcelain --untracked-files=no` on the pinned
upstream was EMPTY after the run (no tracked file modified; asserted in the
notebook cell, which completed without error). Plain `git status` showed only
untracked files — the outputs the unmodified acosta config itself writes into
the scenario directory. The integrity check in the fixed script now uses the
tracked-files form and records the untracked-output count.

Chrome blocked the automated re-download of the refreshed evidence zip to this
machine; the authoritative copy lives in Drive. SUMO source provenance from the
same session: tag v1_27_1 = SHA 7717f2379d9e314a0c81c5cec748444de06a2a91.
