param([switch]$Dev, [string]$Python = '.\.venv-phase5\Scripts\python.exe')
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (!(Test-Path -LiteralPath $Python)) { throw 'Install the Python environment first; see docs/WINDOWS_QUICKSTART.md.' }
if ($Dev) { & $Python scripts/demo.py --dev } else { & $Python scripts/demo.py }
exit $LASTEXITCODE
