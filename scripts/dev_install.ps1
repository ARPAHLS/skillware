# Reinstall Skillware in editable dev mode after removing overlapping PyPI installs.
# See CONTRIBUTING.md and issue #333.

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Py = if ($env:PYTHON) { $env:PYTHON } else { "python" }

Write-Host "Uninstalling existing skillware registrations..."
& $Py -m pip uninstall skillware -y
if ($LASTEXITCODE -ne 0) {
    Write-Host "pip uninstall returned non-zero (orphan metadata may remain)." -ForegroundColor Yellow
}

Write-Host "Installing editable dev dependencies from $Root..."
Push-Location $Root
try {
    & $Py -m pip install -e ".[dev,all]"
} finally {
    Pop-Location
}

Write-Host "Install health:"
& $Py -m skillware doctor --install
