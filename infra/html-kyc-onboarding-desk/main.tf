data "aws_caller_identity" "current" {}

locals {
  name_prefix = "${var.project}-${var.environment}"

  tags = {
    Project     = var.project
    Environment = var.environment
    Owner       = var.owner
    ManagedBy   = "terraform"
  }
}

# ---------------------------------------------------------------------------
# Add resources and modules below. Group them by concern in separate files
# (network.tf, compute.tf, data.tf, iam.tf, ...). Verify every resource
# argument against the provider docs before using it.
# ---------------------------------------------------------------------------
