# kyc-desk

Terraform for AWS (`us-east-1`). Generated with the aws-terraform-deploy skill.

## First-time setup
1. Sign in: `aws sso login --profile <profile>` and set `AWS_PROFILE`.
2. Create the state bucket once: `cd bootstrap`, `terraform init`, `terraform apply -var="state_bucket_name=<unique-name>"`.
3. Put the bucket name in `envs/*.backend.hcl`. Set `allowed_account_ids` in `envs/*.tfvars`.

## Deploy
```
./scripts/deploy.sh dev plan      # Windows: .\scripts\deploy.ps1 -Env dev
./scripts/deploy.sh dev apply
```
Plans are saved to `.plans/` and `apply` only applies the saved plan after you confirm. Production needs you to type `prod`.

## Layout
- `*.tf` root stack, `envs/` per-environment values, `bootstrap/` state bucket,
  `scripts/` deploy wrappers, `.github/workflows/` CI.
