$ErrorActionPreference = "Stop"

# Determine repository root whether invoked from scripts/ or backend/scripts/
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (Test-Path (Join-Path (Split-Path -Parent $ScriptDir) "frontend")) {
    $RepoRoot = Split-Path -Parent $ScriptDir
} elseif (Test-Path (Join-Path (Split-Path -Parent (Split-Path -Parent $ScriptDir)) "frontend")) {
    $RepoRoot = Split-Path -Parent (Split-Path -Parent $ScriptDir)
} else {
    $RepoRoot = Split-Path -Parent $ScriptDir
}

$FrontendDir = Join-Path $RepoRoot "frontend"
Write-Host "Building frontend assets in $FrontendDir..." -ForegroundColor Cyan

Push-Location $FrontendDir
try {
    # Use npm.cmd on Windows to bypass PowerShell script execution policy
    if (Get-Command "npm.cmd" -ErrorAction SilentlyContinue) {
        & npm.cmd run build
    } else {
        npm run build
    }
    Write-Host "`n[OK] Frontend production build completed. Dist assets updated for port 8000." -ForegroundColor Green
} finally {
    Pop-Location
}
