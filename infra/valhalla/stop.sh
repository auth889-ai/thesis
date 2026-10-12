#!/bin/bash
# Terminate the Valhalla routing server (cost rule 6: nothing is left running without the owner's word).
#   infra/valhalla/stop.sh <instance-id>      or with no argument: every instance tagged project=dhakaflow, phase=routing in ap-south-1
set -euo pipefail
REGION=ap-south-1
if [ -n "${1:-}" ]; then IDS="$1"; else
  IDS="$(aws ec2 describe-instances --region $REGION --filters Name=tag:project,Values=dhakaflow Name=tag:phase,Values=routing Name=instance-state-name,Values=pending,running,stopping,stopped --query 'Reservations[].Instances[].InstanceId' --output text)"
fi
[ -n "$IDS" ] || { echo "no routing instance is running"; exit 0; }
aws ec2 terminate-instances --region $REGION --instance-ids $IDS --query 'TerminatingInstances[].[InstanceId,CurrentState.Name]' --output text
echo "the saved tiles stay in S3 (about 2 GB); restart with: infra/valhalla/launch.sh --approved --from-s3"
