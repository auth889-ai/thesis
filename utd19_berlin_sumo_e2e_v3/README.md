# UTD19 → Berlin → SUMO End-to-End Reconstruction

A runnable, transparent reconstruction of the VTC 2024 paper:

> Advanced Traffic Demand Generation in SUMO: ML-based Prediction of Flow Rate based on Real-world Measured Datasets

This is **not the authors' unpublished code**. It implements the published pipeline with official public datasets and SUMO tools while recording every assumption caused by missing implementation details.

## Quick start

1. Open `notebooks/UTD19_Berlin_SUMO_Full_End_to_End.ipynb` in Google Colab.
2. Upload this repository ZIP when prompted.
3. Run `demo`, then `subset`/`full_colab`, and use `full` only on high-memory infrastructure.

CLI:

```bash
bash scripts/install_colab.sh
python -m src.pipeline --config config/subset.yaml
python -m src.pipeline --config config/full.yaml
```

See `README_BANGLA.md`, `docs/PAPER_WALKTHROUGH_BANGLA.md`, and `docs/REPRODUCIBILITY_GAPS.md`.


Validation boundaries are documented in `docs/VALIDATION_STATUS.md`.
