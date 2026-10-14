provider "aws" {
  region = var.aws_region

  # Safety net: Terraform refuses to run against any other account.
  allowed_account_ids = length(var.allowed_account_ids) > 0 ? var.allowed_account_ids : null

  # Credentials come from AWS_PROFILE (SSO) or CI OIDC. Never hard-code keys.
  default_tags {
    tags = local.tags
  }
}
