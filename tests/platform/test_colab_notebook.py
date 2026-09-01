from __future__ import annotations

import json
from pathlib import Path


def test_colab_notebook_uses_legacy_basicts_and_one_pair_default():
    nb = json.loads(Path("notebooks/Predict_BasicTS_Colab.ipynb").read_text())
    source = "\n".join("".join(cell.get("source", "")) for cell in nb["cells"])

    assert "4c3e2d373c647667c2123e1591f2d79c229dfcc6" in source
    assert "TARGET_MODEL = 'STID'" in source
    assert "TARGET_DATASET = 'METR-LA'" in source
    assert "RUN_ALL_READY_PAIRS = False" in source
    assert "DCRNN_DRIVE_FOLDER_ID = '10FOTa6HXPqX8Pf5WRoRwcFnW9BrNZEIX'" in source
    assert "DATASETS" not in source
