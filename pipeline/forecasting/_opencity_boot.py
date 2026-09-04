#!/usr/bin/env python3
"""Run OpenCity's own Run.py under a modern NumPy, without editing a line of their source.

OpenCity was written against NumPy 1.x. NumPy 2.0 deleted a handful of pure ALIASES — `np.mat` is
literally `np.asmatrix` under another name, `np.float_` is `np.float64`, and so on. Nothing about
the numerics changed; the names were removed.

Rather than patch the authors' files (which would void the pinned SHA and the upstream-first
guarantee), this restores those aliases on the `numpy` module in this process and then hands over
to their entry point untouched, exactly as `_fedgtp_boot.py` does for the transport wrapper.

Every alias restored here is recorded in `SHIMS` and reported in the run log, so the compatibility
layer is auditable rather than invisible. If a future failure is anything other than a removed
alias — a real behavioural difference — it will surface as an error here instead of being silently
smoothed over, which is the intended behaviour.

    DF_OC_ARGS is not used; argv is passed straight through.
"""
from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path

import numpy as np

# name on numpy -> the modern object it was an alias for
SHIMS = {
    "mat": "asmatrix",
    "float_": "float64",
    "int_": "int64",
    "complex_": "complex128",
    "unicode_": "str_",
    "NaN": "nan",
    "Inf": "inf",
    "infty": "inf",
}


def install_torch_cpu_load() -> str:
    """Released weights were saved on CUDA; this machine may have none.

    Upstream calls `torch.load(path)` with no `map_location`, which raises on a CPU-only host —
    the error message itself prescribes `map_location=torch.device('cpu')`. This defaults that
    argument when, and only when, CUDA is genuinely unavailable. It changes where tensors are
    placed, never their values, and does nothing at all on a GPU host.
    """
    import torch
    if torch.cuda.is_available():
        return ""
    original = torch.load

    def load(*args, **kwargs):
        kwargs.setdefault("map_location", torch.device("cpu"))
        return original(*args, **kwargs)

    torch.load = load
    return "torch.load(map_location='cpu') [no CUDA on this host]"


def install() -> list[str]:
    restored = []
    for old, new in SHIMS.items():
        if not hasattr(np, old) and hasattr(np, new):
            setattr(np, old, getattr(np, new))
            restored.append(f"np.{old} -> np.{new}")
    return restored


def install_generic_dataset() -> str:
    """Let OpenCity's loader accept a dataset of OURS, whole, with its real clock.

    `lib.data_process.load_st_dataset` dispatches on the dataset NAME; its final branch is not
    generic but a hard-coded two-month slice (`[288*60 : 288*121]`) for one particular corpus, so
    any array shorter than 17,280 steps arrives empty. Names beginning with `DF_` are routed here
    instead: the array is used whole, NaN becomes 0 (their missing-value convention), and the
    time features are produced by THEIR `time_add`, started at the real slot-of-day and weekday of
    our first sample (DF_OC_DAY_START, DF_OC_WEEK_START) rather than at an assumed midnight.
    Nothing else in their pipeline is touched, and every other dataset name goes to their code
    exactly as before.
    """
    try:
        from lib import data_process as dp
    except ImportError:
        return ""
    original = dp.load_st_dataset

    def load_st_dataset(dataset, args):
        if not str(dataset).startswith("DF_"):
            return original(dataset, args)
        data_path = os.path.join(f"../data/{dataset}/{dataset}.npz")
        data = np.load(data_path)["data"]
        data[np.isnan(data)] = 0
        interval, week_day = 5, 7
        args.interval, args.week_day = interval, week_day
        day_start = int(os.environ.get("DF_OC_DAY_START", "0"))
        week_start = int(os.environ.get("DF_OC_WEEK_START", "7"))
        day_data, week_data, _holiday = dp.time_add(data, week_start, interval=interval,
                                                    weekday_only=False, holiday_list=None,
                                                    day_start=day_start)
        data = np.expand_dims(data, axis=-1)
        day_data = np.expand_dims(day_data, axis=-1).astype(int)
        week_data = np.expand_dims(week_data, axis=-1).astype(int)
        data = np.concatenate([data, day_data, week_data], axis=-1)
        print("Load %s Dataset shaped: " % dataset, data.shape, data[..., 0:1].max(),
              data[..., 0:1].min(), data[..., 0:1].mean(), np.median(data[..., 0:1]), data.dtype)
        return data

    dp.load_st_dataset = load_st_dataset
    return "lib.data_process.load_st_dataset: DF_* names load whole, with their own time_add"


def main() -> None:
    restored = install()
    cpu = install_torch_cpu_load()
    if cpu:
        restored.append(cpu)
    if restored:
        print(f"[opencity-boot] compatibility shims: {', '.join(restored)}", flush=True)
    target = Path(os.environ["DF_OC_SCRIPT"]).resolve()
    os.chdir(target.parent)                 # Run.py reads ../conf and ../data by relative path
    # `python Run.py` puts model/ on sys.path[0]; runpy does not, and Model.py imports its
    # architectures as top-level packages (`from OpenCity.OpenCity import OpenCity`). Put the
    # script's own directory first, and the repo root after it for `lib.*`.
    sys.path.insert(0, str(target.parent))
    sys.path.insert(1, str(target.parent.parent))
    generic = install_generic_dataset()
    if generic:
        print(f"[opencity-boot] compatibility shim: {generic}", flush=True)
    sys.argv = [str(target)] + sys.argv[1:]
    runpy.run_path(str(target), run_name="__main__")


if __name__ == "__main__":
    main()
