#!/usr/bin/env python3
"""Bootstrap one FedGTP process with the impairment wrapper installed, then hand over to upstream.

This exists so that the official repository is executed EXACTLY as its authors wrote it. We do not
patch their files, we do not vendor their code, and `git status` inside the pinned clone stays
clean. All this does is:

    1. install the transport wrapper (src/pipeline/federated/v2x_impairment.py),
    2. `runpy` the upstream entry point with the argv it expects,
    3. write the link meter out when the process finishes, however it finishes.

Driven by environment variables so the upstream argv stays untouched:
    DF_UPSTREAM   path to the pinned FedGTP checkout
    DF_SCRIPT     server.py | client.py
    DF_ROLE       server | client
    DF_PROFILE    a key of v2x_impairment.PROFILES
    DF_SEED       impairment RNG seed
    DF_METER_OUT  where to write this process's link meter
"""
from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path

from core.common.paths import REPO
sys.path.insert(0, str(REPO))

from core.ml.forecasting.federated import v2x_impairment  # noqa: E402


def main() -> None:
    upstream = Path(os.environ["DF_UPSTREAM"]).resolve()
    script = upstream / os.environ["DF_SCRIPT"]
    meter_out = Path(os.environ["DF_METER_OUT"])

    os.chdir(upstream)                      # upstream reads config/ and data/ by relative path
    meter = v2x_impairment.install(
        profile=os.environ.get("DF_PROFILE", "ideal"),
        role=os.environ.get("DF_ROLE", "?"),
        seed=int(os.environ.get("DF_SEED", "0")),
        repo_on_path=upstream,
    )
    sys.argv = [str(script)] + sys.argv[1:]
    try:
        runpy.run_path(str(script), run_name="__main__")
    finally:
        meter.dump(meter_out)               # record the link even if the run crashes


if __name__ == "__main__":
    main()
