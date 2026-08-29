# DhakaFlow Nexus — Labs 00–01 Research Package

This package is the **first two labs** of the DhakaFlow Nexus thesis roadmap.

- **Lab 00 — UTD19 Traffic Science Foundation**: real multi-city detector data, network traffic science, MFD, critical point, full released-dataset audit, paper-faithful reconstruction where the released data permits it.
- **Lab 01 — SUMO Foundation**: canonical SUMO paper, official SUMO tutorials, official real-world Bologna/Acosta scenario, TraCI, deterministic signal control baselines, and research-grade metrics.

## Non-negotiable research rule

A successful script is **not** a successful reproduction. Each lab must preserve the distinction between:

1. **Official reproduction** — verified authors' code/scenario.
2. **Paper-faithful reconstruction** — independent implementation from paper/methods.
3. **DhakaFlow original module** — our later adaptation/integration.

## Compute/storage architecture

```text
LOCAL PC / GitHub
  code + notebooks + configs + tests + docs + small figures
              |
              v
GOOGLE COLAB / AWS
  heavy queries + training + simulation sweeps
              |
              v
GOOGLE DRIVE / S3
  raw datasets + large intermediates + checkpoints + large outputs
```

Large UTD19 data must **never** be committed to Git or copied to the local repo.

## Correct order

```text
Lab 00: Traffic science / UTD19
    -> PASS
Lab 01: SUMO / TraCI / official Bologna scenario
    -> PASS
Lab 02 later: Dhaka OSM -> SUMO
    -> ...
```

## Start

1. Copy `.env.example` to `.env` **only on your private machine** if needed. Never commit `.env`.
2. Put large UTD19 files in Google Drive, not inside this repo.
3. Open `paper_labs/00_utd19/notebooks/Lab00_UTD19_Full_Colab.ipynb` in Colab.
4. Run Lab 00 in order. Do not skip the audit gates.
5. Only after Lab 00 passes, open `paper_labs/01_sumo_foundation/notebooks/Lab01_SUMO_Foundation_Colab.ipynb`.

See each lab README and `CLAUDE_RUN_PROMPT.md` for exact handoff instructions.
