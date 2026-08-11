# Claude Handoff Instructions

This is a **merge-ready Lab 01 candidate**, not an authoritative PASS result.

## Merge target

Merge/adapt into the existing active thesis repository:

`paper_labs/01_sumo_foundation/`

Do **not** create a nested DhakaFlow project.

## Required audit before execution

1. Compare this package against the project's current `MASTER_*` documents and architecture rules.
2. Verify the two upstream SHAs and official provenance. Keep the pinned SHAs by default; update only with a documented reason.
3. Inspect SUMO XML/API compatibility against the actual installed SUMO version.
4. Do not install SUMO on the Mac; local checks must remain static/tiny and SUMO-free.
5. Install the complete pinned runtime in Colab using `scripts/install_colab.sh`, then run Colab smoke first.
6. If any network/controller/API issue appears, modify **our wrapper code**, not official upstream.
7. Run full 5-seed matrix.
8. Run Bologna/Acosta unmodified from pinned official upstream.
9. Independently recompute at least one trip metric and one queue metric.
10. Copy lightweight evidence into Git and leave heavy raw output in Drive.
11. Complete `REPRODUCTION_REPORT.md` using real output only.

## Scientific review points

- Confirm that zero-duration phase termination actually preserves the intended yellow transition in the pinned SUMO version.
- Confirm controlled link indices in `network.net.xml` match `GGrr / yyrr / rrGG / rryy`.
- Check that queue-actuated and max-pressure controllers cannot violate min/max-green rules.
- If `waitingCount` semantics differ in the installed version, rename the stop metric rather than mislabel it.
- Treat spillback as a proxy unless a proper detector-based jam-length metric is added.
- Do not claim the unit max-pressure implementation is a full Varaiya network reproduction.

## Final gate

Return exactly:

`LAB 01 STATUS: PASS / PARTIAL / FAIL`

with commands, versions, upstream SHAs, metrics, tests, evidence paths and limitations.

Do not start Lab 02 without explicit user approval.


## Colab-only installation rule

The official SUMO runtime and all simulation dependencies must be installed in Google Colab, not on the user's Mac. Use `requirements-colab.txt`, `scripts/install_colab.sh`, and `COLAB_ONLY_RUNBOOK.md`. The pinned simulator release is SUMO 1.27.1. The official source tag `v1_27_1` is for provenance/API inspection; official scenario code is fetched at the pinned commit. Claude may change OUR handoff code after extraction if real execution shows an incompatibility, but must document every such modification.
