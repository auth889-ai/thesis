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
    sys.argv = [str(target)] + sys.argv[1:]
    runpy.run_path(str(target), run_name="__main__")


if __name__ == "__main__":
    main()
