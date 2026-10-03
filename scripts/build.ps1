param([ValidateSet('onedir', 'onefile')][string]$Mode = 'onedir')
$ErrorActionPreference = 'Stop'
Set-Location (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = (Resolve-Path '.venv\Scripts\python.exe').Path
& $python scripts\build_jpg.py --mode $Mode
if ($LASTEXITCODE -ne 0) { throw "JPG $Mode build or smoke failed" }
