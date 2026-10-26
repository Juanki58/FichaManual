<#
.SYNOPSIS
  Empaqueta la carpeta dist y el instalador listo para enviar a otro PC.
#>
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

& "$PSScriptRoot\build_exe.ps1"

$Release = Join-Path $Root "release\FichaManual-Setup"
$Payload = Join-Path $Release "app"
$InstallerPayload = Join-Path $Root "installer\app"
Remove-Item -Recurse -Force $Release -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force $InstallerPayload -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $Payload | Out-Null
New-Item -ItemType Directory -Force -Path $InstallerPayload | Out-Null

Copy-Item -Recurse -Force (Join-Path $Root "dist\FichaManual\*") $Payload
Copy-Item -Recurse -Force (Join-Path $Root "dist\FichaManual\*") $InstallerPayload
Copy-Item -Force (Join-Path $Root "assets\fichamanual.ico") (Join-Path $Release "fichamanual.ico")
Copy-Item -Force (Join-Path $Root "assets\fichamanual.ico") (Join-Path $Root "installer\fichamanual.ico")
Copy-Item -Force (Join-Path $Root "installer\Install-FichaManual.ps1") $Release
Copy-Item -Force (Join-Path $Root "installer\Uninstall-FichaManual.ps1") $Release
Copy-Item -Force (Join-Path $Root "installer\FichaManual-Setup.bat") $Release

$exeInRelease = Join-Path $Payload "FichaManual.exe"
$exeInInstaller = Join-Path $InstallerPayload "FichaManual.exe"
if (-not (Test-Path $exeInRelease)) { throw "Falta el exe en el payload: $exeInRelease" }
if (-not (Test-Path $exeInInstaller)) { throw "Falta el exe en installer\app: $exeInInstaller" }

$Zip = Join-Path $Root "release\FichaManual-Setup.zip"
if (Test-Path $Zip) { Remove-Item -Force $Zip }
Compress-Archive -Path (Join-Path $Release "*") -DestinationPath $Zip -Force

Write-Host ""
Write-Host "Instalador listo para enviar:"
Write-Host "  Carpeta: $Release"
Write-Host "  ZIP:     $Zip"
Write-Host "  Local:   $InstallerPayload"
Write-Host ""
Write-Host "El usuario final solo tiene que ejecutar FichaManual-Setup.bat"
