"""One protocol, every model, on datasets where the future is actually known: the command and import surface
of Protocol B. The code lives in `protocol_b/` (settings, data, baselines, scoring, stages, records, run),
one responsibility per file; this module keeps the command every document names and the names other
modules import.

    python -m core.ml.forecasting.evaluation.evaluate_models --dataset METR-LA --windows 120 --seed 11 --max-nodes 0
    python -m core.ml.forecasting.evaluation.evaluate_models --all
"""
from __future__ import annotations

import sys

from core.ml.forecasting.evaluation.protocol_b.baselines import (build_hist_avg, fit_trees, predict_chronos,  # noqa: F401
                                                             predict_hist_avg, predict_persistence, predict_trees)
from core.ml.forecasting.evaluation.protocol_b.data import free_flow, load, node_index, splits, subsample, windows  # noqa: F401
from core.ml.forecasting.evaluation.protocol_b.records import key as _key, merge, summary, write  # noqa: F401
from core.ml.forecasting.evaluation.protocol_b.run import evaluate, main  # noqa: F401
from core.ml.forecasting.evaluation.protocol_b.scoring import onset_lead, score  # noqa: F401
from core.ml.forecasting.evaluation.protocol_b.settings import (BIN_MIN, CONGESTION_RATIO, CONTEXT, HORIZONS_MIN,  # noqa: F401
                                                            N_JOBS, OUT, WORKSPACE)
from core.ml.forecasting.evaluation.protocol_b.stages import stage  # noqa: F401

if __name__ == "__main__":
    sys.exit(main())
