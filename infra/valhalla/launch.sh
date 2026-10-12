#!/bin/bash
# Launch the Valhalla routing server (AWS cost rules: stated and approved first; tags; on-demand because a routing
# server must stay up; ap-south-1; shuts itself down after MAXH hours). Prints the instance id and public IP.
#   infra/valhalla/launch.sh --approved            # after the owner's yes in chat: downloads the extracts, builds the tiles (1-2 h), saves them to S3
#   infra/valhalla/launch.sh --approved --from-s3  # starts from the saved tiles instead: ready in minutes (for user tests and the defense)
set -euo pipefail
[ "${1:-}" = "--approved" ] || { echo "refusing: run with --approved only after the owner approved type, hours and cost"; exit 2; }
FROMS3=0; [ "${2:-}" = "--from-s3" ] && FROMS3=1
REGION=ap-south-1; TYPE=${TYPE:-t3.xlarge}; MAXH=${MAXH:-48}; DISK=60
ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
BUCKET="dhakaflow-routing-$ACCOUNT"
PROFILE=${PROFILE:-dhakaflow-valhalla-profile}       # an instance profile allowed to read and write that bucket
HERE0="$(cd "$(dirname "$0")" && pwd)"; "$HERE0/setup-iam.sh"
if ! aws s3api head-bucket --bucket "$BUCKET" --region $REGION 2>/dev/null; then
  aws s3api create-bucket --bucket "$BUCKET" --region $REGION --create-bucket-configuration LocationConstraint=$REGION >/dev/null
  aws s3api put-bucket-tagging --bucket "$BUCKET" --tagging 'TagSet=[{Key=project,Value=dhakaflow},{Key=phase,Value=routing}]'
  aws s3api put-public-access-block --bucket "$BUCKET" --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
fi
IMAGE=ghcr.io/valhalla/valhalla-scripted:3.9.0
EXTRACTS="dhaka=asia/bangladesh los_angeles=north-america/us/california/socal"
HERE="$(cd "$(dirname "$0")" && pwd)"; ROOT="$(cd "$HERE/../.." && pwd)"
MYIP="$(curl -fs https://checkip.amazonaws.com)/32"
AMI="$(aws ssm get-parameter --region $REGION --name /aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id --query Parameter.Value --output text)"
VPC="$(aws ec2 describe-vpcs --region $REGION --filters Name=is-default,Values=true --query 'Vpcs[0].VpcId' --output text)"
SG="$(aws ec2 describe-security-groups --region $REGION --filters Name=group-name,Values=dhakaflow-valhalla --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null || true)"
if [ -z "$SG" ] || [ "$SG" = "None" ]; then
  SG="$(aws ec2 create-security-group --region $REGION --group-name dhakaflow-valhalla --description "TrafficTwin Valhalla, owner IP only" --vpc-id "$VPC" --query GroupId --output text)"
fi
for p in 8002 8003; do aws ec2 authorize-security-group-ingress --region $REGION --group-id "$SG" --protocol tcp --port $p --cidr "$MYIP" >/dev/null 2>&1 || true; done
sed -e "s#@MAXH@#$MAXH#g" -e "s#@IMAGE@#$IMAGE#g" -e "s#@EXTRACTS@#$EXTRACTS#g" -e "s#@BUCKET@#$BUCKET#g" -e "s#@FROMS3@#$FROMS3#g" "$HERE/user-data.sh" > /tmp/valhalla-user-data.sh
grep -q "@" /tmp/valhalla-user-data.sh && { echo "unfilled placeholder in user data"; exit 1; }
TAGS='[{Key=project,Value=dhakaflow},{Key=phase,Value=routing},{Key=Name,Value=dhakaflow-valhalla}]'      # the CLI's shorthand syntax, not JSON
ID="$(aws ec2 run-instances --region $REGION --image-id "$AMI" --instance-type "$TYPE" --security-group-ids "$SG" --iam-instance-profile "Name=$PROFILE" \
  --instance-initiated-shutdown-behavior terminate --user-data "file:///tmp/valhalla-user-data.sh" \
  --block-device-mappings "[{\"DeviceName\":\"/dev/sda1\",\"Ebs\":{\"VolumeSize\":$DISK,\"VolumeType\":\"gp3\",\"DeleteOnTermination\":true}}]" \
  --tag-specifications "ResourceType=instance,Tags=$TAGS" "ResourceType=volume,Tags=$TAGS" \
  --query 'Instances[0].InstanceId' --output text)"
aws ec2 wait instance-running --region $REGION --instance-ids "$ID"
IP="$(aws ec2 describe-instances --region $REGION --instance-ids "$ID" --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)"
python3 - "$ID" "$IP" "$TYPE" "$MAXH" "$REGION" "$IMAGE" "$EXTRACTS" "$ROOT" "$FROMS3" "$BUCKET" <<'PY'
import json, sys, datetime
i, ip, t, h, r, img, ex, root, fs, b = sys.argv[1:]
p = f"{root}/evidence/routing/valhalla_instance.json"
try: d = json.load(open(p))
except Exception: d = {"launches": []}
d["launches"].append({"instance_id": i, "public_ip": ip, "type": t, "max_hours": int(h), "region": r, "image": img, "extracts": ex, "from_s3": bool(int(fs)), "bucket": b, "launched_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "spot": False})
json.dump(d, open(p, "w"), indent=1)
PY
echo "instance $ID at $IP; Dhaka on :8002, Los Angeles on :8003 ($([ $FROMS3 = 1 ] && echo 'ready in minutes from the saved tiles' || echo 'ready after the tile build, roughly 1-2 h; the tiles are then saved to s3://'$BUCKET'/tiles/'))"
echo "then: TRAFFICTWIN_VALHALLA_URL_DHAKA=http://$IP:8002 and TRAFFICTWIN_VALHALLA_URL_LOS_ANGELES=http://$IP:8003 in .env"
echo "stop:    infra/valhalla/stop.sh $ID        (aws ec2 terminate-instances --region $REGION --instance-ids $ID)"
echo "restart: infra/valhalla/launch.sh --approved --from-s3"
