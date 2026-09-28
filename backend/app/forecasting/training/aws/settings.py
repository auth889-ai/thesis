"""Where the jobs run and where their results land."""
from __future__ import annotations

from app.paths import REPO

BUCKET = "dhakaflow-train-915644996102"
REGION = "us-east-1"
# Deep Learning OSS Nvidia Driver AMI GPU **PyTorch** (AL2023). The *Base* AMI ships drivers but no
# framework: a pip-installed torch there fails with `libcudnn.so.9: cannot open shared object file`,
# and the system python3.9 has a numpy/pytables ABI clash that breaks the data prep. This AMI carries
# a working conda env (`source activate pytorch`) with matched torch + CUDA + cuDNN.
AMI = "ami-001972c501ec6b965"          # PyTorch 2.9 (AL2023) 20260829
BASICTS_SHA = "4c3e2d373c647667c2123e1591f2d79c229dfcc6"
OPENCITY_SHA = "eca64c9d9c65ff803d0f9d02c65e2544a0d2e96f"
JOB = "predict-baselines"              # the benchmark job; city jobs get their own name so each dataset keeps its own S3 space
RESULTS = REPO / "results/forecasting"
