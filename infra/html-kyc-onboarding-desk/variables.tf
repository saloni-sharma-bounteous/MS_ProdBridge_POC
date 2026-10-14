variable "project" {
  description = "Short project name, used in resource names and tags."
  type        = string
  default     = "kyc-desk"
}

variable "environment" {
  description = "Deployment environment."
  type        = string

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be one of: dev, staging, prod."
  }
}

variable "aws_region" {
  description = "AWS region to deploy into."
  type        = string
  default     = "us-east-1"
}

variable "allowed_account_ids" {
  description = "Only these AWS account IDs may be used. Empty list disables the check."
  type        = list(string)
  default     = []
}

variable "owner" {
  description = "Team or person responsible for this stack (tag)."
  type        = string
  default     = "platform"
}

variable "cloudfront_price_class" {
  description = "CloudFront price class. PriceClass_100 covers North America and Europe only and is the cheapest."
  type        = string
  default     = "PriceClass_100"

  validation {
    condition     = contains(["PriceClass_100", "PriceClass_200", "PriceClass_All"], var.cloudfront_price_class)
    error_message = "cloudfront_price_class must be PriceClass_100, PriceClass_200 or PriceClass_All."
  }
}

variable "log_retention_days" {
  description = "Days to keep CloudFront access logs."
  type        = number
  default     = 90

  validation {
    condition     = var.log_retention_days >= 1
    error_message = "log_retention_days must be at least 1."
  }
}
