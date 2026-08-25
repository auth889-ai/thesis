#!/usr/bin/env bash
# One-time IAM bootstrap for DhakaFlow training instances.
#
# WHY THIS IS A USER-RUN SCRIPT: creating IAM roles is an account-security
# action, so the assistant does not execute it. Run it yourself once:
#
#     ! bash scripts/aws/bootstrap_iam.sh
#
# It creates (idempotently):
#   role             dhakaflow-train-role      (EC2 assume-role)
#   inline policy    s3-train-access           (ONLY the dhakaflow-train bucket)
#   instance profile dhakaflow-train-profile   (carries the role)
#
# Scope is minimal on purpose: instances get read/write to the training bucket
# and nothing else — no IAM, no EC2, no other buckets.
set -euo pipefail

ROLE=dhakaflow-train-role
PROFILE=dhakaflow-train-profile
BUCKET=dhakaflow-train-915644996102

set -a; source "$(dirname "$0")/../../dhakaflow/.env" 2>/dev/null || true; set +a

echo "== role =="
aws iam create-role --role-name "$ROLE" \
  --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ec2.amazonaws.com"},"Action":"sts:AssumeRole"}]}' \
  --query 'Role.RoleName' --output text 2>/dev/null || echo "role exists (ok)"

echo "== inline S3 policy (train bucket only) =="
aws iam put-role-policy --role-name "$ROLE" --policy-name s3-train-access \
  --policy-document "{\"Version\":\"2012-10-17\",\"Statement\":[{\"Effect\":\"Allow\",\"Action\":[\"s3:GetObject\",\"s3:PutObject\",\"s3:ListBucket\"],\"Resource\":[\"arn:aws:s3:::$BUCKET\",\"arn:aws:s3:::$BUCKET/*\"]}]}"
echo "policy attached"

echo "== instance profile =="
aws iam create-instance-profile --instance-profile-name "$PROFILE" \
  --query 'InstanceProfile.InstanceProfileName' --output text 2>/dev/null || echo "profile exists (ok)"
aws iam add-role-to-instance-profile --instance-profile-name "$PROFILE" \
  --role-name "$ROLE" 2>/dev/null || echo "role already in profile (ok)"

echo "== verify =="
aws iam get-instance-profile --instance-profile-name "$PROFILE" \
  --query 'InstanceProfile.{profile:InstanceProfileName,roles:Roles[].RoleName}' --output json
echo "DONE — launcher can now use --profile-name $PROFILE"
