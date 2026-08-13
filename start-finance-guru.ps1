#requires -version 5.1
<#
    start-finance-guru.ps1

    One-command launcher for the GCP FinOps platform: starts the backend
    (FastAPI, port 8000) and the frontend (Next.js, port 6001) as two
    separate visible PowerShell windows so you can see their logs, waits
    for both to come up, then opens http://localhost:6001 in your browser.

    Port 6001, not 6000: Chrome (and other Chromium browsers) hard-block
    port 6000 specifically (it's reserved for the X11 window system) and
    refuse to even attempt the connection - that's the ERR_UNSAFE_PORT
    error, not an app problem. 6001 is not on that blocked list.

    Zero external dependencies: SQLite database, no Redis required, Celery
    runs in-process (see backend/.env). First run installs the Python venv
    and npm packages, which takes a few minutes; every run after that is
    fast (a few seconds).

    Safe to run again while it's already running - it detects the ports
    are in use and just reopens the browser instead of starting duplicates.

    Pass -Prod to browse the app at full speed: `next dev` recompiles each
    page the first time you open it (a real ~seconds-long delay, worse on
    Windows if antivirus is scanning the project folder), which feels like
    the app is slow. -Prod runs `next build` once up front and serves the
    optimized build instead, so every page responds immediately. You lose
    hot-reload-on-save, so use plain `finance-guru` while actively editing
    frontend code and `finance-guru -Prod` when you just want to click
    around a fast, stable build.
#>

param(
    [switch]$Prod
)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$backendDir = Join-Path $root "backend"
$frontendDir = Join-Path $root "frontend"
$backendPort = 8000
$frontendPort = 6001

function Write-Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "    $msg" -ForegroundColor Green }
function Write-Warn2($msg) { Write-Host "    $msg" -ForegroundColor Yellow }

function Test-PortOpen($port) {
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $async = $client.BeginConnect("127.0.0.1", $port, $null, $null)
        $ok = $async.AsyncWaitHandle.WaitOne(300)
        if ($ok -and $client.Connected) { $client.Close(); return $true }
        $client.Close()
        return $false
    } catch { return $false }
}

Write-Host "=======================================================" -ForegroundColor Magenta
Write-Host "  Finance Guru - GCP FinOps Estimation Platform" -ForegroundColor Magenta
Write-Host "=======================================================" -ForegroundColor Magenta

# -- Preflight: Python + Node ------------------------------------------------
Write-Step "Checking prerequisites"
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) { $python = Get-Command py -ErrorAction SilentlyContinue }
if (-not $python) {
    Write-Host "Python was not found on PATH. Install Python 3.11+ from https://python.org and try again." -ForegroundColor Red
    exit 1
}
$node = Get-Command node -ErrorAction SilentlyContinue
if (-not $node) {
    Write-Host "Node.js was not found on PATH. Install Node.js 20+ from https://nodejs.org and try again." -ForegroundColor Red
    exit 1
}
Write-Ok "Python: $($python.Source)"
Write-Ok "Node:   $($node.Source)"

# -- Backend: venv + deps -----------------------------------------------------
$venvDir = Join-Path $backendDir "venv"
$venvPython = Join-Path $venvDir "Scripts\python.exe"
$venvUvicorn = Join-Path $venvDir "Scripts\uvicorn.exe"

if (-not (Test-Path $venvUvicorn)) {
    Write-Step "First run: setting up the Python backend (this takes a few minutes)"
    Push-Location $backendDir
    & $python.Source -m venv venv
    & $venvPython -m pip install --upgrade pip --quiet
    & $venvPython -m pip install -r requirements.txt --quiet
    Pop-Location
    Write-Ok "Backend environment ready"
} else {
    Write-Ok "Backend environment already set up"
}

# -- Frontend: npm install -----------------------------------------------------
$nodeModules = Join-Path $frontendDir "node_modules"
if (-not (Test-Path $nodeModules)) {
    Write-Step "First run: installing frontend packages (this takes a few minutes)"
    Push-Location $frontendDir
    npm install
    Pop-Location
    Write-Ok "Frontend packages installed"
} else {
    Write-Ok "Frontend packages already installed"
}

# -- Start backend -------------------------------------------------------------
if (Test-PortOpen $backendPort) {
    Write-Ok "Backend already running on port $backendPort"
} else {
    Write-Step "Starting backend on http://localhost:$backendPort"
    Start-Process powershell -WorkingDirectory $backendDir -WindowStyle Normal -ArgumentList @(
        "-NoExit", "-Command",
        "Write-Host 'Finance Guru - Backend (FastAPI)' -ForegroundColor Magenta; & '$venvUvicorn' app.main:app --host 127.0.0.1 --port $backendPort"
    )
}

# -- Start frontend --------------------------------------------------------------
if (Test-PortOpen $frontendPort) {
    Write-Ok "Frontend already running on port $frontendPort"
} elseif ($Prod) {
    Write-Step "Building frontend for production (skips per-page compile delays later)"
    Push-Location $frontendDir
    npx next build
    Pop-Location
    Write-Ok "Frontend build ready"

    Write-Step "Starting frontend (production) on http://localhost:$frontendPort"
    Start-Process powershell -WorkingDirectory $frontendDir -WindowStyle Normal -ArgumentList @(
        "-NoExit", "-Command",
        "Write-Host 'Finance Guru - Frontend (Next.js, production build)' -ForegroundColor Magenta; npx next start -p $frontendPort"
    )
} else {
    Write-Step "Starting frontend on http://localhost:$frontendPort"
    Start-Process powershell -WorkingDirectory $frontendDir -WindowStyle Normal -ArgumentList @(
        "-NoExit", "-Command",
        "Write-Host 'Finance Guru - Frontend (Next.js)' -ForegroundColor Magenta; npx next dev --turbopack -p $frontendPort"
    )
}

# -- Wait for both to come up ------------------------------------------------
Write-Step "Waiting for both servers to come online"
$deadline = (Get-Date).AddSeconds(90)
$backendUp = $false
$frontendUp = $false
while ((Get-Date) -lt $deadline -and (-not $backendUp -or -not $frontendUp)) {
    if (-not $backendUp -and (Test-PortOpen $backendPort)) { $backendUp = $true; Write-Ok "Backend is up" }
    if (-not $frontendUp -and (Test-PortOpen $frontendPort)) { $frontendUp = $true; Write-Ok "Frontend is up" }
    if (-not $backendUp -or -not $frontendUp) { Start-Sleep -Milliseconds 750 }
}

if (-not $backendUp)  { Write-Warn2 "Backend didn't come up within 90s - check its window for errors." }
if (-not $frontendUp) { Write-Warn2 "Frontend didn't come up within 90s (first-run compiles can be slow) - check its window." }

# -- Open browser --------------------------------------------------------------
Write-Step "Opening http://localhost:$frontendPort"
Start-Process "http://localhost:$frontendPort"

Write-Host "`nFinance Guru is running:" -ForegroundColor Magenta
Write-Host "  App:     http://localhost:$frontendPort"
Write-Host "  API:     http://localhost:$backendPort"
Write-Host "  API docs http://localhost:$backendPort/docs"
Write-Host "`nBackend and frontend are running in their own windows - close those windows to stop them.`n"
