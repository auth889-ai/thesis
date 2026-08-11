# Read this first — Colab-only execution package

This ZIP contains **only the next active lab**: `01_sumo_foundation` (the second lab after Lab 00).

## Execution policy

- **Do not install SUMO or heavy experiment dependencies on the Mac.**
- Claude may extract, audit, edit, and merge the code/docs on the Mac, but all SUMO installation and real simulation execution must happen in **Google Colab**.
- Heavy/full outputs go to Google Drive. Git/local keeps source, configs, tests, reports, and lightweight evidence.
- The supplied Colab notebook installs a pinned SUMO release and Python dependencies inside the temporary Colab runtime.

## What to give Claude

Give Claude this ZIP and the prompt in `CLAUDE_PROMPT_TO_USE.txt`.

Claude should:
1. extract the ZIP;
2. read `01_sumo_foundation/CLAUDE_HANDOFF.md` and `COLAB_ONLY_RUNBOOK.md`;
3. audit and modify the **extracted candidate folder** when needed;
4. merge/adapt the final audited lab into the active thesis repo at `paper_labs/01_sumo_foundation/`;
5. execute the real lab in Colab;
6. never create a second/nested DhakaFlow project.

The ZIP contains all DhakaFlow-authored Lab 01 code, configs, tests, notebook, installation automation, simulation specification, and resource manifests. Official SUMO/scenario repositories are **not vendored into the ZIP**; the Colab scripts fetch pinned official sources so provenance, versioning, and licensing stay explicit.
