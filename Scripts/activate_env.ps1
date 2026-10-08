# Usage (from project root, dot-source so variables persist in your session):
#   . .\Scripts\activate_env.ps1
# Activates .venv and loads variables from .env into the current session.

$root = Split-Path -Parent $PSScriptRoot
& "$root\.venv\Scripts\Activate.ps1"

Get-Content "$root\.env" | ForEach-Object {
    $line = $_.Trim()
    if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
        $name, $value = $line.Split("=", 2)
        Set-Item -Path "Env:$($name.Trim())" -Value $value.Trim()
    }
}
Write-Host "venv active; loaded JIRA_* variables from .env"
