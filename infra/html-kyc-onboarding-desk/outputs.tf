output "account_id" {
  description = "AWS account this stack was applied to."
  value       = data.aws_caller_identity.current.account_id
}

output "name_prefix" {
  description = "Prefix used for resource names."
  value       = local.name_prefix
}

output "site_url" {
  description = "HTTPS URL of the site."
  value       = "https://${aws_cloudfront_distribution.site.domain_name}/login.html"
}

output "site_bucket" {
  description = "Bucket the publish script uploads the site to."
  value       = aws_s3_bucket.site.id
}

output "distribution_id" {
  description = "CloudFront distribution ID, used for cache invalidation."
  value       = aws_cloudfront_distribution.site.id
}
