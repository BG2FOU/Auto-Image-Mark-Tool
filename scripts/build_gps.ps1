# Build the local GPS-only prototype on Windows x64 using pinned project tools.
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
& $python -m PyInstaller --noconfirm --distpath dist --workpath build\gps-prototype packaging\GpsPrototype.spec
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller onedir build failed' }
& $python scripts\smoke_gps.py --exe dist\AutoImageMarkGps\AutoImageMarkGps.exe
if ($LASTEXITCODE -ne 0) { throw 'GPS onedir smoke failed' }
& $python -m PyInstaller --noconfirm --distpath dist\gps-onefile --workpath build\gps-onefile packaging\GpsPrototypeOnefile.spec
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller onefile build failed' }
& $python scripts\smoke_gps.py --exe dist\gps-onefile\AutoImageMarkGps.exe
if ($LASTEXITCODE -ne 0) { throw 'GPS onefile smoke failed' }
Get-FileHash dist\gps-onefile\AutoImageMarkGps.exe -Algorithm SHA256
