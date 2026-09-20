#!/usr/bin/env pwsh
# Keep argv boundaries; do not load .env or alter the caller environment.
$ErrorActionPreference = 'Stop'
$launcherPython = if ($env:AI_PYTHON) { $env:AI_PYTHON } else { 'python' }
& $launcherPython (Join-Path $PSScriptRoot 'launch.py') @args
exit $LASTEXITCODE
