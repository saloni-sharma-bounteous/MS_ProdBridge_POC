terraform {
  # use_lockfile (S3-native state locking) needs Terraform 1.10 or newer.
  required_version = ">= 1.10.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0" # verify the latest major with the Terraform MCP before release
    }
  }
}
