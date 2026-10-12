#!/usr/bin/env python3
"""Train the forecasting baselines on an AWS spot GPU — launched and collected from the terminal.

    python -m core.ml.forecasting.training.aws_train --plan                 # show what would run and what it costs
    python -m core.ml.forecasting.training.aws_train --launch               # start the spot GPU job
    python -m core.ml.forecasting.training.aws_train --status               # is it running / done?
    python -m core.ml.forecasting.training.aws_train --collect              # pull results into results/forecasting/
    python -m core.ml.forecasting.training.aws_train --terminate            # stop it now
    python -m core.ml.forecasting.training.aws_train --launch --city-dataset user:<id> --models STID --epochs 100
    python -m core.ml.forecasting.training.aws_train --collect-city city-<name>

Why this exists: project policy is that no model is trained on the laptop, and the Colab path needs
a human to press Run all. This path needs neither — the job runs on a spot GPU, uploads its results
to S3 and terminates itself.

Safety, because this spends real credit:
  * spot g5.xlarge (1x A10G, 4 vCPU) — the smallest GPU that trains these models comfortably
  * `--instance-initiated-shutdown-behavior terminate` and the job script ends with `shutdown -h now`,
    so a finished OR crashed job stops billing immediately
  * a hard watchdog kills the instance after --max-hours no matter what
  * spot type "one-time": if AWS reclaims it, it terminates rather than relaunching silently
  * --launch refuses to start a second instance while one is already tagged running

The work lives in core.ml.forecasting.training.aws (settings, scripts, ec2, benchmark, report, city, cli);
this module is the import surface and the entry point.
"""
from __future__ import annotations

import sys

from core.ml.forecasting.training.aws.benchmark import collect, collect_checkpoints, launch, plan, status, terminate  # noqa: F401
from core.ml.forecasting.training.aws.city import city_collect, city_job_name, city_launch, city_poll, city_terminate  # noqa: F401
from core.ml.forecasting.training.aws.cli import main as _main
from core.ml.forecasting.training.aws.ec2 import aws, run_instance as _run_instance, running_instances as _running  # noqa: F401
from core.ml.forecasting.training.aws.report import PUB, parse_logs, write_benchmark  # noqa: F401
from core.ml.forecasting.training.aws.scripts import CITY_SCRIPT, FED_SCRIPT, JOB_SCRIPT, OPENCITY_SCRIPT, render  # noqa: F401
from core.ml.forecasting.training.aws.settings import AMI, BASICTS_SHA, BUCKET, JOB, OPENCITY_SHA, REGION, RESULTS  # noqa: F401


def running_instances(job: str = JOB) -> list[dict]:
    """Instances tagged with a job; the benchmark job when none is named."""
    return _running(job)


def main() -> int:
    return _main(__doc__)


if __name__ == "__main__":
    sys.exit(main())
