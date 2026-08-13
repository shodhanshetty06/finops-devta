#requires -version 5.1
<#
    register-finance-guru.ps1

    Run this ONCE (from any terminal, in this folder):

        .\register-finance-guru.ps1

    It adds a `finance-guru` command to your PowerShell profile, so typing
    `finance-guru` in any terminal (including the VS Code integrated
    terminal) starts the app and opens http://localhost:6000.

    After running this once, restart your terminal (or run
    `. $PROFILE`) for the new command to become available.
#>

$ErrorActionPreference = "Stop"
$launcherPath = Join-Path $PSScriptRoot "start-finance-guru.ps1"

if (-not (Test-Path $launcherPath)) {
    Write-Host "Could not find start-finance-guru.ps1 next to this script. Run register-finance-guru.ps1 from inside the gcp-finops-platform folder." -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $PROFILE)) {
    New-Item -ItemType File -Path $PROFILE -Force | Out-Null
}

$marker = "# --- finance-guru (auto-added) ---"
$existing = Get-Content $PROFILE -Raw -ErrorAction SilentlyContinue
if ($existing -and $existing.Contains($marker)) {
    Write-Host "finance-guru is already registered in your PowerShell profile ($PROFILE)." -ForegroundColor Yellow
    Write-Host "Nothing to do. If it's not working, restart your terminal." -ForegroundColor Yellow
    exit 0
}

$functionBlock = @"

$marker
function finance-guru {
    powershell -NoProfile -ExecutionPolicy Bypass -File "$launcherPath" @args
}
# --- end finance-guru ---
"@

Add-Content -Path $PROFILE -Value $functionBlock
Write-Host "Added the 'finance-guru' command to your PowerShell profile:" -ForegroundColor Green
Write-Host "  $PROFILE"
Write-Host ""
Write-Host "Restart your terminal (close and reopen the VS Code terminal), then just type:" -ForegroundColor Cyan
Write-Host "  finance-guru" -ForegroundColor Cyan
