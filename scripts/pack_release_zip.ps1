<#
.SYNOPSIS
  Regenera solo release\FichaManual-Setup.zip desde la carpeta ya empaquetada.
#>
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Release = Join-Path $Root "release\FichaManual-Setup"
$Zip = Join-Path $Root "release\FichaManual-Setup.zip"
$Exe = Join-Path $Release "app\FichaManual.exe"

if (-not (Test-Path $Exe)) {
  throw "Falta $Exe. Ejecuta primero scripts\build_installer.ps1"
}

# Sync latest installer scripts into the release folder
Copy-Item -Force (Join-Path $Root "installer\Install-FichaManual.ps1") $Release
Copy-Item -Force (Join-Path $Root "installer\Uninstall-FichaManual.ps1") $Release
Copy-Item -Force (Join-Path $Root "installer\FichaManual-Setup.bat") $Release
Copy-Item -Force (Join-Path $Root "assets\fichamanual.ico") (Join-Path $Release "fichamanual.ico")

if (Test-Path $Zip) { Remove-Item -Force $Zip }
Compress-Archive -Path (Join-Path $Release "*") -DestinationPath $Zip -Force
Write-Host "OK: $Zip"
Write-Host "Payload: $Exe"
