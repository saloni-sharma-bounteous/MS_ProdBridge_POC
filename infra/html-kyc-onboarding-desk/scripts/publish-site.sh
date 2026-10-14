#!/usr/bin/env bash
# Upload the POC site to S3 and invalidate CloudFront. Run AFTER `deploy.sh dev apply`.
# Usage: ./scripts/publish-site.sh dev
set -euo pipefail

env="${1:?usage: publish-site.sh <dev|staging|prod>}"
root="$(cd "$(dirname "$0")/.." && pwd)"
src="$(cd "$root/../../apps/html-kyc-onboarding-desk" && pwd)"

aws sts get-caller-identity --query '[Account,Arn]' --output text
read -r -p "Publish to ${env} in this account? (yes/no) " ok
[ "$ok" = "yes" ] || exit 1

bucket="$(terraform -chdir="$root" output -raw site_bucket)"
dist="$(terraform -chdir="$root" output -raw distribution_id)"

# old-dashboard.html contains a sandbox API key and README.md is not site content.
aws s3 sync "$src" "s3://${bucket}" --delete --exclude 'old-dashboard.html' --exclude 'README.md'
aws cloudfront create-invalidation --distribution-id "$dist" --paths '/*' >/dev/null
echo "Published. Site: $(terraform -chdir="$root" output -raw site_url)"
