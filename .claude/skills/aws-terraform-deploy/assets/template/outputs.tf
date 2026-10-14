output "account_id" {
  description = "AWS account this stack was applied to."
  value       = data.aws_caller_identity.current.account_id
}

output "name_prefix" {
  description = "Prefix used for resource names."
  value       = local.name_prefix
}
