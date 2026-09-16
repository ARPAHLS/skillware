# Rebuild a contributor checkout without leaving stale package metadata behind.
$ErrorActionPreference = 'Stop'

# Locate incomplete metadata that pip cannot uninstall safely and remove only it.
$sitePackages = py -c "import site; print('\n'.join(site.getsitepackages()))"
foreach ($root in $sitePackages -split "`n") {
    Get-ChildItem -Path $root -Filter 'skillware-*.dist-info' -Directory -ErrorAction SilentlyContinue |
        Where-Object { -not ((Test-Path (Join-Path $_.FullName 'METADATA')) -and (Test-Path (Join-Path $_.FullName 'RECORD'))) } |
        ForEach-Object {
            Write-Host "Removing orphan metadata: $($_.FullName)"
            Remove-Item -Recurse -Force $_.FullName
        }
}

# Remove the old distribution before installing the full editable developer set.
py -m pip uninstall skillware -y
py -m pip install -e ".[dev,all]"
