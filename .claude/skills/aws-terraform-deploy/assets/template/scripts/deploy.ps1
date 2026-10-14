<#
Safe Terraform deploy wrapper for Windows PowerShell.
  .\scripts\deploy.ps1 -Env dev                      validate + save a plan (default, changes nothing)
  .\scripts\deploy.ps1 -Env dev -Action apply        apply the saved plan after confirmation
  .\scripts\deploy.ps1 -Env dev -Action destroy-plan save a destroy plan (never applies it)
#>
param(
  [Parameter(Mandatory = $true)][ValidateSet('dev', 'staging', 'prod')][string]$Env,
  [ValidateSet('plan', 'apply', 'destroy-plan')][string]$Action = 'plan'
)
$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')

function Run {
  param([string]$Exe, [string[]]$CmdArgs = @())
  & $Exe @CmdArgs
  if ($LASTEXITCODE -ne 0) { throw "$Exe $($CmdArgs -join ' ') failed with exit code $LASTEXITCODE" }
}

foreach ($f in "envs/$Env.tfvars", "envs/$Env.backend.hcl") {
  if (-not (Test-Path $f)) { throw "Missing $f" }
}
foreach ($t in 'terraform', 'aws') {
  if (-not (Get-Command $t -ErrorAction SilentlyContinue)) { throw "$t is not installed or not on PATH" }
}

Write-Host '== Who am I =='
Run aws @('sts', 'get-caller-identity', '--output', 'table')
Write-Host "Environment: $Env   Action: $Action"

Write-Host '== Format, init, validate =='
Run terraform @('fmt', '-check', '-recursive')
Run terraform @('init', '-input=false', '-reconfigure', "-backend-config=envs/$Env.backend.hcl")
Run terraform @('validate')

if (Get-Command tflint -ErrorAction SilentlyContinue) { Write-Host '== tflint =='; & tflint --init | Out-Null; Run tflint @() }
if (Get-Command checkov -ErrorAction SilentlyContinue) { Write-Host '== checkov =='; Run checkov @('-d', '.', '--framework', 'terraform', '--quiet', '--compact') }

New-Item -ItemType Directory -Force -Path .plans | Out-Null
$Plan = ".plans/$Env.tfplan"

switch ($Action) {
  'plan' {
    Run terraform @('plan', '-input=false', "-var-file=envs/$Env.tfvars", "-out=$Plan")
    Write-Host "Plan saved to $Plan. Review it, then run: .\scripts\deploy.ps1 -Env $Env -Action apply"
  }
  'destroy-plan' {
    Run terraform @('plan', '-destroy', '-input=false', "-var-file=envs/$Env.tfvars", "-out=$Plan")
    Write-Host "Destroy plan saved to $Plan. Applying it is a deliberate manual step."
  }
  'apply' {
    if (-not (Test-Path $Plan)) { throw "No saved plan. Run with -Action plan first." }
    Run terraform @('show', $Plan)
    if ($Env -eq 'prod') {
      $answer = Read-Host "Type 'prod' to confirm applying to PRODUCTION"
      if ($answer -ne 'prod') { throw 'Aborted.' }
    } else {
      $answer = Read-Host "Apply this plan to $Env? (yes/no)"
      if ($answer -ne 'yes') { throw 'Aborted.' }
    }
    Run terraform @('apply', '-input=false', $Plan)
    Run terraform @('output')
  }
}
