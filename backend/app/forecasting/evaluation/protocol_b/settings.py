"""The constants of Protocol B, and the thread bound every stage needs before torch or sklearn load."""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Bound the thread pools BEFORE torch or sklearn are imported. Left unbounded, sklearn's joblib workers
# (n_jobs=-1) and torch's intra-op pool deadlock on this machine: the process sits at 0 % CPU forever
# after the Chronos weights load. Diagnosed by finding an idle process an hour in.
for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_v, "4")
N_JOBS = 4

from app.paths import REPO  # noqa: E402

sys.path.insert(0, str(REPO))
OUT = REPO / "results/forecasting"
WORKSPACE = Path.home() / ".dhakaflow/upstream"

HORIZONS_MIN = (5, 15, 30, 60)
BIN_MIN = 5
CONTEXT = 96                # 8 hours; enough for Chronos, cheap for the trees
CONGESTION_RATIO = 0.6      # of the node's own free-flow (85th pct of TRAIN observed)
STEPS = max(HORIZONS_MIN) // BIN_MIN
