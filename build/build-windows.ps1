param([string]$Python = '.\.venv\Scripts\python.exe', [string]$ISCC = '')
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
& $Python 'build\lock-environment.py'
if ($LASTEXITCODE -ne 0) { throw 'Dependency lock/license collection failed' }
& $Python -m PyInstaller --noconfirm --clean HarryTranslate.spec
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed' }
$forbidden = Get-ChildItem 'dist\HarryTranslate' -Recurse -Force -File | Where-Object {
    $_.Name -eq '.env' -or $_.Name -eq 'glossary.json' -or $_.Extension -eq '.log'
}
if ($forbidden) { throw 'Personal configuration or logs found in release folder' }
& "$PSScriptRoot\..\installer\prepare-webview2.ps1"
if (-not $ISCC) { $ISCC = (Get-Command ISCC.exe -ErrorAction Stop).Source }
& $ISCC 'installer\HarryTranslate.iss'
if ($LASTEXITCODE -ne 0) { throw 'Installer compilation failed' }
Get-FileHash 'dist\installer\HarryTranslateSetup.exe' -Algorithm SHA256
