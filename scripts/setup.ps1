param([string]$Python = 'python', [string]$Environment = '.venv')
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if ($Environment -notmatch '^\.venv(?:-[a-z0-9]+)?$') { throw 'Use .venv or .venv-name' }
if (Test-Path -LiteralPath $Environment) { throw 'Environment exists; choose a new name.' }
& $Python -c 'import sys; assert sys.version_info[:2] == (3,12), "Python 3.12 required"'
if ($LASTEXITCODE -ne 0) { throw 'A working Python 3.12 installation is required.' }
& $Python -m venv $Environment
if ($LASTEXITCODE -ne 0) { throw 'venv creation failed' }
$venvPython = Join-Path $Environment 'Scripts\python.exe'
& $venvPython -m pip install --require-hashes -r requirements-dev.lock
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
& $venvPython -m pip install --no-deps --no-build-isolation -e .
if ($LASTEXITCODE -ne 0) { throw 'Package installation failed' }
& $venvPython -m agenteval.cli validate
if ($LASTEXITCODE -ne 0) { throw 'Dataset validation failed' }
Write-Host 'Installation complete. No activation or execution-policy changes were made.'
