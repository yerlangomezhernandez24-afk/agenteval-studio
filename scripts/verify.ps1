param([string]$Python = '.\.venv\Scripts\python.exe')
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
& $Python -m ruff check .
if ($LASTEXITCODE -ne 0) { throw 'Ruff failed' }
& $Python -m ruff format --check backend tests scripts
if ($LASTEXITCODE -ne 0) { throw 'Formatting failed' }
& $Python -m mypy
if ($LASTEXITCODE -ne 0) { throw 'mypy failed' }
& $Python -m pytest -q
if ($LASTEXITCODE -ne 0) { throw 'pytest failed' }
