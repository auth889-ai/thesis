"""BasicTS's masked metrics (Apache-2.0; third_party/SOURCES.md "Forecasting comparison, RQ1"), loaded unchanged from the pinned
checkout. Only its `basicts/metrics` folder is loaded: the package's top level imports the training launcher, which scoring
does not need. A value of 0.0 is a sensor outage (null_val=0.0), as in the METR-LA and PEMS-BAY releases.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

import numpy as np

CHECKOUT = Path.home() / ".dhakaflow/upstream/BasicTS_legacy"
PINNED = "4c3e2d373c647667c2123e1591f2d79c229dfcc6"
HORIZONS_MIN = (15, 30, 60)
BIN_MIN = 5


@lru_cache(maxsize=1)
def basicts_metrics():
    """The checkout's metrics package, after checking it is the pinned commit."""
    head = subprocess.run(["git", "-C", str(CHECKOUT), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    if head != PINNED:
        raise RuntimeError(f"BasicTS checkout is at {head}, not the pinned {PINNED}")
    folder = CHECKOUT / "basicts/metrics"
    spec = importlib.util.spec_from_file_location("basicts_metrics", folder / "__init__.py", submodule_search_locations=[str(folder)])
    mod = importlib.util.module_from_spec(spec)
    sys.modules["basicts_metrics"] = mod
    spec.loader.exec_module(mod)
    return mod


def score(pred: np.ndarray, truth: np.ndarray, horizons_min=HORIZONS_MIN, null_val: float = 0.0) -> dict:
    """pred/truth (W, steps, N) -> {minutes: {mae, rmse, mape_pct}} with BasicTS's masked_mae / masked_rmse / masked_mape."""
    import torch
    m = basicts_metrics()
    out = {}
    for h in horizons_min:
        k = h // BIN_MIN - 1
        if k >= pred.shape[1]:
            continue
        p, y = torch.as_tensor(np.asarray(pred[:, k], dtype="float32")), torch.as_tensor(np.asarray(truth[:, k], dtype="float32"))
        out[h] = {"mae": round(float(m.masked_mae(p, y, null_val)), 4), "rmse": round(float(m.masked_rmse(p, y, null_val)), 4),
                  "mape_pct": round(float(m.masked_mape(p, y, null_val)) * 100, 3)}
    return out
