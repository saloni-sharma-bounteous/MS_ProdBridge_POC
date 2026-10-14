# Remote state in S3 with native locking. Bucket and region are supplied per
# environment:  terraform init -backend-config=envs/dev.backend.hcl
# Create the bucket once with ./bootstrap (see README).
terraform {
  backend "s3" {
    key          = "kyc-desk/terraform.tfstate"
    use_lockfile = true
    encrypt      = true
  }
}
