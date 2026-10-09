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
Remove-Item -Recurse -Force $Release -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $Payload | Out-Null

Copy-Item -Recurse -Force (Join-Path $Root "dist\FichaManual\*") $Payload
Copy-Item -Force (Join-Path $Root "assets\fichamanual.ico") (Join-Path $Release "fichamanual.ico")
Copy-Item -Force (Join-Path $Root "installer\Install-FichaManual.ps1") $Release
Copy-Item -Force (Join-Path $Root "installer\Uninstall-FichaManual.ps1") $Release
Copy-Item -Force (Join-Path $Root "installer\FichaManual-Setup.bat") $Release

$Zip = Join-Path $Root "release\FichaManual-Setup.zip"
if (Test-Path $Zip) { Remove-Item -Force $Zip }
Compress-Archive -Path (Join-Path $Release "*") -DestinationPath $Zip -Force

Write-Host ""
Write-Host "Instalador listo para enviar:"
Write-Host "  Carpeta: $Release"
Write-Host "  ZIP:     $Zip"
Write-Host ""
Write-Host "El usuario final solo tiene que ejecutar FichaManual-Setup.bat"
