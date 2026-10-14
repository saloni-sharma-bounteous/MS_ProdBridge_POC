variable "project" {
  description = "Short project name, used in resource names and tags."
  type        = string
  default     = "__PROJECT__"
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
  default     = "__REGION__"
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
