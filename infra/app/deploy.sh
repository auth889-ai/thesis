#!/bin/bash
# Deploy the hosted app (Q5) onto the running routing instance: package, open 80/443 to everyone (the password is on every page),
# keep 8002/8003 (Valhalla) as they are (the owner's IP only), and run setup.sh there through SSM. Reads the user and the bcrypt hash
# from .env (never the password itself).   infra/app/deploy.sh [instance-id]
set -euo pipefail
ID="${1:-i-0e8476dac1d2fa7c1}"; REGION=ap-south-1; CADDY_VER=2.11.7
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
USER_="$(grep '^TRAFFICTWIN_HOSTED_USER=' .env | cut -d= -f2-)"; HASH="$(grep '^TRAFFICTWIN_HOSTED_BCRYPT=' .env | cut -d= -f2-)"
[ -n "$USER_" ] && [ -n "$HASH" ] || { echo "TRAFFICTWIN_HOSTED_USER / TRAFFICTWIN_HOSTED_BCRYPT missing in .env"; exit 1; }
IP="$(aws ec2 describe-instances --region $REGION --instance-ids "$ID" --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)"
HOST="${IP//./-}.sslip.io"
BUCKET="dhakaflow-routing-$(aws sts get-caller-identity --query Account --output text)"
# the package holds what the pages read, every backend requirement is installed, and the app starts without research-only libraries
( cd backend && DHAKAFLOW_NO_OBSERVATORY=1 python -m pytest -q -p no:cacheprovider tests/test_hosted_package.py ) || { echo "deploy refused: tests/test_hosted_package.py failed"; exit 1; }
infra/app/package.sh
SG="$(aws ec2 describe-security-groups --region $REGION --filters Name=group-name,Values=dhakaflow-valhalla --query 'SecurityGroups[0].GroupId' --output text)"
for p in 80 443; do aws ec2 authorize-security-group-ingress --region $REGION --group-id "$SG" --protocol tcp --port $p --cidr 0.0.0.0/0 >/dev/null 2>&1 || true; done
SCRIPT="$(base64 < infra/app/setup.sh | tr -d '\n')"; H64="$(printf '%s' "$HASH" | base64 | tr -d '\n')"
CID="$(aws ssm send-command --region $REGION --instance-ids "$ID" --document-name AWS-RunShellScript --timeout-seconds 3600 \
      --parameters "commands=[\"echo $SCRIPT | base64 -d > /srv/app_setup.sh && bash /srv/app_setup.sh $BUCKET $HOST $USER_ $H64 $CADDY_VER\"],executionTimeout=[\"3600\"]" \
      --query Command.CommandId --output text)"
echo "setup sent: $CID"
while :; do
  ST="$(aws ssm get-command-invocation --region $REGION --command-id "$CID" --instance-id "$ID" --query Status --output text 2>/dev/null || echo Pending)"
  case "$ST" in Pending|InProgress|Delayed) sleep 20;; *) break;; esac
done
aws ssm get-command-invocation --region $REGION --command-id "$CID" --instance-id "$ID" --query '[StandardOutputContent,StandardErrorContent]' --output text | tail -15
echo "status: $ST"
echo "https://$HOST/"
