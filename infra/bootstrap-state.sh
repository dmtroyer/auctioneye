#!/usr/bin/env bash
# One-time bootstrap: create the S3 bucket that holds Terraform state, with
# versioning (state history / recovery), default encryption, and public access
# blocked. Run this ONCE before switching to the S3 backend (see backend.tf).
#
# Uses your current AWS credentials (AWS_PROFILE / SSO). Safe to re-run: each
# step is idempotent.
set -euo pipefail

BUCKET="${1:-auctioneye-tfstate-dmtroyer}"
REGION="${2:-us-east-2}"

echo "Creating state bucket '$BUCKET' in $REGION ..."

# us-east-1 must NOT be given a LocationConstraint; every other region must.
if aws s3api head-bucket --bucket "$BUCKET" 2>/dev/null; then
  echo "Bucket already exists, skipping create."
elif [ "$REGION" = "us-east-1" ]; then
  aws s3api create-bucket --bucket "$BUCKET" --region "$REGION"
else
  aws s3api create-bucket --bucket "$BUCKET" --region "$REGION" \
    --create-bucket-configuration "LocationConstraint=$REGION"
fi

aws s3api put-bucket-versioning \
  --bucket "$BUCKET" \
  --versioning-configuration Status=Enabled

aws s3api put-bucket-encryption \
  --bucket "$BUCKET" \
  --server-side-encryption-configuration \
  '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"},"BucketKeyEnabled":true}]}'

aws s3api put-public-access-block \
  --bucket "$BUCKET" \
  --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true

echo "Done. Bucket '$BUCKET' is ready for use as the Terraform backend."
