<#
.SYNOPSIS
  Construye FichaManual.exe con PyInstaller.
#>
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Test-Path "$Root\.venv\Scripts\python.exe")) {
  python -m venv "$Root\.venv"
}
& "$Root\.venv\Scripts\python.exe" -m pip install --upgrade pip
& "$Root\.venv\Scripts\python.exe" -m pip install -r "$Root\requirements.txt"
& "$Root\.venv\Scripts\python.exe" "$Root\scripts\generate_icon.py"
& "$Root\.venv\Scripts\python.exe" -m PyInstaller --noconfirm "$Root\FichaManual.spec"

$exe = Join-Path $Root "dist\FichaManual\FichaManual.exe"
if (-not (Test-Path $exe)) {
  throw "No se generó el ejecutable: $exe"
}
Write-Host "OK: $exe"
