#!/bin/bash
# The instance profile the Valhalla server runs with: read and write of the routing bucket only. Idempotent.
set -euo pipefail
ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
BUCKET="dhakaflow-routing-$ACCOUNT"; ROLE=dhakaflow-valhalla-role; PROFILE=dhakaflow-valhalla-profile
TRUST='{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ec2.amazonaws.com"},"Action":"sts:AssumeRole"}]}'
POLICY="{\"Version\":\"2012-10-17\",\"Statement\":[{\"Effect\":\"Allow\",\"Action\":[\"s3:ListBucket\"],\"Resource\":\"arn:aws:s3:::$BUCKET\"},{\"Effect\":\"Allow\",\"Action\":[\"s3:GetObject\",\"s3:PutObject\",\"s3:PutObjectTagging\"],\"Resource\":\"arn:aws:s3:::$BUCKET/*\"}]}"
aws iam get-role --role-name $ROLE >/dev/null 2>&1 || aws iam create-role --role-name $ROLE --assume-role-policy-document "$TRUST" --tags Key=project,Value=dhakaflow Key=phase,Value=routing >/dev/null
aws iam put-role-policy --role-name $ROLE --policy-name routing-bucket --policy-document "$POLICY"
aws iam get-instance-profile --instance-profile-name $PROFILE >/dev/null 2>&1 || { aws iam create-instance-profile --instance-profile-name $PROFILE >/dev/null; sleep 8; }
aws iam list-instance-profiles-for-role --role-name $ROLE --query 'InstanceProfiles[].InstanceProfileName' --output text | grep -q $PROFILE || aws iam add-role-to-instance-profile --instance-profile-name $PROFILE --role-name $ROLE
echo "profile $PROFILE -> role $ROLE -> s3://$BUCKET"
