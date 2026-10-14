# Upload the POC site to S3 and invalidate CloudFront. Run AFTER `deploy.ps1 dev apply`.
# Usage: .\scripts\publish-site.ps1 dev
param([Parameter(Mandatory)][ValidateSet('dev','staging','prod')][string]$Env)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$src  = Join-Path $root '..\..\apps\html-kyc-onboarding-desk' | Resolve-Path

$id = aws sts get-caller-identity --output json | ConvertFrom-Json
Write-Host "Account $($id.Account) as $($id.Arn)"
if ((Read-Host "Publish to $Env in this account? (yes/no)") -ne 'yes') { exit 1 }

Push-Location $root
try {
  $bucket = terraform output -raw site_bucket
  $dist   = terraform output -raw distribution_id
} finally { Pop-Location }

# old-dashboard.html contains a sandbox API key and README.md is not site content.
aws s3 sync $src "s3://$bucket" --delete --exclude 'old-dashboard.html' --exclude 'README.md'
aws cloudfront create-invalidation --distribution-id $dist --paths '/*' | Out-Null
Write-Host "Published. Site: $(terraform -chdir=$root output -raw site_url)"
