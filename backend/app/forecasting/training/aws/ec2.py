"""The aws CLI, the instances tagged with a job, and launching one instance: spot first across a
ladder of types and zones, on-demand only when allowed. Every instance terminates itself."""
from __future__ import annotations

import base64
import json
import subprocess

from .settings import AMI, REGION


def aws(*args: str, region: bool = True) -> str:
    cmd = ["aws", *args] + (["--region", REGION] if region else [])
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f"aws {' '.join(args[:3])} failed:\n{r.stderr[-800:]}")
    return r.stdout


def running_instances(job: str) -> list[dict]:
    out = aws("ec2", "describe-instances", "--filters", f"Name=tag:dhakaflow-job,Values={job}",
              "Name=instance-state-name,Values=pending,running",
              "--query", "Reservations[].Instances[].{id:InstanceId,state:State.Name,type:InstanceType,t:LaunchTime}",
              "--output", "json")
    return json.loads(out or "[]")


def terminate_instances(job: str) -> list[str]:
    """Stop every instance of this job now (a cancelled or failed job must not keep billing)."""
    ids = [i["id"] for i in running_instances(job)]
    if ids:
        aws("ec2", "terminate-instances", "--instance-ids", *ids)
    return ids


def s3(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["aws", "s3", *args, "--region", REGION], check=check, capture_output=True, text=True)


def run_instance(a, script: str, job: str):
    """Start one instance with this user-data script. Returns (instance id, (type, zone, market), attempts)."""
    ud = base64.b64encode(script.encode()).decode()
    spec = json.dumps({"MarketType": "spot", "SpotOptions": {"SpotInstanceType": "one-time", "InstanceInterruptionBehavior": "terminate"}})
    # Spot capacity for a single GPU type in a single AZ is routinely exhausted, so try a ladder of
    # equivalent instances across zones instead of failing. Order = cheapest capable first.
    types = [t for t in a.instance_type.split(",") if t]
    zones = json.loads(aws("ec2", "describe-availability-zones", "--query", "AvailabilityZones[?State=='available'].ZoneName", "--output", "json"))
    # --no-spot: a reclaimed spot instance loses the whole run (PEMS-BAY was reclaimed 7 min in,
    # Server.SpotInstanceTermination), so long jobs that must finish should not start on spot.
    markets = ["on-demand"] if a.no_spot else (["spot", "on-demand"] if a.allow_on_demand else ["spot"])
    attempts: list[str] = []
    for market in markets:
        for t in types:
            for z in zones:
                try:
                    out = aws("ec2", "run-instances", "--image-id", AMI, "--instance-type", t,
                              "--placement", json.dumps({"AvailabilityZone": z}),
                              *(["--instance-market-options", spec] if market == "spot" else []),
                              "--instance-initiated-shutdown-behavior", "terminate",
                              "--block-device-mappings", json.dumps([{"DeviceName": "/dev/xvda", "Ebs": {"VolumeSize": 120, "DeleteOnTermination": True}}]),
                              "--user-data", ud,
                              *(["--iam-instance-profile", json.dumps({"Name": a.instance_profile})] if a.instance_profile else []),
                              "--tag-specifications", json.dumps([{"ResourceType": "instance", "Tags": [{"Key": "dhakaflow-job", "Value": job}, {"Key": "Name", "Value": job}]}]),
                              "--query", "Instances[0].InstanceId", "--output", "text")
                    return out.strip(), (t, z, market), attempts
                except SystemExit as ex:
                    reason = "no capacity" if "InsufficientInstanceCapacity" in str(ex) else str(ex)[-90:]
                    attempts.append(f"{market} {t}/{z}: {reason}")
    print("[launch] no spot capacity anywhere. Attempts:")
    for x in attempts:
        print("   ", x)
    print("\nOptions: widen --instance-type (e.g. g4dn.xlarge,g5.xlarge,g6.xlarge), try another --region, or use the Colab notebooks instead.")
    return None, None, attempts
