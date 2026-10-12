#!/bin/bash
# The security group admits the launching machine's IP only; when that IP changes (it did on 2026-10-06), this re-points both ports to the current one.
set -euo pipefail
REGION=ap-south-1
MYIP="$(curl -fs https://checkip.amazonaws.com)/32"
SG="$(aws ec2 describe-security-groups --region $REGION --filters Name=group-name,Values=dhakaflow-valhalla --query 'SecurityGroups[0].GroupId' --output text)"
for p in 8002 8003; do
  for old in $(aws ec2 describe-security-groups --region $REGION --group-ids "$SG" --query "SecurityGroups[0].IpPermissions[?FromPort==\`$p\`].IpRanges[].CidrIp" --output text); do
    [ "$old" = "$MYIP" ] || aws ec2 revoke-security-group-ingress --region $REGION --group-id "$SG" --protocol tcp --port $p --cidr "$old" >/dev/null
  done
  aws ec2 authorize-security-group-ingress --region $REGION --group-id "$SG" --protocol tcp --port $p --cidr "$MYIP" >/dev/null 2>&1 || true
done
echo "ports 8002 and 8003 open to $MYIP only"
