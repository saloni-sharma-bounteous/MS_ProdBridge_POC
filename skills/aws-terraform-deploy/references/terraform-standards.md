# Terraform standards for this skill

## Contents
1. Project layout
2. Versions and providers
3. State
4. Naming, tags and variables
5. Modules vs resources
6. Security baseline
7. Reliability and cost
8. Quality gates
9. Deployment rules

## 1. Project layout

Root stack with focused files, not one giant `main.tf`:

```
versions.tf providers.tf backend.tf variables.tf locals/main.tf outputs.tf
network.tf compute.tf data.tf iam.tf   (split by concern)
envs/<env>.tfvars  envs/<env>.backend.hcl
modules/<name>/    only for logic reused 2+ times
bootstrap/         state bucket, applied once with local state
scripts/           deploy.sh, deploy.ps1
```

Use one directory with per-environment `tfvars` and backend files. Avoid Terraform workspaces for environments that differ materially.

## 2. Versions and providers

- Pin `required_version` and the provider with `~>` (pessimistic constraint). Commit `.terraform.lock.hcl`.
- Before writing code, confirm the **latest provider and module versions** with the Terraform MCP. Do not rely on remembered versions.
- Set `default_tags` on the provider and `allowed_account_ids` so a wrong profile cannot apply to the wrong account.

## 3. State

- Remote state in S3 with versioning, encryption, public access blocked, TLS-only policy, and S3-native locking (`use_lockfile = true`, Terraform 1.10+).
- One state per environment, separate keys or buckets. Prod state access is restricted.
- Never commit state or plan files. Plans can contain secrets.

## 4. Naming, tags and variables

- Names: `<project>-<environment>-<purpose>`. Keep within each service's length limits.
- Required tags: `Project`, `Environment`, `Owner`, `ManagedBy=terraform`. Add `CostCenter` if the user has one.
- Every variable has a `description` and `type`. Add `validation` for anything with a fixed set of values. Mark secrets `sensitive = true` and never give them defaults.
- Secrets live in AWS Secrets Manager or SSM Parameter Store (SecureString). Reference them, do not hard-code them.

## 5. Modules vs resources

- Prefer well-maintained community or AWS-IA modules (for example `terraform-aws-modules/*`) for complex, standard building blocks such as VPC, ALB, EKS, RDS. Check the module's recent activity, inputs and version through the Terraform MCP.
- Write plain resources for simple things and when a module would hide important settings.
- Do not create a local module that wraps a single resource.

## 6. Security baseline (apply by default, deviate only with a written reason)

- Encryption at rest everywhere (KMS or service default) and TLS in transit.
- No public S3 buckets, no `0.0.0.0/0` ingress except HTTPS on a load balancer or CDN that needs it.
- IAM: least privilege, no `*` actions or resources unless unavoidable, roles not users, no long-lived keys. Use OIDC for CI.
- EC2: IMDSv2 required. Databases in private subnets, deletion protection on for prod, backups on.
- Logging on: CloudTrail, VPC flow logs where relevant, ALB/CloudFront logs, CloudWatch log groups with retention.
- Prefer VPC endpoints for S3 and DynamoDB over NAT where traffic is heavy.

## 7. Reliability and cost

- Multi-AZ for anything stateful in prod. Single-AZ is acceptable in dev if you say so.
- Right-size by default (small in dev). Set log retention, S3 lifecycle rules, and budgets or alarms.
- Call out the main cost drivers (NAT gateways, load balancers, RDS, data transfer) in the handoff, and give an estimate if a pricing tool is available.

## 8. Quality gates (run in this order, fix before moving on)

1. `terraform fmt -recursive`
2. `terraform init -backend=false` then `terraform validate`
3. `tflint` (if installed)
4. `checkov -d . --framework terraform` or `trivy config .` (if installed)
5. `terraform plan` with real credentials (see rules below)

Do not silence a security finding without a comment explaining why the risk is accepted.

## 9. Deployment rules

- **Plan is the default.** Never run `terraform apply` or `destroy` unless the user has explicitly asked for it in this conversation, and always apply a **saved plan** the user has seen.
- No `-auto-approve` unless the user explicitly asks for it for a non-production environment.
- Production requires typing the environment name to confirm (the bundled scripts do this).
- Confirm the account and region (`aws sts get-caller-identity`) before any plan or apply, and tell the user which account it is.
- Destroys: only create a destroy **plan**, show it, and let the user decide.
- After an apply, verify with read-only checks and give a rollback note (previous state version, `git revert` plus re-apply, or targeted import).
