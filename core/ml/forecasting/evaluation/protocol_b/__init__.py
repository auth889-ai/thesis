"""Protocol B: every model on the same contiguous test windows, scored where it matters.

    settings   the constants of the protocol (horizons, context, congestion rule, output folder)
    data       loading a benchmark, the chronological split, free-flow thresholds, contiguous windows
    baselines  persistence, the literature's historical average, the tree models, Chronos-Bolt
    scoring    error by horizon and regime, congestion precision/recall, onset lead
    stages     one model family computed in its own process and saved as predictions
    records    persisted prediction blocks, the comparison record file, cross-seed summary, merge
    run        the evaluation of a dataset end to end, and the command line

`core.ml.forecasting.evaluation.evaluate_models` stays as the command and import surface.
"""
from core.ml.forecasting.evaluation.protocol_b.settings import BIN_MIN, CONGESTION_RATIO, CONTEXT, HORIZONS_MIN, N_JOBS, OUT, WORKSPACE  # noqa: F401
