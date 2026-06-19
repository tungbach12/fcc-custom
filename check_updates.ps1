# FCC Custom - Update Checker
# Checks for upstream FCC updates and custom patch updates

$ErrorActionPreference = "SilentlyContinue"

Write-Host "FCC Custom - Checking for updates..." -ForegroundColor Cyan

# Get installed FCC version
$installedVersion = & uv run python -c "import importlib.metadata; print(importlib.metadata.version('free-claude-code'))" 2>$null
Write-Host "Installed FCC version: $installedVersion" -ForegroundColor Gray

# Check upstream (Alishahryar1/free-claude-code)
Write-Host ""
Write-Host "Checking upstream (Alishahryar1/free-claude-code)..." -ForegroundColor Yellow
$upstream = gh api repos/Alishahryar1/free-claude-code --jq '{pushed_at: .pushed_at, default_branch: .default_branch}' 2>$null
if ($upstream) {
    $pushed = ($upstream | ConvertFrom-Json).pushed_at
    Write-Host "Last upstream push: $pushed" -ForegroundColor Gray

    # Check latest PyPI version
    $pypiVersion = & uv run python -c "import urllib.request, json; print(json.loads(urllib.request.urlopen('https://pypi.org/pypi/free-claude-code/json').read())['info']['version'])" 2>$null
    if ($pypiVersion) {
        Write-Host "Latest PyPI version: $pypiVersion" -ForegroundColor Gray
        if ($pypiVersion -ne $installedVersion) {
            Write-Host "UPDATE AVAILABLE: $installedVersion -> $pypiVersion" -ForegroundColor Green
            Write-Host "Run: uv tool install free-claude-code --force" -ForegroundColor Cyan
        } else {
            Write-Host "Up to date!" -ForegroundColor Green
        }
    }
} else {
    Write-Host "Could not check upstream" -ForegroundColor Red
}

# Check custom patches (tungbach12/fcc-custom)
Write-Host ""
Write-Host "Checking custom patches (tungbach12/fcc-custom)..." -ForegroundColor Yellow
$custom = gh api repos/tungbach12/fcc-custom --jq '{pushed_at: .pushed_at}' 2>$null
if ($custom) {
    $pushed = ($custom | ConvertFrom-Json).pushed_at
    Write-Host "Last custom patch push: $pushed" -ForegroundColor Gray
} else {
    Write-Host "Could not check custom patches" -ForegroundColor Red
}

# Check patch compatibility
Write-Host ""
Write-Host "Checking patch compatibility..." -ForegroundColor Yellow
$compatResult = & uv run python -c "
import sys, inspect
try:
    from providers.rate_limit import GlobalRateLimiter
    sig = inspect.signature(GlobalRateLimiter.execute_with_retry)
    params = list(sig.parameters.keys())
    if 'fn' in params and 'max_retries' in params:
        print('OK: execute_with_retry compatible')
    else:
        print(f'WARN: execute_with_retry params changed: {params}')
except Exception as e:
    print(f'ERROR: {e}')
" 2>$null
Write-Host $compatResult -ForegroundColor $(if ($compatResult -like "OK:*") { "Green" } else { "Yellow" })

Write-Host ""
Write-Host "Done!" -ForegroundColor Cyan
