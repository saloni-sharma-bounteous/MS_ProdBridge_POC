#!/usr/bin/env bash
# Safe Terraform deploy wrapper (macOS, Linux, WSL, Git Bash).
#   ./scripts/deploy.sh <env> plan       validate + save a plan (default, changes nothing)
#   ./scripts/deploy.sh <env> apply      apply the saved plan after confirmation
#   ./scripts/deploy.sh <env> destroy-plan   save a destroy plan (never applies it)
set -euo pipefail

ENV="${1:?usage: deploy.sh <dev|staging|prod> [plan|apply|destroy-plan]}"
ACTION="${2:-plan}"
cd "$(dirname "$0")/.."

[ -f "envs/${ENV}.tfvars" ] || { echo "Missing envs/${ENV}.tfvars"; exit 1; }
[ -f "envs/${ENV}.backend.hcl" ] || { echo "Missing envs/${ENV}.backend.hcl"; exit 1; }
command -v terraform >/dev/null || { echo "terraform is not installed"; exit 1; }
command -v aws >/dev/null || { echo "aws CLI is not installed"; exit 1; }

echo "== Who am I =="
aws sts get-caller-identity --output table
echo "Environment: ${ENV}   Action: ${ACTION}"

echo "== Format, init, validate =="
terraform fmt -check -recursive
terraform init -input=false -reconfigure -backend-config="envs/${ENV}.backend.hcl"
terraform validate

if command -v tflint >/dev/null; then echo "== tflint =="; tflint --init >/dev/null; tflint; fi
if command -v checkov >/dev/null; then echo "== checkov =="; checkov -d . --framework terraform --quiet --compact; fi

mkdir -p .plans
PLAN=".plans/${ENV}.tfplan"

case "$ACTION" in
  plan)
    terraform plan -input=false -var-file="envs/${ENV}.tfvars" -out="$PLAN"
    echo "Plan saved to $PLAN. Review it, then run: ./scripts/deploy.sh ${ENV} apply"
    ;;
  destroy-plan)
    terraform plan -destroy -input=false -var-file="envs/${ENV}.tfvars" -out="$PLAN"
    echo "Destroy plan saved to $PLAN. Applying it is a deliberate manual step."
    ;;
  apply)
    [ -f "$PLAN" ] || { echo "No saved plan. Run '${0} ${ENV} plan' first."; exit 1; }
    terraform show "$PLAN"
    if [ "$ENV" = "prod" ]; then
      read -r -p "Type 'prod' to confirm applying to PRODUCTION: " ANSWER
      [ "$ANSWER" = "prod" ] || { echo "Aborted."; exit 1; }
    else
      read -r -p "Apply this plan to ${ENV}? (yes/no): " ANSWER
      [ "$ANSWER" = "yes" ] || { echo "Aborted."; exit 1; }
    fi
    terraform apply -input=false "$PLAN"
    terraform output
    ;;
  *) echo "Unknown action: $ACTION"; exit 1 ;;
esac
