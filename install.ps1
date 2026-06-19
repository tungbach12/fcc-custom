# FCC Custom - Install Script
# Installs Free Claude Code with NIM fallback patches

$ErrorActionPreference = "Stop"

Write-Host "FCC Custom - Installing..." -ForegroundColor Cyan

# Check if uv is installed
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "uv not found. Installing..." -ForegroundColor Yellow
    irm https://astral.sh/uv/install.ps1 | iex
}

# Install/update base FCC
Write-Host "Installing Free Claude Code..." -ForegroundColor Green
uv tool install free-claude-code --force

# Get Python lib path
$pythonLib = & uv run python -c "import sys; print([p for p in sys.path if 'site-packages' in p][0])" 2>$null
if (-not $pythonLib) {
    # Fallback: find it manually
    $pythonLib = Get-ChildItem "$env:APPDATA\uv\python\cpython-*\Lib\site-packages" -Directory | Select-Object -First 1 -ExpandProperty FullName
}

if (-not $pythonLib) {
    Write-Host "ERROR: Could not find Python site-packages" -ForegroundColor Red
    exit 1
}

Write-Host "Python lib: $pythonLib" -ForegroundColor Gray

# Backup existing sitecustomize.py
$sitecustomize = Join-Path (Split-Path $pythonLib) "sitecustomize.py"
if (Test-Path $sitecustomize) {
    $backup = "$sitecustomize.bak.$(Get-Date -Format 'yyyyMMdd-HHmmss')"
    Copy-Item $sitecustomize $backup
    Write-Host "Backed up existing sitecustomize.py" -ForegroundColor Yellow
}

# Copy sitecustomize.py
Write-Host "Installing NIM fallback patch..." -ForegroundColor Green
Copy-Item ".\sitecustomize.py" $sitecustomize -Force

# Copy admin UI files
$adminStatic = Join-Path $pythonLib "api\admin_static"
if (Test-Path $adminStatic) {
    Write-Host "Installing NIM Tester UI..." -ForegroundColor Green
    Copy-Item ".\admin_static\*" $adminStatic -Recurse -Force
}

# Create .env if not exists
$envFile = Join-Path $env:USERPROFILE ".fcc\.env"
if (-not (Test-Path $envFile)) {
    Write-Host "Creating .env file..." -ForegroundColor Yellow
    $envDir = Split-Path $envFile
    if (-not (Test-Path $envDir)) {
        New-Item -ItemType Directory -Path $envDir -Force | Out-Null
    }
    Copy-Item ".\.env.example" $envFile
    Write-Host "Created .env - Please edit $envFile with your API keys" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Installation complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Edit $envFile with your NVIDIA NIM API keys"
Write-Host "  2. Get free key at: https://build.nvidia.com/settings/api-keys"
Write-Host "  3. Run: fcc-server"
Write-Host "  4. Open http://127.0.0.1:8082/admin for NIM Tester"
Write-Host ""
