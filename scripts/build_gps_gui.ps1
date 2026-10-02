# Build the native GPS graphical preview on Windows x64.
$ErrorActionPreference = 'Stop'
Set-Location (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = (Resolve-Path '.venv\Scripts\python.exe').Path
$exiftool = (Resolve-Path 'tools\exiftool\exiftool.exe').Path
if (-not (Test-Path 'tools\exiftool\exiftool_files')) {
    throw 'ExifTool support directory is missing'
}
$version = (& $exiftool -ver).Trim()
if ($LASTEXITCODE -ne 0 -or $version -ne '13.59') {
    throw "Expected ExifTool 13.59, got $version"
}
Remove-Item Env:AIM_EXIFTOOL -ErrorAction SilentlyContinue
& $python -m PyInstaller --noconfirm --clean --distpath dist --workpath build\gps-gui packaging\GpsGui.spec
if ($LASTEXITCODE -ne 0) { throw 'GPS GUI onedir build failed' }
& $python scripts\smoke_gps_gui.py --exe dist\AutoImageMarkGpsGui\AutoImageMarkGpsGui.exe --version 0.2.0rc2
if ($LASTEXITCODE -ne 0) { throw 'GPS GUI onedir smoke failed' }
& $python -m PyInstaller --noconfirm --clean --distpath dist\gps-gui-onefile --workpath build\gps-gui-onefile packaging\GpsGuiOnefile.spec
if ($LASTEXITCODE -ne 0) { throw 'GPS GUI onefile build failed' }
& $python scripts\smoke_gps_gui.py --exe dist\gps-gui-onefile\AutoImageMarkGpsGui.exe --version 0.2.0rc2
if ($LASTEXITCODE -ne 0) { throw 'GPS GUI onefile smoke failed' }
Get-FileHash dist\gps-gui-onefile\AutoImageMarkGpsGui.exe -Algorithm SHA256
