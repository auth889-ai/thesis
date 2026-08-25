#!/usr/bin/env python3
"""Launch one training arm on an EC2 spot GPU with S3 checkpointing.

Design (Phase 2 of docs/SPRINT_140H.md):

* One arm = one spot instance running one job script. The job script is
  uploaded to s3://<bucket>/jobs/<name>/job.sh and is responsible for its own
  resume: on start it MUST look at s3://<bucket>/ckpt/<name>/ and continue
  from the newest checkpoint if present. The launcher guarantees the plumbing,
  the job guarantees resumability — that split keeps the launcher generic.
* User-data starts the job under nohup, syncs ./ckpt and ./logs to S3 every
  5 minutes, and terminates the instance when the job exits (shutdown behavior
  = terminate, so a finished or failed arm stops billing immediately).
* Spot type "one-time": if AWS reclaims the instance, it terminates. Relaunch
  the same arm with the same name — it resumes from the last synced
  checkpoint. `scripts/aws/monitor_arms.py` automates that.
* AMI: AWS Deep Learning Base OSS Nvidia GPU (AL2023) — driver + toolkit
  preinstalled; per-job python deps are the job script's first lines.

Quota reality (checked 2026-08-25): us-east-1 G-spot quota is 8 vCPUs
(= 2 × g5.xlarge or 2 × g4dn.xlarge concurrently) until the pending increase
to 32 is granted; us-west-2 is 0 pending. The launcher fails loudly on
InsufficientInstanceCapacity / MaxSpotInstanceCountExceeded — that is the
quota, not a bug.

Usage:
    python scripts/aws/launch_arm.py --name p1-rtdetr-r18 \
        --job research/perception/jobs/rtdetr_r18.sh \
        [--instance-type g5.xlarge] [--region us-east-1] [--dry-run]
    python scripts/aws/launch_arm.py --list
    python scripts/aws/launch_arm.py --terminate p1-rtdetr-r18
"""
from __future__ import annotations

import argparse
import base64
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BUCKET = "dhakaflow-train-915644996102"
PROFILE_NAME = "dhakaflow-train-profile"
AMI_BY_REGION = {
    # Deep Learning Base OSS Nvidia Driver GPU AMI (AL2023), looked up 2026-08-25.
    "us-east-1": "ami-027de6aaa8774e722",
}
TAG_KEY = "dhakaflow-arm"

USER_DATA_TEMPLATE = """#!/bin/bash
set -x
exec > /var/log/dhakaflow-arm.log 2>&1
ARM="{name}"
S3="s3://{bucket}"
mkdir -p /workspace/ckpt /workspace/logs && cd /workspace
aws s3 cp "$S3/jobs/$ARM/job.sh" job.sh && chmod +x job.sh
# background sync: checkpoints + logs every 5 min
( while true; do
    aws s3 sync /workspace/ckpt "$S3/ckpt/$ARM/" --quiet
    aws s3 sync /workspace/logs "$S3/logs/$ARM/" --quiet
    sleep 300
  done ) &
SYNC_PID=$!
ARM_NAME="$ARM" S3_BASE="$S3" ./job.sh; RC=$?
kill $SYNC_PID
aws s3 sync /workspace/ckpt "$S3/ckpt/$ARM/" --quiet
aws s3 sync /workspace/logs "$S3/logs/$ARM/" --quiet
echo "$RC" | aws s3 cp - "$S3/logs/$ARM/EXIT_CODE"
shutdown -h now
"""


def _env_with_creds() -> dict:
    """Process env + AWS_* lines from dhakaflow/.env (self-contained CLI)."""
    import os
    env = dict(os.environ)
    envf = REPO / "dhakaflow" / ".env"
    if envf.exists():
        for line in envf.read_text().splitlines():
            m = re.match(r"\s*(AWS_[A-Z_]+)\s*=\s*(\S+)", line)
            if m and m.group(1) not in env:
                env[m.group(1)] = m.group(2)
    return env


def sh(cmd: list[str]) -> str:
    return subprocess.run(cmd, check=True, capture_output=True,
                          text=True, env=_env_with_creds()).stdout.strip()


def env_region(default: str = "us-east-1") -> str:
    envf = REPO / "dhakaflow" / ".env"
    if envf.exists():
        m = re.search(r"^AWS_REGION=(\S+)", envf.read_text(), re.M)
        if m:
            return m.group(1)
    return default


def launch(args) -> None:
    region = args.region or env_region()
    ami = AMI_BY_REGION.get(region)
    if not ami:
        sys.exit(f"no AMI pinned for {region} — add it to AMI_BY_REGION "
                 f"(aws ec2 describe-images ... 'Deep Learning Base OSS "
                 f"Nvidia Driver GPU AMI (Amazon Linux 2023)*')")
    job = Path(args.job)
    if not job.exists():
        sys.exit(f"job script not found: {job}")

    print(f"upload job -> s3://{BUCKET}/jobs/{args.name}/job.sh")
    sh(["aws", "s3", "cp", str(job), f"s3://{BUCKET}/jobs/{args.name}/job.sh",
        "--region", region])

    user_data = USER_DATA_TEMPLATE.format(name=args.name, bucket=BUCKET)
    cmd = [
        "aws", "ec2", "run-instances", "--region", region,
        "--image-id", ami,
        "--instance-type", args.instance_type,
        "--iam-instance-profile", f"Name={PROFILE_NAME}",
        "--instance-market-options",
        '{"MarketType":"spot","SpotOptions":{"SpotInstanceType":"one-time",'
        '"InstanceInterruptionBehavior":"terminate"}}',
        "--instance-initiated-shutdown-behavior", "terminate",
        "--block-device-mappings",
        '[{"DeviceName":"/dev/xvda","Ebs":{"VolumeSize":100,'
        '"VolumeType":"gp3","DeleteOnTermination":true}}]',
        "--tag-specifications",
        f'ResourceType=instance,Tags=[{{Key={TAG_KEY},Value={args.name}}}]',
        "--user-data", base64.b64encode(user_data.encode()).decode(),
        "--count", "1",
        "--query", "Instances[0].{id:InstanceId,type:InstanceType,az:Placement.AvailabilityZone}",
        "--output", "json",
    ]
    if args.dry_run:
        cmd.append("--dry-run")
    try:
        print(sh(cmd))
    except subprocess.CalledProcessError as exc:
        err = exc.stderr
        if "DryRunOperation" in err:
            print("DRY RUN OK — permissions and parameters are valid.")
            return
        if "MaxSpotInstanceCountExceeded" in err:
            sys.exit("SPOT QUOTA HIT (8 vCPU until the pending increase lands) "
                     "— wait for a slot or the quota grant.\n" + err)
        sys.exit(err)


def list_arms(region: str) -> None:
    print(sh(["aws", "ec2", "describe-instances", "--region", region,
              "--filters", f"Name=tag-key,Values={TAG_KEY}",
              "Name=instance-state-name,Values=pending,running,stopping",
              "--query",
              "Reservations[].Instances[].{arm:Tags[?Key=='" + TAG_KEY +
              "']|[0].Value,id:InstanceId,type:InstanceType,"
              "state:State.Name,launched:LaunchTime}",
              "--output", "table"]))


def terminate(name: str, region: str) -> None:
    ids = sh(["aws", "ec2", "describe-instances", "--region", region,
              "--filters", f"Name=tag:{TAG_KEY},Values={name}",
              "Name=instance-state-name,Values=pending,running",
              "--query", "Reservations[].Instances[].InstanceId",
              "--output", "text"]).split()
    if not ids:
        print(f"no running instance tagged {name}")
        return
    print(sh(["aws", "ec2", "terminate-instances", "--region", region,
              "--instance-ids", *ids, "--output", "json"]))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--name", help="arm name (job id, checkpoint prefix)")
    ap.add_argument("--job", help="local job script to upload and run")
    ap.add_argument("--instance-type", default="g5.xlarge")
    ap.add_argument("--region", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--terminate", metavar="NAME")
    args = ap.parse_args()

    region = args.region or env_region()
    if args.list:
        list_arms(region)
    elif args.terminate:
        terminate(args.terminate, region)
    elif args.name and args.job:
        launch(args)
    else:
        ap.error("need --name and --job (or --list / --terminate NAME)")


if __name__ == "__main__":
    main()
