# Lab 00 — UTD19 Traffic Science Foundation

**DhakaFlow Nexus** paper lab.
Paper: Loder, Ambühl, Menendez, Axhausen (2019), *Understanding traffic capacity
of urban networks*, Scientific Reports 9:16283.

**Classification: Independent paper-faithful reconstruction; this is not the
authors' official analysis code.** (`upstream/author_vignette/` = the authors' README-only
dataset vignette repo, pinned in `upstream/author_vignette/UPSTREAM.txt`.)

## Layout

| Path | Content |
|---|---|
| `PAPER_SUMMARY.md` | teaching-first explanation of the paper (flow → MFD → critical point) |
| `METHOD_SPEC.md` | extracted method, every item tagged PUBLISHED / INFERRED / ASSUMED / UNKNOWN |
| `DATA_SPEC.md` | real UTD19 files, schemas, 41-vs-40-city scope issue, validation rules V1–V10 |
| `ASSUMPTIONS.md` | four-section assumption ledger incl. post-audit relaxations |
| `paper/` | full text (JATS XML + extracted markdown) |
| `notebooks/Lab00_UTD19_Colab.ipynb` | the smoke-test experiment (runs on Google Colab, data in Google Drive) |
| `src/build_notebook.py` | deterministic builder for the notebook (edit this, then rebuild) |
| `tests/test_notebook_sql_synthetic.py` | local synthetic test of the notebook's logic (~2k fake rows, planted defects) |
| `outputs/` | small artifacts copied back from the Colab run (audit CSVs, figures, manifest) |

## Compute/storage policy

Local PC = source of truth for code/docs/small artifacts only.
Google Colab = all heavy computation. Google Drive
(`MyDrive/DhakaFlow-Nexus-Data/Lab00_UTD19/`) = raw UTD19 (~7 GB) and heavy
intermediates. Nothing large enters git (see repo `.gitignore`).

## Reproduce

1. Local check: `python3 tests/test_notebook_sql_synthetic.py`
2. Rebuild notebook after edits: `python3 src/build_notebook.py`
3. Open `notebooks/Lab00_UTD19_Colab.ipynb` in Google Colab → Runtime → Run all.
4. Copy `repo_artifacts_lab00.zip` from Drive back into `outputs/`.

Smoke-test city: **torino** (selection criteria + documented relaxation in
DATA_SPEC §7 and ASSUMPTIONS.md → MODIFIED_BY_US).
